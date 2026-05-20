import * as pulumi from "@pulumi/pulumi";
import * as hcloud from "@pulumi/hcloud";
import * as tls from "@pulumi/tls";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
const config = new pulumi.Config();
const location = config.get("location") || "hel1";
const serverType = config.get("serverType") || "cx43";
const sshAllowedIps = config.getObject<string[]>("sshAllowedIps") || ["0.0.0.0/0", "::/0"];

// ---------------------------------------------------------------------------
// SSH Key
// ---------------------------------------------------------------------------
const sshKeypair = new tls.PrivateKey("martes-ssh-keypair", {
    algorithm: "ED25519",
});

const sshKey = new hcloud.SshKey("martes-ssh-key", {
    publicKey: sshKeypair.publicKeyOpenssh,
});

// ---------------------------------------------------------------------------
// Cloud-init: Docker + martes.app bootstrap
// ---------------------------------------------------------------------------
const cloudInit = `#cloud-config
package_update: true
package_upgrade: true
packages:
  - curl
  - jq
  - git
  - unattended-upgrades
  - fail2ban
  - ufw

runcmd:
  # Firewall (ufw)
  - ufw default deny incoming
  - ufw default allow outgoing
  - ufw allow 22/tcp
  - ufw allow 80/tcp
  - ufw allow 443/tcp
  - ufw --force enable

  # fail2ban
  - |
    cat > /etc/fail2ban/jail.local << 'EOF'
    [sshd]
    enabled = true
    port = ssh
    maxretry = 5
    bantime = 3600
    findtime = 600
    EOF
  - systemctl enable fail2ban
  - systemctl restart fail2ban

  # Install Docker
  - curl -fsSL https://get.docker.com | sh

  # Create martes.app data directories
  - mkdir -p /var/lib/martes/pg-data
  - mkdir -p /var/lib/martes/tenants
  - mkdir -p /var/lib/martes/backups

  # Clone martes.app and start services
  - git clone https://github.com/aikapenelope/martes.app.git /opt/martes
  - cd /opt/martes && docker compose -f infra/docker-compose.yml pull
  - docker pull nousresearch/hermes-agent:0.14.0

  # Note: docker compose up requires .env file with secrets
  # Admin must SSH in and create /opt/martes/infra/.env before starting
`;

// ---------------------------------------------------------------------------
// Server: Hetzner CX43 (8 vCPU, 16 GB RAM, 160 GB NVMe)
// ---------------------------------------------------------------------------
const server = new hcloud.Server("martes-server", {
    serverType: serverType,
    location: location,
    image: "ubuntu-24.04",
    sshKeys: [sshKey.id],
    userData: cloudInit,
    deleteProtection: true,
    rebuildProtection: true,
}, {
    ignoreChanges: ["userData"],
});

// ---------------------------------------------------------------------------
// Firewall: SSH + HTTP/S only
// ---------------------------------------------------------------------------
const firewall = new hcloud.Firewall("martes-firewall", {
    rules: [
        {
            direction: "in",
            protocol: "tcp",
            port: "22",
            sourceIps: sshAllowedIps,
            description: "SSH",
        },
        {
            direction: "in",
            protocol: "tcp",
            port: "80",
            sourceIps: ["0.0.0.0/0", "::/0"],
            description: "HTTP (Traefik redirect to HTTPS)",
        },
        {
            direction: "in",
            protocol: "tcp",
            port: "443",
            sourceIps: ["0.0.0.0/0", "::/0"],
            description: "HTTPS (Traefik)",
        },
    ],
});

new hcloud.FirewallAttachment("martes-firewall-attachment", {
    firewallId: firewall.id.apply((id) => parseInt(id)),
    serverIds: [server.id.apply((id) => parseInt(id))],
});

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
export const serverIpv4 = server.ipv4Address;
export const serverIpv6 = server.ipv6Address;
export const serverStatus = server.status;
export const sshPrivateKey = pulumi.secret(sshKeypair.privateKeyOpenssh);
