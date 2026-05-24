# Integraciones Clave para PyMEs Venezolanas

> **Objetivo**: conectar Hermes con los servicios que realmente usa una pequeña o mediana empresa en Venezuela  
> **Formato**: por cada integración — qué hace, cómo configurarla, caso de uso concreto

---

## Tier 1 — Integraciones esenciales

### 1. WhatsApp Business API

**Por qué**: es EL canal de ventas #1 en Venezuela. El que no está en WhatsApp no existe para el cliente venezolano.

**Cómo funciona con Hermes**:
- Hermes actúa como el asistente en el número de WhatsApp de la empresa
- Responde mensajes, toma pedidos, confirma pagos
- Escala conversaciones complejas al dueño

**Opciones de proveedor**:
| Proveedor | Costo aprox. | Notas |
|---|---|---|
| Twilio (WhatsApp Business API) | $0.005/mensaje | El más establecido |
| 360dialog | €49/mes + mensajes | Más barato para alto volumen |
| WhatsApp Business App (free) | Gratis | Solo 1 dispositivo, sin API oficial |

**Config en Hermes**:
```bash
hermes gateway  # Inicia el gateway con WhatsApp
# Configura WHATSAPP_TOKEN en .env
```

**Caso de uso**: cliente envía "¿tienen zapatos talla 38?" → Hermes consulta Airtable → responde disponibilidad + precio + opciones de pago en 3 segundos.

---

### 2. Airtable — El CRM/ERP del venezolano

**Por qué**: Airtable es la herramienta de organización más accesible para PyMEs que no quieren un ERP caro. Gratis para hasta 1,000 registros/base.

**Qué puede gestionar Hermes via Airtable**:
- Inventario (productos, stock, precios)
- Pedidos (cliente, productos, estado, pago)
- Clientes (historial, preferencias, contacto)
- Proveedores (contactos, condiciones)
- Tareas del equipo

**Configuración**:
```bash
# En Hermes:
hermes skills install airtable
# Pide: AIRTABLE_API_KEY
# Obtenla en: airtable.com → Account → API
```

**Caso de uso**:
```
Dueño → Telegram: "¿Cuántas unidades del producto X me quedan?"
Hermes → consulta Airtable
Hermes → Telegram: "Tienes 8 unidades del producto X. 
  Precio actual: $15. Última venta fue hace 2 días."
```

**Template de base Airtable para retail**:
- Tabla: Inventario (Producto, SKU, Stock, Precio USD, Precio Bs, Foto)
- Tabla: Pedidos (Cliente, Productos, Total, Estado, Forma de pago, Fecha)
- Tabla: Clientes (Nombre, WhatsApp, Email, Notas, Última compra)
- Vista: "Pedidos pendientes de entrega"
- Vista: "Stock bajo (< 5 unidades)"

---

### 3. Google Workspace — El backbone digital

**Por qué**: Gmail + Google Sheets + Google Drive son las herramientas más usadas por PyMEs venezolanas que tienen mínima infraestructura digital.

**Qué puede hacer Hermes**:
- **Gmail**: redactar y enviar emails, leer inbox, buscar correos, crear borradores
- **Google Sheets**: leer y actualizar hojas de cálculo (inventario, presupuestos, etc.)
- **Google Calendar**: agendar y gestionar reuniones, enviar recordatorios
- **Google Drive**: subir, descargar, compartir archivos

**Configuración**:
```bash
hermes skills install google-workspace
# Requiere: google_token.json (OAuth via setup script)
# Script de setup incluido en la skill
```

**Caso de uso — Contadora/contador de la empresa**:
```
Cada lunes 9am:
→ Hermes lee hoja de gastos de la semana anterior en Google Sheets
→ Categoriza los gastos automáticamente
→ Genera un resumen y lo envía a Gmail del dueño
→ Actualiza el Google Sheet con las categorías
```

---

### 4. Telegram — El canal del equipo

**Por qué**: aunque WhatsApp es para clientes, Telegram es mejor para el equipo interno — grupos, canales, bots, sin restricciones de API.

**Usos clave con Hermes**:
- **Alertas del negocio**: stock bajo, pedido grande, pago confirmado
- **Reportes diarios**: resumen de ventas, tareas pendientes
- **Coordinación de equipo**: asignar tareas, confirmar entregas
- **El dueño habla con Hermes desde donde esté**

