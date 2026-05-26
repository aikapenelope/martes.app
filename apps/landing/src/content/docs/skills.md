---
title: "Skills de Hermes"
description: "Skills built-in activos por defecto y skills opcionales instalables."
order: 5
section: "Integraciones"
---

## Sistema de Skills

Los skills son módulos de capacidades que extienden a Hermes más allá de sus herramientas nativas. Hermes también **crea sus propios skills** automáticamente después de resolver tareas complejas, encapsulando el conocimiento para reutilización futura.

El cliente gestiona sus skills desde Telegram:
```
/skills browse         → explorar el hub de skills
/skills install notion → instalar skill de Notion
/skills list           → ver skills instalados
```

---

## Skills built-in (activos por defecto)

### Productividad
| Skill | Qué hace |
|---|---|
| **Notion** | Lectura/escritura de páginas y bases de datos |
| **Airtable** | CRUD completo, filtros, upserts, vistas |
| **Google Workspace** | Gmail, Calendar, Drive, Docs, Sheets, Contacts |
| **Linear** | Issues, proyectos, ciclos, comentarios |
| **Maps / Rutas** | Google Maps, geocoding, distancias, rutas |
| **OCR y documentos** | Extracción de texto de PDFs, imágenes, documentos escaneados |
| **PowerPoint** | Creación y edición de presentaciones |
| **Teams Meeting Pipeline** | Automatización de reuniones de Microsoft Teams |

### Social Media
| Skill | Qué hace |
|---|---|
| **X / Twitter** | Búsqueda, análisis de tweets (OAuth o API key) |

### Investigación
| Skill | Qué hace |
|---|---|
| **ArXiv** | Búsqueda de papers académicos |
| **RSS / HTTP** | Vigilancia de contenido y fuentes |
| **GitHub Watch** | Monitoreo de repositorios |
| **OSINT básico** | Información de dominios y organizaciones |

### Desarrollo
| Skill | Qué hace |
|---|---|
| **GitHub** | Repos, PRs, issues, releases, CI/CD via gh CLI |
| **MLOps** | Entrenamiento, evaluación, bases de datos vectoriales |

### Creative
| Skill | Qué hace |
|---|---|
| **Diagramas** | Excalidraw, UML, arquitectura de sistemas |
| **Arte ASCII** | Diseño visual en terminal |

---

## Skills opcionales (instalar vía `/skills install`)

### Finanzas y mercados
| Skill | Qué hace |
|---|---|
| `stocks` | Cotizaciones, historial, crypto via Yahoo Finance (sin API key) |
| `3-statement-model` | Estado de resultados, balance, flujo de caja |
| `dcf-model` | Valoración por flujos descontados |
| `comps-analysis` | Análisis comparativo de empresas |
| `lbo-model` | Leveraged buyout modeling |
| `merger-model` | Análisis de fusiones y adquisiciones |
| `hyperliquid` | DeFi perpetuos y spot via Hyperliquid SDK |

### Blockchain
| Skill | Qué hace |
|---|---|
| `solana` | Wallets, tokens, transacciones, NFTs, whale detection |
| `evm` | Ethereum + L2s + Base (multi-chain) |

### E-commerce
| Skill | Qué hace |
|---|---|
| `shopify` | Admin API + Storefront GraphQL (productos, órdenes, inventario) |
| `shop-app` | Asistente de compras personal |

### Comunicación
| Skill | Qué hace |
|---|---|
| `telephony` | Llamadas de voz programáticas |

### Productividad adicional
| Skill | Qué hace |
|---|---|
| `memento-flashcards` | Tarjetas de memoria espaciada |
| `here-now` | Localización y contexto geográfico |
| `canvas` | Lienzo de trabajo visual |

---

## Auto-creación de skills

Hermes crea skills automáticamente. Después de resolver una tarea compleja por primera vez, documenta el procedimiento como un skill reutilizable. La próxima vez que se necesite algo similar, lo aplica directamente sin rehacer el trabajo.

Ejemplo:
```
Primera vez: "Extrae todos los contactos de mi Gmail y pásalos a Airtable"
→ Hermes lo resuelve (tarda 3 minutos)
→ Hermes crea el skill "gmail-to-airtable-sync"

Segunda vez: tarda 10 segundos
```

---

## Compatibilidad con agentskills.io

Los skills de Hermes son compatibles con el estándar abierto [agentskills.io](https://agentskills.io), lo que significa que skills creados por la comunidad para otros agentes compatibles también funcionan en Hermes.
