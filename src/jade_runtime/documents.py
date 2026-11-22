"""DEV-032: private 24-hour document artifacts and verified per-turn permissions.

No generated file is executed. The model writes UTF-8 content via a bounded
tool; the server renders a file and returns an opaque attachment reference.
"""
from __future__ import annotations

import asyncio
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import re
import secrets
import time
from urllib.parse import quote
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from .memory_store import identity_of

TTL_SECONDS = 24 * 60 * 60
MAX_TEXT = 180_000
MAX_BYTES = 8 * 1024 * 1024
ID_RE = re.compile(r"[a-f0-9]{32}\Z")
NAME_RE = re.compile(r"[A-Za-z0-9À-ÿ _().-]{1,100}\.[A-Za-z0-9]{1,12}\Z")
MIMES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".zip": "application/zip",
    ".txt": "text/plain", ".md": "text/markdown", ".csv": "text/csv",
    ".html": "text/html", ".htm": "text/html", ".py": "text/x-python",
    ".js": "text/javascript", ".ts": "text/plain", ".css": "text/css",
    ".json": "application/json", ".xml": "application/xml",
}


DOCUMENT_TOOL = {
    "type": "function", "function": {
        "name": "jade_create_document",
        "description": (
            "Créer réellement UNE pièce jointe téléchargeable, UNIQUEMENT "
            "sur demande explicite de l'interlocuteur autorisé. Contenu intégral "
            "UTF-8 du fichier, pas une URL ni une description. Formats PDF/DOCX/TXT/"
            "CSV/XLSX/HTML/PY/JS/CSS/JSON et autres extensions de texte. "
            "Pour .xlsx, content est du CSV ; pour .zip, un objet JSON "
            "chemin relatif → contenu texte de chaque fichier du projet. "
            "Ne jamais créer de fichier spontanément. Ne présume pas du succès."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Nom et extension du fichier"},
                "content": {"type": "string", "description": "Contenu entier ; JSON de fichiers pour ZIP"},
            },
            "required": ["filename", "content"],
            "additionalProperties": False,
        },
    },
}

DOCUMENT_PROMPT = (
    "\n\nDocuments DEV-032 : lorsqu'une personne te DEMANDE explicitement de "
    "fabriquer un fichier, utilise jade_create_document si cet outil est disponible. "
    "S'il n'est pas disponible, refuse brièvement : la création est réservée "
    "aux comptes autorisés. Ne prétends jamais avoir joint un fichier sans "
    "confirmation de l'outil. Le fichier sera livré automatiquement comme pièce "
    "jointe dans le canal d'origine : ne prononce ni n'imprime de lien URL. "
    "Respecte strictement toute extension demandée. Par défaut, choisis PDF "
    "pour une lecture, DOCX pour un document éditable, CSV/XLSX pour un tableau, "
    "et HTML si on demande du code ou un site sans langage spécifié ; .py "
    "pour Python, etc. Pour plusieurs fichiers d'un site, crée un ZIP dont "
    "content est le JSON des fichiers relatifs (index.html, style.css...). "
    "En Discord public ou vocal, n'inclus aucune information privée provenant "
    "d'autres canaux ou personnes dans le fichier, sauf publication explicitement "
    "autorisée par le propriétaire. Évite tout envoi spontané."
)


@dataclass(frozen=True)
class Attachment:
    id: str
    name: str
    mime: str
    size: int
    expires_at: float

    def public(self) -> dict:
        return {"id": self.id, "name": self.name, "size": self.size,
                "expires_at": datetime.fromtimestamp(
                    self.expires_at, timezone.utc).isoformat(),
                "url": "/api/documents/" + self.id}


