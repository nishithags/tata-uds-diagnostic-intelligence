# Technology Decision Matrix
## Project: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation
**Company Reference:** Tata Technologies — Automotive Engineering AI | Project Case Studies (pp. 21–25)  
**Document Status:** Baseline Approved for Phase 0  
**Classification:** Confidential / Tata Technologies Standard  

---

## 1. Architectural Technology Policy & Boundary Conditions

To comply with Tata Technologies automotive security guidelines and customer IP protection rules, the technology stack must adhere to the following mandatory boundary constraints:

1. **Air-Gapped & Local Deployment Capability:** Automotive diagnostic specifications (ODX, CDD, ARXML, proprietary OEM diagnostic tables) contain proprietary intellectual property. All core components (LLM, embeddings, vector stores, databases) must be capable of running locally or in an isolated private cloud without external data egress.
2. **Deterministic Protocol Rules Over Generative Hallucinations:** Large Language Models are inherently probabilistic. ISO 14229 diagnostic communication requires deterministic bit-level accuracy. The architecture strictly mandates deterministic rule validation before any AI-generated test is exported or executed.
3. **No Unapproved Framework Swaps:** The company reference documents specify Streamlit for the engineering pilot and FastAPI for application services. Streamlit must not be replaced with React or other unapproved UI frameworks.
4. **Reproducibility & Auditability:** Every recommendation, generated test case, and execution log must be permanently recorded with citations and immutable audit trails.

---

## 2. Decision Criteria & Weighting Scheme

Each technology option is evaluated using a weighted multi-criteria scoring system ($1 = \text{Poor}$, $5 = \text{Excellent}$):

| Evaluation Criterion | Weight ($W$) | Description & Automotive Relevance |
| :--- | :---: | :--- |
| **Automotive Security & Local Isolation** | $25\%$ | Ability to operate strictly on-premises/air-gapped without leaking proprietary diagnostic data. |
| **Deterministic Verification & Rule Precision** | $20\%$ | Ability to enforce exact ISO 14229 protocol schemas, byte layouts, and timing constraints. |
| **Development Velocity & Pilot Agility** | $20\%$ | Speed of implementing, testing, and iterating the pilot without excessive enterprise overhead. |
| **Extensibility to Production Scale** | $15\%$ | Seamless upgrade path to multi-user, multi-project, high-throughput automotive test benches. |
| **Operational Simplicity & Resource Footprint** | $10\%$ | Reasonable hardware requirements (CPU/GPU, RAM) for engineering workstations. |
| **Community, Tooling & Ecosystem Support** | $10\%$ | Rich libraries, mature automotive interfaces (`python-can`, `udsoncan`, Vector toolchain). |

$$\text{Weighted Score} = \sum_{i} (\text{Score}_i \times W_i)$$

---

## 3. Layer-by-Layer Technology Decision Matrix

### 3.1 User Interface Layer (Reference Document: Page 21, 24)
Company Options: **Streamlit**, **Flask Web UI**, **Optional Enterprise Portal**

| Technology | Security & Isolation (25%) | Rule Precision (20%) | Pilot Velocity (20%) | Scale Path (15%) | Footprint (10%) | Ecosystem (10%) | Weighted Score | Evaluation & Rationale |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Streamlit** *(Selected Pilot)* | 5 (1.25) | 5 (1.00) | 5 (1.00) | 4 (0.60) | 5 (0.50) | 5 (0.50) | **4.85** | **Recommended for Pilot.** Native Python data/engineering app framework. Rapidly exposes document search, test case inspection tables, rule check badges, and HITL approval dialogs. Retained per explicit company requirement. |
| **Flask Web UI** | 5 (1.25) | 4 (0.80) | 3 (0.60) | 4 (0.60) | 4 (0.40) | 4 (0.40) | **4.05** | Flexible traditional HTML/Jinja/JS stack, but requires separate frontend development overhead, slowing pilot velocity. |
| **Enterprise Portal** | 5 (1.25) | 4 (0.80) | 2 (0.40) | 5 (0.75) | 2 (0.20) | 4 (0.40) | **3.80** | Heavyweight enterprise UI (e.g. corporate intranet / React micro-frontends). Recommended for Stage 5 Platform Scale, not Phase 1–3 pilot. |

