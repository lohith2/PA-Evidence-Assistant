"""Shared utilities for agent nodes."""

import json
import structlog

log = structlog.get_logger()


def parse_llm_json(raw: str, fallback: dict) -> dict:
    """
    Safely parse JSON from an LLM response.

    Handles three common failure modes:
    1. Unterminated strings (truncated response due to max_tokens)
    2. Markdown code blocks wrapping the JSON
    3. Extra text before or after the JSON object
    """
    if not raw:
        return fallback

    # Strip markdown code blocks if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Drop opening fence (and optional "json" language tag) and closing fence
        inner = lines[1:-1] if len(lines) > 2 else lines[1:]
        if inner and inner[0].strip().lower() == "json":
            inner = inner[1:]
        text = "\n".join(inner)

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find the outermost JSON object within surrounding text
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        pass

    # Try to repair a truncated JSON object by stripping the incomplete tail
    # and closing the object. Works when the response was cut mid-string.
    try:
        trimmed = text.strip()

        # Walk backwards to find the last complete key-value pair.
        # Strategy: find the last comma at brace-depth 1 and close after it,
        # or fall back to closing after the last complete quoted value.
        depth = 0
        last_safe_pos = -1
        in_string = False
        escape_next = False

        for i, ch in enumerate(trimmed):
            if escape_next:
                escape_next = False
                continue
            if ch == "\\" and in_string:
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            elif ch == "," and depth == 1:
                last_safe_pos = i

        if last_safe_pos > 0:
            candidate = trimmed[:last_safe_pos] + "}"
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
    except Exception:
        pass

    log.warning("parse_llm_json.failed", raw_preview=raw[:200])
    return fallback
