"""
Privacy-Conscious User Activity & Audit Store for Tata Technologies UDS Project.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Features:
- Structured event logging across 11 core application activities.
- Anonymous browser session tracking (sess_<id>) with future user authentication compatibility.
- SQLite-backed persistence (activity_store.db) reusing existing project database design.
- Strict privacy redaction: Never stores passwords, tokens, API keys, secrets, or auth headers.
- Configurable IP logging (disabled by default, anonymized if enabled).
- Query history tracking with user query text and citation counts.
- Summary telemetry analytics for administrator dashboard.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field

from src.core.config import config


# Application Activity Event Types
class ActivityAction:
    KNOWLEDGE_QUERY = "KNOWLEDGE_QUERY"
    DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"
    TEST_GENERATED = "TEST_GENERATED"
    RULE_VERIFIED = "RULE_VERIFIED"
    TEST_REVIEWED = "TEST_REVIEWED"
    TEST_EXECUTED = "TEST_EXECUTED"
    TEST_EXPORTED = "TEST_EXPORTED"
    TEST_OPTIMIZED = "TEST_OPTIMIZED"
    ECU_RESET = "ECU_RESET"
    WORKSPACE_CREATED = "WORKSPACE_CREATED"
    API_ERROR = "API_ERROR"

    ALL_ACTIONS = [
        KNOWLEDGE_QUERY,
        DOCUMENT_UPLOAD,
        TEST_GENERATED,
        RULE_VERIFIED,
        TEST_REVIEWED,
        TEST_EXECUTED,
        TEST_EXPORTED,
        TEST_OPTIMIZED,
        ECU_RESET,
        WORKSPACE_CREATED,
        API_ERROR,
    ]


class ActivityRecord(BaseModel):
    """Represents a single privacy-conscious user or system activity event."""
    __test__ = False
    event_id: str = Field(default_factory=lambda: f"act_{uuid.uuid4().hex[:12]}")
    timestamp_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    session_id: str
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    action: str
    endpoint: Optional[str] = None
    http_method: Optional[str] = None
    query_text: Optional[str] = None
    test_case_id: Optional[str] = None
    status: str = "SUCCESS"  # "SUCCESS", "FAILURE", "ERROR"
    http_status_code: Optional[int] = 200
    duration_ms: float = 0.0
    client_ip: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_authenticated(self) -> bool:
        """True if associated with an authenticated user rather than anonymous session."""
        return bool(self.user_id and self.user_id.strip() and self.user_id.lower() != "anonymous")


# Sensitive key patterns to redact
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(pass(word)?|token|secret|auth(orization)?|api_?key|private_?key|credential|cookie)",
    re.IGNORECASE
)


def sanitize_sensitive_data(val: Any) -> Any:
    """
    Recursively scans and redacts any passwords, tokens, API keys, secrets,
    or raw authorization headers from dictionaries, lists, and strings.
    """
    if isinstance(val, dict):
        sanitized = {}
        for k, v in val.items():
            if _SENSITIVE_KEY_PATTERN.search(str(k)):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_sensitive_data(v)
        return sanitized
    elif isinstance(val, list):
        return [sanitize_sensitive_data(item) for item in val]
    elif isinstance(val, str):
        # Redact Bearer tokens or obvious secret patterns if found in string
        if re.search(r"bearer\s+[A-Za-z0-9_\-\.]{15,}", val, re.IGNORECASE):
            return re.sub(r"bearer\s+[A-Za-z0-9_\-\.]{15,}", "Bearer [REDACTED]", val, flags=re.IGNORECASE)
        return val
    return val


def process_client_ip(ip: Optional[str]) -> Optional[str]:
    """
    Applies privacy configuration to client IP address:
    - If log_client_ip is False: returns None (zero IP collection).
    - If log_client_ip is True and anonymize_ip is True: masks IPv4 last octet (e.g. 192.168.1.0/24).
    """
    if not ip or not config.log_client_ip:
        return None

    if config.anonymize_ip:
        # Mask IPv4
        parts = ip.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.{parts[2]}.xxx"
        # Mask IPv6
        if ":" in ip:
            return ip.split(":")[0] + "::/48"
    return ip


class SQLiteActivityStore:
    """
    SQLite persistence layer for privacy-conscious user and admin activity events.
    Thread-safe and serverless, matching AD-02 architectural patterns.
    """
    __test__ = False

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.activity_db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initializes user_activity_events table and performance indices."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_activity_events (
                    event_id TEXT PRIMARY KEY,
                    timestamp_utc TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    user_id TEXT,
                    project_id TEXT,
                    action TEXT NOT NULL,
                    endpoint TEXT,
                    http_method TEXT,
                    query_text TEXT,
                    test_case_id TEXT,
                    status TEXT NOT NULL,
                    http_status_code INTEGER,
                    duration_ms REAL,
                    client_ip TEXT,
                    metadata_json TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_act_timestamp ON user_activity_events(timestamp_utc)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_act_action ON user_activity_events(action)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_act_session ON user_activity_events(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_act_project ON user_activity_events(project_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_act_status ON user_activity_events(status)")
            conn.commit()

    def log_activity(
        self,
        session_id: str,
        action: str,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        http_method: Optional[str] = None,
        query_text: Optional[str] = None,
        test_case_id: Optional[str] = None,
        status: str = "SUCCESS",
        http_status_code: Optional[int] = 200,
        duration_ms: float = 0.0,
        client_ip: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        event_id: Optional[str] = None,
        timestamp_utc: Optional[str] = None,
    ) -> ActivityRecord:
        """
        Records a sanitized, privacy-compliant user activity event into SQLite.
        """
        # Ensure session ID is valid
        clean_session_id = session_id.strip() if session_id else f"sess_{uuid.uuid4().hex[:12]}"

        # Redact any sensitive information in metadata
        sanitized_metadata = sanitize_sensitive_data(metadata or {})

        # Apply IP privacy policy
        safe_ip = process_client_ip(client_ip)

        record = ActivityRecord(
            event_id=event_id or f"act_{uuid.uuid4().hex[:12]}",
            timestamp_utc=timestamp_utc or datetime.now(timezone.utc).isoformat(),
            session_id=clean_session_id,
            user_id=user_id.strip() if user_id and user_id.strip() else None,
            project_id=project_id.strip() if project_id and project_id.strip() else None,
            action=action,
            endpoint=endpoint,
            http_method=http_method,
            query_text=query_text,
            test_case_id=test_case_id,
            status=status,
            http_status_code=http_status_code,
            duration_ms=round(duration_ms, 2),
            client_ip=safe_ip,
            metadata=sanitized_metadata
        )

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_activity_events (
                    event_id, timestamp_utc, session_id, user_id, project_id,
                    action, endpoint, http_method, query_text, test_case_id,
                    status, http_status_code, duration_ms, client_ip, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.event_id,
                record.timestamp_utc,
                record.session_id,
                record.user_id,
                record.project_id,
                record.action,
                record.endpoint,
                record.http_method,
                record.query_text,
                record.test_case_id,
                record.status,
                record.http_status_code,
                record.duration_ms,
                record.client_ip,
                json.dumps(record.metadata)
            ))
            conn.commit()

        return record

    def get_events(
        self,
        project_id: Optional[str] = None,
        action: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ActivityRecord]:
        """Queries activity records with flexible filtering and pagination."""
        query = "SELECT * FROM user_activity_events WHERE 1=1"
        params: List[Any] = []

        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        if action:
            query += " AND action = ?"
            params.append(action)
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        if start_time:
            query += " AND timestamp_utc >= ?"
            params.append(start_time)
        if end_time:
            query += " AND timestamp_utc <= ?"
            params.append(end_time)
        if search_query:
            query += " AND (query_text LIKE ? OR metadata_json LIKE ? OR test_case_id LIKE ?)"
            wildcard = f"%{search_query}%"
            params.extend([wildcard, wildcard, wildcard])

        query += " ORDER BY timestamp_utc DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        records: List[ActivityRecord] = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            for row in cursor.fetchall():
                try:
                    meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
                except Exception:
                    meta = {}
                records.append(
                    ActivityRecord(
                        event_id=row["event_id"],
                        timestamp_utc=row["timestamp_utc"],
                        session_id=row["session_id"],
                        user_id=row["user_id"],
                        project_id=row["project_id"],
                        action=row["action"],
                        endpoint=row["endpoint"],
                        http_method=row["http_method"],
                        query_text=row["query_text"],
                        test_case_id=row["test_case_id"],
                        status=row["status"],
                        http_status_code=row["http_status_code"],
                        duration_ms=row["duration_ms"] or 0.0,
                        client_ip=row["client_ip"],
                        metadata=meta
                    )
                )
        return records

    def get_event_by_id(self, event_id: str) -> Optional[ActivityRecord]:
        """Retrieves a single activity record by its event ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_activity_events WHERE event_id = ?", (event_id,))
            row = cursor.fetchone()
            if not row:
                return None
            try:
                meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
            except Exception:
                meta = {}
            return ActivityRecord(
                event_id=row["event_id"],
                timestamp_utc=row["timestamp_utc"],
                session_id=row["session_id"],
                user_id=row["user_id"],
                project_id=row["project_id"],
                action=row["action"],
                endpoint=row["endpoint"],
                http_method=row["http_method"],
                query_text=row["query_text"],
                test_case_id=row["test_case_id"],
                status=row["status"],
                http_status_code=row["http_status_code"],
                duration_ms=row["duration_ms"] or 0.0,
                client_ip=row["client_ip"],
                metadata=meta
            )

    def get_summary_stats(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Computes aggregate activity KPIs for the Administrator Dashboard."""
        where_clause = "WHERE project_id = ?" if project_id else ""
        params = (project_id,) if project_id else ()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total events
            cursor.execute(f"SELECT COUNT(*) as total FROM user_activity_events {where_clause}", params)
            total_events = cursor.fetchone()["total"]

            # Unique sessions
            cursor.execute(f"SELECT COUNT(DISTINCT session_id) as sess_cnt FROM user_activity_events {where_clause}", params)
            unique_sessions = cursor.fetchone()["sess_cnt"]

            # Unique authenticated users
            auth_filter = f"WHERE user_id IS NOT NULL AND user_id != 'anonymous' {'AND project_id = ?' if project_id else ''}"
            cursor.execute(f"SELECT COUNT(DISTINCT user_id) as user_cnt FROM user_activity_events {auth_filter}", params)
            authenticated_users = cursor.fetchone()["user_cnt"]

            # Anonymous sessions count (events without authenticated user)
            anon_filter = f"WHERE (user_id IS NULL OR user_id = 'anonymous') {'AND project_id = ?' if project_id else ''}"
            cursor.execute(f"SELECT COUNT(DISTINCT session_id) as anon_cnt FROM user_activity_events {anon_filter}", params)
            anonymous_sessions = cursor.fetchone()["anon_cnt"]

            # Success and Failure counts
            cursor.execute(f"SELECT COUNT(*) as succ_cnt FROM user_activity_events WHERE status = 'SUCCESS' {'AND project_id = ?' if project_id else ''}", params)
            success_count = cursor.fetchone()["succ_cnt"]

            cursor.execute(f"SELECT COUNT(*) as fail_cnt FROM user_activity_events WHERE status != 'SUCCESS' {'AND project_id = ?' if project_id else ''}", params)
            failure_count = cursor.fetchone()["fail_cnt"]

            # Action breakdowns
            cursor.execute(
                f"SELECT action, COUNT(*) as cnt FROM user_activity_events {where_clause} GROUP BY action",
                params
            )
            action_counts = {row["action"]: row["cnt"] for row in cursor.fetchall()}

        return {
            "total_events": total_events,
            "unique_sessions": unique_sessions,
            "unique_authenticated_users": authenticated_users,
            "unique_anonymous_sessions": anonymous_sessions,
            "knowledge_queries_count": action_counts.get(ActivityAction.KNOWLEDGE_QUERY, 0),
            "tests_generated_count": action_counts.get(ActivityAction.TEST_GENERATED, 0),
            "tests_executed_count": action_counts.get(ActivityAction.TEST_EXECUTED, 0),
            "exports_count": action_counts.get(ActivityAction.TEST_EXPORTED, 0),
            "success_count": success_count,
            "failure_count": failure_count,
            "action_breakdown": action_counts
        }

    def get_knowledge_query_history(
        self,
        project_id: Optional[str] = None,
        search_term: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieves dedicated knowledge query history records:
        Session | Query | Result | Time
        """
        records = self.get_events(
            project_id=project_id,
            action=ActivityAction.KNOWLEDGE_QUERY,
            search_query=search_term,
            limit=limit
        )

        history: List[Dict[str, Any]] = []
        for r in records:
            citations_count = r.metadata.get("citations_count", 0)
            time_display = r.timestamp_utc[11:19] if len(r.timestamp_utc) >= 19 else r.timestamp_utc
            history.append({
                "event_id": r.event_id,
                "session_id": r.session_id,
                "user_id": r.user_id or "anonymous",
                "is_authenticated": r.is_authenticated,
                "query": r.query_text or "(No query text)",
                "result": f"{citations_count} citations",
                "citations_count": citations_count,
                "time": time_display,
                "timestamp_utc": r.timestamp_utc,
                "project_id": r.project_id or "global",
                "status": r.status,
                "duration_ms": r.duration_ms
            })
        return history

    def clear_all(self) -> None:
        """Clears all records in activity table (for isolated test runs)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_activity_events")
            conn.commit()


# Singleton Activity Store instance
activity_store = SQLiteActivityStore()
