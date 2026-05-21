# Por qué un agente Hermes NO puede reiniciarse o actualizarse solo

> **Contexto**: Containers Docker en produccion SaaS (martes.app)
> **Version**: Hermes 0.14.0

---

## La pregunta

"¿Por qué el agente no puede reiniciarse o actualizarse sin que el admin lo haga?"

## La respuesta corta

Porque cada agente Hermes corre en un **container aislado** sin acceso al
daemon de Docker. Es una decision de seguridad deliberada:

```
hermes-t001 (container)
├── /opt/data/         ← Sus datos
├── Proceso gateway    ← Lo unico que puede hacer
└── ✗ /var/run/docker.sock  ← NO tiene esto
```

Sin el socket de Docker, el agente no puede:
- Reiniciar su propio container
- Descargar una imagen nueva
- Ver otros containers

---

## Lo que SI puede hacer solo

### /restart (graceful)
El agente puede reiniciar su propio **proceso interno** de forma segura:

```
Cliente: /restart
Hermes:  "Reiniciando..."
         ↓ Termina la conversacion activa (drain)
         ↓ Sale con exit code 75
         ↓ Docker ve exit 75 → restart: unless-stopped lo revive
         ↓ ~5-15 segundos de downtime
         ↓ "Gateway restarted ✓"
```

**Esto funciona SIN Docker socket.** Hermes detecta que esta en un container
(`/.dockerenv`) y delega el restart a Docker via exit code 75.

### /new, /reset
Limpiar el contexto de la sesion. Instantaneo, sin restart.

### Lo que NO puede hacer sin ayuda
- Actualizar su propia imagen Docker (`hermes update` no funciona en Docker)
- Reiniciar si el proceso crashea y Docker no lo levanta
- Cambiar su configuracion en `config.yaml` y aplicarla

---

## Por que la config muestra "no puede reiniciarse"

Si ves un mensaje del agente diciendo que no puede reiniciarse, hay dos causas:

### Causa 1: `restart: unless-stopped` no esta configurado
Si el container se creo sin politica de restart, Docker no lo revive despues
del exit 75. El agente sale y no vuelve.

**Como verificar**:
```bash
docker inspect hermes-t001 | grep -A3 RestartPolicy
# Debe mostrar: "Name": "unless-stopped"
```

**Fix**: El Operador Agno recrea el container con la politica correcta.

### Causa 2: El agente no detecto que esta en un container
Hermes detecta containers por la existencia de `/.dockerenv`. Si por algun
motivo este archivo no esta, intenta el restart "detached" (subprocess) que
no funciona bajo tini (el init del container de Hermes).

**Como verificar**:
```bash
docker exec hermes-t001 ls /.dockerenv
# Debe existir
```

Esto no deberia pasar con la imagen oficial de Hermes.

---

## Las tres formas de reiniciar/actualizar un agente

### 1. El cliente usa /restart (restart del proceso, no de la imagen)
- Que hace: Reinicia el gateway interno
- Cuando usarlo: Para aplicar cambios de sesion, liberar memoria
- Downtime: ~10 segundos
- Imagen: La misma, no se actualiza

### 2. El admin via meta-agente Agno (restart del container)
```
Admin → Telegram → meta-agente
       → restart_tenant("t001")
       → docker restart hermes-t001
       → ~10-15 segundos de downtime
```
- Que hace: SIGTERM → container para → Docker lo revive
- Cuando usarlo: Para aplicar cambios en config.yaml o .env
- Downtime: ~10-15 segundos

### 3. El admin via meta-agente (upgrade de imagen)
```
Admin → Telegram → meta-agente
       → upgrade_tenant("t001", "nousresearch/hermes-agent:0.15.0")
       → Para container, pull imagen nueva, recrea container
       → ~30-60 segundos de downtime
```
- Que hace: Actualiza la version de Hermes
- Cuando usarlo: Para nueva version de Hermes
- Downtime: ~30-60 segundos
- Estado: Preservado (volumen persiste)

---

## La experiencia del cliente durante restart

Con la configuracion actual (`busy_input_mode: queue`, `restart_drain_timeout`):

```
Cliente escribe durante restart:
   ↓ Mensaje se encola (no se pierde)
   ↓ Hermes arranca
   ↓ Procesa el mensaje encolado
   ↓ Responde normalmente
```

Con `restart_drain_timeout: 60` (plan equipo):
```
Hermes recibe /restart mientras procesa algo:
   ↓ Avisa: "Reiniciando cuando termine..."
   ↓ Espera hasta 60s que termine la tarea
   ↓ Reinicia limpiamente
```

---

## Por que NO damos Docker socket a los tenants

Dar `/var/run/docker.sock` a un container = darle control total del servidor:
- Puede ver todos los containers (otros tenants)
- Puede crear containers con privilegios
- Puede montar cualquier directorio del host
- Equivale a root en el servidor

**El meta-agente Agno SI tiene el socket** porque es de confianza y lo
necesita para gestionar todos los tenants. Los tenants individuales, nunca.

---

## Resumen: quien hace que

| Accion | Quien la hace | Como |
|--------|--------------|------|
| Limpiar sesion | El cliente | `/new` o `/reset` |
| Reiniciar proceso | El cliente | `/restart` |
| Reiniciar container | Admin via Agno | `restart_tenant()` |
| Actualizar imagen | Admin via Agno | `upgrade_tenant()` (pendiente) |
| Cambiar config.yaml | Admin via Agno | `update_tenant_config()` + restart |
| Inyectar credencial | Admin via Agno | `inject_credential()` + restart |
