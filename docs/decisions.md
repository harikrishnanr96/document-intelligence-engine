# Design decisions

Each decision with the evidence behind it. This log is the source for the README and write-ups.

## D1. Dataset: CUAD v1

- 510 commercial contracts from SEC filings, 41 clause categories, lawyer-highlighted passages as labels.
- Chosen because the labels make accuracy measurable instead of judged by eye.
- Profile: contracts are ~8K tokens at the median and ~85K at most, so a whole contract fits in one model call and no chunking is needed. Clause presence ranges from 100% (Parties) to 3% (Price Restrictions), so correctly reporting "absent" matters as much as finding clauses.

## D2. Parser: PDF text layer, not OCR or multimodal

- All 510 PDFs have a text layer.
- On 80 random contracts, `pypdf` text extraction preserved **2,261 of 2,263 (99.9%)** gold passages verbatim, at ~0.2 s and $0 per contract.
- Rule: use the cheapest parser that keeps the evidence you need, and prove it against the labels. OCR or multimodal is only for documents without a usable text layer, and that is a separate, optional experiment on simulated scans.

## D3. Fields: 12 of the 41 categories

- 6 factual fields (Document Name, Parties, Agreement/Effective/Expiration Date, Governing Law) and 6 interpretive fields (Renewal Term, Notice Period to Terminate Renewal, Termination for Convenience, Anti-Assignment, Cap on Liability, Non-Compete).
- The mix makes the "what did well vs didn't" analysis meaningful. Adding fields is one registry entry (`src/docintel/fields.py`).

## D4. Output shape: present + evidence + value

- `evidence` holds verbatim quotes, which are scored against CUAD and must point at real text; this is the main guard against invented answers.
- `value` holds the normalized answer a user wants (ISO date, state name, short summary). It is not scored, because CUAD's normalized answers are sparse and inconsistent (e.g. `[]/[]/2000`).
- Dates may be `null` while the clause is present: CUAD's README notes that expiration dates are often computed from other fields ("five years after the Effective Date").

## D5. Validation in three layers

1. Structure: the API's structured outputs enforce the JSON shape.
2. Meaning: Pydantic rules (present ⇔ evidence, real ISO dates, no blank or duplicate quotes).
3. Grounding: every quote must appear in the contract (ignoring case, spacing and punctuation; `...` elisions allowed).

Failures are recorded, not raised, so the eval can report how often each layer fired.

## D6. Metrics

- **Span precision and recall**: a predicted passage matches a gold passage when word-set Jaccard ≥ 0.5 (the CUAD paper's threshold).
- **Presence accuracy**: whether the clause was correctly reported as present or absent; this is where correct "absent" answers get credit.
- **Outcome labels** for every (contract, field) pair: hit, partial_hit, boundary (right place, wrong extent), wrong_passage, missed, false_alarm, correct_absent.

## D7. Dev/test split

- A deterministic split from a hash of the contract id: 415 dev, 95 test.
- Prompts are tuned only on dev; test is scored once at the end.

## Results log

| run | split | span P | span R | span F1 | presence acc | cost |
|---|---|---:|---:|---:|---:|---:|
| keyword baseline | dev (415) | 27.3 | 24.3 | 25.7 | 80.0 | $0 |