---

### 3.2 Application & API Services Layer (Reference Document: Page 21, 24)
Company Options: **FastAPI (Preferred)**, **Flask (Alternative)**

| Technology | Security & Isolation (25%) | Rule Precision (20%) | Pilot Velocity (20%) | Scale Path (15%) | Footprint (10%) | Ecosystem (10%) | Weighted Score | Evaluation & Rationale |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **FastAPI** *(Selected)* | 5 (1.25) | 5 (1.00) | 5 (1.00) | 5 (0.75) | 5 (0.50) | 5 (0.50) | **5.00** | **Recommended.** Explicitly preferred in reference document. Native Pydantic schema validation for strict ISO 14229 byte frame models, async I/O for simulated ECU responses, automatic OpenAPI documentation. |
| **Flask** | 5 (1.25) | 4 (0.80) | 4 (0.80) | 4 (0.60) | 5 (0.50) | 5 (0.50) | **4.45** | Mature WSGI framework, but lacks native async and Pydantic validation by default; requires third-party plugins for OpenAPI docs. |

---

### 3.3 Large Language Model (LLM) Inference Layer (Reference Document: Page 21, 24)
Company Options: **Any approved LLM: Llama, Mistral, Qwen, DeepSeek, Falcon, or equivalent (Local/Private)**  
*Status: [DECISION PENDING FORMAL USER APPROVAL — Model Family & Runtime Host]*

| Technology Option | Security & Isolation (25%) | Rule Precision (20%) | Pilot Velocity (20%) | Scale Path (15%) | Footprint (10%) | Ecosystem (10%) | Weighted Score | Company Reference Evaluation & Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Llama (e.g. Llama 3 / 3.1 / 3.3: 8B/70B)** | 5 (1.25) | 5 (1.00) | 5 (1.00) | 5 (0.75) | 4 (0.40) | 5 (0.50) | **4.90** | *Candidate Option (Pending Approval).* Strong open weights, structured JSON compliance. Candidate runtimes include local Ollama or private server vLLM. |
| **Mistral / Mixtral (7B / 8x7B / Nemo)** | 5 (1.25) | 4 (0.80) | 5 (1.00) | 4 (0.60) | 4 (0.40) | 5 (0.50) | **4.55** | *Candidate Option (Pending Approval).* Strong coding and reasoning; excellent alternative local candidate. |
| **Qwen (e.g. Qwen 2.5: 7B / 14B / 32B)** | 5 (1.25) | 5 (1.00) | 4 (0.80) | 4 (0.60) | 4 (0.40) | 4 (0.40) | **4.45** | *Candidate Option (Pending Approval).* High tabular reasoning and code performance for dense ODX/CDD diagnostic matrices. |
| **DeepSeek (V2/V3/R1)** | 5 (1.25) | 4 (0.80) | 3 (0.60) | 4 (0.60) | 3 (0.30) | 4 (0.40) | **3.95** | *Candidate Option (Pending Approval).* High reasoning power, but requires substantial local GPU infrastructure. |
| **Falcon (7B / 40B / 180B)** | 4 (1.00) | 3 (0.60) | 3 (0.60) | 3 (0.45) | 3 (0.30) | 3 (0.30) | **3.25** | *Candidate Option (Pending Approval).* Older architecture; less fine-grained instruction following for structured automotive JSON schemas. |

---

### 3.4 Text & Table Embedding Service (Reference Document: Page 22, 24)
Company Options: **BGE**, **E5**, **Sentence Transformers**, or equivalent

