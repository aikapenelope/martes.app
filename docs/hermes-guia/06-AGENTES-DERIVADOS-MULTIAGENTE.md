# Guía de Agentes Derivados y Arquitecturas Multi-Agente

> **Para operadores y clientes que quieren ir más allá del asistente básico**  
> **Incluye**: Higgsfield AI, agentes especializados, arquitecturas de producción

---

## Qué es un agente derivado

Un "agente derivado" es un Hermes especializado para una función específica, corriendo en su propio container con su propio `SOUL.md`, su propia wiki de conocimiento, y sus propias integraciones.

Cada agente derivado:
- Tiene una sola responsabilidad clara
- Habla el idioma de su función (el de ventas habla de pedidos, el de marketing de métricas)
- Tiene acceso solo a las tools que necesita (principio de mínimo privilegio)
- Se coordina con los otros via mensajería o APIs

---

## Los 6 agentes principales para una PyME

### 1. Agente de Atención al Cliente
**Canal principal**: WhatsApp  
**Responsabilidad**: primera línea con clientes  
**Tools**: inventario en Airtable, historial de pedidos  
**SOUL.md**: "Eres [Nombre], el asistente de atención de [Empresa]. Eres venezolano, cercano, y eficiente."  
**Escala a**: humano cuando el cliente tiene un reclamo que supera $X o requiere decisión de negocio  

### 2. Agente de Ventas
**Canal principal**: WhatsApp + Instagram DMs  
**Responsabilidad**: convertir consultas en pedidos confirmados  
**Tools**: catálogo de productos, verificación de disponibilidad, generación de facturas  
**SOUL.md**: orientado a cerrar — hace preguntas de calificación, ofrece alternativas cuando no hay stock, aplica técnicas de upselling  
**KPI**: tasa de conversión de consultas a pedidos  

### 3. Agente de Marketing
**Canal principal**: Telegram (notificaciones al dueño)  
**Responsabilidad**: generar contenido semanal para RRSS  
**Tools**: FAL.ai, Higgsfield API, Notion, análisis de tendencias  
**SOUL.md**: creativo, conoce el estilo visual de la marca, sabe qué hashtags funcionan en Venezuela  
**Output**: 10-15 posts listos para aprobar y publicar cada semana  

### 4. Agente de Cobros
**Canal principal**: WhatsApp (clientes) + Telegram (dueño)  
**Responsabilidad**: seguimiento de pagos pendientes  
**Tools**: Airtable (pedidos), registro de confirmaciones  
**SOUL.md**: amable pero firme, sabe cuándo escalar deudas al dueño  
**Automatización**: recordatorio a 24h, 48h, y 72h de mora  

### 5. Agente de Inventario
**Canal principal**: Telegram (interno)  
**Responsabilidad**: mantener el inventario actualizado y alertar sobre stock  
**Tools**: Airtable, Google Sheets, posiblemente scraping de precios de proveedores  
**Automatización**: alerta diaria de productos con stock bajo, actualización semanal de precios según tipo de cambio  

### 6. Agente de Análisis
**Canal principal**: Telegram (dueño)  
**Responsabilidad**: reportes de negocio y análisis estratégico  
**Tools**: Airtable, Google Sheets, stocks (precios de crypto/dólar), búsqueda web  
**Output**: reporte semanal de ventas, análisis mensual de tendencias, comparación con mercado  

---

## Arquitectura multi-agente para una PyME

```
                    DUEÑO
                      │
            ┌─────────┴─────────┐
            │                   │
        Telegram             WhatsApp
            │                   │
     ┌──────┴───────┐      ┌────┴────┐
     │  Meta-agente │      │ Agente  │
     │  (Operador)  │      │ Cliente │
     └──────┬───────┘      └────┬────┘
            │                   │
    ┌───────┼───────────────────┤
    │       │                   │
    ▼       ▼                   ▼
 Agente  Agente            Agente
 Inventario  Marketing     Cobros
    │       │                   │
    └───────┴───────────────────┘
                    │
              [Base de datos]
              [Airtable / Sheets]
```

**El flujo**:
1. Cliente pregunta en WhatsApp → Agente de Cliente responde
2. Si hay pedido → crea registro en Airtable
3. Agente de Cobros ve el registro → hace seguimiento
4. Agente de Inventario actualiza stock cuando se confirma entrega
5. Agente de Análisis genera reporte semanal con todos los datos
6. Dueño ve todo via Telegram sin tener que gestionar nada

---

## Higgsfield AI — Pipeline de contenido completo

### El flujo de 20 minutos/semana para RRSS

**Martes 7am (automatizado)**:
1. Hermes analiza los productos más vendidos esa semana en Airtable
2. Busca tendencias de contenido de esa semana (búsqueda web)
3. Genera 10 ideas de contenido alineadas con la marca

**Martes 8am (dueño recibe por Telegram)**:
- 10 ideas de posts con copy propuesto
- 3 imágenes ya generadas con FAL.ai para las mejores ideas
- 1 video Reels ya generado con Higgsfield para el producto destacado

**Dueño (5 minutos)**:
- Aprueba o ajusta el copy de 5 posts
- Selecciona las 2 mejores imágenes
- Confirma si el video está bien o pide una variación

**Resultado**:
- 5 posts texto + imagen para la semana
- 1 Reels de producto de calidad cinematográfica
- El dueño invirtió 5 minutos en total

