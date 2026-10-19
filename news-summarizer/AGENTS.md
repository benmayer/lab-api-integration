# AGENTS.md

Multi-provider news summarizer for the Ironhack Week 3 API-integration lab ("Two brains, zero single point of failure"). Lab instructions and grading rubric live one level up (`../instructions.md`, `../rubric.md`). The lab is submitted as a PR with a `lab_proof.md` (workflow config, one execution trace, one input payload, one output record).

The lab asks for the AI to be used for review/critique only, not to write the final artifacts. Prefer reviewing and explaining over generating the user's lab code.

## Commands

```bash
pip install -r requirements.txt
python config.py        # Checkpoint 1: validate env config
python news_api.py      # Checkpoint 2: fetch 3 tech headlines
python llm_providers.py # Checkpoint 3: test both LLM providers + cost tracking
pytest                  # tests in test_summarizer.py
pytest test_summarizer.py::test_name   # single test
```

## Architecture

Flat module layout, each module runnable on its own via `if __name__ == "__main__"` as a checkpoint:

- `config.py`: `get_config()` returns a cached frozen `Config` dataclass built from env vars (via `python-dotenv`). Raises `ValueError` listing missing required keys; placeholder values like `<your key ...>` count as missing.
- `news_api.py`: `NewsAPIClient.get_top_headlines()` calls newsapi.org with the key in the `X-Api-Key` header, retries timeouts/429/5xx with exponential backoff, raises `NewsAPIError`, and drops `[Removed]` articles.
- `llm_providers.py`, `summarizer.py`, `main.py`, `test_summarizer.py`: currently empty (not yet implemented).

## Conventions

- Settings come only from `get_config()`; don't read `os.environ` elsewhere.
- Never put API keys in URLs, logs or output. `.env` is gitignored; `.env.example` is the committed template.
- Errors surface as `ValueError` (config) or `NewsAPIError`; entry points print `❌ message` and `raise SystemExit(1)`.

## Gotchas

- The lab's `requirements.txt` lists `anthropic` and `ANTHROPIC_API_KEY`, but this project uses **Cohere** instead (`cohere`, `COHERE_API_KEY`). Keep that substitution consistent in new code, docs and `lab_proof.md`.
- Required keys: `OPENAI_API_KEY`, `COHERE_API_KEY`, `NEWS_API_KEY`. Optional: `ENVIRONMENT`, `MAX_RETRIES` (3), `REQUEST_TIMEOUT` (30), `DAILY_BUDGET` (5.00).
