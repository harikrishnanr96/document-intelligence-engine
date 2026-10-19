# Results

Summaries of the runs quoted in the README and in [docs/decisions.md](../docs/decisions.md). Each folder holds:

- `summary.md`: the per-field score table
- `summary.json`: the same scores plus run settings (model, effort, prompt version), cost, time and validation counts

Full per-contract outputs stay in `runs/`, which is not committed. Re-running the same command with the same settings reproduces a run on the same contracts (fixed sample seed).

| Run | Command | Span F1 |
|---|---|---:|
| [Keyword baseline, 415 dev contracts](20261014-125728-baseline-dev/summary.md) | `python scripts/run_baseline.py` | 25.7 |
| [Haiku 5.5, prompt v1, 20 dev contracts](20261015-210154-claude-haiku-5-5-medium-v1-dev20/summary.md) | `python scripts/run_extraction.py --n 20 --prompt v1` | 51.4 |
| [Haiku 5.5, prompt v2a, 20 dev contracts](20261016-121534-claude-haiku-5-5-medium-v2a-dev20/summary.md) | `python scripts/run_extraction.py --n 20 --prompt v2a` | 84.0 |
| [Haiku 5.5, prompt v2b, 20 dev contracts](20261019-122341-claude-haiku-5-5-medium-v2b-dev20/summary.md) | `python scripts/run_extraction.py --n 20 --prompt v2b` | 86.7 |
| [Haiku 5.5, prompt v1, 80 fresh dev contracts](20261019-140804-claude-haiku-5-5-medium-v1-dev80/summary.md) | `python scripts/run_extraction.py --n 100 --exclude-sample 20 --prompt v1` | 42.7 |
| [Haiku 5.5, prompt v2b, 80 fresh dev contracts](20261019-141153-claude-haiku-5-5-medium-v2b-dev80/summary.md) | `python scripts/run_extraction.py --n 100 --exclude-sample 20 --prompt v2b` | 78.4 |

The 20-contract runs were used to tune the prompt; the 80-contract runs were not, so they are the honest dev numbers.
