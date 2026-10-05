# Implementation Roadmap & Phase Planning
## Project: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation
**Company Reference:** Tata Technologies Case Study 5 (Section 13, Page 23 & Delivery Roadmap, Page 25)  
**Document Status:** Baseline Approved for Phase 0  
**Classification:** Confidential / Tata Technologies Standard  

---

## 1. Roadmap Alignment with Tata Technologies Governance

The implementation strategy directly reflects the **Tata Technologies Implementation Approach** (Section 13, Page 23) and **Recommended Delivery Roadmap** (Stage 3 UDS, Page 25), structured into sequential, gated phases.

Each phase has:
- Defined Work Packages & Technical Modules
- Explicit Entry and Exit Criteria
- Verification & Audit Gates conforming to the company Governance Principle

```
+----------------------------------------------------------------------------------------------------------------+
| PHASE 0: Requirements & Architecture [CURRENT PHASE - COMPLETE]                                                |
|   - Workspace inspection, company requirements analysis, traceability matrix, system architecture,             |
|     technology decision matrix, preliminary database model, UDS scope, simulated ECU strategy, risk register. |
+----------------------------------------------------------------------------------------------------------------+
                                           |
                                           v
+----------------------------------------------------------------------------------------------------------------+
| PHASE 1: Knowledge Pilot (UDS Specification Ingestion & Cited Q&A)                                             |
|   - PyMuPDF / PDFPlumber extraction, BGE / Sentence Transformers embeddings, ChromaDB project isolation,      |
|     FastAPI backend services, Streamlit Document Explorer and Cited Diagnostic Q&A Assistant.                  |
+----------------------------------------------------------------------------------------------------------------+
                                           |
                                           v
+----------------------------------------------------------------------------------------------------------------+
| PHASE 2: Test Generation & Deterministic Rule Verification                                                     |
|   - ISO 14229 deterministic rule engine, AI prompt orchestration for positive and negative test cases,         |
|     Human-in-the-Loop review board, immutable SQLite audit logger, graph traceability linking.                  |
+----------------------------------------------------------------------------------------------------------------+
                                           |
                                           v
+----------------------------------------------------------------------------------------------------------------+
| PHASE 3: Automation Export & Simulated ECU Verification                                                        |
|   - Script exporters for Python (udsoncan/python-can) and Vector CANoe (CAPL), virtual simulated ECU           |
|     runtime (session/security state machines, fault injection), automated response comparison & report.        |
+----------------------------------------------------------------------------------------------------------------+
                                           |
                                           v
+----------------------------------------------------------------------------------------------------------------+
| PHASE 4: Scale, Analytics & Enterprise Integration                                                             |
|   - Multi-project isolation hardening, test coverage analytics, PostgreSQL & Neo4j migration,                 |
|     Dockerized deployment, CI/CD pipeline integration, test management export (Polarion/Jira).                 |
+----------------------------------------------------------------------------------------------------------------+
```

---

## 2. Phase-by-Phase Technical Work Packages

### Phase 1: Knowledge Pilot (Weeks 1–3)
**Primary Focus:** Ingest authorized documents and deliver cited diagnostic Q&A (Section 13, Page 23).

#### Work Package 1.1: Document Ingestion Pipeline (`core.ingestion`)
- Implement PDF document parser with PyMuPDF for structural text extraction and PDFPlumber for table extraction.
- Implement ODX-D / ARXML / CDD structured parameter parsers.
- Enforce document provenance, cryptographic SHA-256 hash checks, and licensing authorization validation (`REQ-SEC-02`).

#### Work Package 1.2: Local Vector Database & Retrieval Engine (`core.retrieval`)
- Implement local dense embeddings using BGE (`bge-large-en-v1.5`) or Sentence Transformers.
- Set up ChromaDB with multi-tenant project and collection isolation (`REQ-DATA-03`).
- Implement hybrid semantic search with exact source citations (document title, section, page, text snippet).

#### Work Package 1.3: Application Backend & Services (`api.services`)
- Set up FastAPI application structure with Pydantic v2 schemas.
- Implement endpoints: `POST /api/v1/workspaces`, `POST /api/v1/documents/upload`, `POST /api/v1/knowledge/query`.

#### Work Package 1.4: Streamlit Knowledge Pilot Interface (`web.streamlit_app`)
- Build Workspace and Ingestion Manager view.
- Build Interactive Cited Q&A Chat View with citation drawers displaying exact source text.

**Phase 1 Exit Gate:**
- [ ] Ingestion verified for ISO 14229 and sample OEM specifications.
- [ ] $\ge 90\%$ citation accuracy verified on standard diagnostic queries.
- [ ] Zero cross-project vector contamination verified.

---

### Phase 2: Test Generation & Rule Verification Engine (Weeks 4–6)
**Primary Focus:** Add structured test templates and deterministic rule-based message validation (Section 13, Page 23).

