"""
FastAPI Main Application for Phase 1 Knowledge Pilot.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.
"""

import time
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.routes import router
from src.core.activity_store import ActivityAction, activity_store
from src.core.config import config


class ActivityTrackingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that captures anonymous session IDs, request latency,
    and logs unhandled API errors while preserving user privacy.
    """
    async def dispatch(self, request: Request, call_next):
        session_id = request.headers.get("X-Session-ID")
        if not session_id or not session_id.strip():
            session_id = f"sess_{uuid.uuid4().hex[:12]}"

        user_id = request.headers.get("X-User-ID")
        if user_id:
            user_id = user_id.strip()

        request.state.session_id = session_id
        request.state.user_id = user_id

        client_ip = request.client.host if request.client else None
        if "x-forwarded-for" in request.headers:
            client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
        request.state.client_ip = client_ip

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            response.headers["X-Session-ID"] = session_id
            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            activity_store.log_activity(
                session_id=session_id,
                user_id=user_id,
                action=ActivityAction.API_ERROR,
                endpoint=request.url.path,
                http_method=request.method,
                status="ERROR",
                http_status_code=500,
                duration_ms=duration_ms,
                client_ip=client_ip,
                metadata={"error": str(exc), "path": request.url.path}
            )
            raise exc


app = FastAPI(
    title=config.app_name,
    version=config.app_version,
    description=(
        "FastAPI Backend for Tata Technologies UDS Diagnostics Knowledge Pilot.\n"
        "Supports authorized document ingestion, isolated vector retrieval, "
        "and cited diagnostic Q&A with strict provenance tracking."
    ),
    docs_url="/docs",
    redoc_url="/redoc"
)

# Activity & Session Tracking Middleware
app.add_middleware(ActivityTrackingMiddleware)

# Enable CORS for local Streamlit pilot UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {
        "project": config.app_name,
        "phase": "PHASE 1 - KNOWLEDGE PILOT: INGESTION + CITED Q&A",
        "documentation": "/docs",
        "api_prefix": "/api/v1"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host=config.api_host, port=config.api_port, reload=True)
