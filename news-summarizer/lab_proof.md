# Lab proof: two brains, zero single point of failure

This is the reviewer's entry point. It shows one article going through the
whole workflow: News API, then OpenAI (summary), then Cohere (sentiment), with
a second run where OpenAI fails and Cohere takes over.

Workflow: `trigger -> transform -> action`

- **Trigger:** `python main.py --category technology --count N`
- **Transform:** article text, then summary (OpenAI), then sentiment (Cohere)
- **Action:** printed result plus one line per call in `usage_log.jsonl`

## 1. Configuration

Settings come only from `.env` (git-ignored). The committed template,
`.env.example`, is exactly what was used, with real keys pasted in:

```bash
OPENAI_API_KEY=<your key from platform.openai.com>
COHERE_API_KEY=<your key from dashboard.cohere.com>
NEWS_API_KEY=<your key from newsapi.org>

ENVIRONMENT=development
MAX_RETRIES=3
REQUEST_TIMEOUT=30
DAILY_BUDGET=5.00
```

![Config check](screenshots/config%20setup.png)

Models: `gpt-4o-mini` (OpenAI) and `command-r-08-2024` (Cohere), both at $0.15
per million input tokens and $0.60 per million output tokens (checked
2026-10-19).

## 2. Input payload

One raw article exactly as News API returned it for
`GET /v2/top-headlines?category=technology&country=us&pageSize=1`
(the key is sent in the `X-Api-Key` header, not in the URL):

```json
{
  "status": "ok",
  "totalResults": 69,
  "articles": [
    {
      "source": {
        "id": "the-washington-post",
        "name": "The Washington Post"
      },
      "author": "Jolie Kerr",
      "title": "Show us your clutter, and we’ll tell you which generation you come from - The Washington Post",
      "description": "Experts say that the type of stuff you have at home — figurines, encyclopedias, old electronics, water bottles — reflects the culture of your formative years.",
      "url": "https://www.washingtonpost.com/home/2026/10/18/hallmarks-boomers-gen-x-millennials-seen-their-clutter/",
      "urlToImage": "https://www.washingtonpost.com/wp-apps/imrs.php?src=https://cloudfront-us-east-1.images.arcpublishing.com/wapo/IAZPK6V5G5CQXFZ7WPH5JFOS4Y.jpg&w=1440",
      "publishedAt": "2026-10-18T12:04:28Z",
      "content": "Each generation has its hallmarks slang, clothing, hair styles and historical touchstones that can give someone away as a boomer, a Gen Xer or a millennial. To those, add an unexpected generational s… [+22 chars]"
    }
  ]
}
```

### Field mapping

| News API field | Used for | Why / risk |
|---|---|---|
| `title` | Prompt text, result title | Always present; articles with a missing title or `[Removed]` are dropped |
| `description` | Prompt text | Often `null`; skipped when missing |
| `content` | Prompt text | Cut at 200 characters; the `[+22 chars]` marker is stripped. Often `null` |
| `source.name` | Result source | Falls back to `Unknown` |
| `url` | Result link | Falls back to an empty string |
| `author`, `urlToImage`, `publishedAt` | Not used | |

The text from `title`, `description` and `content` is wrapped in `<article>`
tags in the prompt, and any `<article>` or `</article>` inside it is removed so
an article cannot close the block early (prompt injection).

## 3. Execution trace

### Run A: normal run (3 articles)

`python main.py --category technology --count 3`

```
Fetching 3 technology articles...

1. Show us your clutter, and we’ll tell you which generation you come from - The Washington Post
   Source:    The Washington Post
   Link:      https://www.washingtonpost.com/home/2026/10/18/hallmarks-boomers-gen-x-millennials-seen-their-clutter/
   Summary:   The article discusses how the items people keep at home, such as figurines and old electronics, can indicate the generation they belong to. Experts suggest that these possessions are reflective of the cultural experiences and trends that shape each generation.  [openai]
   Sentiment: neutral - The article presents an informative analysis without expressing a positive or negative opinion.  [cohere]
   Cost:      $0.000107

2. "I Regretted It After Two Weeks": Homeowners Are Revealing The Popular Home Fads That Aren't Worth Trying Out - BuzzFeed
   Source:    Buzzfeed
   Link:      https://www.buzzfeed.com/dannicaramirez/design-trends-homeowners-followed-and-regret-fs2
   Summary:   Homeowners are sharing their regrets over popular home trends influenced by TikTok, with some feeling that these styles appeared modern but ultimately made their spaces feel dull and boring.  [openai]
   Sentiment: negative - Homeowners express disappointment with TikTok-inspired trends, finding them lacking in personality and charm.  [cohere]
   Cost:      $0.000097

3. Frustrated Windows 11 user makes free app that fixes OLED burn-in. Works on YouTube too - Neowin
   Source:    Neowin
   Link:      https://www.neowin.net/news/frustrated-windows-11-user-makes-free-app-that-fixes-oled-burn-in-works-on-youtube-too/
   Summary:   A frustrated Windows 11 user developed a free app designed to fix OLED burn-in issues, and it is compatible with YouTube as well.  [openai]
   Sentiment: positive - The user's initiative to create a solution for a problem has a positive impact.  [cohere]
   Cost:      $0.000085

Cost summary:
  openai  14 calls  $0.000662
  cohere  13 calls  $0.000674
  total   $0.001335 of $5.00 budget
```

Each article makes two calls, summary then sentiment, tagged with the
provider that answered. No `⚠️` line means no failure and no fallback.

### Run B: fallback (OpenAI fails, Cohere takes over)

For this one command only, the OpenAI key was replaced with an invalid value
(`.env` was not touched):
`OPENAI_API_KEY=sk-invalid python main.py --category technology --count 1`