| Technology | Security & Isolation (25%) | Rule Precision (20%) | Pilot Velocity (20%) | Scale Path (15%) | Footprint (10%) | Ecosystem (10%) | Weighted Score | Evaluation & Rationale |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **BGE (e.g. BAAI/bge-large-en-v1.5 / bge-base)** *(Selected Primary)* | 5 (1.25) | 5 (1.00) | 5 (1.00) | 5 (0.75) | 4 (0.40) | 5 (0.50) | **4.90** | **Recommended Primary.** Top benchmark accuracy for technical and dense structured text retrieval. Supports instruction-tuned retrieval queries ("Represent this automotive diagnostic specification for retrieval"). |
| **E5 (e.g. intfloat/e5-large-v2)** | 5 (1.25) | 4 (0.80) | 5 (1.00) | 4 (0.60) | 4 (0.40) | 5 (0.50) | **4.55** | Excellent general retrieval capabilities with asymmetric passage/query prefixing; strong alternative. |
| **Sentence Transformers (e.g. all-MiniLM-L6-v2)** | 5 (1.25) | 4 (0.80) | 5 (1.00) | 4 (0.60) | 5 (0.50) | 5 (0.50) | **4.65** | Extremely fast and lightweight CPU-runnable embedding, ideal for low-spec workstation edge deployment or CI/CD testing. |

---

### 3.5 Local Vector Store Layer (Reference Document: Page 22, 24)
Company Options: **ChromaDB**, **FAISS**, **Milvus**, **Self-hosted Weaviate**

| Technology | Security & Isolation (25%) | Rule Precision (20%) | Pilot Velocity (20%) | Scale Path (15%) | Footprint (10%) | Ecosystem (10%) | Weighted Score | Evaluation & Rationale |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **ChromaDB** *(Selected Pilot)* | 5 (1.25) | 5 (1.00) | 5 (1.00) | 4 (0.60) | 5 (0.50) | 5 (0.50) | **4.85** | **Recommended for Pilot.** Embedded in-process vector DB with native SQLite persistence, zero daemon setup, robust rich metadata filtering (`project_id`, `standard_type`, `ecu_id`), perfect for local project isolation. |
| **FAISS** | 5 (1.25) | 4 (0.80) | 4 (0.80) | 4 (0.60) | 5 (0.50) | 4 (0.40) | **4.35** | High-performance C++ vector index library from Meta. Superb raw similarity search speed, but lacks native rich relational metadata management. |
| **Milvus / Weaviate (Self-hosted)** | 5 (1.25) | 5 (1.00) | 2 (0.40) | 5 (0.75) | 2 (0.20) | 4 (0.40) | **3.80** | Distributed cluster vector databases. Ideal for Stage 5 enterprise scaling across hundreds of concurrent engineering users, but heavy for Phase 1–3 pilot. |

---

### 3.6 Structured Storage Layer (Reference Document: Page 22, 24)
Company Options: **SQLite (Pilot)**, **PostgreSQL (Production)**

| Technology | Security & Isolation (25%) | Rule Precision (20%) | Pilot Velocity (20%) | Scale Path (15%) | Footprint (10%) | Ecosystem (10%) | Weighted Score | Evaluation & Rationale |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **SQLite (via SQLAlchemy/SQLModel)** *(Selected Pilot)* | 5 (1.25) | 5 (1.00) | 5 (1.00) | 4 (0.60) | 5 (0.50) | 5 (0.50) | **4.85** | **Recommended for Pilot.** Zero configuration, file-based ACID storage. Handled via SQLAlchemy ORM so transitioning to PostgreSQL requires only changing the connection string. |
| **PostgreSQL** *(Selected Production)* | 5 (1.25) | 5 (1.00) | 3 (0.60) | 5 (0.75) | 3 (0.30) | 5 (0.50) | **4.40** | **Recommended for Stage 4/5 Scale.** Full multi-user concurrent transactions, row-level security, JSONB support for test execution traces, and audit logs. |

---

### 3.7 Graph & Traceability Store Layer (Reference Document: Page 24, 25)
Company Options: **Neo4j**, **Equivalent Graph Engine**  
*Status: [DECISION PENDING FORMAL USER APPROVAL — Graph Store Implementation]*

