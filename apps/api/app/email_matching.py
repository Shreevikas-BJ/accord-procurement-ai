"""Conservative supplier and RFQ matching for tenant-owned email intake."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from sqlalchemy import select

from .models import RFQ, Supplier, SupplierContact


GENERIC_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "yahoo.com",
    "icloud.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
}
LEGAL_SUFFIXES = {
    "llc",
    "llp",
    "lp",
    "inc",
    "incorporated",
    "ltd",
    "limited",
    "corp",
    "corporation",
    "plc",
    "gmbh",
}


def normalized_email(value: str | None) -> str:
    return (value or "").strip().casefold()


def normalized_supplier_name(value: str | None) -> str:
    tokens = re.findall(r"[a-z0-9]+", (value or "").casefold())
    if tokens[-3:] == ["l", "l", "c"]:
        tokens = tokens[:-3]
    elif tokens[-3:] == ["l", "l", "p"]:
        tokens = tokens[:-3]
    while tokens and tokens[-1] in LEGAL_SUFFIXES:
        tokens.pop()
    return "".join(tokens)


def domain_from_email(value: str | None) -> str:
    email = normalized_email(value)
    return email.rsplit("@", 1)[-1] if "@" in email else ""


def rfq_token(value: str) -> str | None:
    patterns = (
        r"\bRFQ\s*[-#:]?\s*(\d{3,12})\b",
        r"\bRequest\s+for\s+Quote\s*#?\s*(\d{3,12})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, value or "", re.I)
        if match:
            return f"RFQ-{match.group(1)}"
    return None


@dataclass
class SupplierMatch:
    supplier: Supplier | None = None
    method: str = "NO_MATCH"
    score: float = 0.0
    candidates: list[tuple[Supplier, float]] = field(default_factory=list)
    ambiguous: bool = False


def match_supplier_email(db, org: str, *, email: str, domain: str, name: str | None) -> SupplierMatch:
    email_key = normalized_email(email)
    contacts = db.scalars(select(SupplierContact).where(SupplierContact.organization_id == org)).all()
    exact_contact_ids = {
        contact.supplier_id
        for contact in contacts
        if normalized_email(contact.normalized_email or contact.email) == email_key and email_key
    }
    suppliers = db.scalars(select(Supplier).where(Supplier.organization_id == org)).all()
    by_id = {supplier.id: supplier for supplier in suppliers}
    exact_contacts = [by_id[supplier_id] for supplier_id in exact_contact_ids if supplier_id in by_id]
    if len(exact_contacts) == 1:
        return SupplierMatch(exact_contacts[0], "EXACT_CONTACT_EMAIL", 1.0)
    if len(exact_contacts) > 1:
        return SupplierMatch(method="AMBIGUOUS_CONTACT_EMAIL", ambiguous=True, candidates=[(s, 1.0) for s in exact_contacts])

    domain_key = (domain or domain_from_email(email)).casefold()
    if domain_key and domain_key not in GENERIC_DOMAINS:
        domain_matches = [s for s in suppliers if (s.email_domain or "").casefold() == domain_key]
        if len(domain_matches) == 1:
            return SupplierMatch(domain_matches[0], "EXACT_VERIFIED_DOMAIN", 0.99)
        if len(domain_matches) > 1:
            return SupplierMatch(method="AMBIGUOUS_DOMAIN", ambiguous=True, candidates=[(s, 0.99) for s in domain_matches])

    key = normalized_supplier_name(name)
    if key:
        alias_matches = [
            supplier
            for supplier in suppliers
            if key in {normalized_supplier_name(alias) for alias in supplier.aliases or []}
        ]
        if len(alias_matches) == 1:
            return SupplierMatch(alias_matches[0], "KNOWN_ALIAS", 0.98)
        name_matches = [
            supplier
            for supplier in suppliers
            if key == (supplier.normalized_name or normalized_supplier_name(supplier.name))
        ]
        if len(name_matches) == 1:
            return SupplierMatch(name_matches[0], "NORMALIZED_NAME", 0.97)
        fuzzy = sorted(
            [
                (
                    supplier,
                    max(
                        [SequenceMatcher(None, key, normalized_supplier_name(supplier.name)).ratio()]
                        + [SequenceMatcher(None, key, normalized_supplier_name(a)).ratio() for a in supplier.aliases or []]
                    ),
                )
                for supplier in suppliers
            ],
            key=lambda candidate: candidate[1],
            reverse=True,
        )
        candidates = [(supplier, score) for supplier, score in fuzzy[:3] if score >= 0.78]
        if candidates:
            return SupplierMatch(method="POSSIBLE_EXISTING_SUPPLIER", score=candidates[0][1], candidates=candidates)
    return SupplierMatch()


def supplier_name_from_identity(sender_name: str, signature: str, sender_domain: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip(" ,|-") for line in signature.splitlines() if line.strip()]
    company_words = re.compile(
        r"\b(?:supply|supplies|industrial|industries|manufacturing|component|components|controls|technical|systems|automation|engineering|company|co|corp|inc|incorporated|llc|ltd|gmbh)\b",
        re.I,
    )
    for line in reversed(lines):
        if 2 <= len(line) <= 200 and company_words.search(line) and "@" not in line and not re.search(r"\+?\d[\d ()-]{6}", line):
            return line
    if sender_name and company_words.search(sender_name):
        return sender_name.strip()
    if sender_domain and sender_domain not in GENERIC_DOMAINS:
        stem = sender_domain.split(".")[0].replace("-", " ")
        return stem.title()
    return sender_name.strip()


def match_rfq(db, org: str, *sources: str, explicit_id: str | None = None) -> tuple[RFQ | None, str]:
    if explicit_id:
        rfq = db.scalar(select(RFQ).where(RFQ.organization_id == org, RFQ.id == explicit_id))
        return (rfq, "EXPLICIT_RFQ") if rfq else (None, "UNMATCHED_RFQ")
    tokens = {token for source in sources if (token := rfq_token(source or ""))}
    if len(tokens) != 1:
        return None, "AMBIGUOUS_RFQ" if len(tokens) > 1 else "UNMATCHED_RFQ"
    rows = db.scalars(select(RFQ).where(RFQ.organization_id == org, RFQ.number == next(iter(tokens)))).all()
    return (rows[0], "EXACT_RFQ_NUMBER") if len(rows) == 1 else (None, "AMBIGUOUS_RFQ" if rows else "UNMATCHED_RFQ")