**Configuración**: nativo en Hermes — solo necesitas `TELEGRAM_BOT_TOKEN` del @BotFather.

---

## Tier 2 — Integraciones de alto valor

### 5. Higgsfield AI — Video cinematográfico para redes

**Por qué**: la diferencia visual entre una empresa que usa video IA y una que no es inmediata. Videos de producto de calidad cinematográfica con $0.20-0.50.

**Qué genera**:
- Videos de producto con movimientos de cámara profesionales
- Historias y Reels de Instagram (formato 9:16)
- Clips para WhatsApp Status
- Trailers o teasers de servicios

**Integración con Hermes** (via terminal tool):

```python
# Hermes puede ejecutar esto:
import requests, os

def generate_hermes_video(prompt: str, aspect_ratio: str = "9:16") -> str:
    """Genera un video cinematográfico con Higgsfield AI."""
    response = requests.post(
        "https://api.higgsfield.ai/v1/generation/video",
        headers={"Authorization": f"Bearer {os.environ['HIGGSFIELD_API_KEY']}"},
        json={
            "prompt": prompt,
            "model": "dop-1",          # Director of Photography model
            "aspect_ratio": aspect_ratio,
            "duration": 5,
            "style": "cinematic",
        }
    )
    return response.json().get("video_url", "")
```

**Flujo completo**:
```
1. Dueño: "Crea un video de mi crema hidratante para Instagram"
2. Hermes: "¿Qué aspectos quieres destacar? ¿Textura, aplicación, resultado?"
3. Dueño: "La textura sedosa y que se ve lujoso"
4. Hermes genera prompt cinematográfico:
   "Close-up de crema hidratante con textura sedosa, 
    luz cálida de atardecer, travelling macro hacia adelante, 
    fondo neutro elegante"
5. Hermes llama API de Higgsfield
6. Descarga video y lo envía al dueño por Telegram
7. Dueño aprueba → sube a Instagram Reels
```

**Costo**: ~$0.30 por video de 5 segundos.

---

### 6. FAL.ai — Generación de imágenes de producto

**Por qué**: fotos de producto de calidad con texto exacto sin cámara ni fotógrafo.

**Modelos disponibles** (via Nous Portal o API key directa):
- **Flux Pro**: máxima calidad, mejor para producto sobre fondo limpio
- **Flux Schnell**: más rápido y barato, bueno para variaciones
- **SDXL**: alternativa open source

**Caso de uso**:
```
Dueño: "Necesito fotos del vestido rojo para Instagram. 
  Fondo blanco, luz natural, look minimalista"
Hermes → llama FAL.ai → genera 4 variaciones
Hermes → envía las 4 opciones por Telegram
Dueño elige → ya tiene contenido para publicar
```

**Integración**: built-in cuando uses Nous Portal o configures `FAL_KEY`.

---

### 7. Yahoo Finance / Stocks Skill — Seguimiento de precios

**Por qué**: para muchas PyMEs venezolanas el precio de sus productos está indexado al dólar. El cambio del USDT/USD afecta sus márgenes.

**Lo que puede hacer** (sin API key — completamente gratuito):
- Precio actual de cualquier criptomoneda
- Historial de precios (USDT, BTC, ETH, SOL)
- Alertas cuando el precio cruce un umbral
- Comparación de activos

**Configuración**:
```bash
hermes skills install stocks
# No requiere API key — usa Yahoo Finance unofficial API
```

**Automatización útil**:
```
Hermes cron: "Cada día a las 8am, revisa el precio del USDT/VES 
  (tasa paralela via Binance P2P scraping) y si varió más del 3% 
  desde ayer, envíame alerta por Telegram con el nuevo valor"
```

---

### 8. Notion — Wiki del negocio + base de conocimiento

**Por qué**: Notion es el "cerebro externo" de muchas empresas. Procedimientos, guías de onboarding de empleados, información de productos, FAQs.

**Integración clave con Hermes**:
Hermes puede leer y escribir en Notion. Esto significa que el agente tiene acceso a toda la información de la empresa que el dueño documente ahí.

**Caso de uso**:
```
En Notion: página "FAQ de clientes" con 50 preguntas frecuentes

Hermes (WhatsApp): cuando un cliente pregunta algo,
  Hermes busca primero en la Notion del cliente antes de inventar
  → respuestas más precisas y consistentes con la política de la empresa
```

