---
title: "AI Agents Are Not 'Set and Forget' — Why You Need Ongoing Management"
description: "An AI agent will be obsolete in 90 days without active management. Here is what breaks, what it costs, and why this is actually good news for your business."
date: "2026-07-02"
tags: ["Maintenance", "Operations", "AI Lifecycle"]
author: "martes.app"
---

## The myth

“AI is the future. Just turn it on and it runs forever.”

That is the pitch you see in every demo. It is also wrong, in a specific and predictable way: every AI agent you deploy will be measurably worse in 90 days if no one is watching it.

This is not a scare tactic. It is the operational reality of any system that depends on external APIs, third-party models, and the open-source software underneath it. The question is not *whether* your agent will degrade, but *when* and *how much it will cost* when it does.

## The 7 things that break in the first 90 days

### 1. Model deprecation

OpenRouter and individual model providers retire models on a regular cycle. GPT-3.5 was deprecated in 2024. Claude 2.1 was retired in early 2025. Gemini 1.0 Pro is being phased out. When the model your agent depends on disappears, your agent starts failing silently — generic answers, refusals where there were none before, cost spikes if the replacement is more expensive.

If no one is monitoring deprecation notices, you find out when a customer complains.

### 2. API breaking changes

Telegram deprecates bot API versions. WhatsApp Business API changes webhook signing requirements. Google Workspace APIs require periodic re-authentication. Stripe changes webhook payload structures. None of these are dramatic, but each one can break a specific flow in your agent, and the breakage is usually silent.

### 3. Security vulnerabilities

Hermes Agent and its dependencies ship new CVEs every quarter. A serious vulnerability in a dependency (a PDF parser, an HTTP client, a logging library) can sit in your production agent for weeks before anyone notices. For an agent that handles customer data, this is a compliance risk.

### 4. Cost spikes

When OpenRouter changes the pricing of a model, or a new “smarter” model becomes the default, your token bill can jump 10× overnight. Without alerts on per-conversation cost, you discover the spike in your monthly invoice.

### 5. Response drift

A new agent is good for a few weeks. Then reality sets in: edge cases, novel phrasings, slang, multilingual input. Without a feedback loop where someone reviews bad responses and turns them into training examples, your agent’s quality erodes over time. The drop is usually 10–20% by month three.

### 6. New tools and standards

Last year, MCP (Model Context Protocol) became the de-facto standard for connecting agents to tools. This year, more protocols will emerge. If your agent is not kept current, it falls behind competitors who adopted the new standard six months ago.

### 7. Compliance changes

CCPA enforcement updated in 2025. HIPAA audit procedures tightened in 2024. New York’s automated decision-making law (Local Law 144) is in effect. State-level AI rules are multiplying. An agent that was compliant in January can be non-compliant in June if no one is tracking the regulatory landscape.

## A real example: the agent that broke at 3am

Last quarter, one of our reference customers (a B2B SaaS company, anonymized) had a Telegram bot that processed customer support tickets. At 3am on a Tuesday, OpenRouter rotated the default model to a successor version. The new model had a different refusal behavior — it started refusing to quote prices for products the previous model happily quoted.

The bot did not crash. The webhook was healthy. No error was logged. But by 9am the next morning, 14% of inbound conversations were ending in escalation because the agent was refusing to give pricing. The company’s head of support estimated $8,400 in lost pipeline before someone noticed.

The fix took 22 minutes once detected. The damage was 12 hours of compounding loss.

This is not an outlier. This is what happens to unattended agents.

## The 3 tiers of AI agent management

Every AI deployment falls into one of three tiers, and the difference between them is what determines whether your agent is a competitive advantage or a slow-moving liability.

### Tier 1: Watch — DIY

You monitor the agent yourself. You read GitHub release notes, follow the OpenRouter changelog, and set up your own alerting on cost and uptime. You patch security vulnerabilities when they are disclosed. You review bad responses monthly and update your prompt library.

**Cost:** $0/month in service fees, but you (or someone on your team) spend 4–8 hours per month doing it.
**Best for:** Companies with strong engineering culture, small agent surface area, and tolerance for occasional downtime.

### Tier 2: Manage — We do the watching

We monitor your deployment 24/7. When a model is deprecated, we migrate you before anyone notices. When a CVE is published, we patch within 48 hours. When a webhook payload changes, we fix it the same day. You get a monthly health report and a Slack channel for issues.

**Cost:** A fraction of one human FTE. Sized per agent and per conversation volume.
**Best for:** Most US companies. The default choice for any agent that touches customers or revenue.

### Tier 3: Evolve — We build new features

Beyond maintenance, we add new skills, integrations, and automations on a roadmap we co-design with you. We tune responses to your brand voice. We A/B test new flows. We write custom reports. We keep your agent at the frontier.

**Cost:** Higher than Manage, but with a clear roadmap and quarterly business reviews.
**Best for:** Companies whose agent is a strategic asset, not a side project.

## What we actually do in a typical month

A real week from our Manage service, anonymized:

| Day | Event | Action taken | Time to fix |
|---|---|---|---|
| Mon | Telegram bot API v6.9 deprecation notice | Pinned to v6.8, scheduled migration to v7 | 30 min |
| Tue | Customer reported agent gave wrong shipping ETA | Reviewed 12 conversations, found edge case in prompt, updated prompt | 45 min |
| Wed | OpenRouter announced 40% price cut on claude-sonnet-4 | Switched default model, ran 200 conversation A/B test, deployed | 90 min |
| Thu | New CVE in `pdf-parse` dependency | Updated to patched version, redeployed, smoke-tested | 1 hour |
| Fri | Monthly health report generated | Sent to client with 3 recommendations | 15 min |

Total time on this client: 4.5 hours per month. Without this service, each of those five items would have been discovered by the client (or by their customers) at unpredictable times, with unpredictable cost.

## The ROI of management

A well-managed agent that avoids one 12-hour outage per year pays for itself ten times over. The 90-day “set and forget” agent that quietly loses 10–20% of its quality costs more in lost revenue than the management fee, and the loss is invisible until it is large.

If your agent handles more than 50 conversations per day, or touches revenue directly, the case for active management is not a question of cost. It is a question of how much risk you want to take on.

## When you can DIY (and when you cannot)

| Factor | DIY works | You need management |
|---|---|---|
| Conversation volume | < 30/day | > 50/day |
| Integrations | < 3 | > 5 |
| Engineering team size | > 3 dedicated | < 3 or shared with other priorities |
| Tolerance for surprise outages | High | Low |
| Customer-facing or internal | Internal | Customer-facing |
| Regulatory environment | None | HIPAA, SOC 2, CCPA |

If you are on the right side of the “DIY works” column, you probably do not need us. We are happy to tell you that on a call.

If you are on the left side of the “You need management” column, the question is no longer *whether* to invest in ongoing management. It is *who* does it.

## What to do next

The wrong next step is to wait for the first outage. The right next step is a 30-minute call where we look at your current setup, your current risks, and the realistic cost of doing nothing.

[Book a 30-minute call](#contact). We will give you an honest assessment of your current agent's health, with no obligation and no pitch.

If you do not have an agent yet, that is fine too. We can talk about whether you need one, and what the right scope would be for your specific situation.

---

*We provide ongoing management for AI agents built on Hermes Agent and other open-source stacks. Pricing is sized per project; please contact us for a tailored quote.*