| Technology Option | Security & Isolation (25%) | Rule Precision (20%) | Pilot Velocity (20%) | Scale Path (15%) | Footprint (10%) | Ecosystem (10%) | Weighted Score | Company Reference Evaluation & Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Neo4j (Self-hosted Community / Enterprise)** | 5 (1.25) | 5 (1.00) | 3 (0.60) | 5 (0.75) | 2 (0.20) | 5 (0.50) | **4.30** | *Company Reference Standard (Pending Approval).* Native property graph database using Cypher. Full native graph traversal for cross-artifact relationships. |
| **Relational Graph Model (SQLite/PostgreSQL + NetworkX or SQL CTEs)** | 5 (1.25) | 5 (1.00) | 5 (1.00) | 4 (0.60) | 5 (0.50) | 4 (0.40) | **4.75** | *Candidate Equivalent (Pending Approval).* Uses relational nodes/edges tables in structured store and in-memory traversal; avoids running a separate graph server daemon. |

---

### 3.8 Document Ingestion & Extraction Layer (Reference Document: Page 24)
Company Options: **PyMuPDF**, **PDFPlumber**, **PyPDF**, **Tesseract**, **Custom Parsers**

| Technology Component | Role & Target Input Format | Technical Selection Rationale |
| :--- | :--- | :--- |
| **PyMuPDF (`fitz`)** *(Primary Text/Structure)* | High-speed PDF text, layout, and bookmark extraction. | Fastest PDF parser in Python; retains exact font sizes and heading hierarchy essential for chunking specification clauses. |
| **PDFPlumber** *(Table Extractor)* | Diagnostic table extraction (DIDs, RIDs, NRC tables). | Specialized cell and coordinate boundary detection for extracting structured UDS parameter tables from PDF specifications. |
| **Custom Parsers (`xml.etree` / `lxml`)** | ODX-D (ASAM MCD-2D), AUTOSAR ARXML, CDD, JSON, CSV. | Standard XML/JSON parsers extracting formal diagnostic descriptions (services, DIDs, sessions, security levels) into native schema models. |
| **Tesseract OCR** *(Fallback)* | Scanned legacy diagnostic documents and diagrams. | Self-hosted, offline optical character recognition for non-searchable specification sheets. |

---

### 3.9 Test Automation Export Frameworks (Reference Document: Page 20, 21, 23)
Company Options: **Python (`python-can` / `udsoncan`)**, **Vector CANoe / CAPL**, **Approved Frameworks**

| Automation Target | Output File Type | Target Runtime Environment |
| :--- | :--- | :--- |
| **Python Diagnostic Suite** *(Primary Standard)* | Executable `.py` test files using `udsoncan` and `python-can` | Runs directly in test pipelines, CI/CD runners, virtual benches, or simulated ECU test harness. |
| **Vector CANoe Test Module** | `.can` (CAPL test script) & XML Test Module configuration | Vector CANoe / CANalyzer automotive test execution environments used on Tier-1 OEM engineering benches. |
| **Structured Test Specification** | `.json` / `.csv` / OpenTestSystem format | Machine-readable and human-readable diagnostic test catalog for test management tools (Jira, Polarion). |

---

### 3.10 Deployment & Infrastructure Layer (Reference Document: Page 22, 24)
Company Options: **Docker**, **Optional Kubernetes**

| Deployment Mode | Evaluation | Rationale & Recommendation |
| :--- | :--- | :--- |
| **Docker & Docker Compose** *(Selected Pilot)* | **Primary for Pilot & Benches.** | Provides clean container encapsulation of FastAPI backend, Streamlit UI, ChromaDB, and local inference server. Single-command setup on engineering laptops or air-gapped lab servers. |
| **Kubernetes (k8s)** | **Production Scale Evolution.** | Multi-node cluster orchestration for enterprise scalability, automated load balancing across GPU inference nodes, and multi-tenant department isolation. |

---

## 4. Company Reference Baseline Pilot Stack Summary

