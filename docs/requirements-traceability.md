# Requirements Traceability Matrix (RTM)
## Project: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation
**Company Reference:** Tata Technologies — Automotive Engineering AI | Project Case Studies (Case Study 5, pp. 20–25)  
**Document Status:** Baseline Approved for Phase 0  
**Classification:** Confidential / Tata Technologies Standard  

---

## 1. Executive Summary & Source of Truth

This document establishes the bidirectional traceability between the company reference requirements provided in **Tata Technologies Case Study 5: UDS Diagnostics and Automated Test Generation Assistant** (alongside the Common Reference Solution Architecture, pp. 20–25) and the architectural components, verification methods, and implementation phases of the system.

### 1.1 Source of Truth Hierarchy
1. **Primary Reference:** Tata Technologies Case Study 5 (Project Overview, Business Context, Objectives, Scope, Users, Proposed Solution, Functional Capabilities, Workflow, Inputs/Outputs, Tech Stack, Benefits, Metrics, Risks & Controls, Implementation Approach).
2. **Architectural Standard:** Tata Technologies Common Reference Solution Architecture & Reference Processing Flow (pp. 23–25).
3. **Automotive Domain Standards:** ISO 14229-1 (UDS Application Layer), ISO 14229-2 (Session Layer Services), ISO 15765-2 (DoCAN Transport Layer), ISO 13400 (DoIP), and ASAM ODX / AUTOSAR Diagnostic Extract specifications.

### 1.2 Fundamental Governance Principle (Mandatory)
> *"AI-generated content must be traceable to approved source material and reviewed by authorized engineering specialists before it is used for compliance, design approval, software release, or vehicle validation."*  
> — **Tata Technologies Reference Solution Document, Section 13 (Page 23)**

---

## 2. In-Scope and Out-of-Scope Boundary Enforcement

To prevent project drift and adhere strictly to company boundaries, system requirements enforce hard architectural controls around the defined scope.

| Scope Domain | Company Reference Specification (Page 20, Section 3) | Architectural Enforcement Mechanism | Requirement ID |
| :--- | :--- | :--- | :--- |
| **IN SCOPE** | Approved standard and OEM knowledge retrieval | Isolated vector collections for standard vs OEM vs ECU specifications with metadata tagging. | `REQ-FNC-01` |
| **IN SCOPE** | UDS service and parameter guidance | Cited semantic search with deterministic schema checking for services, subfunctions, DIDs, RIDs, NRCs. | `REQ-FNC-02` |
| **IN SCOPE** | Request-message construction | Deterministic byte-level frame builder verifying service IDs, subfunctions, lengths, and suppression bits. | `REQ-FNC-03` |
| **IN SCOPE** | Positive and negative test generation | Rule-driven test case generator producing boundary values, session prerequisites, security gating, and invalid parameter scenarios. | `REQ-FNC-04` |
| **IN SCOPE** | Expected-response validation | Simulated ECU comparison engine matching actual responses against expected PRPR (Positive Response Parameter Record) or negative response codes (NRCs). | `REQ-FNC-05` |
| **IN SCOPE** | Export to Python, CANoe, CAPL, or approved frameworks | Modulated script generation producing Python (`python-can` / `udsoncan`) and Vector CANoe (`.can` / CAPL) test templates. | `REQ-FNC-06` |
| **OUT OF SCOPE** | Execution against production vehicles without controls | The application includes NO direct physical OBD/CAN vehicle connection interface. All execution runs against a sandboxed simulated ECU or approved bench environment with hardware-in-the-loop (HIL) safety controls. | `REQ-SEC-01` |
| **OUT OF SCOPE** | Use of unauthorized standards content | Ingestion gateway requires administrative validation, license clearance, and digital signature before parsing standards documents into vector stores. | `REQ-SEC-02` |
| **OUT OF SCOPE** | Unreviewed automatic acceptance of ECU behavior | Mandatory Human-in-the-Loop (HITL) review workflow. No test case or validation verdict can be promoted to an approved release without explicit authorized engineer sign-off. | `REQ-GOV-01` |

---

