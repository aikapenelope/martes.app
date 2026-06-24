---
title: "Set up your first agent in 5 minutes"
description: "Step-by-step guide: from zero to a Hermes agent responding on Telegram. All you need is a bot token from @BotFather and your Telegram ID."
date: "2026-06-04"
tags: ["Tutorial", "Telegram", "Getting started"]
author: "martes.app"
---

## What you need before starting

1. A Telegram account
2. A bot created in [@BotFather](https://t.me/BotFather) — free, takes 2 minutes
3. Your numeric Telegram ID — get it from [@userinfobot](https://t.me/userinfobot) in seconds

That's it. No server needed, no AWS account, no programming knowledge.

---

## Step 1: Create the bot in BotFather (2 min)

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. BotFather asks for the bot name — type your company name or any name
4. BotFather asks for the username — must end in `bot`, e.g.: `acme_corp_bot`
5. BotFather replies with the **token** — it looks like this: `123456789:AABBCCddEEFFggHHii...`

Save that token. You need it in the next step.

---

## Step 2: Get your Telegram ID

1. Search for **@userinfobot** in Telegram
2. Send it any message
3. It replies with your **User ID** — a number like `987654321`

---

## Step 3: Message the martes.app admin

Send this message to the admin (via Telegram):

```
I want to activate my agent.
Company name: [your company]
Bot token: [the BotFather token]
Telegram ID: [your @userinfobot number]
```

The admin creates your tenant in ~30 seconds. You will receive a confirmation when it's ready.

---

## Step 4: Your agent is active

Open the bot you created in BotFather and send it anything. Hermes replies.

From the first message, Hermes:
- Starts learning who you are
- Has web search access
- Can execute Python code
- Can schedule automated tasks
- Can connect to your tools (next steps)

---

## Useful commands to get started

```
/model                  → see current model and switch
/skills browse          → explore available skills
/skills install notion  → connect Notion
/cron add               → schedule an automated task
/memory                 → see what it remembers about you
/help                   → see all commands
```

---

## Step 5: Configure your own API key (optional, recommended)

The agent starts with a temporary platform key (30 days). For the service to continue beyond that, the client configures their own OpenRouter key:

1. Create an account at [openrouter.ai](https://openrouter.ai)
2. Generate an API key (free, you only pay for what you use)
3. Message your agent:

```
Configure this OpenRouter API key: sk-or-v1-xxxxx
```

Hermes configures it alone, no restart, immediate effect.

---

## Examples of what you can do from day one

**Search for information:**
```
"Search for the latest news on AI in Venezuela and give me a summary"
```

**Schedule a report:**
```
"Every Monday at 8am, remind me to review the week's pending payments"
```

**Connect Airtable:**
```
"Install the Airtable skill and connect my client database"
```

**Automate:**
```
"Whenever someone writes to me in this chat about a complaint, save it to my Airtable 'Support' table"
```

---

Got questions? [Write to us here](#contact) or directly to the admin via Telegram.