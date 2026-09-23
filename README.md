# LRI Co-Assistant — Artifact Package

Self-contained artifact for **Lean Research Inception (LRI) Co-Assistant**, the
AI-assisted tool introduced in the paper _"An AI-Assisted Tool for Practically
Relevant Research Problem Formulation in Software Engineering"_
(SBES 2026 Tools Track, CBSoft 2026).

This package is prepared for the **CBSoft 2026 Artifact Festival** and targets
both the **Available** and **Functional** badges.

---

## 1. Associated Paper

- **Title:** An AI-Assisted Tool for Practically Relevant Research Problem
  Formulation in Software Engineering
- **Authors:** João Pedro Theodoro, Victoria Cruz de Figueiredo,
  Anrafel Fernandes Pereira, Wallace Albertini Boquimpani,
  Mariana Crisostomo Martins, Marcos Kalinowski
- **Venue:** SBES 2026 — Tools Track (CBSoft 2026), São Paulo, Brazil
- **Paper PDF / accepted article link:** <https://zenodo.org/records/20355609>
- **Artifact DOI:** pending. Insert the version-specific DOI of the archived
  artifact release before claiming the Available badge.
- **Live demo:** <https://lri-tool.vercel.app>

---

## 2. Overview

**LRI Co-Assistant** operationalizes the **Lean Research Inception** framework
in an interactive digital environment. It supports Software Engineering
researchers in formulating practically relevant research problems by
integrating Large Language Models (LLMs) as a _reasoning partner_ — assisting
with structuring problem attributes, suggesting refinements, identifying gaps,
and supporting consistency throughout the five LRI phases:

1. Problem Vision Outline
2. Problem Vision Alignment
3. Research Problem Formulation
4. Research Problem Assessment
5. Go / Pivot / Abort Decision

AI-generated suggestions can be accepted, edited, or discarded at any point:
the researcher remains the central decision-maker.

---

## 3. Repository Structure

```
.
├── backend/            FastAPI + SQLAlchemy + Alembic (Python)
├── frontend/           React app (Vite) with inline AI suggestions
├── scripts/            Startup and smoke-test scripts
├── docs/               Supporting documentation, video, and case study
├── exports/            PDF export output folder
├── docker-compose.yml  Local orchestration (db, backend, worker, frontend)
├── .env.example        Environment variables template
├── .gitignore
├── LICENSE             MIT License for source code
├── LICENSE-DOCS        CC BY 4.0 for documentation and media
└── README.md           This file
```

---

## 4. Requirements

### Software

- **Docker:** ≥ 24.0
- **Docker Compose:** ≥ 2.20
- Tested on Linux (Ubuntu 22.04+), macOS 13+, and Windows 11 with WSL2.

If running without Docker:

- **Python:** 3.11+ (backend and worker)
- **Node.js:** 20.x (frontend, Vite)
- **PostgreSQL:** 15+

### Hardware

- **RAM:** minimum 4 GB, recommended 8 GB
- **CPU:** 2 cores recommended
- **Disk:** approximately 2 GB free (including container images)
- **Internet connection:** required for LLM API calls

### External Service

- An **OpenAI API key** is required for AI-assisted suggestions and synthesis.
  Other OpenAI models can be used by adjusting `LLM_MODEL`.
- API usage will incur costs on the key holder's OpenAI account. A full
  execution of the demonstration scenario typically costs less than US$ 0.10.

### Browsers Tested

Google Chrome 120+, Mozilla Firefox 121+, Microsoft Edge 120+.

---

## 5. Installation

### 5.1 Quick Start (Docker Compose)

The Docker Compose path is the recommended way to run the artifact from a
fresh machine. The host only needs Docker and Docker Compose; Python, Node.js,
PostgreSQL, and project dependencies are installed inside the containers.

```bash
# 1. Install Docker Desktop, or Docker Engine with the Compose plugin.
#    Then verify that both commands are available:
docker --version
docker compose version

# 2. Enter the extracted artifact root
cd <extracted-artifact-directory>

# 3. Copy the environment template
cp .env.example .env

# 4. Start the full stack
docker compose up --build

# 5. Wait until db, backend, worker, and frontend report ready.
```

The stack starts without an OpenAI API key, but AI-assisted features require
`OPENAI_API_KEY`. To execute the complete AI-assisted workflow, edit `.env`
before starting the stack and set `OPENAI_API_KEY` (see Section 6).

Once the stack is up:

