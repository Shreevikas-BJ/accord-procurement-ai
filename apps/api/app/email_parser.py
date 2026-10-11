"""Bounded, local parsing for RFC 5322 messages and pasted supplier email text."""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser


MAX_EMAIL_BYTES = 20 * 1024 * 1024
MAX_BODY_CHARS = 500_000
MAX_ATTACHMENTS = 50


@dataclass
class ParsedAttachment:
    filename: str
    content_type: str
    content: bytes


@dataclass
class ParsedEmail:
    sender_name: str = ""
    sender_email: str = ""
    recipients: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    subject: str = ""
    normalized_subject: str = ""
    sent_at: datetime | None = None
    message_id: str | None = None
    in_reply_to: str | None = None
    references: list[str] = field(default_factory=list)
    body_text: str = ""
    body_html: str = ""
    normalized_body: str = ""
    quoted_history: str = ""
    signature: str = ""
    html_tables: list[list[list[str]]] = field(default_factory=list)
    attachments: list[ParsedAttachment] = field(default_factory=list)
    content_hash: str = ""

    @property
    def sender_domain(self) -> str:
        return self.sender_email.rsplit("@", 1)[-1].casefold() if "@" in self.sender_email else ""


class _HTMLBodyParser(HTMLParser):
    BLOCKS = {"p", "div", "br", "li", "tr", "table", "h1", "h2", "h3", "blockquote"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._ignored = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.casefold()
        if tag in {"script", "style", "head"}:
            self._ignored += 1
            return
        if self._ignored:
            return
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []
        if tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.casefold()
        if tag in {"script", "style", "head"}:
            self._ignored = max(0, self._ignored - 1)
            return
        if self._ignored:
            return
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(_space("".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if any(self._row):
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            if self._table:
                self.tables.append(self._table)
            self._table = None
        if tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._ignored:
            return
        self.parts.append(data)
        if self._cell is not None:
            self._cell.append(data)


def _space(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def html_content(value: str) -> tuple[str, list[list[list[str]]]]:
    parser = _HTMLBodyParser()
    parser.feed(value[:MAX_BODY_CHARS])
    text = "\n".join(line.strip() for line in "".join(parser.parts).splitlines() if line.strip())
    return text[:MAX_BODY_CHARS], parser.tables


def normalize_subject(value: str) -> str:
    subject = _space(value)
    previous = None
    while subject != previous:
        previous = subject
        subject = re.sub(r"^(?:re|fw|fwd)\s*:\s*", "", subject, flags=re.I).strip()
    return subject


def normalize_message_id(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"<[^<>\s]+>", value)
    return (match.group(0) if match else _space(value))[:998] or None


def _addresses(values) -> tuple[str, str, list[str]]:
    pairs = getaddresses([str(v) for v in values if v])
    cleaned = [(name.strip(), address.strip().casefold()) for name, address in pairs if "@" in address]
    first = cleaned[0] if cleaned else ("", "")
    return first[0], first[1], [address for _, address in cleaned]


def _date(value) -> datetime | None:
    if not value:
        return None
    try:
        result = parsedate_to_datetime(str(value))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def separate_quoted_history(value: str) -> tuple[str, str]:
    lines = value.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    cut = len(lines)
    patterns = (
        r"^\s*On .{3,200}wrote:\s*$",
        r"^\s*-{2,}\s*Original Message\s*-{2,}\s*$",
        r"^\s*From:\s+.+@.+$",
        r"^\s*_{5,}\s*$",
    )
    for index, line in enumerate(lines):
        if line.lstrip().startswith(">") or any(re.match(pattern, line, re.I) for pattern in patterns):
            cut = index
            break
    current = "\n".join(lines[:cut]).strip()
    history = "\n".join(lines[cut:]).strip()
    return current[:MAX_BODY_CHARS], history[:MAX_BODY_CHARS]


def separate_signature(value: str) -> tuple[str, str]:
    lines = value.splitlines()
    for index, line in enumerate(lines):
        if index >= 1 and re.match(r"^\s*(?:--\s*|regards[,!]?|best(?: regards)?[,!]?|sincerely[,!]?|thanks[,!]?)\s*$", line, re.I):
            return "\n".join(lines[:index]).strip(), "\n".join(lines[index:]).strip()
    return value.strip(), ""


def classify_email(subject: str, body: str) -> str:
    value = f"{subject}\n{body}".casefold()
    if re.search(r"\b(revised|updated|correction|supersedes|disregard previous|final quotation)\b", value):
        return "QUOTE_REVISION"
    if re.search(r"\b(can you|could you|best we can|reduce|lower price|negotia)", value):
        return "NEGOTIATION"
    if re.search(r"\b(quote|quotation|unit price|pricing)\b", value):
        return "QUOTE"
    if re.search(r"\b(request for quote|rfq response)\b", value):
        return "RFQ_RESPONSE"
    if re.search(r"\b(order confirmation|confirmed order)\b", value):
        return "ORDER_CONFIRMATION"
    return "INFORMATIONAL" if body.strip() else "UNKNOWN"


def _finish(parsed: ParsedEmail) -> ParsedEmail:
    html_text, parsed.html_tables = html_content(parsed.body_html) if parsed.body_html else ("", [])
    visible = parsed.body_text.strip() or html_text
    current, parsed.quoted_history = separate_quoted_history(visible)
    current, parsed.signature = separate_signature(current)
    parsed.normalized_body = "\n".join(line.rstrip() for line in current.splitlines() if line.strip())[:MAX_BODY_CHARS]
    parsed.body_text = visible[:MAX_BODY_CHARS]
    parsed.body_html = parsed.body_html[:MAX_BODY_CHARS]
    parsed.normalized_subject = normalize_subject(parsed.subject)
    identity = "\n".join(
        [parsed.sender_email, parsed.subject, parsed.sent_at.isoformat() if parsed.sent_at else "", parsed.body_text]
    ).encode("utf-8", "replace")
    parsed.content_hash = hashlib.sha256(identity).hexdigest()
    return parsed


def parse_eml(content: bytes) -> ParsedEmail:
    if not content or len(content) > MAX_EMAIL_BYTES:
        raise ValueError("Email must be nonempty and no larger than 20 MB.")
    message = BytesParser(policy=policy.default).parsebytes(content)
    sender_name, sender_email, _ = _addresses(message.get_all("from", []))
    _, _, recipients = _addresses(message.get_all("to", []))
    _, _, cc = _addresses(message.get_all("cc", []))
    parsed = ParsedEmail(
        sender_name=sender_name,
        sender_email=sender_email,
        recipients=recipients,
        cc=cc,
        subject=str(message.get("subject", ""))[:998],
        sent_at=_date(message.get("date")),
        message_id=normalize_message_id(message.get("message-id")),
        in_reply_to=normalize_message_id(message.get("in-reply-to")),
        references=[
            normalized
            for value in re.findall(r"<[^<>]+>", str(message.get("references", "")))
            if (normalized := normalize_message_id(value))
        ][:100],
    )
    text_parts: list[str] = []
    html_parts: list[str] = []
    for part in message.walk():
        if part.is_multipart():
            continue
        filename = part.get_filename()
        disposition = part.get_content_disposition()
        if filename or disposition == "attachment":
            if len(parsed.attachments) >= MAX_ATTACHMENTS:
                continue
            payload = part.get_payload(decode=True) or b""
            parsed.attachments.append(
                ParsedAttachment(filename=(filename or "attachment")[:200], content_type=part.get_content_type(), content=payload)
            )
            continue
        try:
            body = part.get_content()
        except (LookupError, UnicodeDecodeError):
            body = (part.get_payload(decode=True) or b"").decode("utf-8", "replace")
        if part.get_content_type() == "text/plain":
            text_parts.append(str(body))
        elif part.get_content_type() == "text/html":
            html_parts.append(str(body))
    parsed.body_text = "\n".join(text_parts)
    parsed.body_html = "\n".join(html_parts)
    return _finish(parsed)


def parse_pasted(
    *,
    raw_email: str | None = None,
    sender: str | None = None,
    recipients: list[str] | None = None,
    cc: list[str] | None = None,
    subject: str | None = None,
    sent_at: datetime | None = None,
    message_id: str | None = None,
    in_reply_to: str | None = None,
    references: list[str] | None = None,
    body_text: str | None = None,
    body_html: str | None = None,
) -> ParsedEmail:
    if raw_email:
        header_block = raw_email.split("\n\n", 1)[0]
        if re.search(r"^(?:From|To|Subject|Date|Message-ID):", header_block, re.I | re.M):
            return parse_eml(raw_email.encode("utf-8"))
        body_text = raw_email
    sender_name, sender_email, _ = _addresses([sender or ""])
    _, _, to_addresses = _addresses(recipients or [])
    _, _, cc_addresses = _addresses(cc or [])
    parsed = ParsedEmail(
        sender_name=sender_name,
        sender_email=sender_email,
        recipients=to_addresses,
        cc=cc_addresses,
        subject=(subject or "")[:998],
        sent_at=sent_at.astimezone(timezone.utc) if sent_at and sent_at.tzinfo else sent_at,
        message_id=normalize_message_id(message_id),
        in_reply_to=normalize_message_id(in_reply_to),
        references=[v for v in (normalize_message_id(v) for v in references or []) if v],
        body_text=body_text or "",
        body_html=body_html or "",
    )
    return _finish(parsed)
