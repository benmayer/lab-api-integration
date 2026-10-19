# LAB | Two Brains, Zero Single Point of Failure

**Week 3 · Day 1 · API & Integration Patterns**

---

## 1. What you're building (in one sentence)

A small Python app that **fetches real news**, has **one AI write a summary**, has **a second AI judge the mood** (sentiment) of that summary, and **keeps working even if one AI goes down**.

```
   📰 News API          🧠 OpenAI             🧠 Cohere              📋 Output
  ┌───────────┐      ┌─────────────┐      ┌──────────────────┐    ┌──────────────┐
  │ Get top   │ ───▶ │ Summarize   │ ───▶ │ Sentiment of the │ ─▶ │ Title        │
  │ headlines │      │ the article │      │ summary          │    │ Summary      │
  └───────────┘      └─────────────┘      │ (pos/neg/neutral)│    │ Sentiment    │
                            ▲             └──────────────────┘    │ Cost         │
                            │  if one fails, the other takes over └──────────────┘
                            └───────────── FALLBACK ─────────────┘
```

**INPUT → TRANSFORM → OUTPUT.** That's the whole lab. Everything else is about making that path **reliable, cheap, and testable.**

> 📝 The original lab text says **Anthropic**. In our class we use **Cohere** instead. Wherever the lab says "Anthropic", read "Cohere".

---

## 2. Why this matters (the consulting angle)

A client doesn't care which AI you used. They care that:

| Client question | What you build to answer it |
|---|---|
| "What if OpenAI is down?" | **Fallback** to a second provider |
| "What if the network blips?" | **Retries** with a wait in between |
| "How much will this cost us?" | **Cost tracking** + a daily **budget limit** |
| "Will we get blocked by the API?" | **Rate limiting** (small pauses between calls) |
| "How do we know it works?" | **Unit tests** + a **run trace** |

> **No single point of failure** = no one component whose failure stops the whole system.

---

## 3. The 6 files and what each one does

| File | Job | Think of it as… |
|---|---|---|
| `config.py` | Reads your keys and settings from `.env` | The settings panel |
| `news_api.py` | Gets articles from newsapi.org | The input |
| `llm_providers.py` | Talks to OpenAI / Cohere, retries, fallback, costs | The engine room |
| `summarizer.py` | Summary → sentiment, for each article | The workflow |
| `test_summarizer.py` | Checks everything with **fake** AI answers (free) | The safety net |
| `main.py` | The interactive app you run | The front door |

You build them **in this order**. Each one has a **checkpoint**: don't move on until it passes.

---

## 4. How to work: build → run → check

```
Step 1-3   Setup folder, install, .env       ✅ files exist, pip install OK
Step 4     config.py                          ✅ Checkpoint 1: python config.py
Step 5     news_api.py                        ✅ Checkpoint 2: python news_api.py       → 3 articles
Step 6     llm_providers.py                   ✅ Checkpoint 3: python llm_providers.py  → both AIs answer + costs
Step 7     summarizer.py                      ✅ Checkpoint 4: python summarizer.py     → summary + sentiment
Step 8     async (OPTIONAL)                   ⏭  skip if short on time
Step 9     test_summarizer.py                 ✅ Checkpoint 5: pytest test_summarizer.py -v → all pass
Step 10    main.py                            ✅ Checkpoint 6: python main.py           → full app
```

**Golden rule:** one file → run it → green? → next file. Never write all six then run.

---

## 5. Before you start (5 minutes that save you an hour)

### Get 3 API keys
- **OpenAI**: platform.openai.com
- **Cohere**: dashboard.cohere.com (free trial key is enough)
- **News API**: newsapi.org (free tier is enough)

### Our class `.env` and `requirements.txt`
```
# .env (never commit this file)
OPENAI_API_KEY=<your key>
COHERE_API_KEY=<your key>
NEWS_API_KEY=<your key>
ENVIRONMENT=development
MAX_RETRIES=3
REQUEST_TIMEOUT=30
DAILY_BUDGET=5.00
```
In `requirements.txt`, replace `anthropic>=0.18.0` with **`cohere>=5.0.0`**.

### Activate your environment *every time* you open a terminal
```bash
conda activate bootcamp-env        # or: source venv/bin/activate
python -c "import sys; print(sys.executable)"   # check: is this the Python you expect?
```

### Protect your keys
- Keys go **only** in `.env`
- `.env` is listed in `.gitignore` **before your first commit**
- Commit a `.env.example` with placeholders instead, e.g. `OPENAI_API_KEY=<your key>`

> 🔴 A key pushed to GitHub is a leaked key, even if you delete it a minute later. Rotate it immediately.

---

## 6. The 5 errors you will probably hit (and the fix)

