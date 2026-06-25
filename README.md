Русская версия: [README.ru.md](README.ru.md)

# codex-telegram-notifier

A small public-safe utility for Codex Desktop and Codex CLI. It sends Telegram notifications from Codex hooks.

It can notify you when:

- Codex finishes a task through the `Stop` hook event;
- Codex waits for approval or permission through the `PermissionRequest` hook event;
- a notification should include the current project name;
- Codex provides limit data in `transcript_path` through `token_count` or `rate_limits`.

The project is safe to publish publicly: the Telegram bot token and `chat_id` are read only from environment variables.

## Files

- `scripts/codex_tg_notify.py` - the main dependency-free Python script.
- `examples/hooks.json` - an example Codex hooks configuration.
- `.gitignore` - excludes local env files, caches, and logs.

## Security

Never publish your Telegram bot token. A bot token allows other people to control that bot.

Treat `chat_id` as private information too. It identifies where the bot sends messages.

Do not use a production Telegram bot from another project for personal Codex notifications. Create a separate bot just for this utility.

Do not store tokens in `hooks.json`, README files, commits, screenshots, logs, or GitHub issues. Use only the `CODEX_TG_BOT_TOKEN` and `CODEX_TG_CHAT_ID` environment variables.

## Installation

### 1. Create a Telegram bot with BotFather

1. Open Telegram.
2. Find `@BotFather`.
3. Send `/newbot`.
4. Follow BotFather's instructions.
5. Save the token BotFather gives you.

Do not paste the token into project files.

### 2. Get your `chat_id`

1. Open a chat with your new bot.
2. Send any message, for example `/start`.
3. Open this URL in a browser:

```text
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
```

4. Find the `chat.id` field in the response:

```json
"chat": {
  "id": 123456789
}
```

The `id` value is your `CODEX_TG_CHAT_ID`.

For a group chat, add the bot to the group, send a new message in the group, and call `getUpdates` again. Group `chat_id` values are usually negative.

### 3. Save environment variables

Windows PowerShell, current window only:

```powershell
$env:CODEX_TG_BOT_TOKEN = "your_bot_token_here"
$env:CODEX_TG_CHAT_ID = "your_chat_id_here"
```

Windows PowerShell, permanently for the current user:

```powershell
[Environment]::SetEnvironmentVariable("CODEX_TG_BOT_TOKEN", "your_bot_token_here", "User")
[Environment]::SetEnvironmentVariable("CODEX_TG_CHAT_ID", "your_chat_id_here", "User")
```

macOS/Linux, current terminal only:

```bash
export CODEX_TG_BOT_TOKEN="your_bot_token_here"
export CODEX_TG_CHAT_ID="your_chat_id_here"
```

For Codex Desktop on Windows, permanent user environment variables are usually the most convenient option. Restart Codex after setting them.

### 4. Copy the script to `~/.codex/codex_tg_notify.py`

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex"
Copy-Item .\scripts\codex_tg_notify.py "$env:USERPROFILE\.codex\codex_tg_notify.py"
```

macOS/Linux:

```bash
mkdir -p ~/.codex
cp scripts/codex_tg_notify.py ~/.codex/codex_tg_notify.py
chmod +x ~/.codex/codex_tg_notify.py
```

### 5. Add hooks to `~/.codex/hooks.json`

If you do not have hooks yet, copy the example:

Windows PowerShell:

```powershell
Copy-Item .\examples\hooks.json "$env:USERPROFILE\.codex\hooks.json"
```

macOS/Linux:

```bash
cp examples/hooks.json ~/.codex/hooks.json
```

If `hooks.json` already exists, do not overwrite it blindly. Copy only the `Stop` and `PermissionRequest` blocks from `examples/hooks.json` into your existing file.

On Windows, the example uses:

```text
py -3 "%USERPROFILE%\.codex\codex_tg_notify.py"
```

If Python Launcher `py` is not installed, replace `py -3` with `python`.

### 6. Restart Codex

Restart Codex Desktop or start a new Codex CLI session so Codex can reload `hooks.json` and the new environment variables.

### 7. Trust the hooks

Codex requires you to review and trust new or changed command hooks.

- In Codex Desktop, open the hooks review screen if the app asks you to.
- In Codex CLI, run `/hooks`, review the new hooks, and mark them as trusted.

If you change the hook command or script path later, Codex may ask you to trust the hook again.

### 8. Send a test notification

Windows PowerShell:

```powershell
py -3 "$env:USERPROFILE\.codex\codex_tg_notify.py" --test --strict
```

macOS/Linux:

```bash
python3 ~/.codex/codex_tg_notify.py --test --strict
```

To test the message text without sending anything to Telegram:

```bash
python3 scripts/codex_tg_notify.py --test --dry-run
```

## Example Notification

The script currently uses Russian notification labels by default:

```text
✅ Codex: задание выполнено

