from __future__ import annotations

import base64
import re
from collections.abc import Iterable

from shawei.config.constants import DECODE_B64_RE, DOCUMENT_WRITELN_RE, PAGE_DATA_RE, STRDECODE_RE
from shawei.domain.text import normalize_text


def detect_html_charset(raw: bytes) -> str | None:
    head = raw[:4096]
    match = re.search(br"charset\s*=\s*['\"]?\s*([a-zA-Z0-9_\-]+)", head, re.I)
    if not match:
        return None
    return match.group(1).decode("ascii", errors="ignore").lower() or None


def _decode_b64(value: str) -> str | None:
    try:
        stripped = value.strip()
        padded = stripped + ("=" * (-len(stripped) % 4))
        return base64.b64decode(padded, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


def _decoded_matches(pattern: re.Pattern[str], text: str) -> list[str]:
    decoded: list[str] = []
    for match in pattern.finditer(text):
        value = _decode_b64(match.group(2))
        if value:
            decoded.append(value)
    return decoded


def decode_strdecode_blocks(text: str) -> list[str]:
    return _decoded_matches(STRDECODE_RE, text)


def decode_embedded_base64_blocks(text: str) -> list[str]:
    return _decoded_matches(DECODE_B64_RE, text) + _decoded_matches(PAGE_DATA_RE, text)


def collect_decoded_documents(blocks: Iterable[str]) -> list[str]:
    docs = [block for block in blocks if block]
    if docs:
        docs.append("\n".join(docs))
    return docs


def strip_html_tags(text: str) -> str:
    return normalize_text(re.sub(r"<[^>]+>", " ", text or ""))


def decode_document_writeln_html(script: str) -> str:
    parts: list[str] = []
    for match in DOCUMENT_WRITELN_RE.finditer(script):
        value = match.group(2)
        value = re.sub(r"\\(['\"\\])", r"\1", value)
        value = value.replace(r"\r", "\r").replace(r"\n", "\n").replace(r"\t", "\t")
        parts.append(value)
    return "\n".join(parts)