### Configurar la integración con Higgsfield

```python
# Añadir al .env del tenant:
HIGGSFIELD_API_KEY=hf_xxxxxxxxxxxxxxxx

# Crear skill personalizada en src/skills/marketing/:
# SKILL.md con instrucciones para llamar la API
```

```markdown
---
name: higgsfield-video
description: Genera videos cinematográficos de producto via Higgsfield AI DOP-1
prerequisites:
  env_vars: [HIGGSFIELD_API_KEY]
---

## Cuando usar
- Usuario pide video de producto para Instagram/TikTok/Reels
- Necesita clip cinematográfico para campaña de marketing

## Comandos
1. `generate_product_video(description, style, duration_s)` — genera video
2. `get_video_styles()` — lista estilos disponibles (minimal, cinematic, etc.)
```

---

## Casos de uso avanzados específicos para Venezuela

### Caso 1: Tienda de ropa con 3 empleados

**Setup**:
- Agente de Cliente en WhatsApp: atiende 100+ mensajes/día
- Agente de Marketing: genera 3 posts/semana + 1 Reels
- Sin Agente de Cobros (la dueña lo hace personalmente)

**Resultado real esperado**:
- Tiempo ahorrado: 3-4 horas/día
- Ventas recuperadas por respuesta rápida: 5-8 pedidos/semana adicionales
- Contenido creado: 12-15 posts/mes vs 4-6 antes

**ROI**: Si cada pedido promedia $25, y se recuperan 6 ventas/semana adicionales:
- 6 × $25 × 4 semanas = **$600/mes adicional**
- Costo del agente: $30/mes
- **ROI: 20x**

---

### Caso 2: Distribuidora de productos de consumo masivo

**Setup**:
- Agente de Ventas: atiende a vendedores por Telegram
  - Consultan disponibilidad y precios en tiempo real
  - El agente verifica en la base de datos y responde en segundos
  - Sin tener que llamar a la oficina central
- Agente de Inventario: alerta cuando algún SKU baja del mínimo
- Agente de Análisis: reporte semanal de qué se está vendiendo más

**Resultado**:
- Vendedores dan respuestas más rápidas a sus clientes
- Menos pedidos rechazados por falta de stock no detectada
- Dueño sabe en tiempo real qué necesita reponer

---

### Caso 3: Agencia de marketing digital venezolana

**Setup**:
- Hermes como asistente del equipo (Telegram interno)
- Puede hacer tareas de investigación: análisis de competencia, tendencias de mercado
- Genera primeros borradores de copy para clientes
- Analiza métricas de campañas (via Google Sheets)

**Capacidad diferenciadora**:
La agencia puede ofrecer a sus clientes un "mini-asistente de atención al cliente" como servicio adicional — usan martes.app como plataforma y cobran $60-100/mes por cliente.

**Este es el modelo de revendedor de martes.app.**

---

## El modelo de revendedor/agencia

### Estructura de costos
```
Costo del tenant en martes.app: $30/mes
Precio al cliente final: $60-100/mes
Margen: $30-70/mes por cliente
Con 10 clientes: $300-700/mes de margen neto pasivo
```

### Quién puede hacer esto
- Agencias de marketing digital que quieran añadir valor
- Freelancers que manejan RRSS para múltiples empresas
- Consultores de negocios que quieran automatizar la operación de sus clientes
- Técnicos en informática que ya tienen relaciones con PyMEs

### Lo que el revendedor necesita saber
- Configurar el `SOUL.md` para cada cliente
- Conectar las integraciones básicas (WhatsApp, Airtable)
- Hacer el onboarding del cliente
- Monitorear via Metabase que todo esté funcionando

**No necesita saber programar** — martes.app maneja toda la infraestructura.

---

## El potencial a largo plazo

### Con 100 clientes activos
```
Ingresos brutos: 100 × $30 = $3,000/mes
Costos de servidor: ~$200/mes (2-3 servidores Hetzner CX43)
Costo de tokens OpenRouter: ~$300/mes
Margen neto: ~$2,500/mes
```

### Con modelo de revendedor (agencia intermedia)
```
5 agencias × 20 clientes cada una = 100 clientes
Costo wholesale a agencia: $20/cliente/mes
Ingresos: 100 × $20 = $2,000/mes
+ Clientes directos: 20 × $30 = $600/mes
Total: $2,600/mes con mínima gestión directa
```

### El techo de escala
- 1 servidor Hetzner CX43 (16GB RAM): ~25 tenants cómodamente
- Múltiples servidores: escala lineal
- La arquitectura ya está diseñada para multi-server

---

## Cómo hablar de esto con un potencial cliente

**Preguntas que abren la conversación**:
- "¿Cuántos mensajes de WhatsApp recibes de clientes al día?"
- "¿Cuánto tiempo pasas respondiendo mensajes vs. atendiendo el negocio?"
- "¿Cuántas ventas crees que pierdes porque no alcanzas a responder a tiempo?"
- "¿Tienes alguien manejando tus redes sociales? ¿Cuánto te cuesta?"

**El cierre**:
> "¿Y si tuvieras alguien que hace todo eso por $30 al mes y nunca falta ni se cansa?"

---

*Nota sobre Higgsfield AI: higgsfield.ai es un producto independiente de NousResearch. La integración descrita es via API REST pública. Los precios y disponibilidad pueden cambiar. Verificar en https://higgsfield.ai/pricing*
