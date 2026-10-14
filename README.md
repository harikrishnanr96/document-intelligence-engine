# Document Intelligence Engine

**LLM clause extraction from commercial contracts, measured against lawyer labels.**

Turns a contract into validated JSON for 12 key clauses (parties, dates, governing law, renewal, termination, assignment, liability cap, non-compete), with a verbatim quote as evidence for every answer. Accuracy is measured with precision and recall against 13,000+ lawyer-highlighted passages from the [CUAD](https://www.atticusprojectai.org/cuad) dataset.

> 🚧 **Work in progress.** The evaluation harness and keyword baseline are done; LLM extraction is next. Cells marked `?` fill in as experiments run.

## Results (dev set, 415 contracts)

| System | Span precision | Span recall | Span F1 | Presence accuracy | Cost / contract |
|---|---:|---:|---:|---:|---:|
| Keyword baseline (no LLM) | 27.3% | 24.3% | 25.7% | 80.0% | $0 |
| LLM extraction | ? | ? | ? | ? | ? |

Final numbers will be reported once, on 95 held-out test contracts.

## Key findings so far

- **No OCR or vision model needed for these documents.** All 510 PDFs have a text layer, and plain text extraction preserved 99.9% (2,261 / 2,263) of the lawyer-labelled passages, at ~0.2 s and $0 per contract.
- **Keywords can't interpret.** The baseline raised 152 false Non-Compete alarms and missed clauses like *"shall not run banner advertisements for any of 2TheMart's competitors"*. Telling those apart is the job the LLM has to earn its cost on.

## How it works

```mermaid
flowchart LR
    A[Contract PDF] --> B[Parse<br/>PDF text layer]
    B --> C[Extract<br/>LLM + prompt + domain context]
    C --> D{Validate<br/>schema · rules · quote grounding}
    D -- fails --> C
    D -- passes --> E[Structured JSON]
    E --> F[Evaluate<br/>vs lawyer labels]
```

Every field returns three things:

```json
"governing_law": {
  "present": true,
  "evidence": ["This Agreement will be governed and construed in accordance with the laws of the State of California ..."],
  "value": "California"
}
```

- **Validation** has three layers: the JSON structure is enforced by the API; Pydantic rules check meaning (e.g. `present` requires evidence, dates must be real ISO dates); and every quote must actually appear in the contract, which blocks invented evidence.
- **Scoring**: a predicted passage counts as correct when it overlaps a lawyer's highlight by ≥ 50% (word-set Jaccard, as in the CUAD paper). Each field in each contract also gets an error label: missed, false alarm, boundary (right place, wrong extent) or wrong passage.

Design decisions and the evidence behind each are in [docs/decisions.md](docs/decisions.md).

## Run it

```bash
git clone https://github.com/harikrishnanr96/document-intelligence-engine.git
cd document-intelligence-engine
pip install -e ".[dev]"

python scripts/download_data.py      # fetches CUAD (~106 MB) into data/raw/
pytest                               # no dataset or API key needed
python scripts/run_baseline.py       # scores the keyword baseline on the dev set
```

## Roadmap

- [x] Ground-truth loader, deterministic dev/test split
- [x] Pydantic schema and three-layer validation
- [x] Eval harness (span precision/recall, presence accuracy, error types) and keyword baseline
- [ ] First LLM extraction
- [ ] Prompt and context engineering, with before/after scores per field
- [ ] Model trade-off: accuracy, cost and latency for a strong vs a cheap model, plus a vision (PDF-as-image) comparison
- [ ] `docintel extract contract.pdf` CLI with an OCR fallback for scanned PDFs
- [ ] Demo, charts and write-up

## Data and licence

Code: MIT. Data: [CUAD v1](https://www.atticusprojectai.org/cuad) by The Atticus Project, CC BY 4.0 ([paper](https://arxiv.org/abs/2103.06268)). The dataset isn't stored in this repo; `scripts/download_data.py` fetches it.
