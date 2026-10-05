"""
Test Case Persistence Store for Phase 2.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Stores generated test cases and review states per workspace.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel

from src.core.config import config
from src.core.generator import TestCase


class TestCaseStore:
    """Stores and retrieves test cases partitioned by workspace project_id."""
    __test__ = False

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or (config.data_dir / "test_cases")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Dict[str, TestCase]] = {}

    def _get_project_file(self, project_id: str) -> Path:
        clean = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in project_id)
        return self.storage_dir / f"tc_{clean}.json"

    def _load_project(self, project_id: str) -> Dict[str, TestCase]:
        if project_id in self._cache:
            return self._cache[project_id]

        file_path = self._get_project_file(project_id)
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    tc_map = {k: TestCase(**v) for k, v in data.items()}
                    self._cache[project_id] = tc_map
                    return tc_map
            except Exception:
                pass
        self._cache[project_id] = {}
        return self._cache[project_id]

    def _save_project(self, project_id: str) -> None:
        file_path = self._get_project_file(project_id)
        tc_map = self._cache.get(project_id, {})
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({k: v.model_dump() for k, v in tc_map.items()}, f, indent=2)

    def save_test_case(self, test_case: TestCase) -> None:
        project_map = self._load_project(test_case.project_id)
        project_map[test_case.test_case_id] = test_case
        self._save_project(test_case.project_id)

    def get_test_case(self, project_id: str, test_case_id: str) -> Optional[TestCase]:
        project_map = self._load_project(project_id)
        return project_map.get(test_case_id)

    def list_test_cases(self, project_id: str) -> List[TestCase]:
        project_map = self._load_project(project_id)
        return list(project_map.values())


test_case_store = TestCaseStore()
