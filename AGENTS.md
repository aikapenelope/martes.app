# AGENTS.md — martes.app

> Neo lee este archivo al inicio de cada sesión de trabajo en este repo.
> El usuario puede modificarlo para ajustar el comportamiento de Neo.

---

## Filosofía de desarrollo

**Cero workarounds.** Si no existe una solución documentada en los docs oficiales
de la herramienta involucrada, Neo para, reporta, y espera instrucciones.
No se inventa nada. No se itera con parches hasta que "algo funcione".

**Producción desde el primer commit.** No existe "lo arreglamos después".

**Una fuente de verdad por componente:**
- `pulumi/index.ts` → servidor y red (Hetzner)
- `infra/docker-compose.yml` → servicios de aplicación
- `apps/meta-agent/` → código del agente
- `.github/workflows/cd.yml` → CI/CD

---

## REGLA ABSOLUTA — Acceso al servidor de producción

> **Neo NUNCA accede directamente al servidor de producción (204.168.169.254)
> para ejecutar comandos de escritura sin aprobación explícita del usuario.**

### Prohibido sin aprobación explícita:

```
docker restart <container>        ← interrumpe servicios activos
docker stop / docker rm           ← destruye containers
pip install / apt install         ← modifica containers corriendo (no reproducible)
pulumi up / pulumi destroy        ← cambia infraestructura
docker exec ... escribir archivos ← modifica estado en producción
ssh ... && <cualquier mutación>   ← acción no rastreable
```

### Permitido (solo lectura, y aún así reportar antes):

```
docker ps / docker logs           ← diagnóstico
docker inspect                    ← diagnóstico
curl <endpoint>                   ← verificación de salud
cat / ls                          ← lectura de archivos
```

### Por qué esta regla es crítica:

Coolify gestiona el ciclo de vida de los containers del compose stack.
Cualquier acción fuera de Coolify (restart, modificación directa de
containers) **desincroniza el estado interno de Coolify** de lo que
realmente hay en el servidor. Esto puede causar:

- Coolify marca el container como en estado inesperado
- El próximo deploy de Coolify entra en conflicto con el estado actual
- Datos del deployment tracker quedan inconsistentes
- Pérdida de visibilidad sobre qué versión está corriendo realmente

### El único flujo válido para cambios en producción:

```
1. SPEC     — Neo describe el cambio, cita fuente oficial
2. REVIEW   — Usuario aprueba
3. IMPLEMENT — PR con el cambio mínimo
4. MERGE    — Usuario mergea el PR
5. DEPLOY   — Coolify detecta el merge y redespliega automáticamente
              (o usuario hace click en "Redeploy" en la UI de Coolify)
```

**No existe paso intermedio de "lo arreglo rápido en el servidor".**

---

## Reglas antes de escribir código

1. **Leer los docs oficiales actuales** de la herramienta afectada.
   Coolify: https://coolify.io/docs
   Agno: https://docs.agno.com
   Traefik: https://doc.traefik.io/traefik
   Hetzner: https://docs.hetzner.com

2. **Identificar el patrón oficial**, no el workaround.

3. **Presentar el plan** con la URL exacta de la doc que lo respalda.

4. **Esperar aprobación explícita** del usuario antes de implementar.

5. **Nunca hacer merge sin aprobación explícita.** Neo propone PRs, el usuario aprueba.

---

## Estilo de código

### Versiones
- Todas pineadas a versión exacta: `==x.y.z`
- No rangos abiertos (`>=x.y.z`) salvo que la herramienta lo requiera explícitamente
- Ejemplo correcto: `agno[telegram,scheduler]==2.6.8`

### Variables de entorno
- Siempre en `.env` o en Pulumi ESC / GitHub Secrets
- Nunca hardcodeadas en código
- Nunca en logs ni en output de comandos

### Docker Compose
- Sin `container_name` hardcodeado cuando Coolify gestiona el ciclo de vida del container
- Redes: `external: true` para redes que existen antes del compose
- Alias de red para routing estable entre servicios
- Sin labels de Traefik en el compose salvo que Coolify los requiera documentadamente
- `context:` en build siempre relativo al `--project-directory` de Coolify (= raíz del repo)
  → usar `context: .` no `context: ..` cuando el compose está en `infra/`
  Ref: PR #45 — https://github.com/aikapenelope/martes.app/pull/45

### Infraestructura
- Coolify gestiona: routing HTTP/HTTPS, SSL, deploys automáticos
- No crear configs manuales de Traefik salvo patrón documentado en Coolify docs
- Cambios al servidor van en `pulumi/index.ts`, no se hacen a mano
- **Coolify --project-directory**: Coolify pasa `--project-directory=<repo-root>` al ejecutar
  `docker compose`. Las rutas relativas en el compose se resuelven desde la raíz del repo,
  no desde el directorio del compose file. Siempre verificar esto al usar `context:` o volúmenes
  con rutas relativas.

### Commits y PRs
- Un PR = un cambio atómico. No mezclar concerns.
- Descripción del PR incluye:
  - Qué cambió
  - Por qué
  - URL de la documentación oficial que respalda el patrón

---

## Stack del proyecto

| Componente | Herramienta | Versión pineada | Docs |
|---|---|---|---|
| Servidor | Hetzner CX43 vía Pulumi | hcloud `1.36.0` | https://docs.hetzner.com |
| Orquestador | Coolify | `4.1.0` | https://coolify.io/docs |
| Reverse proxy | Traefik (gestionado por Coolify) | `v3.6` | https://doc.traefik.io/traefik |
| Meta-agente | Agno AgentOS | `==2.6.8` | https://docs.agno.com |
| Base de datos | PostgreSQL + pgvector | `agnohq/pgvector:18` | https://docs.agno.com |
| Tenants | Hermes Agent | `v2026.5.16` (= v0.14.0, tag Docker Hub) | — |
| Object storage | SeaweedFS | `4.28` | https://github.com/seaweedfs/seaweedfs |
| VPN admin | Tailscale | latest (gestiona su propia actualización) | https://tailscale.com/kb |

---

## Flujo SDD (Spec-Driven Development)

Para cualquier cambio, en este orden:

```
1. SPEC     — Neo describe qué cambia, por qué, y cita la fuente oficial
2. REVIEW   — Usuario aprueba la spec. Sin aprobación no hay paso 3.
3. IMPLEMENT — Código mínimo que cumple la spec. Nada más.
4. VERIFY   — Contra la documentación oficial. Health checks.
5. DOCUMENT — Commit y PR con fuente citada y pasos de verificación.
```

---

## Template de PR

```markdown
## Qué
[Una línea]

## Por qué
[Problema que resuelve]

## Fuente oficial
[URL exacta]

## Archivos modificados
- `archivo` — motivo

## Verificación
[Comando o URL para confirmar]
```

---

## Regla de oro

> **Si no está en los docs oficiales de la herramienta, no se implementa
> hasta encontrar el patrón correcto documentado.**