- **Frontend:** <http://localhost:5173>
- **Backend health check:** <http://localhost:8000/health>

If ports `8000` or `5173` are already in use on the host machine, edit `.env`
before starting the stack. For example:

```env
BACKEND_PORT=8001
FRONTEND_PORT=5174
VITE_API_URL=http://localhost:8001
```

Then open:

- **Frontend:** <http://localhost:5174>
- **Backend health check:** <http://localhost:8001/health>

To stop the stack:

```bash
docker compose down
```

### 5.2 Verifying the Installation

In another terminal, from the artifact root, run the basic smoke test. This test
validates authentication, project creation, canvas editing, invite creation,
and phase polling without calling the OpenAI API.

```bash
./scripts/smoke_test.sh
```

Expected output includes:

```
Token acquired
Project <id> created
Participant <id> joined
Smoke flow executed
```

If any step fails, inspect container logs:

```bash
docker compose logs -f backend worker
```

## 6. Configuration

The `.env.example` file lists all environment variables required by the
application. Copy it to `.env` and fill in real values. **Never commit `.env`
to any repository.**

OpenAI-backed execution:

```env
OPENAI_API_KEY=your_openai_api_key
LLM_MODEL=gpt-4o-mini
BACKEND_PORT=8000
FRONTEND_PORT=5173
VITE_API_URL=http://localhost:8000
```

### Which Features Work Without an OpenAI Key

If `OPENAI_API_KEY` is left empty, the application still supports project
creation and management, manual completion of the Problem Vision board,
collaborative workshop invitations, semantic differential scale assessment,
aggregation, and export. AI-assisted suggestions and synthesis require a
configured OpenAI API key.

---

## 7. Default Credentials (Seed Data)

The database is seeded with a demo account and the demonstration project used
in the paper.

- **Email:** `researcher@example.com`
- **Password:** `researcher123`
- **Demo project:** _Functional Correctness of AI Systems_

> These credentials are for reviewer/demo use only and must be changed for any
> real deployment.

---

## 8. Reproducing the Paper Demonstration

The following sequence reproduces the scenario reported in Section 4 of the
paper.

1. Log in with the seeded researcher account.
2. Open the demo project _Functional Correctness of AI Systems_.
3. **Phase 1 — Problem Vision Outline**: inspect the seven Problem Vision
   attributes and request an AI-assisted suggestion for at least one
   attribute (e.g., _Practical Problem_ or _Stakeholders_).
4. **Phase 2 — Problem Vision Alignment**: generate an invite URL and join
   as a participant via `/invite/{token}` in a separate browser session.
5. **Phase 3 — Research Problem Formulation**: trigger the holistic
   consistency-oriented refinement and inspect the AI-generated
   observations (gaps, duplications, ambiguities, suggested reformulations).
6. **Phase 4 — Research Problem Assessment**: submit an evaluation using
   the LRI semantic differential scale on _Value_, _Feasibility_, and
   _Applicability_.
7. **Phase 5 — Go / Pivot / Abort Decision**: inspect the aggregated
   assessment, the AI-generated synthesis, and the suggested decision;
   generate the summary and export the final artifact as PDF.

---

## 9. Expected Results

A successful execution of the scenario above is confirmed when:

- The user is able to authenticate and open the demonstration project.
- All seven Problem Vision attributes are visible and editable.
- AI-assisted suggestions are generated for the requested attributes and
  returned in a **structured format** aligned with the Problem Vision schema.
- Phase 3 produces at least one **consistency-oriented observation** (e.g.,
  a suggested refinement of a research question).
- The seven-point semantic differential scale accepts scores for all three
  criteria (_Value_, _Feasibility_, _Applicability_).
- Phase 5 produces an aggregated report containing median scores, the
  AI-generated synthesis, and a suggested Go / Pivot / Abort decision.
- The final artifact can be exported as PDF into the `exports/` folder.

> Because LLM outputs are non-deterministic, the exact textual content of
> AI-generated suggestions **is not expected to be identical** across
> executions when running with a real OpenAI key. The verifiable properties
> are the structural ones listed above: structural validity, presence of the
> seven attributes, non-empty mandatory fields, preservation of user edits,
> and successful export.

---

## 10. Repository Content

- **Frontend:** React application built with Vite; event-driven UI that
  communicates with the backend via asynchronous HTTP.
- **Backend:** FastAPI application with SQLAlchemy ORM and Alembic
  migrations; orchestrates business logic, authentication, and calls to the
  AI service layer.
