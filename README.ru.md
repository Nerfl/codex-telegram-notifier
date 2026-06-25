English version: [README.md](README.md)

# codex-telegram-notifier

Мини-утилита для Codex Desktop и Codex CLI: отправляет уведомления в Telegram через Codex hooks.

Что умеет:

- уведомлять, когда Codex завершил задачу через событие `Stop`;
- уведомлять, когда Codex ждёт подтверждение или разрешение через `PermissionRequest`;
- показывать название проекта;
- показывать остаток лимитов, если Codex передал `transcript_path`, а в transcript есть `token_count` или `rate_limits`.
- отправлять уведомления на английском по умолчанию или на русском при `CODEX_NOTIFY_LANG=ru`.

Проект безопасен для публичной публикации: токен бота и `chat_id` читаются только из переменных окружения.

## Файлы

- `scripts/codex_tg_notify.py` - основной скрипт без внешних зависимостей.
- `examples/hooks.json` - пример конфигурации hooks для Codex.
- `.gitignore` - исключает локальные env-файлы, кеши и логи.

## Безопасность

Не публикуйте Telegram bot token. Он даёт доступ к управлению ботом.

`chat_id` тоже лучше считать приватной информацией: по нему можно понять, куда бот отправляет сообщения.

Не используйте рабочие Telegram-боты проектов для личных уведомлений Codex. Создайте отдельного бота только для этой утилиты.

Не храните токены в `hooks.json`, README, коммитах, скриншотах, логах или issue на GitHub. Используйте только переменные окружения `CODEX_TG_BOT_TOKEN` и `CODEX_TG_CHAT_ID`.

## Локализация

По умолчанию уведомления отправляются на английском языке.

Чтобы включить русские подписи в уведомлениях, задайте:

```bash
CODEX_NOTIFY_LANG=ru
```

Windows PowerShell, постоянно для текущего пользователя:

```powershell
[Environment]::SetEnvironmentVariable("CODEX_NOTIFY_LANG", "ru", "User")
```

macOS/Linux:

```bash
export CODEX_NOTIFY_LANG=ru
```

## Установка

### 1. Создайте Telegram-бота через BotFather

1. Откройте Telegram.
2. Найдите `@BotFather`.
3. Отправьте команду `/newbot`.
4. Следуйте инструкциям BotFather.
5. Сохраните token, который BotFather выдаст в конце.

Не вставляйте token в файлы проекта.

### 2. Получите `chat_id`

1. Откройте чат с новым ботом.
2. Отправьте ему любое сообщение, например `/start`.
3. Откройте в браузере:

```text
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
```

4. Найдите в ответе поле:

```json
"chat": {
  "id": 123456789
}
```

Значение `id` и есть `CODEX_TG_CHAT_ID`.

Для группового чата добавьте бота в группу, отправьте сообщение в группу и снова вызовите `getUpdates`. У групп обычно отрицательный `chat_id`.

### 3. Сохраните переменные окружения

Windows PowerShell, только для текущего окна:

```powershell
$env:CODEX_TG_BOT_TOKEN = "your_bot_token_here"
$env:CODEX_TG_CHAT_ID = "your_chat_id_here"
```

Windows PowerShell, постоянно для текущего пользователя:

```powershell
[Environment]::SetEnvironmentVariable("CODEX_TG_BOT_TOKEN", "your_bot_token_here", "User")
[Environment]::SetEnvironmentVariable("CODEX_TG_CHAT_ID", "your_chat_id_here", "User")
```

Чтобы уведомления были на русском:

```powershell
[Environment]::SetEnvironmentVariable("CODEX_NOTIFY_LANG", "ru", "User")
```

macOS/Linux, только для текущего терминала:

```bash
export CODEX_TG_BOT_TOKEN="your_bot_token_here"
export CODEX_TG_CHAT_ID="your_chat_id_here"
```

Чтобы уведомления были на русском:

```bash
export CODEX_NOTIFY_LANG=ru
```

Для Codex Desktop на Windows обычно удобнее использовать постоянные переменные окружения и затем перезапустить Codex.

### 4. Скопируйте скрипт в `~/.codex/codex_tg_notify.py`

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

### 5. Добавьте hooks в `~/.codex/hooks.json`

Если hooks ещё нет, можно скопировать пример:

Windows PowerShell:

```powershell
Copy-Item .\examples\hooks.json "$env:USERPROFILE\.codex\hooks.json"
```

macOS/Linux:

```bash
cp examples/hooks.json ~/.codex/hooks.json
```

Если `hooks.json` уже существует, не заменяйте его вслепую. Аккуратно перенесите блоки `Stop` и `PermissionRequest` из `examples/hooks.json` в существующий файл.

На Windows пример использует:

```text
py -3 "%USERPROFILE%\.codex\codex_tg_notify.py"
```

Если у вас нет Python Launcher `py`, замените `py -3` на `python`.

### 6. Перезапустите Codex

Перезапустите Codex Desktop или откройте новую сессию Codex CLI, чтобы Codex перечитал `hooks.json` и новые переменные окружения.

