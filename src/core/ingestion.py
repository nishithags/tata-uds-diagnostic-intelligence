"""
Document Ingestion and Parsing Module for Phase 1 Knowledge Pilot.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Extracts text, preserves page and source metadata, calculates cryptographic SHA-256 hash
for provenance, extracts structured tables where practical, and rejects invalid files safely.
"""

import hashlib
import io
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import pypdf

from src.core.config import config


class ExtractedTable(BaseModel):
    """Structured representation of a parsed diagnostic parameter table."""
    page_number: int
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)
    raw_text: str = ""


class PageContent(BaseModel):
    """Extracted text and structural content from a single document page."""
    page_number: int
    text: str
    detected_sections: List[str] = Field(default_factory=list)
    tables: List[ExtractedTable] = Field(default_factory=list)


class IngestedDocument(BaseModel):
    """Complete document extraction payload with metadata and provenance."""
    doc_id: str
    project_id: str
    filename: str
    file_type: str
    file_size_bytes: int
    file_hash_sha256: str
    total_pages: int
    pages: List[PageContent]
    ingested_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    authorization_status: str = "AUTHORIZED_FOR_PILOT"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IngestionError(Exception):
    """Custom exception raised when document ingestion fails validation."""
    pass


class DocumentIngestionEngine:
    """
    Ingestion engine implementing reference-aligned parsing (pypdf/text extraction).
    Validates file integrity, calculates SHA-256 provenance hash, extracts text by page,
    and extracts diagnostic tables where practical.
    """

    def __init__(self, allowed_extensions: Optional[List[str]] = None, max_size_mb: Optional[int] = None):
        self.allowed_extensions = allowed_extensions or config.allowed_extensions
        self.max_size_bytes = (max_size_mb or config.max_file_size_mb) * 1024 * 1024

    def compute_sha256(self, file_bytes: bytes) -> str:
        """Calculates cryptographic SHA-256 hash for document traceability."""
        return hashlib.sha256(file_bytes).hexdigest()

    def validate_file(self, filename: str, file_bytes: bytes) -> None:
        """
        Safely validates file extension, non-empty payload, and size thresholds.
        Rejects unsupported or corrupt files safely.
        """
        if not filename or not filename.strip():
            raise IngestionError("Filename cannot be empty.")

        ext = Path(filename).suffix.lower()
        if ext not in self.allowed_extensions:
            raise IngestionError(
                f"Unsupported file type '{ext}'. Allowed extensions are: {', '.join(self.allowed_extensions)}"
            )

        if not file_bytes or len(file_bytes) == 0:
            raise IngestionError("The uploaded file is empty (0 bytes).")

        if len(file_bytes) > self.max_size_bytes:
            raise IngestionError(
                f"File size exceeds maximum permitted limit ({self.max_size_bytes / (1024 * 1024):.1f} MB)."
            )

        # PDF header signature check
        if ext == ".pdf" and not file_bytes.startswith(b"%PDF-"):
            raise IngestionError("Invalid file content: Expected valid PDF header signature '%PDF-'.")

    def _extract_sections_from_text(self, text: str) -> List[str]:
        """Detects section headings in diagnostic specifications (e.g., '1. Scope', '9.2 Service 0x22')."""
        section_pattern = re.compile(
            r"^\s*(?:[0-9]{1,2}(?:\.[0-9]{1,2})*\.?\s+[A-Z][A-Za-z0-9 \t\-_/]+|(?:Section|Clause)\s+[^\n\r]+)",
            re.MULTILINE
        )
        return [match.group(0).strip() for match in section_pattern.finditer(text)]

    def _extract_tables_from_text(self, text: str, page_number: int) -> List[ExtractedTable]:
        """
        Extracts structured tables where practical from ASCII/pipe/tab formatted text.
        Recognizes diagnostic matrices, DID lists, and NRC tables.
        """
        tables: List[ExtractedTable] = []
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        
        table_buffer: List[str] = []
        in_table = False

        for line in lines:
            # Check for pipe-separated table or multi-column spacing
            if "|" in line or "\t" in line or re.search(r"\s{3,}", line):
                in_table = True
                table_buffer.append(line)
            else:
                if in_table and len(table_buffer) >= 2:
                    parsed_table = self._parse_table_block(table_buffer, page_number)
                    if parsed_table:
                        tables.append(parsed_table)
                table_buffer = []
                in_table = False

        if in_table and len(table_buffer) >= 2:
            parsed_table = self._parse_table_block(table_buffer, page_number)
            if parsed_table:
                tables.append(parsed_table)

        return tables

    def _parse_table_block(self, lines: List[str], page_number: int) -> Optional[ExtractedTable]:
        """Parses a candidate table block into headers and rows."""
        rows: List[List[str]] = []
        for line in lines:
            if "|" in line:
                cells = [c.strip() for c in line.split("|") if c.strip()]
            elif "\t" in line:
                cells = [c.strip() for c in line.split("\t") if c.strip()]
            else:
                cells = [c.strip() for c in re.split(r"\s{3,}", line) if c.strip()]
            
            # Skip separator lines like |---|---|
            if cells and not all(set(c).issubset({"-", "=", "+", ":"}) for c in cells):
                rows.append(cells)

        if len(rows) >= 2:
            headers = rows[0]
            data_rows = rows[1:]
            return ExtractedTable(
                page_number=page_number,
                headers=headers,
                rows=data_rows,
                raw_text="\n".join(lines)
            )
        return None

    def ingest_pdf(self, file_bytes: bytes, filename: str, project_id: str, metadata: Optional[Dict[str, Any]] = None) -> IngestedDocument:
        """
        Parses a PDF file using pypdf, extracting text and tables page-by-page while preserving metadata.
        """
        self.validate_file(filename, file_bytes)
        file_hash = self.compute_sha256(file_bytes)
        doc_id = f"doc_{file_hash[:16]}"
        
        pages: List[PageContent] = []
        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            total_pages = len(reader.pages)
            if total_pages == 0:
                raise IngestionError("PDF contains no pages.")

            for page_idx, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text() or ""
                sections = self._extract_sections_from_text(page_text)
                tables = self._extract_tables_from_text(page_text, page_idx)

                pages.append(
                    PageContent(
                        page_number=page_idx,
                        text=page_text,
                        detected_sections=sections,
                        tables=tables
                    )
                )
        except IngestionError:
            raise
        except Exception as e:
            raise IngestionError(f"Failed to parse PDF document '{filename}': {str(e)}") from e

        return IngestedDocument(
            doc_id=doc_id,
            project_id=project_id,
            filename=filename,
            file_type="PDF",
            file_size_bytes=len(file_bytes),
            file_hash_sha256=file_hash,
            total_pages=total_pages,
            pages=pages,
            ingested_at=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {}
        )

    def ingest_text(self, text: str, filename: str, project_id: str, metadata: Optional[Dict[str, Any]] = None) -> IngestedDocument:
        """
        Ingests plain text or markdown diagnostic specification sheets safely.
        """
        file_bytes = text.encode("utf-8")
        self.validate_file(filename, file_bytes)
        file_hash = self.compute_sha256(file_bytes)
        doc_id = f"doc_{file_hash[:16]}"

        sections = self._extract_sections_from_text(text)
        tables = self._extract_tables_from_text(text, 1)

        pages = [
            PageContent(
                page_number=1,
                text=text,
                detected_sections=sections,
                tables=tables
            )
        ]

        return IngestedDocument(
            doc_id=doc_id,
            project_id=project_id,
            filename=filename,
            file_type="TEXT/MD",
            file_size_bytes=len(file_bytes),
            file_hash_sha256=file_hash,
            total_pages=1,
            pages=pages,
            ingested_at=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {}
        )
