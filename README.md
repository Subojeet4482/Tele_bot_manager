# Telegram Account Manager Bot

A Telegram bot for connecting several Telegram user accounts, keeping their Telethon sessions encrypted in
Firebase Firestore, forwarding incoming messages to you, and sending messages from all of your accounts.

**Multi-admin:** the first ID (`OWNER_ID`) is the **owner**. The owner can add and remove other **admins**.
Every admin connects their *own* accounts and only ever sees and controls those. Anyone else who opens the bot is
told it is only for its admin.

## Safety and Telegram rules

- Use this only for accounts you own or are explicitly allowed to manage. Follow Telegram's Terms of Service,
  rate limits and anti-spam rules. `/alll` and the daily broadcast open new chats: they always keep at least 3 seconds
  between accounts.
- OTP codes, 2-step passwords, API hashes and session strings are deleted from the chat right after they are read.
  OTPs and passwords are never stored. API hashes and sessions are encrypted before they go to Firestore.
- Keep `SESSION_ENCRYPTION_KEY` private and backed up.
- Logs never contain message texts, secrets or raw chat/sender/user ids (ids appear as short masked tags like `#a1b2c3`).

## How the bot works

`/start` shows **Connect account · Logout account · My accounts · (owner: Manage admins) · Menu**.
`/menu` shows every action as a button. Every step-by-step screen has **⬅️ Back** and **❌ Cancel**.

| Command | What it does |
|---|---|
| `/all` | Message a user from all your accounts (existing chats only) |
| `/alll` | Same, but opens the chat if needed (at least 3 sec between accounts) |
| `/allblock` | Block a user on all your accounts |
| `/message` | Send from one account (pick account → chat → text) |
| `/usermessage` `/botmessage` `/channelmessage` | Forwarding switch for one account (opens a screen with buttons) |
| `/list` | Your accounts |
| `/logs` | (owner) one-time link to the live logs |
| `/cancel` | Cancel the current step / stop a running bulk action |

The daily broadcast (old `/onalltime`) and the delay setting (old `/delay`) are no longer commands: the daily
broadcast is a menu button that asks one question at a time, and the delay is asked every time you run a bulk action.

### `/all`, `/alll`, `/allblock` step by step

```
You: /all
Bot: Enter the user name          →  @mandal4482
Bot: Confirm the user  [✅ Confirm] [⬅️ Back] [❌ Cancel]
Bot: Delay between accounts (0–100 sec)   0 = instant, or 1 / 3 / 5 / 10 / 30 … or type a number
Bot: Send the message text        →  hello
Bot: Working on 5 account(s) …    →  result: "✅ Message sent: 5/5 accounts"
```

- **Delay 0 = instant:** all accounts act at the same moment. **Delay N:** one account acts, the bot waits N seconds,
  then the next account acts.
- `/alll` accepts 3–100 seconds only. `/allblock` has the same steps as `/all` but no message question.
- Offline accounts are reported and skipped without waiting. A **🛑 Stop** button (or `/cancel`) stops a running job.

### One-line forms

```
/all @mandal4482 hello 3sec Y     runs now (Y = confirmed, 3sec = delay between accounts)
/all @mandal4482 hello Y          asks only for the delay
/all @mandal4482 hello 3sec       asks you to confirm first
/all @mandal4482 hello 3sec N     cancelled
/allblock @mandal4482 3sec Y      same idea, no message
/message 1 @mandal4482 hello      sends right away from your account 1
```

A trailing `Y`/`N` and a trailing `3sec` are read as options, so a message that really ends in "Y" or "5s" should
go through the step-by-step flow.

### Owner and admins

- The owner (`OWNER_ID`) opens **👑 Manage admins** from `/start`: add an admin by Telegram user ID, or remove one.
- Removing an admin logs out and deletes **their** accounts and stops their daily broadcast.
- Account numbers (`1, 2, 3…`) are per admin. Forwarded messages, replies, reactions, bulk actions, notifications and
  the daily broadcast always stay inside the admin who owns the account.