### 7. Доверьте hooks

Codex требует доверять новым или изменённым command hooks.

- В Codex Desktop откройте экран проверки hooks, если приложение попросит это сделать.
- В Codex CLI выполните `/hooks`, просмотрите новые hooks и отметьте их как trusted.

Если вы измените команду hook или путь к скрипту, Codex может снова попросить доверить hook.

### 8. Проверьте тестовое уведомление

Windows PowerShell:

```powershell
py -3 "$env:USERPROFILE\.codex\codex_tg_notify.py" --test --strict
```

macOS/Linux:

```bash
python3 ~/.codex/codex_tg_notify.py --test --strict
```

Без отправки в Telegram можно проверить текст сообщения:

```bash
python3 scripts/codex_tg_notify.py --test --dry-run
```

## Пример уведомления

Для такого русскоязычного вывода нужно задать `CODEX_NOTIFY_LANG=ru`.

```text
✅ Codex: задание выполнено

Время: 20:14:35
Событие: задание выполнено
Проект: my-project
Остаток лимита: 5ч - 18% 18:08, Еженедельно - 5%
```

Если Codex не передал данные о лимитах, строка `Остаток лимита` не показывается.

## Как это работает

Codex запускает command hook и передаёт JSON-событие в stdin, когда это доступно. Скрипт:

1. читает hook payload из stdin;
2. определяет событие: `Stop`, `PermissionRequest` или тест;
3. определяет имя проекта из payload, переменной `CODEX_PROJECT_NAME` или текущей папки;
4. если есть `transcript_path`, читает transcript и ищет `rate_limits` или `token_count`;
5. отправляет короткое текстовое сообщение в Telegram.

Ошибки отправки не ломают работу Codex по умолчанию. Для ручной проверки используйте `--strict`, чтобы получить ненулевой код выхода при ошибке.

## Troubleshooting

### `getUpdates` возвращает `result: []`

Сначала отправьте сообщение боту в Telegram, например `/start`, и повторите запрос `getUpdates`.

Проверьте, что используете token именно этого бота. Для группы убедитесь, что бот добавлен в группу и в группе было новое сообщение после добавления бота.

Если бот уже получал старые updates, Telegram мог их отметить как прочитанные. Отправьте новое сообщение и повторите запрос.

### PowerShell зависает из-за stdin

Для ручной проверки используйте `--test`, он не читает hook stdin:

```powershell
py -3 "$env:USERPROFILE\.codex\codex_tg_notify.py" --test --dry-run
```

Если хотите вручную имитировать hook-событие, передайте пустой JSON через pipe:

```powershell
'{}' | py -3 "$env:USERPROFILE\.codex\codex_tg_notify.py" --event stop --dry-run
```

### Codex не отправляет уведомление, но ручной тест работает

Проверьте:

- файл лежит в `~/.codex/hooks.json`;
- JSON валидный, без комментариев и лишних запятых;
- hooks включены в Codex;
- hook доверен в Codex Desktop или через `/hooks` в CLI;
- после изменения hook вы снова доверили новую версию;
- Codex был перезапущен после добавления переменных окружения;
- на Windows команда `commandWindows` запускается вручную;
- если используется Desktop, переменные окружения заданы постоянно для пользователя, а не только в одном окне PowerShell.

### `hooks.json` не читается из-за лишних полей

Файл должен быть строгим JSON. Не добавляйте комментарии, trailing commas или произвольные верхнеуровневые поля.

Минимальная форма:

```json
{
  "hooks": {
    "Stop": []
  }
}
```

Сравните свой файл с `examples/hooks.json`.

### Лимиты не отображаются

Строка `Остаток лимита` появляется только если Codex передал `transcript_path`, а в transcript есть понятные поля `rate_limits` или `token_count`.

Если Codex не передал `transcript_path`, transcript недоступен, или в нём нет `token_count`, скрипт просто отправит уведомление без лимитов.

## Разработка

Проверка синтаксиса:

```bash
python -m py_compile scripts/codex_tg_notify.py
python -m json.tool examples/hooks.json
```

Dry-run:

```bash
python scripts/codex_tg_notify.py --test --dry-run
```

Имитация permission request:

```bash
echo "{\"tool_name\":\"Bash\"}" | python scripts/codex_tg_notify.py --event permission --dry-run
```

## Первый коммит и публикация на GitHub

Через GitHub CLI:

```bash
git init
git add README.md README.ru.md .gitignore scripts/codex_tg_notify.py examples/hooks.json
git commit -m "Initial codex telegram notifier"
gh repo create codex-telegram-notifier --public --source=. --remote=origin --push
```

Без GitHub CLI:

```bash
git init
git add README.md README.ru.md .gitignore scripts/codex_tg_notify.py examples/hooks.json
git commit -m "Initial codex telegram notifier"
git branch -M main
git remote add origin https://github.com/<your-github-username>/codex-telegram-notifier.git
git push -u origin main
```
