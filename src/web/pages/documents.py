"""
Documents Page for UDS Diagnostic Intelligence Platform.
Provides document library management, specification ingestion, and index status monitoring.
"""

from pathlib import Path
import streamlit as st
from src.core.activity_store import ActivityAction, activity_store
from src.core.chunking import ContextAwareChunker
from src.core.ingestion import DocumentIngestionEngine, IngestionError
from src.core.vector_store import IsolatedVectorStore
from src.core.workspace_manager import workspace_manager


def render_documents_page(active_ws):
    """Renders the Documents management workspace."""
    ingestion_engine = DocumentIngestionEngine()
    chunker = ContextAwareChunker()
    vector_store = IsolatedVectorStore()

    st.markdown("### 📄 Diagnostic Specifications & Document Library")
    st.caption(
        f"Manage authorized diagnostic specifications for workspace **`{active_ws.name}`** (`{active_ws.project_id}`). "
        "Specifications are cryptographically hashed (SHA-256), chunked with boundary awareness, and indexed into isolated collections."
    )

    # 1. Index Status Cards
    st.markdown("##### 📊 Vector Index & Isolation Status")
    docs = workspace_manager.get_documents_for_project(active_ws.project_id)
    total_docs = len(docs)
    total_chunks = vector_store.count_chunks(active_ws.project_id)

    s_col1, s_col2, s_col3, s_col4 = st.columns(4)
    s_col1.metric("Indexed Documents", total_docs)
    s_col2.metric("Total Context Chunks", total_chunks)
    s_col3.metric("Vector Collection", f"col_{active_ws.project_id}")
    s_col4.metric("Workspace Isolation", "STRICT (Zero Leakage)")

    st.markdown("---")

    # 2. Document Library Table
    st.markdown("##### 📚 Document Library")
    if not docs:
        st.info("No diagnostic documents have been indexed for this workspace yet. Upload an authorized specification below.")
    else:
        doc_rows = []
        for d in docs:
            doc_rows.append({
                "Document Name": d["filename"],
                "Classification": d.get("metadata", {}).get("doc_type", d.get("file_type", "UNKNOWN")),
                "File Size": f"{d['file_size_bytes'] / 1024:.1f} KB",
                "Pages": d["total_pages"],
                "Chunks": d["total_chunks"],
                "Status": "✅ INDEXED",
                "Ingested At": d["ingested_at"][:19].replace("T", " ")
            })
        st.dataframe(doc_rows, use_container_width=True)

        with st.expander("🔎 Cryptographic Hash & Provenance Inspector"):
            for d in docs:
                st.markdown(f"**{d['filename']}** (`{d['doc_id']}`)")
                c1, c2 = st.columns([1, 3])
                c1.caption("SHA-256 Checksum:")
                c2.code(d["file_hash_sha256"], language="text")

    st.markdown("---")

    # 3. Upload Specification
    st.markdown("##### 📤 Upload Authorized Diagnostic Specification")
    st.caption("Supported formats: PDF (via PyPDF parser), TXT, MD. Binary files and unrecognized formats are rejected with strict validation.")

    up_col1, up_col2 = st.columns([2, 1])
    with up_col1:
        uploaded_file = st.file_uploader(
            "Select Diagnostic Specification File",
            type=["pdf", "txt", "md"],
            help="Upload an authorized ISO standard, OEM diagnostic specification, or ECU parameter table."
        )
    with up_col2:
        doc_type = st.selectbox(
            "Document Classification",
            ["STANDARD_SPEC", "OEM_SPEC", "ECU_EXTRACT", "REQUIREMENTS"],
            help="Metadata taxonomy tag used for isolated retrieval."
        )

    if uploaded_file is not None:
        file_bytes = uploaded_file.read()
        file_size_kb = len(file_bytes) / 1024
        st.caption(f"Selected file: **`{uploaded_file.name}`** ({file_size_kb:.1f} KB)")

        if st.button("🚀 Ingest & Build Vector Index", type="primary"):
            with st.spinner("Extracting text, computing SHA-256 provenance hash, and indexing context chunks..."):
                try:
                    filename = uploaded_file.name
                    ext = Path(filename).suffix.lower()

                    if ext == ".pdf":
                        ingested_doc = ingestion_engine.ingest_pdf(
                            file_bytes=file_bytes,
                            filename=filename,
                            project_id=active_ws.project_id,
                            metadata={"doc_type": doc_type}
                        )
                    else:
                        text_content = file_bytes.decode("utf-8", errors="replace")
                        ingested_doc = ingestion_engine.ingest_text(
                            text=text_content,
                            filename=filename,
                            project_id=active_ws.project_id,
                            metadata={"doc_type": doc_type}
                        )

                    chunks = chunker.chunk_document(ingested_doc)
                    vector_store.add_chunks(project_id=active_ws.project_id, chunks=chunks)

                    doc_record = {
                        "doc_id": ingested_doc.doc_id,
                        "project_id": active_ws.project_id,
                        "filename": ingested_doc.filename,
                        "file_type": ingested_doc.file_type,
                        "file_size_bytes": ingested_doc.file_size_bytes,
                        "file_hash_sha256": ingested_doc.file_hash_sha256,
                        "total_pages": ingested_doc.total_pages,
                        "total_chunks": len(chunks),
                        "ingested_at": ingested_doc.ingested_at,
                        "authorization_status": ingested_doc.authorization_status,
                        "metadata": {"doc_type": doc_type}
                    }
                    workspace_manager.record_document(project_id=active_ws.project_id, doc_metadata=doc_record)

                    activity_store.log_activity(
                        session_id=st.session_state.session_id,
                        user_id=st.session_state.user_id,
                        project_id=active_ws.project_id,
                        action=ActivityAction.DOCUMENT_UPLOAD,
                        endpoint="UI",
                        http_method="UI",
                        status="SUCCESS",
                        metadata={
                            "filename": filename,
                            "doc_type": doc_type,
                            "chunks_count": len(chunks)
                        }
                    )

                    st.success(
                        f"Document '{filename}' successfully ingested! Extracted {ingested_doc.total_pages} page(s) and {len(chunks)} chunks."
                    )
                    st.rerun()

                except IngestionError as e:
                    activity_store.log_activity(
                        session_id=st.session_state.session_id,
                        user_id=st.session_state.user_id,
                        project_id=active_ws.project_id,
                        action=ActivityAction.DOCUMENT_UPLOAD,
                        endpoint="UI",
                        http_method="UI",
                        status="FAILURE",
                        metadata={"error": str(e)}
                    )
                    st.error(f"Ingestion Rejected: {str(e)}")
                except Exception as e:
                    st.error(f"Ingestion Error: {str(e)}")