- **Worker:** background service that handles longer-running AI calls,
  keeping the request/response cycle responsive.
- **Database:** PostgreSQL, storing projects, Problem Vision attribute
  versions, AI interactions, workshop invitations, assessments, and
  decisions.
- **docker-compose.yml:** local orchestration (db, backend, worker, frontend)
- **docs/:** supporting documentation, presentation video, and case study
- **exports/:** folder that contains the pdf generated by the tool
- **scripts/:** folder that contains the tools smoke tests

---

## 11. Limitations

- The current version depends on an external LLM provider and its
  availability. Latency and cost vary with provider load.
- LLM outputs are non-deterministic; textual suggestions may vary across
  executions. Structural properties (Section 9) are stable.
- Empirical evaluation with independent researchers and practitioners is
  planned as future work.
- Phase 2 (Problem Vision Alignment) and Phase 4 (Research Problem
  Assessment) are intentionally conducted without AI support in the current
  version, to preserve participant autonomy and avoid biasing human judgment.

---

## 12. Data, Privacy, and Ethical Considerations

- **Data collected during invited workshops:** participant name and company
  (optional). Consent is required at the invite-join step.
- **Data sent to the LLM provider:** text submitted by users to the
  AI service layer is forwarded to the configured LLM provider (OpenAI by
  default) and is subject to that provider's data-handling policies. Do not
  submit confidential material through the hosted demo.
- **Exported reports** are not anonymized by default; anyone with the export
  can see participant names and comments. Downstream anonymization is the
  responsibility of the exporting user.
- **Authentication:** the tool does not collect personally identifiable
  information beyond the account email.
- **Demonstration data:** the seeded scenario was derived from a workshop
  conducted with informed participants in December 2025 and does not include
  personally identifiable data.
- **No human-subjects data** is redistributed as part of this artifact.

---

## 13. License

Two licenses apply to this artifact:

- **Source code** (`backend/`, `frontend/`, `scripts/`, `docker-compose.yml`,
  and other executable content): **MIT License** — see `LICENSE`.
- **Documentation, video, case study, and other non-code materials**
  (`docs/` and `README.md`): **Creative Commons
  Attribution 4.0 International (CC BY 4.0)** — see `LICENSE-DOCS`.

---

## 14. Citation

If you use LRI Co-Assistant or this artifact package in your research, please
cite the paper and the artifact:

```bibtex
@inproceedings{theodoro2026lricoassistant,
  author    = {Theodoro, Jo{\~a}o Pedro and Figueiredo, Victoria Cruz de and
               Pereira, Anrafel Fernandes and Boquimpani, Wallace Albertini and
               Martins, Mariana Crisostomo and Kalinowski, Marcos},
  title     = {An {AI}-Assisted Tool for Practically Relevant Research
               Problem Formulation in Software Engineering},
  booktitle = {Proceedings of the 40th Brazilian Symposium on Software
               Engineering (SBES 2026), Tools Track},
  year      = {2026},
  address   = {S{\~a}o Paulo, Brazil},
  publisher = {ACM}
}

@misc{theodoro2026artifact,
  author    = {Theodoro, Jo{\~a}o Pedro and Figueiredo, Victoria Cruz de and
               Pereira, Anrafel Fernandes and Boquimpani, Wallace Albertini and
               Martins, Mariana Crisostomo and Kalinowski, Marcos},
  title     = {Artifact Package: An {AI}-Assisted Tool for Practically
               Relevant Research Problem Formulation in Software Engineering},
  year      = {2026},
  publisher = {Zenodo},
  note      = {Insert the version-specific artifact DOI after archival}
}
```

---

## 15. Badge Claims

This artifact targets both CBSoft 2026 Artifact Festival badges:

- **Available** — pending until the artifact is archived in a persistent
  public repository with a version-specific DOI. The repository already
  contains a `README` and a `LICENSE` in the root.
- **Functional** — the artifact is complete and executable via
  `docker compose up --build`; requirements and installation instructions
  are provided in Sections 4 and 5; a smoke test with expected results is
  provided in Section 5.2

---

## 16. Contact

For questions, bug reports, or collaboration inquiries:

- João Pedro Theodoro — <joaotheodoro@aluno.puc-rio.br>
- Marcos Kalinowski — <kalinowski@inf.puc-rio.br>

Institution: **Pontifical Catholic University of Rio de Janeiro (PUC-Rio)**
