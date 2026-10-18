# Golden dataset for scored LLM evals

Each `<TICKER>_context.txt` is the computed context string the CLI would hand
to the language model for that ticker, derived offline from the committed
EDGAR fixtures in `tests/fixtures/` (no network I/O). `responses/` caches
model responses so a repeated eval run does not re-bill the model (T048).

Regenerate contexts with:

```powershell
python tests/evals/golden/generate_contexts.py
```

Produced by the Copilot CLI on 2026-10-19 from the committed fixtures.