**Configuración**:
```bash
hermes skills install notion
# Pide: NOTION_API_KEY
# Obtenla en: notion.so/my-integrations
```

---

### 9. Shopify — E-commerce estructurado

**Por qué**: para PyMEs que ya tienen o quieren tener una tienda online formal.

**Lo que puede hacer Hermes via Shopify**:
- Ver/actualizar inventario de productos
- Consultar pedidos (status, historial)
- Gestionar información de clientes
- Crear descuentos y códigos promocionales
- Generar reportes de ventas

**Configuración**:
```bash
hermes skills install shopify
# Pide: SHOPIFY_ACCESS_TOKEN, SHOPIFY_STORE_DOMAIN
```

---

### 10. Solana/EVM — Blockchain y crypto nativo

**Por qué**: el USDT en Tron (TRC-20) es el método de pago preferido entre empresas en Venezuela. Poder verificar transacciones on-chain es valioso.

**Lo que puede hacer la skill de Solana/EVM**:
- Verificar si se recibió un pago a una wallet
- Consultar el balance de una wallet
- Ver historial de transacciones
- Detectar whales (grandes movimientos)

**Configuración**:
```bash
hermes skills install solana  # Sin API key necesaria
hermes skills install evm     # Para Ethereum/Tron/Base
```

**Caso de uso**:
```
Cliente: "Te mandé $50 USDT a la wallet TXXX"
Hermes: verifica on-chain si llegó el pago
→ Si llegó: "Confirmado, recibí el pago. Preparo tu pedido ahora."
→ Si no llegó: "Aún no lo veo, ¿puedes verificar el hash de la transacción?"
```

---

## Tier 3 — Integraciones avanzadas

### 11. MCP Servers — Extensibilidad infinita

**Qué es**: Model Context Protocol (MCP) es un estándar open source de Anthropic que permite conectar Hermes con cualquier fuente de datos o herramienta externa que tenga un servidor MCP.

**Servidores MCP disponibles** (instalables via `hermes mcp install`):
- Postgres, MySQL (bases de datos directas)
- GitHub, GitLab
- Jira, Asana, Monday.com
- Stripe, PayPal
- Cloudflare Workers
- Cualquier sistema con MCP server

**Aplicación venezolana**: si la empresa usa un sistema de facturación propio o un ERP local, se puede construir un MCP server en horas para que Hermes tenga acceso.

---

### 12. Email Marketing — Campañas automatizadas

**Via Google Workspace**:
Hermes puede gestionar campañas de email directamente desde Gmail — segmentar clientes de Airtable, personalizar mensajes, y enviar en masa (con límites de Gmail).

**Para volúmenes mayores**: integración via API con Mailchimp, Brevo o similares via terminal tool.

---

### 13. Webhook — Conector universal

Hermes puede recibir webhooks de cualquier sistema. Esto abre integraciones infinitas:
- MercadoLibre notifica cuando llega un pedido → Hermes procesa y notifica al equipo
- Stripe/PayPal confirma pago → Hermes actualiza pedido en Airtable
- Formulario de Google → Hermes crea cliente en Airtable y envía bienvenida por WhatsApp

---

## Stack recomendado por tipo de negocio

### Comercio / Retail
```
WhatsApp Business API (canal de ventas)
+ Airtable (inventario + pedidos)
+ Telegram (alertas al dueño)
+ FAL.ai / Higgsfield (contenido para RRSS)
+ Stocks skill (precio del dólar)
```

### Servicios profesionales (contador, abogado, coach)
```
WhatsApp Business API (clientes)
+ Google Calendar (agenda)
+ Google Drive / Notion (documentos)
+ Gmail (comunicación formal)
+ Telegram (coordinación interna)
```

### Restaurante / Food delivery
```
WhatsApp Business API (pedidos)
+ Airtable (menú + disponibilidad)
+ Telegram (cocina y delivery)
+ Google Sheets (caja diaria)
```

### Agencia de marketing / freelancer
```
Telegram (comunicación con clientes)
+ Notion (gestión de proyectos, wikis)
+ Google Workspace (documentos + presentaciones)
+ FAL.ai + Higgsfield (creación de contenido)
+ GitHub (si hay desarrollo)
```

### E-commerce formal
```
WhatsApp Business API (atención al cliente)
+ Shopify (tienda online)
+ Airtable (inventario adicional)
+ Gmail (emails transaccionales)
+ FAL.ai (fotos de producto)
```
