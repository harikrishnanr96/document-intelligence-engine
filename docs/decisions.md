# Design decisions

Each decision with the evidence behind it. This log is the source for the README and write-ups.

## D1. Dataset: CUAD v1

- 510 commercial contracts from SEC filings, 41 clause categories, lawyer-highlighted passages as labels.
- Chosen because the labels make accuracy measurable instead of judged by eye.
- Profile: contracts are ~8K tokens at the median and ~85K at most, so a whole contract fits in one model call and no chunking is needed. Clause presence ranges from 100% (Parties) to 3% (Price Restrictions), so correctly reporting "absent" matters as much as finding clauses.

## D2. Parser: PDF text layer, not OCR or multimodal

- All 510 PDFs have a text layer.
- On 80 random contracts, `pypdf` text extraction preserved **2,261 of 2,263 (99.9%)** gold passages verbatim, at ~0.2 s and $0 per contract. (Superseded by the full-corpus check in D14: 98.1% for our 12 fields.)
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
| Haiku 5.5, medium effort, prompt v1 | fresh dev (80, not used for tuning) | 52.8 | 35.9 | 42.7 | 91.1 | $0.004 / contract |
| Haiku 5.5, medium effort, prompt v2b | fresh dev (80, not used for tuning) | 79.9 | 77.1 | 78.4 | 93.8 | $0.005 / contract |

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

## D13. Fresh-contract check: gains are real; freeze prompt v2b

- v1 and v2b re-run on 80 dev contracts never used for tuning (`--n 100 --exclude-sample 20`).
- Both dropped ~8 points versus the tuning set (v1 51.4 → 42.7, v2b 86.7 → 78.4), and the v1 → v2b gain held (+35.3 on tuning, +35.7 fresh). An equal drop for both means the fresh contracts are harder, not that v2b overfit.
- Honest dev number for v2b: **F1 78.4** (P 79.9, R 77.1, presence accuracy 93.8).
- Per field: factual fields strong (Document Name 96.3, Governing Law 93.9, Parties 86.9, Agreement Date 83.8). Weakest: Non-Compete 56.7 (recall 54), Effective Date 61.2 (14 boundary errors), Cap on Liability 66.5, Anti-Assignment 68.2.
- Most common remaining error is `partial_hit` (153): on multi-passage fields the model finds some passages but not all.
- Validation: 16/80 first attempts (20%) quoted text not in the contract (0/80 under v1; short exact quotes are easier to get slightly wrong). The retry fixed 15; 1 unsupported quote was dropped.
- Decision: freeze v2b. Further tuning would need studying these 80 contracts' errors, which would use up another fresh check. The weak fields are documented as known limitations.

## D14. Parse step: pypdf text layer + header/footer removal

- `parse.py`: read each page's text layer; refuse PDFs averaging under 100 characters per page as scans (OCR is out of scope, and empty text would silently produce "nothing found"); remove lines that repeat in the top or bottom 3 lines of at least half the pages. Page numbers ("Page 3 of 9", "- 2 -") count as one repeated line; any other line must repeat exactly, so numbered headings like "ARTICLE 3" survive (a unit test caught an earlier version that would have deleted them).
- Checked on all 510 CUAD PDFs (`scripts/check_parsing.py`, no API cost): 0 refused as scans; headers/footers removed in 327 of 505; 5 PDFs couldn't be matched to their label record by file name.
- Strict check (every word of the passage, in order, ignoring case/spacing/punctuation): **98.1%** of the 7,032 lawyer passages for our 12 fields are found in the raw PDF text, **98.0%** after cleanup. The earlier 99.9% was a sample of 80 contracts across all 41 categories; the full-corpus number for our fields is the one to quote.
- The ~2% misses are small text differences, not lost content: superscript ordinals split by the PDF ("1st" → "1 st"), passages that cross a page break, and quirks in CUAD's own text that the labels copy (e.g. "17t h day of February", a truncated "AGREEMENT, d"). In most misses every word is present. Scoring uses word overlap, which tolerates these, so the end-to-end impact should be smaller; the PDF-input extraction run will measure it.
- Cleanup cost: 9 passages (0.1%) stopped matching, all of which had a header or footer inside them in CUAD's text.
- Speed: ~0.9 s per PDF with pypdf 6.

## D10. Self-hosting: a focused comparison here, a deep dive as a separate project

- In this project: one open-source model (~7–14B) served with vLLM on a cloud GPU, run on the same contracts, prompt, validation and eval as Claude. Answers one question: API or self-hosted for this system?
- Not on the local machine: an RTX 3050 with 4 GB of GPU memory can't hold a 7B+ model plus a long contract's context.
- Done after the prompt is final, so the GPU runs only once.
- Deeper serving work (quantization, batching, latency, LoRA fine-tuning) is a separate follow-up project that reuses this eval as its benchmark, so it measures quality, not just speed.