## 3. High-Level Requirements Traceability Matrix

The table below maps each requirement from the source document to its architectural module, lifecycle phase, verification method, and acceptance criteria.

### Verification Methods:
- **[I] Inspection:** Static code or document review.
- **[D] Demonstration:** Operational showing of capability.
- **[T] Automated Test:** Execution of unit, integration, or regression test suite.
- **[R] Static Rule Verification:** Deterministic protocol validation engine check.

```
Requirement ID Legend:
REQ-BIZ: Business & User Objective Requirements
REQ-FNC: Functional Capability Requirements
REQ-DATA: Ingestion & Storage Requirements
REQ-RULE: Deterministic Protocol Validation Requirements
REQ-ECU: Simulated ECU & Execution Requirements
REQ-EXP: Automation & Export Requirements
REQ-GOV: Human-in-the-Loop & Governance Requirements
REQ-SEC: Security, Safety & Isolation Requirements
```

| Req ID | Source Section & Step | Requirement Description | Target Module | Phase | Method | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **REQ-BIZ-01** | Sec 2, p. 20 | Reduce diagnostic specification interpretation effort through natural language Q&A. | `core.retrieval`, `web.ui` | Phase 1 | D, T | System answers engineer diagnostic queries citing exact spec sections, tables, and page numbers with $\ge 90\%$ citation accuracy. |
| **REQ-BIZ-02** | Sec 2, p. 20 | Generate consistent positive and negative test scenarios. | `core.generator`, `core.rules` | Phase 2 | T, R | Produces complete positive and negative test matrices covering valid inputs, invalid parameters, out-of-order sessions, and unauthorized security states. |
| **REQ-BIZ-03** | Sec 2, p. 20 | Validate request and expected-response structures deterministically before test execution. | `core.rules` | Phase 2 | R, T | $100\%$ detection of protocol syntax errors (invalid SID, length mismatch, missing subfunction, invalid NRC expectation) prior to execution. |
| **REQ-BIZ-04** | Sec 2, p. 20 | Accelerate conversion of requirements into executable test templates. | `core.exporter` | Phase 3 | D, T | Export validated test cases into ready-to-run Python (`python-can`/`udsoncan`) and Vector CAPL scripts in $< 3$ seconds. |
| **REQ-FNC-01** | Sec 6, p. 21 | Natural language diagnostic knowledge search across ingested specifications. | `core.retrieval` | Phase 1 | D, T | Engineer can query terms like "ReadDID 0xF190 extended session rules" and receive cited paragraphs from relevant standards and OEM specs. |
| **REQ-FNC-02** | Sec 6, p. 21 | Service, subfunction, DID, RID, NRC, session, and security guidance. | `core.retrieval`, `core.rules` | Phase 1 | D, T | Provides contextual guidance on prerequisite session (e.g. 0x03), security level (e.g. Seed-Key 0x01/0x02), and expected NRCs (e.g. 0x22, 0x33, 0x7E). |
| **REQ-FNC-03** | Sec 6, p. 21 | Request structure validation against ISO 14229 and OEM extract. | `core.rules` | Phase 2 | R, T | Validates byte payload formatting, subfunction bits, parameter lengths, and suppresses bit 7 handling ($0\text{x}80$). |
| **REQ-FNC-04** | Sec 6, p. 21 | Test case generation with preconditions, test steps, and pass/fail criteria. | `core.generator` | Phase 2 | T, I | Generates structured test case objects with preconditions (session state, security access), request byte sequences, timeout limits ($P2$/$P2^*$), and exact pass/fail assertions. |
| **REQ-FNC-05** | Sec 6, p. 21 | Positive and negative coverage generation. | `core.generator`, `core.rules` | Phase 2 | T, R | Automatically builds complementary negative cases for every positive service request (e.g., SubfunctionNotSupported 0x12, IncorrectMessageLength 0x13, ConditionsNotCorrect 0x22, SecurityAccessDenied 0x33). |
| **REQ-FNC-06** | Sec 6, p. 21 | Automation template export to Python and CANoe/CAPL. | `core.exporter` | Phase 3 | D, T | Generates syntactically correct Python scripts compatible with `udsoncan` and CAPL test modules compilable in CANoe. |
| **REQ-FNC-07** | Sec 6, p. 21 | Response comparison and reporting against simulated ECU. | `core.simulator` | Phase 3 | T, D | Executes test requests against simulated ECU, compares actual response bytes against expected positive/negative template, and logs pass/fail verdict with timing analysis. |
| **REQ-DATA-01**| Sec 7 (29), p. 21 | Ingest authorized UDS, OEM, ECU, and project specifications. | `core.ingestion` | Phase 1 | T, D | Supports PDF, ODX-D, CDD, ARXML, JSON, CSV formats with metadata tagging (document type, version, OEM, ECU model). |
| **REQ-DATA-02**| Sec 7 (30), p. 21 | Extract services, parameters, preconditions, and response rules from specifications. | `core.ingestion`, `core.rules` | Phase 1 | T, I | Structured extractor identifies tables of DIDs, RIDs, session transitions, security levels, and NRC mappings into deterministic database records. |
| **REQ-DATA-03**| Sec 7 (31), p. 21 | Store embedded chunks in project-specific local collections. | `core.retrieval` | Phase 1 | T, I | Chunks stored in ChromaDB/FAISS with strict project, OEM, and ECU metadata isolation; cross-project leakage prevented. |
| **REQ-DATA-04**| Sec 8, p. 21 | Support inputs: authorized UDS specs, OEM specs, ECU extract, requirements, existing tests, automation templates. | `core.ingestion` | Phase 1 | T, D | Ingestion pipeline handles heterogeneous inputs and associates them within the structured project data model. |
| **REQ-DATA-05**| Sec 8, p. 21 | Deliver expected outputs: diagnostic guidance with citations, validated request template, expected positive response, negative-response scenarios, structured test case, automation script template, coverage report. | All modules | Phases 1–3 | T, D | System delivers all 7 required outputs defined in Section 8 via Streamlit UI and REST API. |
| **REQ-RULE-01**| Sec 7 (33), p. 21 | Apply deterministic validation rules to all AI-generated diagnostic requests. | `core.rules` | Phase 2 | R, T | AI-generated requests must pass protocol rule verification prior to engineer review or execution. Non-compliant payloads are rejected with explicit diagnostic rule error flags. |
| **REQ-RULE-02**| Sec 12, p. 22 | Control Risk 1: Incorrect diagnostic message generation. | `core.rules`, `core.governance` | Phase 2 | R, I | Double barrier: 1) Deterministic rule verification checks SID, subfunction, length, and timing; 2) Authorized engineer inspection and sign-off. |
| **REQ-RULE-03**| Sec 12, p. 22 | Control Risk 2: Misinterpretation of OEM-specific behavior. | `core.retrieval`, `core.rules` | Phase 1 | T, R | Multi-tenant collection isolation: standard ISO 14229 rules are overridden only by explicitly prioritized OEM/ECU-specific collections. |
| **REQ-ECU-01** | Sec 3, p. 20 | Safe test execution in an approved test environment with safeguards (Simulated ECU). | `core.simulator` | Phase 3 | T, D | Built-in virtual ECU simulates ISO 14229 diagnostic server, session state machine, security state machine, and configurable fault injection. |
| **REQ-ECU-02** | Sec 12, p. 22 | Control Risk 3: Unsafe execution sequence. | `core.simulator`, `core.rules` | Phase 3 | R, T | The system prohibits live production vehicle execution (`REQ-SEC-01`). The simulated ECU enforces sequence prerequisites and isolates test runs. |
| **REQ-GOV-01** | Sec 7 (35), p. 21 | Require engineer review before controlled execution or export. | `core.governance`, `web.ui` | Phase 2 | D, T | Generated test cases enter `PENDING_REVIEW` state. Approval workflow allows Accept, Edit, or Reject with mandatory engineer comments. |
| **REQ-GOV-02** | Sec 13, p. 23 | Governance principle enforcement: Traceable to approved source material and reviewed by authorized engineering specialist. | `core.governance` | Phase 1 | T, I | Every generated output records citation pointers (file, section, chunk ID) and links to human approval audit log. |
| **REQ-GOV-03** | Flow (48-49), p. 25| Approved artifacts and decisions stored in structured database; traceability maintained in graph store. | `storage.sql`, `storage.graph` | Phase 2 | T, I | SQLite/PostgreSQL stores approvals and audit events. Graph store (Neo4j or equivalent — specific implementation pending formal approval) maintains nodes (Requirement -> Spec -> Rule -> Test -> Approval -> Run). |
| **REQ-SEC-01** | Sec 3, p. 20 | Prevent direct unmonitored production vehicle execution. | `api.services`, `core.simulator` | Phase 3 | I, T | The system explicitly lacks production bus interfaces without physical bench controls. Simulator runs in sandboxed virtual environment. |
| **REQ-SEC-02** | Sec 12, p. 22 | Control Risk 4: Standards licensing violation. | `core.ingestion`, `core.governance` | Phase 1 | I, T | Access control list (ACL) and document provenance tracking ensure only authorized, licensed documents are ingested. |
| **REQ-UI-01**  | Sec 9, p. 21 | Engineering user interface built with Streamlit for pilot. | `web.ui` | Phase 1 | D | Dedicated Streamlit interface featuring Document Explorer, Cited Q&A Assistant, Test Generator & Rule Validator, Test Review Board, and ECU Simulator Runner. |
| **REQ-API-01** | Sec 9, p. 21 | Application and API services built with FastAPI. | `api.services` | Phase 1 | T, D | Modular FastAPI backend providing REST endpoints for ingestion, query, rule checking, generation, review, export, and simulation. |
| **REQ-AI-01**   | Sec 9, p. 21 | LLM inference using approved locally/privately hosted models. | `core.generator` | Phase 1 | T, D | Air-gapped / local LLM integration (any approved LLM: Llama, Mistral, Qwen, DeepSeek, Falcon, or equivalent — specific model & runtime pending formal approval) ensuring zero automotive IP leakage. |
| **REQ-AI-02**   | Sec 9, p. 22 | Embeddings using BGE, E5, or Sentence Transformers. | `core.retrieval` | Phase 1 | T, D | Local embedding pipeline evaluates domain-specific diagnostic queries without external API dependencies. |

