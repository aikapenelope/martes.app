---
title: "Hermes Skills"
description: "Built-in skills active by default and optional installable skills."
order: 5
section: "Integrations"
---

## Skills System

Skills are capability modules that extend Hermes beyond its native tools. Hermes also **creates its own skills** automatically after solving complex tasks, encapsulating knowledge for future reuse.

The client manages their skills from Telegram:
```
/skills browse         → explore the skills hub
/skills install notion → install Notion skill
/skills list           → see installed skills
```

---

## Built-in skills (active by default)

### Productivity
| Skill | What it does |
|---|---|
| **Notion** | Read/write of pages and databases |
| **Airtable** | Full CRUD, filters, upserts, views |
| **Google Workspace** | Gmail, Calendar, Drive, Docs, Sheets, Contacts |
| **Linear** | Issues, projects, cycles, comments |
| **Maps / Routes** | Google Maps, geocoding, distances, routes |
| **OCR and documents** | Text extraction from PDFs, images, scanned documents |
| **PowerPoint** | Creation and editing of presentations |
| **Teams Meeting Pipeline** | Microsoft Teams meeting automation |

### Social Media
| Skill | What it does |
|---|---|
| **X / Twitter** | Search, tweet analysis (OAuth or API key) |

### Research
| Skill | What it does |
|---|---|
| **ArXiv** | Academic paper search |
| **RSS / HTTP** | Content and source monitoring |
| **GitHub Watch** | Repository monitoring |
| **Basic OSINT** | Domain and organization information |

### Development
| Skill | What it does |
|---|---|
| **GitHub** | Repos, PRs, issues, releases, CI/CD via gh CLI |
| **MLOps** | Training, evaluation, vector databases |

### Creative
| Skill | What it does |
|---|---|
| **Diagrams** | Excalidraw, UML, system architecture |
| **ASCII Art** | Visual design in terminal |

---

## Optional skills (install via `/skills install`)

### Finance and markets
| Skill | What it does |
|---|---|
| `stocks` | Quotes, history, crypto via Yahoo Finance (no API key) |
| `3-statement-model` | Income statement, balance sheet, cash flow |
| `dcf-model` | Valuation by discounted cash flows |
| `comps-analysis` | Comparative company analysis |
| `lbo-model` | Leveraged buyout modeling |
| `merger-model` | Merger and acquisition analysis |
| `hyperliquid` | DeFi perpetuals and spot via Hyperliquid SDK |

### Blockchain
| Skill | What it does |
|---|---|
| `solana` | Wallets, tokens, transactions, NFTs, whale detection |
| `evm` | Ethereum + L2s + Base (multi-chain) |

### E-commerce
| Skill | What it does |
|---|---|
| `shopify` | Admin API + Storefront GraphQL (products, orders, inventory) |
| `shop-app` | Personal shopping assistant |

### Communication
| Skill | What it does |
|---|---|
| `telephony` | Programmatic voice calls |

### Additional productivity
| Skill | What it does |
|---|---|
| `memento-flashcards` | Spaced memory cards |
| `here-now` | Location and geographic context |
| `canvas` | Visual work canvas |

---

## Auto-creation of skills

Hermes creates skills automatically. After solving a complex task for the first time, it documents the procedure as a reusable skill. The next time something similar is needed, it applies it directly without redoing the work.

Example:
```
First time: "Extract all contacts from my Gmail and pass them to Airtable"
→ Hermes solves it (takes 3 minutes)
→ Hermes creates the "gmail-to-airtable-sync" skill

Second time: takes 10 seconds
```

---

## Compatibility with agentskills.io

Hermes skills are compatible with the open standard [agentskills.io](https://agentskills.io), which means community-created skills for other compatible agents also work in Hermes.