# ScholarLens: Research Reading and Evidence Workspace

A grounded Q&A, structured extraction, cross-study comparison and evidence-board tool for research papers, with role-based and document-level access control.

## Features
- Register/login with roles (owner, reviewer, viewer)
- PDF upload with page-number and coordinate-aware chunking
- Permission-aware retrieval and grounded Q&A with citations
- Claim verification, with explicit abstention when evidence is missing
- Structured extraction (objective, methodology, population/dataset, findings, limitations)
- Cross-study comparison with a comparability check
- Evidence board with approve, reject, undo, and Markdown/CSV export

## How to run
Windows: run `start_all.bat` (or `start_all.ps1`) from the project root.
- Backend: http://localhost:8000 (API docs at /docs)
- Frontend: http://localhost:3000

## Tests
`backend_venv\Scripts\python.exe -m pytest backend/tests`

## Limitations and honest status
- Answers are generated extractively from retrieved passages (template-based, no large language model). Claim verification uses lexical and numerical overlap with the cited passage, not a trained entailment model.
- Evaluation so far used a small set of self-written questions and partly synthetic test documents. Reported figures are prototype results, not a rigorous benchmark.
- A comparison against a baseline RAG pipeline with precision@k and recall@k on real, independently labeled papers has not yet been completed.
- Retrieval and access control were tested on SQLite with NumPy ranking. PostgreSQL + pgvector via Docker was configured but not run, because Docker was unavailable.
- A brief flash of the login screen on page reload was addressed but not fully verified.
- Future work: real benchmark papers with hand-labeled ground truth, a proposed-versus-baseline evaluation, an LLM-based answer generator and verifier, and pgvector deployment.