```
Fetching 1 technology articles...
⚠️  openai failed, falling back to cohere

1. Show us your clutter, and we’ll tell you which generation you come from - The Washington Post
   Source:    The Washington Post
   Link:      https://www.washingtonpost.com/home/2026/10/18/hallmarks-boomers-gen-x-millennials-seen-their-clutter/
   Summary:   The article suggests that the clutter and possessions in your home can reveal your generational identity. Experts argue that the items we hold onto, from figurines to old electronics, reflect the cultural norms and trends of our formative years, providing insights into one's generation.  [cohere]
   Sentiment: neutral - The article presents an objective analysis of the connection between personal possessions and generational identity.  [cohere]
   Cost:      $0.000135  (fallback used)

Cost summary:
  openai  14 calls  $0.000662
  cohere  15 calls  $0.000808
  total   $0.001470 of $5.00 budget
```

An invalid key is a 401, which is not retried (retrying cannot fix it), so the
app switched provider on the first failure. The failed OpenAI call costs
nothing and is not logged. Both summary and sentiment were then answered by
Cohere, and the summary call is flagged `used_fallback: true`.

### The call log behind both runs (`usage_log.jsonl`)

One line is appended for every successful call. These are the lines written by
Runs A and B, in order. The first two are article 1 of Run A, the seventh is
the fallback summary of Run B:

```json
{"time": "2026-10-19T18:18:33+02:00", "provider": "openai", "model": "gpt-4o-mini", "input_tokens": 193, "output_tokens": 45, "cost": 5.5950000000000005e-05, "used_fallback": false}
{"time": "2026-10-19T18:18:36+02:00", "provider": "cohere", "model": "command-r-08-2024", "input_tokens": 249, "output_tokens": 22, "cost": 5.0549999999999995e-05, "used_fallback": false}
{"time": "2026-10-19T18:18:36+02:00", "provider": "openai", "model": "gpt-4o-mini", "input_tokens": 172, "output_tokens": 33, "cost": 4.5600000000000004e-05, "used_fallback": false}
{"time": "2026-10-19T18:18:39+02:00", "provider": "cohere", "model": "command-r-08-2024", "input_tokens": 237, "output_tokens": 26, "cost": 5.1149999999999996e-05, "used_fallback": false}
{"time": "2026-10-19T18:18:40+02:00", "provider": "openai", "model": "gpt-4o-mini", "input_tokens": 122, "output_tokens": 28, "cost": 3.51e-05, "used_fallback": false}
{"time": "2026-10-19T18:18:42+02:00", "provider": "cohere", "model": "command-r-08-2024", "input_tokens": 234, "output_tokens": 24, "cost": 4.95e-05, "used_fallback": false}
{"time": "2026-10-19T18:18:49+02:00", "provider": "cohere", "model": "command-r-08-2024", "input_tokens": 343, "output_tokens": 51, "cost": 8.205e-05, "used_fallback": true}
{"time": "2026-10-19T18:18:57+02:00", "provider": "cohere", "model": "command-r-08-2024", "input_tokens": 255, "output_tokens": 24, "cost": 5.265e-05, "used_fallback": false}
```

### What the trace does not show

Retries with backoff happen only on timeouts, HTTP 429 and 5xx errors, which I
could not trigger on demand with the live APIs. They are covered by unit tests
with simulated failures instead (`test_ask_retries_transient_error_then_succeeds`,
`test_ask_gives_up_after_max_retries`, `test_news_api_retries_server_error_then_succeeds`).

![49 tests passing](screenshots/pytest%20passes.png)

Screenshot of a separate 3-article `technology` run made after Run A (the
model wording and cost totals differ slightly from the text above, because
each run asks the models again):

![Main app run](screenshots/main%20run.png)

## 4. Output record

The final record for article 1 of Run A (the same article as the input payload
above), built from the log lines 1 and 2:

| Field | Value |
|---|---|
| Title | Show us your clutter, and we’ll tell you which generation you come from - The Washington Post |
| Source | The Washington Post |
| Link | https://www.washingtonpost.com/home/2026/10/18/hallmarks-boomers-gen-x-millennials-seen-their-clutter/ |
| Summary (OpenAI) | The article discusses how the items people keep at home, such as figurines and old electronics, can indicate the generation they belong to. Experts suggest that these possessions are reflective of the cultural experiences and trends that shape each generation. |
| Sentiment (Cohere) | neutral |
| Sentiment reason | The article presents an informative analysis without expressing a positive or negative opinion. |
| Cost | $0.000107 ($0.0000560 OpenAI + $0.0000506 Cohere) |
| Fallback used | No |

The summary stays within the input: figurines and old electronics come from the
`description`, and the generational point from the `content`.

## 5. Explain

**What is the first failure mode I would monitor if this ran daily?**
A provider failing silently. If an API key is revoked or a quota runs out, the
app keeps working because it falls back to the other provider, so nobody
notices until the second provider fails too. Every call is logged with
`used_fallback`, so I would watch the share of `used_fallback: true` lines in
`usage_log.jsonl` per day and alert when it rises above zero. A close second is
News API returning fewer articles than requested, which the app already reports
with a one-line note.

**Operational risks I accepted:**

- The daily budget is best effort. It is the sum of today's log lines, so
  deleting the file resets it and it cannot see spend made outside this app.
  A spending limit set in each provider's dashboard is the real cap.
- Prices are stored in `llm_providers.py` and will go stale.
- Prompt-injection protection reduces the risk but cannot remove it. A hostile
  article could still influence the summary text; the sentiment answer is
  checked against a fixed list, so it cannot return anything else.