Conforming precisely to the "Recommended Pilot Stack" on Page 23 and Common Reference Solution Architecture (pp. 24–25), preserving company reference options:

```
+---------------------------------------------------------------------------------------------------------+
|                                    COMPANY REFERENCE PILOT STACK                                        |
+---------------------------------------------------------------------------------------------------------+
| User Interface        | Streamlit (Engineering Web UI - mandatory reference framework)                  |
| Application & API     | FastAPI (Preferred for modular APIs; Flask alternative)                         |
| AI Orchestration      | LangChain, LlamaIndex, or custom Python pipeline (Controlled prompts/citations) |
| LLM Inference         | Locally hosted approved LLM: Llama, Mistral, Qwen, DeepSeek, Falcon, or equiv.  |
|                       | [STATUS: PENDING USER APPROVAL — Specific Model Family & Runtime Host]          |
| Text Embeddings       | BGE, E5, Sentence Transformers, or equivalent                                   |
| Vector Database       | ChromaDB or FAISS (Local persistent storage; Milvus/Weaviate for scale)         |
| Structured Database   | SQLite for pilot; PostgreSQL for production                                     |
| Graph Store           | Neo4j or equivalent (Cross-artifact relationships and traceability)             |
|                       | [STATUS: PENDING USER APPROVAL — Specific Implementation Option]                |
| Ingestion & OCR       | PyMuPDF, PDFPlumber, PyPDF, Tesseract, custom parsers (ODX, ARXML, CDD, CSV)    |
| Export Frameworks     | Python (udsoncan / python-can), Vector CANoe, CAPL, or approved frameworks       |
| Simulated Environment | Approved test environment with safeguards (Safe non-production execution)       |
|                       | [STATUS: PENDING USER APPROVAL — Harness & Bus Interface Option]                |
| Deployment            | Docker; optional Kubernetes (Network isolation & access control)                 |
+---------------------------------------------------------------------------------------------------------+
```

---

## 5. Architectural Decisions & Formal User Approvals

> **FORMAL APPROVAL STATUS:** The following three material architectural decisions have received **FORMAL USER APPROVAL**.  
> The approved options strictly follow the Tata Technologies Reference Solution Document (pp. 20–25) and are recorded below.  
> Note: Component installations (e.g. LLM runtime, graph components) will occur only upon explicit instruction.

### Decision 1 (AD-01): Local LLM Model Family & Runtime Host
- **Company Reference Specification:** *"Any approved LLM: Llama, Mistral, Qwen, DeepSeek, Falcon, or equivalent (Local, on-premises, or private environment)"* (Pages 21, 24).
- **Approved Selection:** **Option 1A — Local Llama 3.1 8B (or Qwen 2.5 7B) via Ollama**, subject to actual hardware feasibility.
- **Approval Date:** 2026-09-30
- **Status:** `APPROVED BY USER (Option 1A)`

### Decision 2 (AD-02): Graph Traceability Store Implementation Strategy
- **Company Reference Specification:** *"Graph Store: Neo4j or equivalent (Cross-artifact relationships and traceability)"* (Pages 24, 25).
- **Approved Selection:** **Option 2A — SQLite / NetworkX relational graph equivalent** (preserves zero-dependency portable deployment while fulfilling cross-artifact relationship tracking).
- **Approval Date:** 2026-09-30
- **Status:** `APPROVED BY USER (Option 2A)`

### Decision 3 (AD-03): Simulated ECU / Test Environment Execution Interface
- **Company Reference Specification:** *"Execute only in approved test environments with safeguards"* (Page 22) and *"Export to Python, CANoe, CAPL, or approved frameworks"* (Page 20).
- **Approved Selection:** **Option 3C — Maintain the decoupled dual-tier architecture** with the in-process simulated adapter (`SimulatedECUAdapter`) as the default and Virtual CAN (`python-can` virtual bus / `vcan0`) support only where required.
- **Approval Date:** 2026-09-30
- **Status:** `APPROVED BY USER (Option 3C)`

