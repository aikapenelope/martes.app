---
title: "Hermes v0.14.0 — What Changed and Why It Matters"
description: "The most important Hermes release of 2026: 180x faster browser automation, computer use in GPT-4o and Gemini, Microsoft Teams, and more."
date: "2026-05-20"
tags: ["Hermes", "Product", "Release"]
author: "martes.app"
---

## Hermes v0.14.0 is now in production

NousResearch just published version 0.14.0 of Hermes Agent (Docker tag: `v2026.5.16`). It is the most significant update of the year. martes.app tenants are running this version since launch day.

These are the changes that matter most for enterprise use.

---

## 180x faster in browser automation

The CDP (Chrome DevTools Protocol) engine was completely rewritten. Interactions with web pages — navigation, clicks, data extraction, screenshots — are now 180 times faster than in v0.13.x.

In practice: what used to take 3 minutes to scrape data from a web table now takes 1 second.

---

## Computer use without Claude

Until v0.13.x, mouse and keyboard control (computer use) only worked with Anthropic models. In v0.14.0 it works with **any model**:

- GPT-4o ✓
- Gemini 2.0 Flash ✓
- DeepSeek V4 Flash ✓ (and much cheaper)

This means your screen automations are no longer tied to Anthropic pricing.

---

## Microsoft Teams end-to-end

Hermes can now read Teams messages and reply from the same agent you already use on Telegram. One Hermes, all channels.

Especially useful for companies with part of the team on Teams and customers on WhatsApp.

---

## More updates

**`/handoff`** — transfers an active session (with full context) to another model without losing anything. You started with DeepSeek, you need Claude's reasoning for this specific part, then back to DeepSeek. Without losing the thread.

**Claude prompt caching cross-session** — if you use Claude for long conversations, -60% on cost. System prompts and context are cached across sessions.

**Grok 4.3 at 1M tokens** — entire documents, complete repositories, large databases in a single query.

**LSP semantic diagnostics** — when Hermes writes code, it now verifies semantic errors before ending the turn. Fewer iterations of "fix this error".

**pip install hermes-agent** — available on PyPI. No need to clone the repo anymore.

---

## For martes.app tenants

All containers already run `v2026.5.16`. No action required from your side.

If you want to try `/handoff` or the new computer use capabilities, just ask your agent from Telegram.