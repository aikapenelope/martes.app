import * as pulumi from "@pulumi/pulumi";
import * as hcloud from "@pulumi/hcloud";
import * as tls from "@pulumi/tls";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
const config = new pulumi.Config();
const location  = config.get("location")   || "hel1";
const serverType = config.get("serverType") || "cx43";

// Puerto 22 abierto a todos por defecto — Neo y admin siempre pueden conectar.
const sshAllowedIps = config.getObject<string[]>("sshAllowedIps") ?? ["0.0.0.0/0", "::/0"];

// tailscaleAuthKey es opcional. Si se configura, el servidor se une a la red
// Tailscale automáticamente en el primer boot (conveniente para VPS nuevos).
//   pulumi config set --secret martes-infra:tailscaleAuthKey <tskey-...>
// Si no se configura, el admin puede unirse manualmente: tailscale up --hostname=martes-vps
const tailscaleAuthKey: pulumi.Output<string> =
    config.getSecret("tailscaleAuthKey") ?? pulumi.output("");

// ---------------------------------------------------------------------------
// SSH Key (ED25519, generada por Pulumi — guardada como secret en el stack)
// ---------------------------------------------------------------------------
const sshKeypair = new tls.PrivateKey("martes-ssh-keypair", {
    algorithm: "ED25519",
});

const sshKey = new hcloud.SshKey("martes-ssh-key", {
    publicKey: sshKeypair.publicKeyOpenssh,
});

// ---------------------------------------------------------------------------
// Cloud-init: provisioning completo para un VPS nuevo
//
// Orden de ejecución:
//   1. packages  — apt instala dependencias base
//   2. write_files — escribe configuraciones antes de los servicios
//   3. runcmd    — comandos secuenciales: UFW → fail2ban → Docker →
//                  Tailscale → directorios + red Docker → Coolify
//
// NOTA: ignoreChanges["userData"] está activo en el recurso Server.
// Los cambios aquí solo se aplican en servidores creados de nuevo con
// `pulumi up`. El VPS existente NO se toca.
// ---------------------------------------------------------------------------
const cloudInit = tailscaleAuthKey.apply((tsKey: string) => `#cloud-config
package_update: true
package_upgrade: true
packages:
  - curl
  - jq
  - git
  - unattended-upgrades
  - fail2ban
  - ufw

write_files:
  - path: /etc/fail2ban/jail.local
    permissions: "0644"
    content: |
      [sshd]
      enabled  = true
      port     = ssh
      maxretry = 5
      bantime  = 3600
      findtime = 600

runcmd:
  # --- Firewall (UFW) --------------------------------------------------------
  # 22/tcp   : SSH abierto a todos (Neo + admin sin restricciones)
  # 80/tcp   : HTTP  (Coolify Traefik — redirige a HTTPS)
  # 443/tcp  : HTTPS (Coolify Traefik)
  # 41641/udp: Tailscale WireGuard (peer-to-peer directo, reduce latencia)
  # 8000/tcp : Coolify UI — SOLO desde Tailscale (100.64.0.0/10), no internet
  - ufw default deny incoming
  - ufw default allow outgoing
  - ufw allow 22/tcp
  - ufw allow 80/tcp
  - ufw allow 443/tcp
  - ufw allow 41641/udp
  - ufw allow from 100.64.0.0/10 to any port 8000 proto tcp
  - ufw --force enable

  # --- fail2ban ---------------------------------------------------------------
  - systemctl enable fail2ban
  - systemctl restart fail2ban

  # --- Docker -----------------------------------------------------------------
  - curl -fsSL https://get.docker.com | sh
  - systemctl enable docker
  - systemctl start docker

  # --- Tailscale --------------------------------------------------------------
  - curl -fsSL https://tailscale.com/install.sh | sh
${tsKey
    ? `  - tailscale up --authkey="${tsKey}" --hostname=martes-vps --accept-dns=false`
    : `  # tailscaleAuthKey no configurado -- unirse manualmente despues del boot:`
      + `\n  #   tailscale up --hostname=martes-vps`}

  # --- Swap (4 GB) ------------------------------------------------------------
  # Sin swap, un OOM con múltiples tenants mata procesos sin aviso.
  - fallocate -l 4G /swapfile
  - chmod 600 /swapfile
  - mkswap /swapfile
  - swapon /swapfile
  - echo '/swapfile none swap sw 0 0' >> /etc/fstab
  - echo 'vm.swappiness=10' >> /etc/sysctl.conf
  - sysctl vm.swappiness=10

  # --- Directorios de datos (host volumes, persistentes entre redeploys) ------
  - mkdir -p /var/lib/martes/pg-data
  - mkdir -p /var/lib/martes/tenants
  - mkdir -p /var/lib/martes/backups
  - mkdir -p /var/lib/martes/meta-agent

  # --- Red Docker de tenants --------------------------------------------------
  # martes-tenants es "external: true" en el compose. Debe existir antes del
  # primer deploy. Coolify no la recrea en redeploys, preservando los containers
  # de tenants Hermes que ya estén corriendo.
  - docker network create martes-tenants || true

  # --- Coolify ----------------------------------------------------------------
  # Instala Coolify en /data/coolify. Trae su propio Traefik para 80/443.
  # La UI queda en http://<tailscale-ip>:8000 (solo accesible via Tailscale).
  #
  # Setup inicial (una sola vez tras el boot):
  #   1. Abrir http://<tailscale-ip>:8000 y crear cuenta admin
  #   2. Registrar el servidor (localhost / SSH)
  #   3. Crear proyecto → New Resource → Docker Compose → Git repository
  #   4. URL: https://github.com/aikapenelope/martes.app
  #   5. Compose path: infra/docker-compose.yml
  #   6. Configurar dominio api.martes.app y las env vars
  #   7. Agregar credenciales GHCR (ghcr.io + GitHub PAT read:packages)
  #   8. Obtener webhook URL → guardar en GitHub Secret COOLIFY_WEBHOOK_URL
  #   9. Registrar webhook Telegram:
  #      curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://api.martes.app/telegram/webhook"
  - curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
