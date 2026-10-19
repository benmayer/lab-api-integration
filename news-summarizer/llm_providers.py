"""LLM providers: OpenAI and Cohere behind one interface.

Handles retries, rate limiting, fallback between providers, and cost tracking.
"""

import json
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import cohere
import httpx
import openai

from config import get_config

# Both models were picked for being the cheap tier: this app sends short
# prompts and needs short answers, so a bigger model would only add cost.
OPENAI_MODEL = "gpt-4o-mini"
COHERE_MODEL = "command-r-08-2024"

# Price in USD per 1 million tokens: (input, output).
# Checked on 2026-10-19 against:
#   OpenAI: developers.openai.com/api/docs/models/gpt-4o-mini
#   Cohere: docs.cohere.com changelog (command-r-08-2024)
# Provider prices change. Re-check them before trusting the cost numbers.
PRICING = {
    OPENAI_MODEL: (0.15, 0.60),
    COHERE_MODEL: (0.15, 0.60),
}

# HTTP statuses worth retrying: timeout, rate limit, and server-side errors.
# Anything else (400 bad request, 401 bad key, ...) fails the same way every
# time, so retrying would only waste time and money.
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
OTHER_PROVIDER = {"openai": "cohere", "cohere": "openai"}

# Every successful call is appended here (JSON Lines: one JSON object per
# line), and the daily budget is computed from today's lines. It lives next to
# this file (not in the current directory) so every entry point, whatever
# folder it is run from, shares the same log. It is gitignored.
USAGE_LOG = Path(__file__).resolve().parent / "usage_log.jsonl"


class LLMError(Exception):
    """Raised when no provider could answer."""


class BudgetExceededError(LLMError):
    """Raised when the daily budget has been used up."""


@dataclass(frozen=True)
class LLMResponse:
    """One answer from a provider, with usage and cost."""

    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    used_fallback: bool = False


class CostTracker:
    """Adds up spend per provider and enforces the daily budget.

    If `log_file` is given, every successful call is appended to it as one
    JSON line (time, provider, model, tokens, cost, fallback). Today's spend
    is never stored as a running total: it is always the sum of today's lines.
    That keeps the budget across restarts, resets it each day (old lines are
    ignored), lets two programs write at the same time without overwriting
    each other, and leaves a record of what happened and when.

    This is a best-effort guard, not a hard limit:
      - deleting or editing the file resets it;
      - it only knows about calls made through this class, not spend made
        elsewhere with the same API keys.
    Set a spending limit in each provider's dashboard for a real cap.
    """

    def __init__(self, daily_budget, log_file=None):
        self.daily_budget = daily_budget
        self.log_file = Path(log_file) if log_file else None
        self.total = 0.0
        self.by_provider = {}
        self.calls = {}
        self._refresh()

    def calculate(self, model, input_tokens, output_tokens):
        """Return the USD cost of one call."""
        input_price, output_price = PRICING[model]
        return (input_tokens * input_price + output_tokens * output_price) / 1_000_000

    def check_budget(self):
        """Raise BudgetExceededError if spend has reached the daily budget."""
        self._refresh()  # pick up spend logged by any other running program
        if self.total >= self.daily_budget:
            raise BudgetExceededError(
                f"Daily budget of ${self.daily_budget:.2f} reached "
                f"(spent ${self.total:.4f})"
            )

    def record(self, response):
        """Add one LLMResponse to the totals and append it to the log."""
        self._add(response.provider, response.cost)
        if not self.log_file:
            return
        entry = {
            "time": datetime.now().astimezone().isoformat(timespec="seconds"),
            "provider": response.provider,
            "model": response.model,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "cost": response.cost,
            "used_fallback": response.used_fallback,
        }
        try:
            # One small write in append mode: lines from two programs don't mix.
            with self.log_file.open("a") as log:
                log.write(json.dumps(entry) + "\n")
        except OSError as error:
            # Failing to log should not fail a call that already succeeded.
            print(f"⚠️  Could not write {self.log_file.name}: {error}")

    def summary(self):
        """Return a printable cost summary."""
        lines = ["Cost summary:"]
        for provider, cost in self.by_provider.items():
            lines.append(f"  {provider:<7} {self.calls[provider]} calls  ${cost:.6f}")
        lines.append(f"  total   ${self.total:.6f} of ${self.daily_budget:.2f} budget")
        return "\n".join(lines)

    def _add(self, provider, cost):
        """Add one call to the in-memory totals."""
        self.total += cost
        self.by_provider[provider] = self.by_provider.get(provider, 0.0) + cost
        self.calls[provider] = self.calls.get(provider, 0) + 1

    def _refresh(self):
        """Rebuild the totals from today's lines in the log file."""
        if not self.log_file or not self.log_file.exists():
            return
        self.total, self.by_provider, self.calls = 0.0, {}, {}
        today = date.today().isoformat()
        skipped = 0
        try:
            lines = self.log_file.read_text().splitlines()
        except OSError as error:
            print(f"⚠️  Could not read {self.log_file.name}: {error}")
            return
        for line in lines:
            try:
                entry = json.loads(line)
                if entry["time"][:10] == today:  # local date, e.g. "2026-10-19"
                    self._add(entry["provider"], float(entry["cost"]))
            except (ValueError, KeyError, TypeError):
                skipped += 1  # e.g. a half-written line after a crash
        if skipped:
            print(f"⚠️  Skipped {skipped} unreadable line(s) in {self.log_file.name}")


