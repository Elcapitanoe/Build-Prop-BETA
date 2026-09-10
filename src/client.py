"""HTTP client for probing and fetching Android OTA pages."""

from dataclasses import dataclass
from typing import Self

import httpx


@dataclass
class FetchResult:
    """Result of an HTTP fetch request."""

    status_code: int
    url: str
    text: str


class OTAClient:
    """Client for querying developer.android.com with proper headers and cookies."""

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self.client = httpx.Client(
            timeout=self.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": self.DEFAULT_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Cookie": "devsite_wall_acks=nexus-ota-tos",
            },
        )

    def fetch_page(self, url: str) -> FetchResult:
        """Fetch a page and return FetchResult with status, final URL, and text."""
        response = self.client.get(url)
        return FetchResult(
            status_code=response.status_code,
            url=str(response.url),
            text=response.text,
        )

    def close(self) -> None:
        """Close the underlying HTTP client session."""
        self.client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
