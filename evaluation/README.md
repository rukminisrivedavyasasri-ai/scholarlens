# Evaluation Benchmark Suite: ScholarLens

This directory houses the evaluation harness, gold-standard ground-truth templates, test cases, and automated metrics calculation scripts for the **Research Reading and Evidence Workspace**.

## 1. Directory Structure

```
evaluation/
├── ground_truth_templates/
│   ├── annotations_schema.json     # Formal JSON schema for ground-truth annotations
│   └── sample_gold_standard.json   # Concrete labeled example for imitation
├── test_cases/
│   ├── retrieval_cases.json        # Test queries with gold-standard relevant passage IDs
│   ├── verification_cases.json     # Claims with labeled support states (supported/partial/unsupported)
│   └── acl_negative_cases.json     # Negative security assertions (unauthorized document IDs per user)
├── benchmark_dataset/              # Place open-access PDFs here (e.g. PubMed Central / arXiv)
│   └── README.md
├── results/                        # Auto-generated CSV and Markdown benchmark reports
└── run_evaluation.py               # Evaluation execution script
```

## 2. Ground-Truth Labeling Template

To add a new paper to the gold-standard benchmark:
1. Copy `evaluation/ground_truth_templates/sample_gold_standard.json` or create a new JSON file following `annotations_schema.json`.
2. Provide the document metadata (title, DOI, open-access URL).
3. Annotate the 5 canonical structured extraction fields:
   - `objective`
   - `methodology`
   - `population`
   - `findings`
   - `limitations` (or set `is_unavailable: true` with rationale if omitted by authors)
4. Add question-answer evaluation pairs with:
   - Gold-standard answer text
   - Gold-standard passage citations (page number, start offset or verbatim excerpt)
   - Atomic claims with ground-truth support state: `SUPPORTED`, `PARTIALLY_SUPPORTED`, or `UNSUPPORTED`
   - Flag `is_unanswerable: true` if the question cannot be answered from the document, to test model abstention.

## 3. Metrics Computed

When `python evaluation/run_evaluation.py` is executed, it measures and contrasts both the **Proposed Pipeline** and the **Baseline RAG**:
- **Retrieval Precision@k & Recall@k**: Percentage of retrieved passages that match gold-standard citations.
- **Extraction Accuracy**: Semantic similarity and field-level exact match across the 5 canonical dimensions.
- **Citation Support Rate**: Fraction of generated claims whose cited passages actually substantiate the statement (NLI entailment).
- **Comparability & Contradiction Accuracy**: Correct identification of false contradictions vs true empirical divergence.
- **Abstention Accuracy**: Does the system explicitly report "insufficient evidence" on unanswerable queries?
- **Access Control Correctness**: 100% negative test requirement — zero unauthorized passages leaked.
