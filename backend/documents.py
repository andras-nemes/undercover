"""The policy wording and the claims manual, read one numbered section at a time."""

import re
import sqlite3

from fastapi import HTTPException

from backend import claims, rules
from backend.db import DATA
from backend.models import DocumentName, Section

FILES = {"wording": "policy_wording.md", "manual": "claims_manual.md"}
HEADING = re.compile(r"^## (\d+)\. (.+)$", re.MULTILINE)


def split(document: str) -> dict[int, tuple[str, str]]:
    """The sections of a document as {number: (title, text)}, or a 404."""
    if document not in FILES:
        raise claims.not_found("Document", document)
    text = (DATA / FILES[document]).read_text(encoding="utf-8")
    headings = list(HEADING.finditer(text))
    ends = [h.start() for h in headings[1:]] + [len(text)]
    return {
        int(h.group(1)): (h.group(2), text[h.start() : end].strip())
        for h, end in zip(headings, ends, strict=True)
    }


def list_sections(document: str) -> list[Section]:
    """The numbers and titles of a document's sections."""
    return [Section(number=n, title=t) for n, (t, _) in split(document).items()]


def read_section(
    db: sqlite3.Connection, claim_id: str, document: DocumentName, number: int
) -> str:
    """The text of one section, noted as read on the claim."""
    rules.get_status(db, claim_id)
    sections = split(document)
    if number not in sections:
        raise HTTPException(
            status_code=404, detail=f"Section {number} not found in the {document}"
        )
    title, text = sections[number]
    with db:
        db.execute(
            "INSERT OR IGNORE INTO reads (claim_id, document, section, title)"
            " VALUES (?, ?, ?, ?)",
            (claim_id, document, number, title),
        )
    return text