#### Work Package 2.1: Deterministic UDS Protocol Rule Engine (`core.rules`)
- Implement rule verification engine for ISO 14229 services (0x10, 0x11, 0x14, 0x19, 0x22, 0x27, 0x28, 0x2E, 0x2F, 0x31, 0x34, 0x36, 0x37, 0x3E, 0x85).
- Implement byte length verification, subfunction validation, suppress-positive-response bit handling.
- Implement session prerequisite checks and security access state validations.
- Implement comprehensive NRC schema validation.

#### Work Package 2.2: AI Prompt Orchestration & Test Generator (`core.generator`)
- Design controlled system prompts enforcing strict Pydantic JSON test case models.
- Implement positive test scenario generator (nominal parameters, valid sessions).
- Implement negative test scenario generator (invalid lengths, wrong sessions, missing security, invalid DIDs).
- Integrate immediate post-generation rule verification interceptor (`REQ-RULE-01`).

#### Work Package 2.3: Human-in-the-Loop Governance & Audit Manager (`core.governance`)
- Implement review lifecycle: `DRAFT` $\rightarrow$ `RULE_VERIFIED` $\rightarrow$ `PENDING_REVIEW` $\rightarrow$ `APPROVED` / `EDITED` / `REJECTED`.
- Implement immutable audit logger recording user actions, timestamps, and full diffs.
- Implement relational graph traceability linking (`traceability_nodes` / `traceability_edges`).

#### Work Package 2.4: Streamlit Test Studio & Review Board (`web.streamlit_app`)
- Build Test Generation Studio with parameter selectors and prompt inputs.
- Build Rule Verification Inspector showing live PASS/FAIL rule badges and byte breakdowns.
- Build HITL Review Board for formal engineer inspection and sign-off.

**Phase 2 Exit Gate:**
- [ ] Deterministic rule engine achieves $100\%$ interception of protocol errors in benchmark suites.
- [ ] Mandatory human review gate enforced: unapproved tests cannot be exported or executed.
- [ ] Complete positive/negative test pair generation verified.

---

### Phase 3: Automation Export & Simulated ECU Verification (Weeks 7–9)
**Primary Focus:** Export to Python, CANoe, CAPL and execute tests against simulated ECU (Section 13, Page 23).

#### Work Package 3.1: Automation Script Exporters (`core.exporter`)
- Implement Python script exporter generating executable `udsoncan` / `python-can` suites with session setup and assertions.
- Implement Vector CANoe CAPL exporter generating `.can` test modules with `testcase` and `testWaitMessage` constructs.
- Implement structured export to JSON and CSV formats for test management systems.

#### Work Package 3.2: Stateful Virtual Simulated ECU Runtime (`core.simulator`)
- Implement ISO 14229 in-memory server with active session state machine and $S3$ keep-alive timer.
- Implement Security Access state machine with seed generation, key validation, and anti-hammering lockout.
- Implement virtual DID and routine memory maps.
- Implement configurable fault injection engine (forced NRCs, response delays, length corruptions).

#### Work Package 3.3: Automated Test Runner & Response Comparator (`core.simulator`)
- Build automated execution harness supporting direct in-process and virtual CAN execution.
- Build response comparator verifying actual byte response vs expected PRPR / NRC and timing ($P2 \le P2_{Server\_max}$).
- Build detailed execution report generator.

#### Work Package 3.4: Streamlit Simulated ECU Runner (`web.streamlit_app`)
- Build Live Simulation Runner tab with real-time CAN trace log, byte diff inspector, and timing waterfall charts.

**Phase 3 Exit Gate:**
- [ ] Python scripts and CAPL test modules generated and syntax-validated.
- [ ] Automated execution of positive and negative test cases against simulated ECU passes with $100\%$ expected verdicts.
- [ ] Fault injection scenarios verified against client error handling.

---

### Phase 4: Enterprise Scale, Analytics & Toolchain Integration (Weeks 10–12)
**Primary Focus:** Add project isolation, coverage analytics, and toolchain integration (Section 13, Page 23 & Stage 5, Page 25).

#### Work Package 4.1: Coverage Analytics Engine (`core.analytics`)
- Implement diagnostic test coverage calculator (service coverage, DID coverage, negative NRC branch coverage).
- Generate executive compliance and audit reports with complete traceability matrices.

#### Work Package 4.2: Enterprise Storage & Traceability Migration (`storage`)
- Migrate structured data storage from SQLite to PostgreSQL with row-level security.
- Integrate Neo4j property graph database for enterprise-wide cross-artifact relationship querying.

#### Work Package 4.3: Containerization & Deployment (`ops`)
- Create production Docker Compose and multi-container Docker images with network isolation.
- Implement automated regression test pipeline in CI/CD.

**Phase 4 Exit Gate:**
- [ ] Multi-tenant security and workspace isolation audited.
- [ ] End-to-end traceability demonstrated from high-level requirement to test execution log.
- [ ] System packaged for turnkey deployment on engineering workstations and private lab servers.