---

## 4. Indicative Success Metrics Verification Plan

Section 11 (Page 22) defines five key success metrics. The table below traces each metric to its architectural measurement telemetry.

| Company Metric (Page 22) | Source Meaning | Telemetry & Measurement Method | Target Baseline Goal |
| :--- | :--- | :--- | :--- |
| **Test Design Time** | Average time to create reviewed diagnostic test cases. | Timestamps recorded in `audit_logs` from requirement query to `review_status = APPROVED`. | Reduction of test authoring time by $\ge 60\%$ compared to manual authoring. |
| **Generation Accuracy** | Accepted request and response structures. | Ratio of generated requests passing `core.rules` deterministic validation on first pass, plus engineer acceptance rate without major manual edits. | $\ge 95\%$ deterministic rule pass rate; $\ge 85\%$ unedited engineer acceptance. |
| **Coverage Improvement** | Positive, negative, session, security, and timing coverage. | Coverage analytics engine calculating percent coverage of services, subfunctions, NRC branches, and session state transitions. | $100\%$ negative-case pairing for all generated positive test suites. |
| **Reuse Rate** | Percentage of generated tests based on approved templates. | Database query calculating tests derived from pre-approved master templates vs ad-hoc generation. | $\ge 80\%$ test cases reusing standard ISO 14229 approved building blocks. |
| **Defect Detection** | Confirmed ECU issues found through generated cases. | Simulation and HIL execution logging unexpected NRCs or timing deviations against specification. | Zero false passes in deterministic simulation test harness. |

---

## 5. Requirements Sign-Off and Baselining

- **Prepared By:** Lead Automotive Diagnostic Systems Architect  
- **Approved For Phase 0:** Pending User Formal Review  
- **Next Phase Gate:** Phase 1 Implementation Authorization  