| You see… | What it means | Fix |
|---|---|---|
| `AttributeError: module 'config' has no attribute 'XYZ'` | One file uses a different name than `config.py` defines (e.g. `NEWS_API_KEY` vs `news_api_key`) | Open `config.py`, see the real names, use them **consistently** in every file |
| `No module named 'cohere'` (but you installed it!) | You installed into one Python, you're running another | Activate the right env, then `pip install -r requirements.txt` again |
| `Missing required configuration` | A key in `.env` is empty or still says `<your key>` | Paste the real key, no quotes, no spaces |
| `UnicodeEncodeError … '✅'` (Windows) | Your terminal can't print emojis ✅❌ | Run `$env:PYTHONIOENCODING="utf-8"` first |
| `EOFError` when running `main.py` | The app is waiting for you to type | Type a category or press Enter |

**When stuck:** read the **last line** of the error first, then the **file + line number** above it.

---

## 7. Using Codex effectively in this lab: smart, fast, and honest

The goal is not to make Codex do the lab for you. Use it to understand, review, debug, and verify your own work. Clear instructions make Codex faster and reduce unnecessary token usage.

### The rule
✅ **Allowed:** AI as a **reviewer, debugger, explainer**
❌ **Not allowed:** "write my lab / write my proof for me"

### The big mistake: copy-pasting everything
```
❌  [pastes the whole lab page + all 6 files + 200-line error] "fix it"
    → thousands of tokens, slow, generic answer, you learn nothing

✅  "news_api.py line 20 raises AttributeError: module 'config' has no
     attribute 'NEWS_API_KEY'. Check config.py and tell me the mismatch."
    → short, fast, precise, and you still write the fix
```
Codex is running **inside your project folder**, so it can **read your files itself**. Don't paste them, just **name them**.

**Token-saving rule:** give Codex the smallest useful context: the file name, the command you ran, the last 5-10 lines of the error, and exactly what you want to know or change.

### Step 1: Write the rules once, in `AGENTS.md`
Codex automatically reads a file called **`AGENTS.md`** in your project folder at the start of every session. Put your standing rules there **once**, instead of retyping them in every prompt.