Время: 20:14:35
Событие: задание выполнено
Проект: my-project
Остаток лимита: 5ч - 18% 18:08, Еженедельно - 5%
```

If Codex does not provide limit data, the `Остаток лимита` line is omitted.

## How It Works

Codex runs a command hook and, when available, passes the hook event JSON through stdin. The script:

1. reads the hook payload from stdin;
2. detects the event: `Stop`, `PermissionRequest`, or test;
3. detects the project name from the payload, `CODEX_PROJECT_NAME`, or the current directory;
4. reads `transcript_path`, if provided, and searches for `rate_limits` or `token_count`;
5. sends a short text message to Telegram.

By default, Telegram send errors do not break Codex. For manual checks, use `--strict` to return a non-zero exit code on errors.

## Troubleshooting

### `getUpdates` returns `result: []`

Send a message to the bot first, for example `/start`, and then call `getUpdates` again.

Make sure you are using the token for the same bot. For a group chat, make sure the bot is added to the group and that a new group message was sent after the bot was added.

If the bot already received older updates, Telegram may have marked them as read. Send a new message and retry the request.

### PowerShell hangs because of stdin

For manual checks, use `--test`. It does not read hook stdin:

```powershell
py -3 "$env:USERPROFILE\.codex\codex_tg_notify.py" --test --dry-run
```

To manually simulate a hook event, pipe an empty JSON object:

```powershell
'{}' | py -3 "$env:USERPROFILE\.codex\codex_tg_notify.py" --event stop --dry-run
```

### Codex does not send notifications, but the manual test works

Check that:

- the file is located at `~/.codex/hooks.json`;
- the JSON is valid, with no comments or trailing commas;
- hooks are enabled in Codex;
- the hook is trusted in Codex Desktop or through `/hooks` in CLI;
- after changing the hook, you trusted the new version again;
- Codex was restarted after you added environment variables;
- on Windows, the `commandWindows` command works when run manually;
- if you use Codex Desktop, the environment variables are permanent user variables, not variables set only in one PowerShell window.

### `hooks.json` is not read because of extra fields

The file must be strict JSON. Do not add comments, trailing commas, or arbitrary top-level fields.

Minimal valid shape:

```json
{
  "hooks": {
    "Stop": []
  }
}
```

Compare your file with `examples/hooks.json`.

### Limits are not shown

The limit line is shown only when Codex provides `transcript_path` and the transcript contains recognizable `rate_limits` or `token_count` fields.

If Codex does not provide `transcript_path`, the transcript is unavailable, or there is no `token_count`, the script sends the notification without limit data.

## Development

Syntax and JSON checks:

```bash
python -m py_compile scripts/codex_tg_notify.py
python -m json.tool examples/hooks.json
```

Dry-run:

```bash
python scripts/codex_tg_notify.py --test --dry-run
```

Simulate a permission request:

```bash
echo "{\"tool_name\":\"Bash\"}" | python scripts/codex_tg_notify.py --event permission --dry-run
```

## First Commit And GitHub Publishing

With GitHub CLI:

```bash
git init
git add README.md README.ru.md .gitignore scripts/codex_tg_notify.py examples/hooks.json
git commit -m "Initial codex telegram notifier"
gh repo create codex-telegram-notifier --public --source=. --remote=origin --push
```

Without GitHub CLI:

```bash
git init
git add README.md README.ru.md .gitignore scripts/codex_tg_notify.py examples/hooks.json
git commit -m "Initial codex telegram notifier"
git branch -M main
git remote add origin https://github.com/<your-github-username>/codex-telegram-notifier.git
git push -u origin main
```