- Only the owner can open the logs.

## Live logs, without a secret in the URL

`/logs` (owner only) sends a **one-time link** that expires after 10 minutes. Opening it shows a page with an
**Open logs** button; pressing it starts a 12-hour browser session (HttpOnly, SameSite=Strict cookie) and the address
becomes plain `/logs`. So the browser history and referrers never contain a secret, and a link preview or scanner
cannot use the link up. `/logs/logout` ends the session. `/status` (JSON) needs the same session.

## Health for UptimeRobot

| URL | Answer |
|---|---|
| `/` and `/health` | Real health: `200 ok` / `200 degraded` (some accounts offline) / `503 down` (bot not answering Telegram, watchdog stalled, or every saved account offline). A new start gets 3 minutes of grace. A standby copy (see the instance lease) reports ok. |
| `/live` | Always `200` while the process runs (use this for a platform check that should not restart you when Telegram is down) |

Health uses a bot heartbeat (`get_me` every minute) and the connection watchdog. The response contains only a
status and a reason code, never account names. Other paths return 404.

## Setup

Requirements: Python 3.11+, a bot token from [@BotFather](https://t.me/BotFather), API ID/hash from
[my.telegram.org](https://my.telegram.org), a Firebase project with Firestore.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # → SESSION_ENCRYPTION_KEY
base64 -w 0 firebase-service-account.json                                                    # → FIREBASE_CREDENTIALS_B64
```

Set `OWNER_ID` to your numeric Telegram ID (ask [@userinfobot](https://t.me/userinfobot)). `TIMEZONE` (IANA name,
default `UTC`) is used by the daily broadcast. Then `python app.py`.

Optional: add a Firestore TTL policy on the `expires_at` field of `telegram_reply_map` to auto-delete old entries.

## Upgrading from the single-admin version

Nothing to migrate by hand. On first start: your existing accounts become the owner's, the owner's old global
forwarding switches and account counter move to the new per-admin settings, and the old daily job becomes the owner's
daily broadcast. `ADMIN_ID` still works as `OWNER_ID`. `LOGS_TOKEN` and the `/logs?token=` URLs are gone (old links
stop working; use `/logs`). The global `/delay` setting is no longer used.

## Tests

```bash
python -m unittest discover -s tests -v
```

116 tests cover parsing, config, the web server (health states, one-time login, cookies), Firestore isolation between
admins, every wizard (bulk, message, connect with 2-step password and Back, daily broadcast, admin add/remove),
access control, per-admin forwarding and bulk timing. Without the Telegram/Telethon libraries installed, the tests use
tiny stand-ins (`tests/stubs.py`); with them installed nothing is replaced.

## Project layout (one file per job)

```text
app.py                          entry point
telegram_manager/
  config.py constants.py crypto.py errors.py log_setup.py parsing.py access.py
  store/      accounts admins settings jobs lease replies database   (Firestore, one class each)
  core/       manager + mixins: login, accounts, dialogs, messaging (bulk), forwarding,
              replies, scheduler, watchdog, lease, lifecycle, status
  web/        server, access (one-time login), health, selfping, logs_page, login_page
  bot/
    registry.py lifecycle.py middleware.py guard.py keyboards.py bulk_runner.py ui.py deps.py
    wizard/   engine spec state        (step-by-step flows with Back/Cancel)
    flows/    bulk message connect schedule admins common
    handlers/ start accounts forwarding commands schedule admins logs text
tests/
```

## Deployment notes

Use `/health` for UptimeRobot and `/live` for a platform liveness check. Self-ping (`SELF_PING_INTERVAL`, default 600 s,
`0` = off) keeps a sleeping host awake. Firestore stores encrypted sessions, so the same `SESSION_ENCRYPTION_KEY` must be
present after restarts. Never commit `.env`, Firebase JSON files or session strings.