Create `news-summarizer/AGENTS.md` (keep it short: it's loaded every time, so every line costs tokens):

```markdown
# AGENTS.md

## Project
Multi-provider news summarizer (bootcamp lab).
News API → OpenAI (summary) → Cohere (sentiment). Fallback between providers.

## Environment
- Python env: bootcamp-env (conda). Run tests: `pytest test_summarizer.py -v`
- Settings live in config.py as a Config object: use `get_config()` and lowercase names.

## How to help me (I am learning)
- Do NOT write whole files or the final lab_proof.md / README for me.
- Explain the cause in max 5 bullets, then point to file + line.
- Suggest the smallest fix; let me type it.
- Never print or ask for my API keys. Never touch .env.
```

> 💡 Codex can draft one for you with **`/init`**. Then **cut it down** to ~15 lines like the one above.

### Step 2: Prompt like a consultant: small, specific, one thing
Use this shape: **Where + What happened + What you want**. Always give Codex a clear boundary.

| Situation | Good short prompt |
|---|---|
| Error | "Running `python summarizer.py` fails. Last line: `<paste last 5-10 lines>`. Why?" |
| Understand code | "Explain `ask_with_fallback` in llm_providers.py in 5 bullets." |
| Review before moving on | "Review news_api.py only. List 3 risks. Don't rewrite it." |
| Tests failing | "Run `pytest -v`. For the first failing test only, tell me why." |
| Before submitting | Use the reviewer prompt below |

### Step 3: Use Codex efficiently: 7 habits
1. **Name files, don't paste them.** Codex can read them.
2. **Paste only the last 5-10 lines of an error**, not the whole terminal.
3. **Work in small steps.** Ask Codex to inspect, explain, or fix one thing at a time.
4. **Long chat getting slow?** Type **`/compact`** and press Enter. Codex keeps the important working context while reducing the conversation size.
5. **Ask for a small fix**, not "rewrite the file".
6. **Ask for short answers**: "in 5 bullets", "one sentence", "just the line number".
7. **Start a new chat after a completed milestone** when the previous discussion is no longer useful.

**Recommended checkpoint loop:** ask Codex to inspect one file, make the smallest change, run the checkpoint command, and explain the result. Then move to the next file. This keeps the conversation focused and makes errors easier to diagnose.

### Most useful Codex commands for this lab

Use these commands after you have created the project. Type the command in the Codex chat and press Enter. Command availability can vary slightly between the Codex app, IDE extension, and CLI.

| Command | Use it when | What it does in this lab |
|---|---|---|
| **`/init`** | Creating project instructions | Creates a starting `AGENTS.md`. Review it and keep only useful project rules. |
| **`/review`** | Reviewing your work before a checkpoint or submission | Asks Codex to inspect local code changes and report risks. Ask it not to rewrite the files. |
| **`/diff`** | Inspecting what changed | Shows the changes so you can check that only the intended files were modified. |
| **`/compact`** | Continuing a long conversation | Reduces the current chat context while preserving useful working state. Type it with no arguments. |
| **`/new`** | Starting a clean session | Starts a new conversation when the old chat is no longer useful. If your client does not support `/new`, use its New Chat button. |
| **`/status`** | Checking the current session | Shows session/workspace information and, where supported, context or rate-limit information. |
| **`/model`** | Choosing a model | Displays or changes the model used for the session, if your client allows model selection. |
| **`/approvals`** | Understanding permission levels | Shows or changes when Codex must ask before running commands or modifying files. Keep approval settings conservative while learning. |

### A practical command sequence

Use this sequence during the lab:

1. **`/init`** once, then review `AGENTS.md`.
2. Build one file and run its checkpoint command.
3. Use **`/diff`** to inspect the change.
4. Use **`/review`** to ask for risks or missing checks.
5. If the chat becomes long, use **`/compact`**.
6. After a completed milestone, use **`/new`** or the New Chat button for a clean session.

Do not use `/compact` or `/new` as a substitute for saving important work. Code changes are in your files; decisions and next steps can be saved in `progress.md` for a future chat.

> **Important:** `/compact` preserves context for the current chat; it does not create a file that you can import into a new chat. Before starting a new chat, ask Codex to save a handoff summary in `progress.md`. In the new chat, say: **"Read `progress.md` and continue the work."**

`/compact` is for continuing the **same** chat. `progress.md` is an optional handoff file for continuing in a **new** chat.


### Step 4: Reuse your best prompts with templates
Found a prompt that works? Save it as a prompt template, e.g. `prompts/debug.md`, and reuse it. We call it `debug.md`—not `skills.md`—because this is only a saved prompt, not a Codex skill:
```
Read the error below. Find the root cause in my code (file + line).
Explain in max 3 bullets. Suggest the smallest fix. Do not rewrite the file.
ERROR:
```
Then just say: *"Use prompts/debug.md with this error: …"* This saves you from rewriting the same instructions every time. A real Codex skill is a separate folder with a required `SKILL.md` file and optional supporting files.

Students do not need to create a skill for this lab. Use `AGENTS.md` for permanent project rules and `prompts/debug.md` for a prompt you want to reuse manually. A real Codex skill is a separate folder with a required `SKILL.md` file and optional supporting files.

### The reviewer prompt (from the lab, use before you submit)
```
Role: Workflow reviewer
Task: Challenge my event-flow plan before I build or submit.
Inputs: trigger, sample payload, destination schema, and proof plan.
Constraints: Do not build the workflow for me. Find brittle mappings and missing checks.
Output format: three workflow risks, two trace checks, and one simplification.
Verification: Name the execution evidence that proves the workflow ran.
```

---

## 8. What you submit (one GitHub repo URL)

```
news-summarizer/
├── config.py, news_api.py, llm_providers.py,
│   summarizer.py, test_summarizer.py, main.py   ← code
├── requirements.txt, .gitignore, .env.example   ← config (NO real .env!)
├── AGENTS.md        ← your Codex rules (optional, nice to show)
├── README.md        ← what it does, setup, how to run, example output, cost analysis
├── lab_summary.md   ← ONE short paragraph: challenges, fixes, learnings, improvements
├── lab_proof.md     ← ⭐ reviewer starts here
└── screenshots/     ← pytest passing + main.py processing 3-5 articles
```

### `lab_proof.md`: the reviewer's entry point
It must contain these 4 things:

1. **Configuration**: your `.env.example` / settings used
2. **One input payload**: one raw article as it came from News API
3. **One execution trace**: the terminal output of one run (which provider did what, retries, fallback)
4. **One output record**: the final title + summary + sentiment + cost

---

## 9. Final checklist ✔

- [ ] All 6 checkpoints passed
- [ ] `pytest` → all green
- [ ] App processed 3-5 articles (screenshot)
- [ ] OpenAI = summary, Cohere = sentiment
- [ ] Fallback works (tip: break one key on purpose and watch it switch!)
- [ ] Cost summary shown
- [ ] **No API keys in the repo**
- [ ] `lab_proof.md` exists and has the 4 items

---

## 10. Think about this while you build

> **If this ran every morning for a client, what is the first thing that would break, and how would you notice?**

You'll answer this in your reflection.

### Optional stretch (finished early?)
Caching · SQLite storage · Web UI (Flask/FastAPI) · Scheduling · Email reports · Add Gemini as a 3rd provider · Trending topics
