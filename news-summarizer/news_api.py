"""News API client: fetches top headlines from newsapi.org."""

import time

import requests

from config import get_config

BASE_URL = "https://newsapi.org/v2"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class NewsAPIError(Exception):
    """Raised when News API cannot return articles."""


class NewsAPIClient:
    """Small wrapper around the News API top-headlines endpoint."""

    def __init__(self):
        cfg = get_config()
        self.max_retries = cfg.max_retries
        self.timeout = cfg.request_timeout
        # The key goes in a header (not the URL) so it never ends up in logs.
        self.headers = {"X-Api-Key": cfg.news_api_key}

    def get_top_headlines(self, category="technology", country="us", page_size=5):
        """Return a list of article dicts, newest-first as News API sends them.

        Each article keeps the raw News API fields (title, description, url,
        content, source, publishedAt, ...). Articles that were removed by the
        publisher ("[Removed]") are dropped.
        """
        params = {"category": category, "country": country, "pageSize": page_size}
        data = self._get("/top-headlines", params)

        articles = [
            article for article in data.get("articles", [])
            if article.get("title") and article["title"] != "[Removed]"
        ]
        return articles

    def _get(self, path, params):
        """GET with retries on timeouts, rate limits and server errors."""
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.get(
                    BASE_URL + path,
                    params=params,
                    headers=self.headers,
                    timeout=self.timeout,
                )
            except (requests.Timeout, requests.ConnectionError) as error:
                last_error = f"network problem: {error.__class__.__name__}"
            else:
                if response.status_code in RETRYABLE_STATUS:
                    last_error = f"HTTP {response.status_code}"
                else:
                    return self._parse(response)

            if attempt < self.max_retries:
                time.sleep(2 ** (attempt - 1))  # wait 1s, 2s, 4s, ...

        raise NewsAPIError(
            f"News API failed after {self.max_retries} attempts ({last_error})"
        )

    @staticmethod
    def _parse(response):
        """Return the JSON body, or raise NewsAPIError with the API's message."""
        try:
            data = response.json()
        except ValueError:
            raise NewsAPIError(f"News API sent invalid JSON (HTTP {response.status_code})")

        if response.status_code != 200 or data.get("status") != "ok":
            code = data.get("code", "unknown")
            message = data.get("message", "no message")
            raise NewsAPIError(f"News API error [{code}]: {message}")
        return data


if __name__ == "__main__":
    try:
        client = NewsAPIClient()
        articles = client.get_top_headlines(category="technology", page_size=3)
    except (ValueError, NewsAPIError) as error:
        print(f"❌ {error}")
        raise SystemExit(1)

    print(f"✅ Fetched {len(articles)} articles\n")
    for number, article in enumerate(articles, start=1):
        print(f"{number}. {article['title']}")
        print(f"   Source: {article['source']['name']}")
        print(f"   {article.get('description') or 'No description'}")
        print(f"   {article['url']}\n")
