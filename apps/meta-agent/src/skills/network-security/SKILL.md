---
name: network-security
description: "Seguridad de red, aislamiento de tenants, y hardening de containers"
license: MIT
metadata:
  tags: [security, networking, docker, isolation, hardening]
  category: infrastructure
---

# Seguridad de Red e Infraestructura

## Aislamiento de tenants

Cada tenant tiene su propia bridge network:
- `tenant-{code}-net` — red aislada del tenant
- NO puede ver otros tenants (redes separadas)
- NO puede acceder a la red de plataforma (martes-platform)
- SI puede salir a internet (NAT, para llamar APIs)
- Traefik se conecta a todas las redes para rutear trafico

## Hardening de containers (aplicado automaticamente)

| Setting | Valor | Proposito |
|---------|-------|-----------|
| `security_opt` | no-new-privileges | Previene escalacion de privilegios |
| `pids_limit` | 256 | Previene fork bombs |
| `cap_drop` | ALL | Elimina todas las capabilities de Linux |
| `cap_add` | NET_RAW | Solo permite ping/wget |
| `dns` | 1.1.1.1, 8.8.8.8 | DNS explicito (no usa resolver del host) |
| `tmpfs /tmp` | 100MB | Escrituras temporales en RAM |
| `log_config` | max-size 50MB, 3 files | Previene llenado de disco por logs |
| `mem_limit` | segun plan | OOM kill si excede |

## Firewall del servidor (ufw)

```
22/tcp   ALLOW   (SSH)
80/tcp   ALLOW   (HTTP → redirect HTTPS)
443/tcp  ALLOW   (HTTPS via Traefik)
*        DENY    (todo lo demas)
```

## Firewall de Hetzner (capa externa)

Mismas reglas que ufw pero a nivel de datacenter.
Doble capa de proteccion.

## Acceso al Docker socket

- Solo el meta-agente tiene acceso al socket (`/var/run/docker.sock`)
- Los tenants NO tienen acceso al socket
- Portainer solo accesible via localhost (127.0.0.1:9000)

## Credenciales

- `.env` de cada tenant: permisos 600 (solo owner puede leer)
- Volumen owned por UID 1000 (usuario hermes dentro del container)
- PostgreSQL password en .env del host (no en el repo)
- API keys nunca en codigo, siempre en .env

## Traefik (reverse proxy)

- Dashboard deshabilitado (`--api.dashboard=false`)
- HTTPS obligatorio (redirect HTTP → HTTPS)
- Let's Encrypt para certificados automaticos
- Access logs habilitados
- Cada tenant tiene su propio router con TLS

## Que NO hacer

- NUNCA dar `--privileged` a un container de tenant
- NUNCA montar el Docker socket en un tenant
- NUNCA usar `network_mode: host` en multi-tenant
- NUNCA poner API keys en labels o environment visibles
- NUNCA exponer puertos de tenants directamente (siempre via Traefik)
