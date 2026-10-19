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
| keyword baseline | dev sample (20) | 30.5 | 28.4 | 29.4 | 80.8 | $0 |
| Haiku 5.5, medium effort, prompt v1 | dev sample (20) | 59.0 | 45.6 | 51.4 | 92.5 | $0.003 / contract |
| Haiku 5.5, medium effort, prompt v2a (+ quoting rules) | dev sample (20) | 81.3 | 87.0 | 84.0 | 91.2 | $0.004 / contract |
| Haiku 5.5, medium effort, prompt v2b (+ field definitions) | dev sample (20) | 85.3 | 88.1 | 86.7 | 96.2 | $0.004 / contract |

## D8. Develop on Haiku 5.5, not Opus 5.5

- The 1-contract smoke test cost $0.062 on Opus vs $0.004 on Haiku, with identical scores (F1 40%, 12/12 presence correct).
- Prompt iteration runs many times, so it uses Haiku. Opus is run once on the final prompt for the model comparison.

## D9. Prompt v1 findings (Haiku, 20 dev contracts)

- **Boundary errors dominate (44):** the answers are usually right, but the quote extent differs from the labelling convention. Lawyers highlight only the name or date for Parties and the date fields, but whole sentences for clauses. The keyword baseline beats Haiku on Agreement Date (F1 64.5 vs 43.9) only because it quotes just the date.
- **False alarms (14)** cluster in interpretive fields: Non-Compete 4, Termination for Convenience 3, Effective Date 3. These are understanding errors, not formatting ones.
- **Low recall on multi-passage fields:** Parties (18.7%; lawyers label each name and each alias) and Cap on Liability (39.1%; often several separate passages).
- Validation: 1/20 first attempts contained a quote not in the contract; the retry fixed it.
- Caveat: 20 contracts is a small sample, and per-field numbers rest on a handful of examples.

## D11. Prompt v2a: quoting rules (ablation step 1)

- One change from v1: rules on how much to quote, matching CUAD's highlighting conventions (names and dates only for parties/dates; full sentences, every passage, for clauses).
- F1 51.4 → 84.0. Biggest gains: Parties 25.9 → 92.7, Agreement Date 43.9 → 95.2, Document Name 87.8 → 97.6. Boundary errors fell from 44 to 7.
- Most of v1's "errors" were therefore labelling-convention mismatches, not misunderstanding.
- False alarms rose slightly (14 → 17), and Non-Compete precision is 35%. All 6 Non-Compete false alarms were neighbouring CUAD categories the model doesn't know are separate: No-Solicit of Customers, No-Solicit of Employees, Exclusivity. That is the target for v2b (definitions with explicit exclusions).

## D12. Prompt v2b: definitions with explicit exclusions (ablation step 2)

- One change from v2a: an "Includes / Does not include" line for 8 judgement-heavy fields. Non-Compete's exclusions name the neighbouring categories it confused in v2a (non-solicitation of customers and employees, exclusivity).
- F1 84.0 → 86.7, false alarms 17 → 8, presence accuracy 91.2 → 96.2.
- Non-Compete precision 35.3 → 60.0 with recall unchanged at 100: the exclusions did not make the model over-cautious.
- Notice Period 85.7 → 100, Effective Date 66.7 → 75.0, Expiration Date 64.7 → 72.2.
- Regression: Cap on Liability 72.7 → 68.1. The unmatched quotes are mostly carve-outs ("except for indemnification obligations…"), which CUAD labels as a separate category, Uncapped Liability. One case (Verizon) is arguably a cap the labellers didn't mark. Candidate fix: exclude carve-outs explicitly.
- Overfitting risk: v1 → v2a → v2b were all judged on the same 20 contracts, and several fields have only 5–10 positive examples there. Next step is to confirm v2b on a larger dev sample before any further tuning.

## D10. Self-hosting: a focused comparison here, a deep dive as a separate project

- In this project: one open-source model (~7–14B) served with vLLM on a cloud GPU, run on the same contracts, prompt, validation and eval as Claude. Answers one question: API or self-hosted for this system?
- Not on the local machine: an RTX 3050 with 4 GB of GPU memory can't hold a 7B+ model plus a long contract's context.
- Done after the prompt is final, so the GPU runs only once.
- Deeper serving work (quantization, batching, latency, LoRA fine-tuning) is a separate follow-up project that reuses this eval as its benchmark, so it measures quality, not just speed.