def _docx(content: str) -> bytes:
    paragraphs = "".join(
        "<w:p><w:r><w:t xml:space=\"preserve\">" + escape(line)
        + "</w:t></w:r></w:p>"
        for line in content.splitlines() or [""]
    )
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body>' + paragraphs + '<w:sectPr/></w:body></w:document>')
    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>')
        archive.writestr("_rels/.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>')
        archive.writestr("word/document.xml", document)
    return out.getvalue()


def _xlsx(content: str) -> bytes:
    rows = csv.reader(StringIO(content))
    xml_rows = []
    for i, row in enumerate(rows, 1):
        if i > 5000 or len(row) > 100:
            raise ValueError("tableau trop grand")
        cells = "".join(
            '<c t="inlineStr"><is><t xml:space="preserve">'
            + escape(value) + '</t></is></c>'
            for value in row
        )
        xml_rows.append(f'<row r="{i}">{cells}</row>')
    sheet = ('<?xml version="1.0" encoding="UTF-8"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             '<sheetData>' + "".join(xml_rows) + '</sheetData></worksheet>')
    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>')
        archive.writestr("_rels/.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>')
        archive.writestr("xl/workbook.xml",
            '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Feuille1" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return out.getvalue()


def _pdf(content: str) -> bytes:
    # Portable stdlib fallback: readable, multi-page, Latin-1 text-only PDF.
    # DOCX preserves full Unicode and is preferable for non-Latin documents.
    lines = []
    for line in content.splitlines() or [""]:
        while len(line) > 94:
            lines.append(line[:94])
            line = line[94:]
        lines.append(line)
    pages = [lines[i:i + 49] for i in range(0, len(lines), 49)] or [[]]
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>", b"", 
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    kids = []
    for page in pages:
        page_id = len(objects) + 1
        kids.append(f"{page_id} 0 R")
        instructions = [b"BT /F1 11 Tf 48 790 Td 14 TL"]
        for line in page:
            safe = line.encode("latin-1", "replace").replace(b"\\", b"\\\\")
            safe = safe.replace(b"(", b"\\(").replace(b")", b"\\)")
            instructions.append(b"(" + safe + b") Tj T*")
        instructions.append(b"ET")
        stream = b"\n".join(instructions) + b"\n"
        objects.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                        f"/Resources << /Font << /F1 3 0 R >> >> "
                        f"/Contents {page_id + 1} 0 R >>").encode("ascii"))
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode()
                       + stream + b"endstream")
    objects[1] = (f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>").encode()
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, data in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + data + b"\nendobj\n"
    start = len(out)
    out += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
            f"startxref\n{start}\n%%EOF\n").encode()
    return bytes(out)


def _zip_site(content: str) -> bytes:
    files = json.loads(content)
    if not isinstance(files, dict) or not 1 <= len(files) <= 20:
        raise ValueError("ZIP : objet JSON de 1 à 20 fichiers attendu")
    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as archive:
        for name, source in files.items():
            parts = name.split("/") if isinstance(name, str) else ()
            if (not 1 <= len(parts) <= 5 or any(
                    part in ("", ".", "..") or part.startswith(".") or
                    not re.fullmatch(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*", part)
                    for part in parts) or not isinstance(source, str)
                    or len(source) > MAX_TEXT):
                raise ValueError("chemin ou contenu ZIP interdit")
            archive.writestr(name, source.encode("utf-8"))
    return out.getvalue()


def _render(name: str, content: str) -> bytes:
    suffix = Path(name).suffix.lower()
    if suffix == ".pdf":
        return _pdf(content)
    if suffix == ".docx":
        return _docx(content)
    if suffix == ".xlsx":
        return _xlsx(content)
    if suffix == ".zip":
        return _zip_site(content)
    return content.encode("utf-8")


class DocumentStore:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory).expanduser()
        if not self.directory.is_absolute() or self.directory.is_symlink():
            raise ValueError("document directory must be absolute and private")
        self.directory.mkdir(parents=True, exist_ok=True)

    def _metadata(self, document_id: str) -> Path:
        if not ID_RE.fullmatch(document_id):
            raise ValueError("invalid document id")
        return self.directory / (document_id + ".json")

    def _load(self, document_id: str) -> dict | None:
        try:
            return json.loads(self._metadata(document_id).read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError):
            return None

    def _write_metadata(self, data: dict) -> None:
        path = self._metadata(data["id"])
        temp = self.directory / (data["id"] + ".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(temp, path)

    def prune(self, now: float | None = None) -> None:
        now = time.time() if now is None else now
        for metadata in self.directory.glob("*.json"):
            data = self._load(metadata.stem)
            if not data:
                continue
            if data.get("expires_at", 0) <= now:
                (self.directory / (metadata.stem + ".bin")).unlink(missing_ok=True)
                if not data.get("discord") or now > data["expires_at"] + 7 * TTL_SECONDS:
                    metadata.unlink(missing_ok=True)

    def create(self, filename: str, content: str) -> Attachment:
        if (not isinstance(filename, str) or not NAME_RE.fullmatch(filename)
                or filename in (".", "..") or not isinstance(content, str)
                or not content or len(content) > MAX_TEXT
                or any(ord(char) < 32 for char in filename)):
            raise ValueError("nom, format ou contenu de document invalide")
        data = _render(filename, content)
        if not data or len(data) > MAX_BYTES:
            raise ValueError("document trop volumineux")
        self.prune()
        key = secrets.token_hex(16)
        expiry = time.time() + TTL_SECONDS
        (self.directory / (key + ".bin")).write_bytes(data)
        meta = {"id": key, "name": filename, "mime": MIMES.get(
                Path(filename).suffix.lower(), "text/plain"),
                "size": len(data), "expires_at": expiry, "discord": []}
        self._write_metadata(meta)
        return Attachment(key, filename, meta["mime"], len(data), expiry)

    def read(self, document_id: str) -> tuple[Attachment, bytes] | None:
        data = self._load(document_id)
        if not data or data.get("expires_at", 0) <= time.time():
            self.prune()
            return None
        try:
            payload = (self.directory / (document_id + ".bin")).read_bytes()
            attachment = Attachment(data["id"], data["name"], data["mime"],
                                    data["size"], data["expires_at"])
            return (attachment, payload) if len(payload) == attachment.size else None
        except (OSError, KeyError, ValueError):
            return None

    def path(self, attachment: Attachment) -> Path:
        if self.read(attachment.id) is None:
            raise FileNotFoundError("document expired")
        return self.directory / (attachment.id + ".bin")

    def mark_discord(self, attachments: tuple[Attachment, ...],
                     channel_id: str, message_id: int) -> None:
        for attachment in attachments:
            data = self._load(attachment.id)
            if data and data["expires_at"] > time.time():
                data.setdefault("discord", []).append({
                    "channel": str(channel_id), "message": int(message_id)})
                self._write_metadata(data)

    def expired_discord(self) -> list[tuple[str, str, int]]:
        self.prune()
        results = []
        for path in self.directory.glob("*.json"):
            data = self._load(path.stem)
            if data and data.get("expires_at", 0) <= time.time():
                for item in data.get("discord", []):
                    results.append((data["id"], item["channel"], item["message"]))
        return results

    def ack_discord(self, document_id: str, channel: str, message: int) -> None:
        data = self._load(document_id)
        if data:
            data["discord"] = [x for x in data.get("discord", [])
                               if (x["channel"], x["message"]) != (channel, message)]
            if not data["discord"] and data["expires_at"] <= time.time():
                self._metadata(document_id).unlink(missing_ok=True)
            else:
                self._write_metadata(data)


class DocumentAction:
    def __init__(self, store: DocumentStore, allowed: bool):
        self.store = store
        self.allowed = allowed
        self.attachments: list[Attachment] = []

    async def create_document(self, raw: str) -> dict:
        if not self.allowed:
            return {"status": "refusé", "reason": "not_authorized"}
        if len(self.attachments) >= 4 or len(raw) > MAX_TEXT + 4000:
            return {"status": "refusé", "reason": "limit_reached"}
        try:
            args = json.loads(raw)
            if not isinstance(args, dict) or set(args) != {"filename", "content"}:
                raise ValueError("invalid fields")
            artifact = await asyncio.to_thread(
                self.store.create, args["filename"], args["content"])
        except (ValueError, TypeError, OSError):
            return {"status": "erreur", "reason": "invalid_or_unavailable"}
        self.attachments.append(artifact)
        return {"status": "created", "filename": artifact.name,
                "expires_in_seconds": TTL_SECONDS}


class DocumentService:
    def __init__(self, directory: str | Path, *, memory_store=None,
                 access_mode: str = "owner", allowed_discord_ids=()):
        if access_mode not in ("owner", "allowlist", "all"):
            raise ValueError("invalid document access mode")
        self.store = DocumentStore(directory)
        self.memory_store = memory_store
        self.access_mode = access_mode
        self.allowed_discord_ids = frozenset(str(x) for x in allowed_discord_ids)
        self._cleaner: asyncio.Task | None = None

    async def start(self):
        await asyncio.to_thread(self.store.prune)

        async def clean():
            while True:
                await asyncio.sleep(60)
                await asyncio.to_thread(self.store.prune)

        self._cleaner = asyncio.create_task(clean(), name="jade-document-retention")

    async def close(self):
        if self._cleaner:
            self._cleaner.cancel()
            await asyncio.gather(self._cleaner, return_exceptions=True)

    async def for_turn(self, incoming) -> DocumentAction:
        key = identity_of(incoming)
        eligible = incoming.platform in ("mobile", "discord", "discord_voice")
        owner = bool(eligible and incoming.platform == "mobile")
        if (eligible and not owner and key and self.memory_store is not None):
            try:
                owner = await asyncio.to_thread(self.memory_store.is_goldaj, key)
            except (ValueError, OSError):
                owner = False
        permitted = owner
        if eligible and key and self.access_mode == "all":
            permitted = True
        if (eligible and key and self.access_mode == "allowlist"
                and key[0] == "discord" and key[1] in self.allowed_discord_ids):
            permitted = True
        return DocumentAction(self.store, permitted)
