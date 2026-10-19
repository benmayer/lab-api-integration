"""Interactive news summarizer.

Run it with no arguments for the interactive menu, or give --category and/or
--count to process one batch and exit (handy for scripts and screenshots):

    python main.py
    python main.py --category science --count 3
"""

import argparse

from llm_providers import LLMError
from news_api import NewsAPIError
from summarizer import ArticleResult, NewsSummarizer

# The categories News API accepts for top headlines.
CATEGORIES = ("business", "entertainment", "general", "health",
              "science", "sports", "technology")
DEFAULT_CATEGORY = "technology"
DEFAULT_COUNT = 3
MAX_COUNT = 5  # keeps a run cheap and inside the free News API tier


def print_result(number, result: ArticleResult):
    """Print one processed article."""
    print(f"\n{number}. {result.title}")
    print(f"   Source:    {result.source}")
    print(f"   Link:      {result.url}")
    print(f"   Summary:   {result.summary}  [{result.summary_provider}]")
    print(f"   Sentiment: {result.sentiment} - {result.sentiment_reason}"
          f"  [{result.sentiment_provider}]")
    print(f"   Cost:      ${result.cost:.6f}"
          f"{'  (fallback used)' if result.used_fallback else ''}")


def process_batch(summarizer, category, count):
    """Fetch, process and print one batch, then the running cost summary."""
    print(f"\nFetching {count} {category} articles...")
    try:
        results = summarizer.run(category=category, count=count)
    except NewsAPIError as error:
        print(f"❌ Could not fetch news: {error}")
        return
    except LLMError as error:
        print(f"❌ {error}")
        return

    if not results:
        print("❌ No articles were processed")
        return

    for number, result in enumerate(results, start=1):
        print_result(number, result)
    print(f"\n{summarizer.llm.costs.summary()}")


def ask_category():
    """Ask for a category. Returns None when the user wants to quit."""
    while True:
        answer = input(f"\nCategory [{DEFAULT_CATEGORY}] "
                       f"({', '.join(CATEGORIES)}), or 'q' to quit: ").strip().lower()
        if answer in ("q", "quit", "exit"):
            return None
        if not answer:
            return DEFAULT_CATEGORY
        if answer in CATEGORIES:
            return answer
        print(f"Unknown category '{answer}'. Choose one from the list.")


def ask_count():
    """Ask how many articles to process (1 to MAX_COUNT)."""
    while True:
        answer = input(f"How many articles? [1-{MAX_COUNT}, default {DEFAULT_COUNT}]: ").strip()
        if not answer:
            return DEFAULT_COUNT
        if answer.isdigit() and 1 <= int(answer) <= MAX_COUNT:
            return int(answer)
        print(f"Please enter a number from 1 to {MAX_COUNT}.")


def interactive_loop(summarizer):
    """Keep asking for a category and a count until the user quits."""
    print("📰 Multi-Provider News Summarizer")
    print("   OpenAI writes the summary, Cohere rates the sentiment.")
    try:
        while True:
            category = ask_category()
            if category is None:
                break
            process_batch(summarizer, category, ask_count())
    except (EOFError, KeyboardInterrupt):
        print()  # Ctrl-D / Ctrl-C or closed input: leave cleanly
    print("Goodbye!")


def parse_args():
    """Read the optional command-line arguments."""
    parser = argparse.ArgumentParser(description="Summarize news with two LLM providers.")
    parser.add_argument("--category", choices=CATEGORIES,
                        help="process one batch of this category and exit")
    parser.add_argument("--count", type=int, choices=range(1, MAX_COUNT + 1),
                        metavar=f"1-{MAX_COUNT}", help="how many articles (default 3)")
    return parser.parse_args()


def main():
    """Entry point: one-shot mode if flags were given, otherwise interactive."""
    args = parse_args()
    try:
        summarizer = NewsSummarizer()
    except ValueError as error:  # missing or invalid configuration
        print(f"❌ {error}")
        raise SystemExit(1)

    if args.category or args.count:
        process_batch(summarizer, args.category or DEFAULT_CATEGORY,
                      args.count or DEFAULT_COUNT)
    else:
        interactive_loop(summarizer)


if __name__ == "__main__":
    main()
