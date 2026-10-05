# Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation

> **Engineering Pilot Reference:** Tata Technologies Case Study 5  
> **Status:** Phase 1–5 Verification Complete • Docker Ready • Pre-Commit Cleaned  
> **Target ECU:** Powertrain & Body Diagnostic Controller  

---

## 🔒 Confidentiality & Internal Use Notice

**IMPORTANT:** This repository is intended strictly for authorized, private internal engineering evaluation. System specifications, technology matrices, and architectural benchmarks are derived from the **Tata Technologies Case Study 5** reference solution document. 

* This software represents an engineering proof-of-concept and pilot evaluation prototype.
* It does not constitute a certified production deployment and does not imply formal corporate warranty or OEM product endorsement.
* Redistribution, public hosting, or external dissemination without prior authorization from Tata Technologies is strictly prohibited.

---

## 1. Project Overview & Purpose

Modern automotive Electronic Control Units (ECUs) require rigorous, standards-compliant Unified Diagnostic Services (**ISO 14229-1**) test sequences. Manual test authoring is labor-intensive, error-prone, and struggles to cover the full combinatorial space of session prerequisites, security constraints, and negative response codes (NRCs).

This platform combines:
1. **Context-Aware Retrieval (RAG):** Ingestion and vector search grounded in authorized diagnostic specifications with cryptographic provenance and page-level citations.
2. **Deterministic Rule Verification:** Hardcoded, non-probabilistic validation of all 15 core ISO 14229 services before test cases can be saved or executed.
3. **Mandatory Human-in-the-Loop (HITL) Governance:** Strict review gate preventing unapproved AI-generated tests from being executed on ECUs or exported to test tools.
4. **Software-in-the-Loop (SIL) ECU Simulator:** Dual-tier diagnostic execution engine enforcing session state machines, seed-key security algorithms, P2/P2* timing, and hardware-style fault injection.
5. **Bidirectional Relational Traceability:** Graph lineage connecting requirements, UDS rules, generated tests, review decisions, simulated executions, and production export scripts.

---

## 2. Key Capabilities

* **Deterministic ISO 14229 Enforcement:** Full validation for 15 services:
  * `0x10` (DiagnosticSessionControl)
  * `0x11` (ECUReset)
  * `0x14` (ClearDiagnosticInformation)
  * `0x19` (ReadDTCInformation)
  * `0x22` (ReadDataByIdentifier)
  * `0x23` (ReadMemoryByAddress)
  * `0x27` (SecurityAccess)
  * `0x28` (CommunicationControl)
  * `0x2E` (WriteDataByIdentifier)
  * `0x2F` (InputOutputControlByIdentifier)
  * `0x31` (RoutineControl)
  * `0x34` (RequestDownload)
  * `0x36` (TransferData)
  * `0x37` (RequestTransferExit)
  * `0x3E` (TesterPresent)
  * `0x85` (ControlDTCSetting)
* **Automated Test Generation:** Generates nominal positive requests, unsupported subfunction checks (NRC `0x12`), message length errors (NRC `0x13`), session prerequisite violations (NRC `0x7E`/`0x7F`/`0x22`), and security access violations (NRC `0x33`).
* **SIL Execution & Fault Injection:** Test runner executes against an in-process simulated ECU with runtime configurable fault injection (forced NRC, dropped frames, corrupt message lengths).
* **Production Script Exporter:** Generates standalone Python (`udsoncan`) test suites and Vector CANoe CAPL test modules for approved test cases.
* **Traceability & Coverage Telemetry:** Section 11 Success Metrics scorecard and bidirectional graph explorer powered by SQLite and NetworkX.
* **Privacy-Conscious User & Admin Dashboard:** Session-based activity logging, client IP masking, and a protected administrator telemetry dashboard.

---

## 3. Approved Architectural Decisions

* **AD-01: LLM Model & Host Strategy:**
  * Local Llama 3.1 8B (or Qwen 2.5 7B) running locally via Ollama, subject to hardware feasibility.
  * System operates fully air-gapped with transparent fallback to deterministic generation when Ollama is offline.
* **AD-02: Traceability Graph Store:**
  * SQLite + NetworkX relational directed graph equivalent. No external Neo4j or graph server dependency.