`);

// ---------------------------------------------------------------------------
// Server: Hetzner CX43 (8 vCPU, 16 GB RAM, 160 GB NVMe)
// ---------------------------------------------------------------------------
const server = new hcloud.Server("martes-server", {
    serverType:  serverType,
    location:    location,
    image:       "ubuntu-24.04",
    sshKeys:     [sshKey.id],
    userData:    cloudInit,
    deleteProtection:  true,
    rebuildProtection: true,
}, {
    // cloud-init solo corre en el primer boot. Ignorar cambios aquí evita
    // que `pulumi up` recree el servidor por cambios de configuración.
    ignoreChanges: ["userData"],
});

// ---------------------------------------------------------------------------
// Firewall Hetzner (capa de red, antes de llegar al servidor)
//
// Puerto 8000 (Coolify UI) NO se abre aquí: el tráfico Tailscale entra por
// WireGuard (UDP 41641) y UFW en el servidor permite 8000 solo desde la
// red Tailscale (100.64.0.0/10). Doble capa de protección.
// ---------------------------------------------------------------------------
const firewall = new hcloud.Firewall("martes-firewall", {
    rules: [
        {
            direction: "in",
            protocol:  "tcp",
            port:      "22",
            sourceIps: sshAllowedIps,
            description: "SSH (Neo + admin, abierto a todos)",
        },
        {
            direction: "in",
            protocol:  "tcp",
            port:      "80",
            sourceIps: ["0.0.0.0/0", "::/0"],
            description: "HTTP (Coolify Traefik, redirige a HTTPS)",
        },
        {
            direction: "in",
            protocol:  "tcp",
            port:      "443",
            sourceIps: ["0.0.0.0/0", "::/0"],
            description: "HTTPS (Coolify Traefik)",
        },
        {
            direction: "in",
            protocol:  "udp",
            port:      "41641",
            sourceIps: ["0.0.0.0/0", "::/0"],
            description: "Tailscale WireGuard (peer-to-peer directo)",
        },
        {
            direction: "in",
            protocol:  "tcp",
            port:      "6001",
            sourceIps: ["0.0.0.0/0", "::/0"],
            description: "Coolify Soketi WebSocket (real-time UI)",
        },
        {
            direction: "in",
            protocol:  "tcp",
            port:      "6002",
            sourceIps: ["0.0.0.0/0", "::/0"],
            description: "Coolify terminal access",
        },
    ],
});

new hcloud.FirewallAttachment("martes-firewall-attachment", {
    firewallId: firewall.id.apply((id) => parseInt(id)),
    serverIds:  [server.id.apply((id) => parseInt(id))],
});

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
export const serverIpv4   = server.ipv4Address;
export const serverIpv6   = server.ipv6Address;
export const serverStatus = server.status;
export const sshPrivateKey = pulumi.secret(sshKeypair.privateKeyOpenssh);