class RateLimiter:
    """Makes sure calls to one provider are at least `min_interval` seconds apart.

    One limiter per provider, because each provider has its own quota. This is
    a simple spacing rule rather than a token bucket: it never allows bursts,
    which is fine for a small app that calls the APIs one article at a time.
    """

    def __init__(self, calls_per_minute):
        self.min_interval = 60.0 / calls_per_minute
        self._last_call = 0.0
        self._lock = threading.Lock()

    def wait(self):
        """Sleep if the last call was too recent."""
        with self._lock:
            delay = self._last_call + self.min_interval - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self._last_call = time.monotonic()


def _is_retryable(error):
    """True for errors worth retrying: rate limits, server errors, network problems."""
    if isinstance(error, (openai.APIConnectionError, httpx.TransportError)):
        return True
    return getattr(error, "status_code", None) in RETRYABLE_STATUS


class LLMProviders:
    """Ask OpenAI or Cohere, retry on transient errors, fall back to the other."""

    def __init__(self, calls_per_minute=30, usage_log=USAGE_LOG):
        cfg = get_config()
        self.max_retries = cfg.max_retries

        # Both SDKs retry failed requests by default (2 retries each). We turn
        # that off and retry in ask() instead. Otherwise the layers multiply:
        # 3 attempts of ours x 3 attempts of the SDK = 9 requests for one
        # failure, with the sleeps hidden from us and the rate limiter unable
        # to see the extra calls. One retry layer keeps the behaviour, the
        # timing and the MAX_RETRIES setting predictable.
        self._openai = openai.OpenAI(
            api_key=cfg.openai_api_key, timeout=cfg.request_timeout, max_retries=0
        )
        self._cohere = cohere.ClientV2(
            api_key=cfg.cohere_api_key, timeout=cfg.request_timeout, max_retries=0
        )
        self.costs = CostTracker(cfg.daily_budget, log_file=usage_log)
        self._limiters = {
            "openai": RateLimiter(calls_per_minute),
            "cohere": RateLimiter(calls_per_minute),
        }

    def ask(self, provider, prompt, system=None, max_tokens=300, used_fallback=False):
        """Ask one provider, retrying transient errors. Raises LLMError on failure.

        `used_fallback` only labels the answer (and its log line) as coming from
        a fallback; ask_with_fallback() sets it, callers normally leave it alone.
        """
        call = {"openai": self._call_openai, "cohere": self._call_cohere}[provider]
        self.costs.check_budget()

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            self._limiters[provider].wait()
            try:
                text, model, tokens_in, tokens_out = call(prompt, system, max_tokens)
            except Exception as error:  # the SDKs raise many types; filtered below
                last_error = error
                if not _is_retryable(error):
                    break
                if attempt < self.max_retries:
                    time.sleep(2 ** (attempt - 1))  # wait 1s, 2s, 4s, ...
                continue

            cost = self.costs.calculate(model, tokens_in, tokens_out)
            response = LLMResponse(
                text, provider, model, tokens_in, tokens_out, cost, used_fallback
            )
            self.costs.record(response)
            return response

        raise LLMError(f"{provider} failed: {last_error.__class__.__name__}: {last_error}")

    def ask_with_fallback(self, prompt, primary="openai", system=None, max_tokens=300):
        """Ask `primary`; if it fails, ask the other provider instead."""
        try:
            return self.ask(primary, prompt, system, max_tokens)
        except BudgetExceededError:
            # The budget is shared by both providers, so falling back would
            # just spend the same exhausted budget.
            raise
        except LLMError as primary_error:
            backup = OTHER_PROVIDER[primary]
            print(f"⚠️  {primary} failed, falling back to {backup}")
            try:
                return self.ask(backup, prompt, system, max_tokens, used_fallback=True)
            except LLMError as backup_error:
                raise LLMError(
                    f"All providers failed. {primary_error}; {backup_error}"
                ) from None

    def _call_openai(self, prompt, system, max_tokens):
        """One OpenAI chat call. Returns (text, model, input_tokens, output_tokens)."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self._openai.chat.completions.create(
            model=OPENAI_MODEL, messages=messages, max_tokens=max_tokens
        )
        usage = response.usage
        return (
            response.choices[0].message.content.strip(),
            OPENAI_MODEL,
            usage.prompt_tokens,
            usage.completion_tokens,
        )

    def _call_cohere(self, prompt, system, max_tokens):
        """One Cohere chat call. Returns (text, model, input_tokens, output_tokens)."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self._cohere.chat(
            model=COHERE_MODEL, messages=messages, max_tokens=max_tokens
        )
        # Cohere reports billed usage under usage.tokens, not usage.billed_units.
        tokens = response.usage.tokens
        return (
            response.message.content[0].text.strip(),
            COHERE_MODEL,
            int(tokens.input_tokens),
            int(tokens.output_tokens),
        )


if __name__ == "__main__":
    try:
        llm = LLMProviders()
        question = "In one sentence, what is an API?"

        for name in ("openai", "cohere"):
            answer = llm.ask(name, question, max_tokens=60)
            print(f"✅ {name} ({answer.model}): {answer.text}")
            print(f"   tokens in/out: {answer.input_tokens}/{answer.output_tokens}"
                  f"  cost: ${answer.cost:.6f}\n")

        answer = llm.ask_with_fallback(question, primary="openai", max_tokens=60)
        print(f"✅ fallback helper answered via {answer.provider}\n")
        print(llm.costs.summary())
    except (ValueError, LLMError) as error:
        print(f"❌ {error}")
        raise SystemExit(1)
