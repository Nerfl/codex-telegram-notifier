#!/usr/bin/env python3
"""Send Telegram notifications from Codex hooks.

The script reads Codex hook JSON from stdin when Codex provides it. It is
deliberately dependency-free and keeps hook failures non-fatal by default.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


BOT_TOKEN_ENV = "CODEX_TG_BOT_TOKEN"
CHAT_ID_ENV = "CODEX_TG_CHAT_ID"
LANG_ENV = "CODEX_NOTIFY_LANG"

RATE_LIMIT_KEYS = {"rate_limits", "rateLimits", "limits", "limit_status"}
TOKEN_COUNT_KEYS = {"token_count", "tokenCount", "tokens"}

TEXT = {
    "en": {
        "context": "context",
        "daily": "Daily",
        "event": "Event",
        "hourly": "Hourly",
        "limit": "limit",
        "limit_left": "Limit left",
        "monthly": "Monthly",
        "permission": "permission required",
        "project": "Project",
        "reset_in_minutes": "in {minutes} min",
        "stop": "task completed",
        "test": "test notification",
        "time": "Time",
        "tool": "Tool",
        "weekly": "Weekly",
    },
    "ru": {
        "context": "контекст",
        "daily": "Ежедневно",
        "event": "Событие",
        "hourly": "Ежечасно",
        "limit": "лимит",
        "limit_left": "Остаток лимита",
        "monthly": "Ежемесячно",
        "permission": "требуется подтверждение",
        "project": "Проект",
        "reset_in_minutes": "через {minutes} мин",
        "stop": "задание выполнено",
        "test": "тестовое уведомление",
        "time": "Время",
        "tool": "Инструмент",
        "weekly": "Еженедельно",
    },
}

EVENT_ICONS = {
    "stop": "✅",
    "permission": "⚠️",
    "test": "🔔",
}


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            continue


def parse_args() -> argparse.Namespace:
    default_timeout = number(os.getenv("CODEX_TG_TIMEOUT")) or 10.0
    parser = argparse.ArgumentParser(
        description="Send a Telegram notification for a Codex hook event."
    )
    parser.add_argument(
        "--event",
        help="Event hint: stop, permission, or test. If omitted, inferred from stdin.",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Send a test notification without reading hook stdin.",
    )
    parser.add_argument(
        "--project",
        help="Override project name shown in the Telegram message.",
    )
    parser.add_argument(
        "--transcript",
        help="Path to a Codex transcript file to scan for token_count/rate_limits.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the notification text instead of calling Telegram.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return a non-zero exit code on missing env vars or send errors.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=default_timeout,
        help="Telegram API timeout in seconds. Default: 10.",
    )
    return parser.parse_args()


def choose_lang() -> str:
    return "ru" if os.getenv(LANG_ENV, "").strip().lower() == "ru" else "en"


def text(lang: str, key: str) -> str:
    return TEXT.get(lang, TEXT["en"]).get(key, TEXT["en"][key])


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def sanitize_line(value: Any, max_len: int = 120) -> str:
    text = str(value).strip().replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text


def basename_like(value: Any) -> str | None:
    text = sanitize_line(value)
    if not text:
        return None
    text = text.rstrip("\\/")
    parts = [part for part in re.split(r"[\\/]+", text) if part]
    return parts[-1] if parts else text


def read_stdin_json(skip: bool = False) -> dict[str, Any]:
    if skip:
        return {}

    try:
        if sys.stdin is None or sys.stdin.closed or sys.stdin.isatty():
            return {}
    except OSError:
        return {}

    raw = sys.stdin.read()
    if not raw.strip():
        return {}

    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {"payload": value}
    except json.JSONDecodeError:
        pass

    # Some tools emit JSONL. Keep the last parseable object as the payload.
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        return value if isinstance(value, dict) else {"payload": value}

    return {}


def deep_find(data: Any, wanted_keys: set[str]) -> Any | None:
    wanted_normalized = {normalize_key(key) for key in wanted_keys}
    if isinstance(data, dict):
        for key, value in data.items():
            if normalize_key(str(key)) in wanted_normalized:
                return value
        for value in data.values():
            found = deep_find(value, wanted_keys)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = deep_find(item, wanted_keys)
            if found is not None:
                return found
    return None


def deep_collect(data: Any, wanted_keys: set[str]) -> list[Any]:
    wanted_normalized = {normalize_key(key) for key in wanted_keys}
    found: list[Any] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if normalize_key(str(key)) in wanted_normalized:
                found.append(value)
            found.extend(deep_collect(value, wanted_keys))
    elif isinstance(data, list):
        for item in data:
            found.extend(deep_collect(item, wanted_keys))
    return found


def normalize_event(value: Any) -> str:
    text = normalize_key(str(value or ""))
    if text in {"test", "check"}:
        return "test"
    if text in {
        "permission",
        "permissionrequest",
        "approval",
        "approvalrequest",
        "confirm",
        "confirmation",
    }:
        return "permission"
    if text in {"stop", "done", "complete", "completed", "finish", "finished"}:
        return "stop"
    return "stop"


def choose_event(args: argparse.Namespace, payload: dict[str, Any]) -> str:
    if args.test:
        return "test"
    if args.event:
        return normalize_event(args.event)
    value = deep_find(
        payload,
        {
            "event",
            "event_name",
            "eventName",
            "hook_event_name",
            "hookEventName",
            "type",
        },
    )
    return normalize_event(value)


def choose_project(args: argparse.Namespace, payload: dict[str, Any]) -> str:
    if args.project:
        return sanitize_line(args.project, 80)

    env_name = os.getenv("CODEX_PROJECT_NAME")
    if env_name:
        return sanitize_line(env_name, 80)

    name = deep_find(
        payload,
        {"project_name", "projectName", "repo_name", "repoName", "workspace_name"},
    )
    if name:
        return sanitize_line(basename_like(name) or name, 80)

    path_value = deep_find(
        payload,
        {
            "cwd",
            "current_working_directory",
            "currentWorkingDirectory",
            "workspace",
            "workspace_path",
            "workspacePath",
            "project_path",
            "projectPath",
        },
    )
    if path_value:
        return sanitize_line(basename_like(path_value) or path_value, 80)

    return sanitize_line(Path.cwd().name or "unknown-project", 80)


def choose_transcript_path(args: argparse.Namespace, payload: dict[str, Any]) -> Path | None:
    value = args.transcript or deep_find(
        payload,
        {
            "transcript_path",
            "transcriptPath",
            "transcript",
            "conversation_path",
            "conversationPath",
        },
    )
    if not value or not isinstance(value, (str, os.PathLike)):
        return None
    return Path(os.path.expandvars(os.path.expanduser(str(value))))


def iter_json_values(path: Path) -> list[Any]:
    try:
        if not path.is_file():
            return []
        size = path.stat().st_size
    except OSError:
        return []

    values: list[Any] = []
    try:
        if size <= 8 * 1024 * 1024:
            text = path.read_text(encoding="utf-8", errors="replace")
            try:
                values.append(json.loads(text))
            except json.JSONDecodeError:
                pass
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    values.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return values

        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    values.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []

    return values


def number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace("%", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def pick_number(data: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    wanted = {normalize_key(key) for key in keys}
    for key, value in data.items():
        if normalize_key(str(key)) in wanted:
            parsed = number(value)
            if parsed is not None:
                return parsed
    return None


def format_percent(value: float) -> str:
    if 0 <= value <= 1:
        value *= 100
    value = max(0, min(100, value))
    return f"{value:.0f}" if value.is_integer() else f"{value:.1f}"


def translate_limit_label(value: Any, lang: str) -> str:
    label = sanitize_line(value, 40)
    normalized = normalize_key(label)

    match = re.search(r"(\d+)\s*(?:h|hr|hrs|hour|hours|час)", label, re.IGNORECASE)
    if match:
        suffix = "ч" if lang == "ru" else "h"
        return f"{match.group(1)}{suffix}"
    if normalized in {"5h", "5hr", "5hrs", "5hour", "5hours", "fivehour"}:
        return "5ч" if lang == "ru" else "5h"
    if "weekly" in normalized or normalized in {"week", "7d", "7day", "7days"}:
        return text(lang, "weekly")
    if "daily" in normalized or normalized in {"day", "24h", "24hour", "24hours"}:
        return text(lang, "daily")
    if "monthly" in normalized or normalized in {"month", "30d", "30day", "30days"}:
        return text(lang, "monthly")
    if "hourly" in normalized:
        return text(lang, "hourly")
    return label


def looks_like_limit_bucket(value: str | None) -> bool:
    if not value:
        return False
    normalized = normalize_key(value)
    return any(
        marker in normalized
        for marker in (
            "hour",
            "hr",
            "weekly",
            "week",
            "daily",
            "day",
            "monthly",
            "month",
            "limit",
            "quota",
            "percent",
        )
    ) or bool(re.fullmatch(r"\d+h", normalized))


def format_reset(value: Any, lang: str) -> str | None:
    if value is None:
        return None

    parsed = number(value)
    if parsed is not None:
        if parsed > 10_000_000_000:
            return datetime.fromtimestamp(parsed / 1000).strftime("%H:%M")
        if parsed > 1_000_000_000:
            return datetime.fromtimestamp(parsed).strftime("%H:%M")
        if parsed > 0:
            minutes = max(1, round(parsed / 60))
            return text(lang, "reset_in_minutes").format(minutes=minutes)

    text = sanitize_line(value, 40)
    if not text:
        return None
    if re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", text):
        return ":".join(text.split(":")[:2])

    try:
        iso_text = text.replace("Z", "+00:00")
        return datetime.fromisoformat(iso_text).astimezone().strftime("%H:%M")
    except ValueError:
        return text


def first_present(data: dict[str, Any], keys: tuple[str, ...]) -> Any | None:
    wanted = {normalize_key(key) for key in keys}
    for key, value in data.items():
        if normalize_key(str(key)) in wanted and value not in (None, ""):
            return value
    return None


def format_limit_item(
    value: Any, fallback_label: str | None = None, lang: str = "en"
) -> str | None:
    if isinstance(value, str):
        return sanitize_line(value, 180) or None

    if isinstance(value, (int, float)) and looks_like_limit_bucket(fallback_label):
        return f"{translate_limit_label(fallback_label, lang)} - {format_percent(float(value))}%"

    if isinstance(value, list):
        parts = [format_limit_item(item, lang=lang) for item in value]
        return ", ".join(part for part in parts if part) or None

    if not isinstance(value, dict):
        return None

    label = first_present(
        value,
        (
            "label",
            "name",
            "window",
            "bucket",
            "period",
            "scope",
            "description",
        ),
    )
    label_text = translate_limit_label(label or fallback_label or text(lang, "limit"), lang)

    percent = pick_number(
        value,
        (
            "remaining_percent",
            "remainingPercentage",
            "remaining_pct",
            "percent_remaining",
            "percentRemaining",
            "available_percent",
            "available_pct",
        ),
    )

    used_percent = pick_number(
        value,
        ("used_percent", "usedPercentage", "used_pct", "percent_used", "percentUsed"),
    )
    if percent is None and used_percent is not None:
        percent = 100 - used_percent

    remaining = pick_number(
        value,
        (
            "remaining",
            "remaining_tokens",
            "remainingTokens",
            "available",
            "available_tokens",
            "availableTokens",
        ),
    )
    total = pick_number(
        value,
        ("limit", "max", "maximum", "total", "quota", "token_limit", "tokenLimit"),
    )
    if percent is None and remaining is not None and total and total > 0:
        percent = remaining / total * 100

    reset_value = first_present(
        value,
        (
            "reset_at",
            "resetAt",
            "resets_at",
            "resetsAt",
            "reset_time",
            "resetTime",
            "next_reset",
            "nextReset",
            "retry_after",
            "retryAfter",
            "reset_after",
            "resetAfter",
        ),
    )
    reset = format_reset(reset_value, lang)

    if percent is not None:
        result = f"{label_text} - {format_percent(percent)}%"
        if reset:
            result += f" {reset}"
        return result

    summary = first_present(value, ("summary", "message", "text"))
    if summary:
        return sanitize_line(summary, 180)

    nested_parts: list[str] = []
    for key, nested_value in value.items():
        if normalize_key(str(key)) in {normalize_key(k) for k in RATE_LIMIT_KEYS}:
            nested = format_limit_item(nested_value, lang=lang)
        else:
            nested = format_limit_item(nested_value, str(key), lang=lang)
        if nested:
            nested_parts.append(nested)
    return ", ".join(nested_parts) or None


def format_token_count(value: Any, lang: str) -> str | None:
    if isinstance(value, list):
        parts = [format_token_count(item, lang) for item in value]
        return ", ".join(part for part in parts if part) or None

    if not isinstance(value, dict):
        return None

    direct = format_limit_item(value, text(lang, "context"), lang)
    if direct and "%" in direct:
        return direct

    remaining = pick_number(
        value,
        ("remaining_tokens", "remainingTokens", "remaining", "available_tokens"),
    )
    total = pick_number(
        value,
        (
            "context_window",
            "contextWindow",
            "token_limit",
            "tokenLimit",
            "limit",
            "max_tokens",
            "maxTokens",
            "total",
        ),
    )
    used = pick_number(
        value,
        (
            "total_token_count",
            "totalTokenCount",
            "used_tokens",
            "usedTokens",
            "input_tokens",
            "inputTokens",
        ),
    )

    if remaining is not None and total and total > 0:
        return f"{text(lang, 'context')} - {format_percent(remaining / total * 100)}%"
    if used is not None and total and total > 0:
        return f"{text(lang, 'context')} - {format_percent(100 - used / total * 100)}%"
    return None


def extract_limit_summary(
    payload: dict[str, Any], transcript_path: Path | None, lang: str
) -> str | None:
    rate_candidates = deep_collect(payload, RATE_LIMIT_KEYS)
    token_candidates = deep_collect(payload, TOKEN_COUNT_KEYS)

    if transcript_path:
        for value in iter_json_values(transcript_path):
            rate_candidates.extend(deep_collect(value, RATE_LIMIT_KEYS))
            token_candidates.extend(deep_collect(value, TOKEN_COUNT_KEYS))

    for candidate in reversed(rate_candidates):
        formatted = format_limit_item(candidate, lang=lang)
        if formatted:
            return formatted

    for candidate in reversed(token_candidates):
        formatted = format_token_count(candidate, lang)
        if formatted:
            return formatted

    return None


def pick_tool_name(payload: dict[str, Any]) -> str | None:
    value = deep_find(
        payload,
        {
            "tool_name",
            "toolName",
            "tool",
            "matcher",
            "tool_input_name",
            "toolInputName",
        },
    )
    if not value:
        return None
    text = sanitize_line(value, 60)
    return text if text and text not in {"*", "None"} else None


def build_message(
    event: str,
    project: str,
    limit_summary: str | None,
    payload: dict[str, Any],
    lang: str,
) -> str:
    normalized_event = event if event in EVENT_ICONS else "stop"
    event_label = text(lang, normalized_event)
    title = f"{EVENT_ICONS[normalized_event]} Codex: {event_label}"
    lines = [
        title,
        "",
        f"{text(lang, 'time')}: {datetime.now().strftime('%H:%M:%S')}",
        f"{text(lang, 'event')}: {event_label}",
        f"{text(lang, 'project')}: {project}",
    ]

    if event == "permission":
        tool_name = pick_tool_name(payload)
        if tool_name:
            lines.append(f"{text(lang, 'tool')}: {tool_name}")

    if limit_summary:
        lines.append(f"{text(lang, 'limit_left')}: {limit_summary}")

    return "\n".join(lines)


def send_telegram(token: str, chat_id: str, text: str, timeout: float) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
    try:
        result = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Telegram returned non-JSON response: {body[:160]}") from exc
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {result}")


def redact_secrets(text: str) -> str:
    token = os.getenv(BOT_TOKEN_ENV)
    chat_id = os.getenv(CHAT_ID_ENV)
    if token:
        text = text.replace(token, "<redacted-token>")
    if chat_id:
        text = text.replace(chat_id, "<redacted-chat-id>")
    return text


def main() -> int:
    configure_stdio()
    args = parse_args()
    payload = read_stdin_json(skip=args.test)

    lang = choose_lang()
    event = choose_event(args, payload)
    project = choose_project(args, payload)
    transcript_path = choose_transcript_path(args, payload)
    limit_summary = extract_limit_summary(payload, transcript_path, lang)
    message = build_message(event, project, limit_summary, payload, lang)

    if args.dry_run:
        print(message)
        return 0

    token = os.getenv(BOT_TOKEN_ENV)
    chat_id = os.getenv(CHAT_ID_ENV)
    if not token or not chat_id:
        eprint(
            f"{BOT_TOKEN_ENV} and {CHAT_ID_ENV} must be set to send Telegram notifications."
        )
        return 2 if args.strict else 0

    try:
        send_telegram(token, chat_id, message, args.timeout)
    except (urllib.error.URLError, TimeoutError, RuntimeError, OSError) as exc:
        eprint(redact_secrets(f"Failed to send Telegram notification: {exc}"))
        return 1 if args.strict else 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