* **AD-03: Bus / ECU Execution Architecture:**
  * Decoupled dual-tier architecture:
    * `SimulatedECUAdapter` (in-process SIL simulated ECU) is the default regression engine.
    * `VirtualCANBusAdapter` (`python-can` virtual bus interface) is available for optional hardware integration.

---

## 4. System Architecture & Project Structure

```text
Tata Technologies project/
├── .dockerignore                    # Docker build context exclusions
├── .gitignore                       # Git repository ignore rules
├── .streamlit/
│   └── config.toml                  # Streamlit client configuration (viewer mode)
├── .env.example                     # Environment template (placeholders only)
├── Dockerfile                       # Python 3.10-slim container image specification
├── docker-compose.yml               # Multi-container orchestration (FastAPI + Streamlit)
├── requirements.txt                 # Pinned Python package dependencies
├── README.md                        # Project documentation and engineering guide
├── docs/                            # Formal architecture and compliance documentation
│   ├── architecture.md              # System design and component interactions
│   ├── implementation-roadmap.md   # Phased delivery breakdown
│   ├── phase5-closure-report.md     # Verification evidence and milestone sign-off
│   ├── requirements-traceability.md # Bidirectional requirement mapping
│   ├── simulated-ecu-strategy.md    # Dual-tier ECU execution and fault profiles
│   └── technology-matrix.md         # Framework and library evaluation rationale
├── src/
│   ├── api/                         # FastAPI REST application
│   │   ├── main.py                  # API application factory and middleware
│   │   ├── models.py                # Pydantic request/response schemas
│   │   └── routes.py                # REST endpoints (workspaces, rules, tests, execution)
│   ├── core/                        # Business logic and diagnostic engines
│   │   ├── activity_store.py        # Privacy-conscious event journal (SQLite)
│   │   ├── analytics.py             # Section 11 KPI measurement engine
│   │   ├── chunking.py              # Context-aware document chunking
│   │   ├── config.py                # System settings and environment bindings
│   │   ├── embeddings.py            # Domain-aware vectorizer & sentence-transformers
│   │   ├── execution_engine.py      # Dual-tier execution engine (SIL / Virtual CAN)
│   │   ├── execution_store.py       # JSON execution result storage
│   │   ├── exporter.py              # Python udsoncan and Vector CANoe CAPL exporter
│   │   ├── generator.py             # UDS test case generator
│   │   ├── governance.py            # Cryptographic audit trail & HITL review gates
│   │   ├── graph_store.py           # SQLite + NetworkX relational graph store
│   │   ├── ingestion.py             # SHA-256 document hashing and ingestion
│   │   ├── llm_interface.py         # Ollama client and deterministic fallback
│   │   ├── optimizer.py             # Coverage matrix and suite deduplication
│   │   ├── rules.py                 # Deterministic ISO 14229 rule engine (15 services)
│   │   ├── simulator.py             # Software-in-the-Loop simulated ECU
│   │   ├── test_case_store.py       # Test case persistence store
│   │   ├── vector_store.py          # Isolated ChromaDB vector store
│   │   └── workspace_manager.py     # Multi-project isolation manager
│   └── web/                         # Streamlit Automotive Engineering UI
│       ├── app.py                   # UI entrypoint and navigation router
│       ├── components/header.py     # Persistent engineering telemetry header
│       ├── pages/                   # Individual workspace pages
│       │   ├── admin_activity.py    # Protected Administrator Activity Dashboard
│       │   ├── documents.py         # Specification library and hash provenance
│       │   ├── execution.py         # Simulated ECU execution and fault injection
│       │   ├── export_opt.py        # Coverage matrix, deduplication, and export
│       │   ├── knowledge.py         # Grounded Q&A with exact citations
│       │   ├── metrics.py           # Enterprise KPI scorecard and audit trail
│       │   ├── overview.py          # Command center, telemetry KPIs, pipeline view
│       │   ├── test_studio.py       # Deterministic generator and frame validator
│       │   └── traceability.py      # Relational graph lineage visualizer
│       └── styles/theme.py          # Custom automotive engineering CSS design system
├── tests/                           # Complete test suite (185 tests)
└── data/                            # Project data directory
    ├── sample_specs/                # Synthetic reference specifications
    ├── test_cases/                  # Seed test cases for default workspace
    ├── execution_runs/              # Seed execution records
    ├── workspaces/                  # Workspace index catalog
    └── uploaded_documents/          # Storage for ingested documents (.gitkeep)
```

