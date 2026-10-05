"""
Context-Aware Knowledge Chunking Module for Phase 1 Knowledge Pilot.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Splits extracted document content into context-aware chunks while strictly preserving
document name, page number, section title, and provenance metadata.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from src.core.config import config
from src.core.ingestion import IngestedDocument, PageContent


class DocumentChunk(BaseModel):
    """
    Traceable document chunk containing content, section metadata,
    and source provenance pointers.
    """
    chunk_id: str
    doc_id: str
    project_id: str
    document_name: str
    page_number: int
    section_title: str
    content: str
    char_count: int
    source_hash_sha256: str
    metadata: dict = Field(default_factory=dict)


class ContextAwareChunker:
    """
    Context-aware chunking engine designed for technical and diagnostic specifications.
    Respects paragraph and section boundaries, preventing fragmented diagnostic tables
    and rules while attaching rich metadata to every chunk.
    """

    def __init__(self, chunk_size_chars: Optional[int] = None, overlap_chars: Optional[int] = None):
        self.chunk_size = chunk_size_chars or config.chunk_size_chars
        self.overlap = overlap_chars or config.chunk_overlap_chars

    def chunk_document(self, doc: IngestedDocument) -> List[DocumentChunk]:
        """
        Chunks an ingested document page-by-page, tracking active section headers
        and generating uniquely identifiable, traceable chunks.
        """
        all_chunks: List[DocumentChunk] = []
        chunk_counter = 0

        current_section = "General / Introduction"

        for page in doc.pages:
            page_text = page.text.strip()
            if not page_text:
                continue

            # Update active section if new section detected on page
            if page.detected_sections:
                current_section = page.detected_sections[0]

            # Split page text into natural paragraphs/blocks
            paragraphs = [p.strip() for p in page_text.split("\n\n") if p.strip()]
            
            # If page text has few paragraph splits, split by line breaks or sentences
            if not paragraphs:
                paragraphs = [page_text]

            current_chunk_text = ""
            for p in paragraphs:
                # Check if paragraph begins with a new section header
                for sec in page.detected_sections:
                    if p.startswith(sec):
                        current_section = sec
                        break

                if len(current_chunk_text) + len(p) + 2 <= self.chunk_size:
                    if current_chunk_text:
                        current_chunk_text += "\n\n" + p
                    else:
                        current_chunk_text = p
                else:
                    if current_chunk_text:
                        chunk_counter += 1
                        chunk_id = f"{doc.doc_id}_p{page.page_number}_c{chunk_counter:03d}"
                        all_chunks.append(
                            DocumentChunk(
                                chunk_id=chunk_id,
                                doc_id=doc.doc_id,
                                project_id=doc.project_id,
                                document_name=doc.filename,
                                page_number=page.page_number,
                                section_title=current_section,
                                content=current_chunk_text.strip(),
                                char_count=len(current_chunk_text.strip()),
                                source_hash_sha256=doc.file_hash_sha256,
                                metadata={
                                    "total_pages": doc.total_pages,
                                    "file_type": doc.file_type,
                                    "ingested_at": doc.ingested_at
                                }
                            )
                        )
                        # Overlap: keep trailing characters if practical
                        if self.overlap > 0 and len(current_chunk_text) > self.overlap:
                            overlap_text = current_chunk_text[-self.overlap:].strip()
                            current_chunk_text = overlap_text + "\n\n" + p
                        else:
                            current_chunk_text = p
                    else:
                        # Single paragraph exceeds chunk size, split into sub-chunks
                        p_start = 0
                        step = self.chunk_size - self.overlap if self.chunk_size > self.overlap else self.chunk_size
                        while p_start < len(p):
                            p_sub = p[p_start:p_start + self.chunk_size]
                            if p_sub.strip():
                                chunk_counter += 1
                                chunk_id = f"{doc.doc_id}_p{page.page_number}_c{chunk_counter:03d}"
                                all_chunks.append(
                                    DocumentChunk(
                                        chunk_id=chunk_id,
                                        doc_id=doc.doc_id,
                                        project_id=doc.project_id,
                                        document_name=doc.filename,
                                        page_number=page.page_number,
                                        section_title=current_section,
                                        content=p_sub.strip(),
                                        char_count=len(p_sub.strip()),
                                        source_hash_sha256=doc.file_hash_sha256,
                                        metadata={
                                            "total_pages": doc.total_pages,
                                            "file_type": doc.file_type,
                                            "ingested_at": doc.ingested_at
                                        }
                                    )
                                )
                            p_start += step
                        current_chunk_text = ""

            # Flush remaining buffer for this page
            if current_chunk_text.strip():
                chunk_counter += 1
                chunk_id = f"{doc.doc_id}_p{page.page_number}_c{chunk_counter:03d}"
                all_chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        doc_id=doc.doc_id,
                        project_id=doc.project_id,
                        document_name=doc.filename,
                        page_number=page.page_number,
                        section_title=current_section,
                        content=current_chunk_text.strip(),
                        char_count=len(current_chunk_text.strip()),
                        source_hash_sha256=doc.file_hash_sha256,
                        metadata={
                            "total_pages": doc.total_pages,
                            "file_type": doc.file_type,
                            "ingested_at": doc.ingested_at
                        }
                    )
                )

        return all_chunks
