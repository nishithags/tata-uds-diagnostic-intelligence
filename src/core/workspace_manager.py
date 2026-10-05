"""
Workspace & Document Metadata Store for Phase 1 Knowledge Pilot.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Maintains project workspace isolation and document provenance records.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from src.core.config import config


class WorkspaceRecord(BaseModel):
    project_id: str
    name: str
    description: str = ""
    oem_name: str = "Generic OEM"
    ecu_model: str = "Generic ECU"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    documents: Dict[str, dict] = Field(default_factory=dict)


class WorkspaceManager:
    """
    Manages persistent workspaces and documents metadata.
    Enforces project boundaries and tracks document ingestion status.
    """

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or config.workspaces_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.storage_dir / "workspaces_index.json"
        self._load_index()

    def _load_index(self) -> None:
        if self.index_file.exists():
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.workspaces: Dict[str, WorkspaceRecord] = {
                        k: WorkspaceRecord(**v) for k, v in data.items()
                    }
            except Exception:
                self.workspaces = {}
        else:
            self.workspaces = {}
            # Initialize with default Tata Technologies pilot project
            self.create_workspace(
                project_id="tata_uds_pilot",
                name="Tata Technologies UDS Diagnostic Pilot",
                description="Default engineering workspace for ISO 14229 UDS diagnostic verification",
                oem_name="Tata Technologies Reference OEM",
                ecu_model="Powertrain & Body Diagnostic Controller"
            )

    def _save_index(self) -> None:
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump({k: v.model_dump() for k, v in self.workspaces.items()}, f, indent=2)

    def create_workspace(
        self, project_id: str, name: str, description: str = "", oem_name: str = "", ecu_model: str = ""
    ) -> WorkspaceRecord:
        clean_id = project_id.strip()
        if clean_id in self.workspaces:
            return self.workspaces[clean_id]

        record = WorkspaceRecord(
            project_id=clean_id,
            name=name,
            description=description,
            oem_name=oem_name or "Generic OEM",
            ecu_model=ecu_model or "Generic ECU",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        self.workspaces[clean_id] = record
        self._save_index()
        return record

    def get_workspace(self, project_id: str) -> Optional[WorkspaceRecord]:
        return self.workspaces.get(project_id.strip())

    def list_workspaces(self) -> List[WorkspaceRecord]:
        return list(self.workspaces.values())

    def record_document(self, project_id: str, doc_metadata: dict) -> None:
        ws = self.get_workspace(project_id)
        if not ws:
            ws = self.create_workspace(project_id=project_id, name=f"Project {project_id}")
        doc_id = doc_metadata.get("doc_id")
        if doc_id:
            ws.documents[doc_id] = doc_metadata
            self._save_index()

    def get_documents_for_project(self, project_id: str) -> List[dict]:
        ws = self.get_workspace(project_id)
        if not ws:
            return []
        return list(ws.documents.values())


workspace_manager = WorkspaceManager()