---

## 5. Local Development Setup

### Prerequisites
* Python 3.10+
* Docker Desktop & WSL2 (for containerized deployment)
* Ollama (optional, for local LLM inference)

### 1. Environment Configuration
Copy the template configuration file:
```bash
cp .env.example .env
```
Edit `.env` to configure your settings. Note that `UDS_ADMIN_KEY` is required for accessing the Administrator Activity Dashboard.

### 2. Python Virtual Environment
```bash
python -m venv .venv

# Windows PowerShell:
.venv\Scripts\Activate.ps1

# Linux / macOS:
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Running the REST Backend (FastAPI)
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```
* API Base URL: `http://localhost:8000/`
* Swagger Interactive API Docs: `http://localhost:8000/docs`

### 4. Running the Engineering Web UI (Streamlit)
In a separate terminal:
```bash
streamlit run src/web/app.py --server.port 8501
```
* UI Dashboard: `http://localhost:8501/`

---

## 6. Docker Deployment

The application is fully containerized using Docker and Docker Compose.

### Build and Start Containers
```bash
# Build the Docker images
docker compose build

# Start services in detached mode
docker compose up -d

# Check service status and health checks
docker compose ps
```

### Verified Endpoints
| Component | URL | Expected Response |
| :--- | :--- | :---: |
| FastAPI Root | `http://localhost:8000/` | HTTP 200 (Service metadata) |
| OpenAPI Swagger UI | `http://localhost:8000/docs` | HTTP 200 (Interactive docs) |
| Streamlit Health Probe | `http://localhost:8501/_stcore/health` | HTTP 200 (`ok`) |
| Streamlit Web UI | `http://localhost:8501/` | HTTP 200 (Engineering dashboard) |

### Stopping Containers
```bash
docker compose down
```

---

## 7. Automated Test Suite

The repository contains 185 automated unit, integration, and API tests covering all five project phases.

```bash
python -m pytest tests/ -v
```

**Expected Result:**
```text
======================= 185 passed in 17.0s =======================
```

Key test coverage areas:
* `test_rules.py`: Deterministic verification of all 15 ISO 14229 services, subfunction masks, lengths, SPRMIB bits, sessions, and security gating.
* `test_simulator.py`: In-process ECU state machine transitions, seed-key anti-hammering, P2/P2* timers, and fault injection.
* `test_generator.py`: Automated test case generation across positive and negative scenarios.
* `test_governance.py`: Immutable audit logging, digital signatures, and execution gating.
* `test_virtual_can.py`: Decoupled dual-tier adapter and virtual bus routing.
* `test_project_isolation.py`: Zero cross-workspace data leakage in vector stores and metadata catalogs.
* `test_admin_api.py`: Protected admin endpoints and credential verification.

---

## 8. Governance & Security Model

1. **Mandatory Human-in-the-Loop Gate:**
   AI-generated test cases are stored in `DRAFT` status. The system strictly forbids running unapproved tests against an ECU (`403 Forbidden`) and forbids exporting unapproved tests (`GovernanceError`). An engineer must review and approve test cases with comments before execution.
2. **Immutable Audit Trail:**
   Every document upload, test generation, review verdict, execution attempt, and blocked action is logged in an append-only cryptographic journal with SHA-256 content hashes.
3. **Privacy-Preserving Telemetry:**
   User activity logging uses pseudonymous browser session IDs (`sess_<id>`). IP logging is disabled by default (`UDS_LOG_CLIENT_IP=false`) and masked to `/24` subnets when enabled.
4. **Protected Administrator Dashboard:**
   Access to security telemetry, query histories, and audit logs requires providing the secret configured via `UDS_ADMIN_KEY`. If no key is set, admin endpoints are safely disabled.

---

*Tata Technologies UDS Diagnostic Intelligence Platform • Case Study 5 Engineering Reference*
