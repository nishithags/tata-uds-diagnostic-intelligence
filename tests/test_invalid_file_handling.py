"""
Unit tests for invalid file handling and safety validations.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.
"""

import pytest
from src.core.ingestion import DocumentIngestionEngine, IngestionError


@pytest.fixture
def engine():
    return DocumentIngestionEngine(max_size_mb=2)


def test_reject_empty_filename(engine):
    with pytest.raises(IngestionError, match="Filename cannot be empty"):
        engine.validate_file("", b"some content")


def test_reject_unsupported_extension(engine):
    with pytest.raises(IngestionError, match="Unsupported file type"):
        engine.validate_file("diagnostic_tool.exe", b"executable payload")


def test_reject_empty_file(engine):
    with pytest.raises(IngestionError, match="empty"):
        engine.validate_file("empty_spec.pdf", b"")


def test_reject_oversized_file(engine):
    # 2 MB limit configured
    oversized = b"X" * (3 * 1024 * 1024)
    with pytest.raises(IngestionError, match="exceeds maximum permitted limit"):
        engine.validate_file("giant_spec.pdf", oversized)


def test_reject_fake_pdf_header(engine):
    fake_pdf = b"NOT_A_REAL_PDF_HEADER_JUST_TEXT"
    with pytest.raises(IngestionError, match="Expected valid PDF header"):
        engine.validate_file("corrupt.pdf", fake_pdf)
