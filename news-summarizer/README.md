# Multi-Provider News Summarizer

Fetches top headlines from News API, has **OpenAI** write a short summary of
each article, then passes that summary to **Cohere** to rate its sentiment.
If either provider fails, the other one takes over, so neither is a single
point of failure. Every call is priced and logged, and a daily budget stops
the app before it overspends.

```
News API --> article text --(OpenAI)--> summary --(Cohere)--> sentiment
                               \______ either provider falls back to the other ______/
```

Cohere never sees the original article, only OpenAI's summary.

## Files

| File | Job |
|---|---|
| `config.py` | Reads settings from `.env` into one cached `Config` object (`get_config()`) |
| `news_api.py` | News API client: key in a header, retries, error handling |
| `llm_providers.py` | OpenAI + Cohere behind one interface: retries, rate limiting, fallback, cost tracking |
| `summarizer.py` | The pipeline: article, summary, sentiment, result |
| `main.py` | Interactive app and one-shot command line |
| `test_summarizer.py` | 49 unit tests, all with fakes (no network, no cost) |
| `usage_log.jsonl` | Created at run time: one line per LLM call (git-ignored) |

## Setup

You need Python 3.12 and three API keys: OpenAI
([platform.openai.com](https://platform.openai.com)), Cohere
([dashboard.cohere.com](https://dashboard.cohere.com)) and News API
([newsapi.org](https://newsapi.org)). The free tiers are enough.

```bash
cd news-summarizer
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # with uv: uv pip install -r requirements.txt

cp .env.example .env                   # then paste your real keys into .env
python config.py                       # should print "Configuration is valid"
```

`.env` is git-ignored. Never commit it. `.env.example` is the committed
template. Settings in it:

| Variable | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY`, `COHERE_API_KEY`, `NEWS_API_KEY` | required | API keys |
| `ENVIRONMENT` | `development` | Label only |
| `MAX_RETRIES` | `3` | Attempts per request before giving up |
| `REQUEST_TIMEOUT` | `30` | Seconds before a request times out |
| `DAILY_BUDGET` | `5.00` | USD per day across both providers |

## Run

```bash
python main.py                                    # interactive menu
python main.py --category technology --count 3    # one batch, then exit
python news_api.py        # checkpoint: fetch 3 headlines
python llm_providers.py   # checkpoint: ask both providers, show costs
python summarizer.py      # checkpoint: summarize 2 articles
pytest test_summarizer.py -v
```

Categories: business, entertainment, general, health, science, sports,
technology. `--count` accepts 1 to 5.

## Example output

```
$ python main.py --category technology --count 3

Fetching 3 technology articles...

(articles 1 and 2 left out here for space)
3. Frustrated Windows 11 user makes free app that fixes OLED burn-in. Works on YouTube too - Neowin
   Source:    Neowin
   Summary:   A frustrated Windows 11 user developed a free app designed to fix OLED burn-in issues, and it is compatible with YouTube as well.  [openai]
   Sentiment: positive - The user's initiative to create a solution for a problem has a positive impact.  [cohere]
   Cost:      $0.000085

Cost summary:
  openai  14 calls  $0.000662
  cohere  13 calls  $0.000674
  total   $0.001335 of $5.00 budget
```

Screenshots of a full run and of the passing tests are in
[`screenshots/`](screenshots/):

![Config check](screenshots/config%20setup.png)
![Tests passing](screenshots/pytest%20passes.png)
![Main app run, 3 articles](screenshots/main%20run.png)

## Cost analysis

Prices (USD per million tokens, checked 2026-10-19 on each provider's docs):

| Model | Input | Output |
|---|---|---|
| OpenAI `gpt-4o-mini` | $0.15 | $0.60 |
| Cohere `command-r-08-2024` | $0.15 | $0.60 |

Measured from the 29 calls logged on 2026-10-19 (`usage_log.jsonl`):

| | Calls | Avg input tokens | Avg output tokens | Avg cost per call |
|---|---|---|---|---|
| OpenAI (summary) | 14 | 150 | 41 | $0.000047 |
| Cohere (sentiment) | 15 | 253 | 27 | $0.000054 |

- One article (one summary call plus one sentiment call) costs about
  **$0.0001**. A three-article run measured $0.000085 to $0.000107 each.
- At that rate 1,000 articles cost about **$0.10**, and the default $5 daily
  budget would allow tens of thousands. Treat this as an estimate from a small
  sample, not a guarantee.
- Cohere is the larger half of the bill even though it writes less. Its input
  averages about 100 tokens more than OpenAI's, although it only reads a short
  summary, so the sentiment step is where to look first when optimizing.
- Cheap ways to cut cost further: cache results for articles already processed,
  lower `max_tokens`, or skip sentiment for articles with no description.

## How the main requirements are met

- **Fetch from an external API, handle errors:** `news_api.py` retries
  timeouts, rate limits and 5xx errors, and turns API errors into readable
  messages. A bad key fails immediately because retrying cannot help.
- **Two providers, chained:** OpenAI summarizes, Cohere rates the summary.
- **Fallback:** `ask_with_fallback()` tries the primary provider and, on
  failure, the other one. Fallback calls are marked `used_fallback` in the
  output and in the log.
- **Rate limiting:** one `RateLimiter` per provider spaces calls at least two
  seconds apart (30 per minute).
- **Cost tracking:** every call is priced from its token counts and appended to
  `usage_log.jsonl`. The daily budget is the sum of today's lines, so it
  survives restarts and resets each day.
- **Tests:** 49 tests cover config, News API handling, retries, fallback,
  budget, rate limiting, sentiment parsing, the pipeline, and prompt injection.
- **Configuration:** everything comes from environment variables; no key is in
  the code or the repository.

## Design decisions

- **One retry layer.** Both SDKs retry by default. That is turned off so
  retries happen once, in our code. Otherwise 3 attempts of ours times 3 of the
  SDK would send 9 requests per failure, hidden from the rate limiter and the
  cost tracker. The price is that we do not read `Retry-After` headers or add
  jitter the way the SDKs do.
- **Budget as an append-only log.** A running total can be overwritten by two
  programs at once and says nothing about what happened. Summing log lines
  avoids both problems and doubles as an audit trail.
- **Prompt injection.** Article text is untrusted. It is wrapped in `<article>`
  tags, the system prompt says to treat it as data, and any `<article>` or
  `</article>` inside the text is removed so an article cannot close the block
  early. This reduces the risk but cannot remove it.

## Limitations

- News API sometimes returns fewer articles than requested even when it reports
  more matches (for example 2 of 3 for `science`, see the
  [screenshot](screenshots/main%20run%20-%202%20API%20responses%20instead%20of%203.png)).
  The app prints a note when this happens.
- News API categories are loose, so a `technology` headline may not be about
  technology.
- The budget guard is best effort: deleting `usage_log.jsonl` resets it, and it
  only counts calls made through this app. Set a spending limit in each
  provider's dashboard for a hard cap.
- Prices are copied into `llm_providers.py` and will go stale. Re-check them.
- The optional async step (Step 8) was not built.
