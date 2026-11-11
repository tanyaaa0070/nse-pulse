"""NSE HTTP client with session management, retries, and rate limiting.

NSE India's API requires a valid session cookie obtained by first visiting
the main page. This client handles that transparently and provides a
respectful, rate-limited interface for data retrieval.
"""

import logging
import time
from typing import Any, Dict, Optional

import requests

from app.config.settings import Settings

logger = logging.getLogger("nse_pulse.nse_client")

# Respectful browser-like headers
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}


class NSEClient:
    """HTTP client for NSE India API with session management.

    Handles:
        - Session cookie acquisition from the NSE homepage
        - Exponential backoff retries on transient failures
        - Rate limiting between consecutive requests
        - Proper HTTP error categorization

    Args:
        settings: Application settings with timeout/retry configuration.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session: Optional[requests.Session] = None
        self._last_request_time: float = 0.0

    def _get_session(self) -> requests.Session:
        """Get or create an HTTP session with NSE cookies.

        The session is initialized lazily on first use. If cookie
        acquisition fails, subsequent API calls will likely fail too,
        but we let them try and report the actual error.
        """
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update(_DEFAULT_HEADERS)
            self._init_cookies()
        return self._session

    def _init_cookies(self) -> None:
        """Visit NSE homepage to obtain session cookies.

        This is required before making API calls. If it fails,
        we log the error but don't raise — the API call itself
        will report the actual failure.
        """
        try:
            logger.info("Initializing NSE session cookies...")
            response = self._session.get(  # type: ignore[union-attr]
                self._settings.nse_base_url,
                timeout=self._settings.nse_request_timeout,
            )
            response.raise_for_status()
            logger.info(
                "NSE session initialized (cookies: %d)",
                len(self._session.cookies),  # type: ignore[union-attr]
            )
        except requests.RequestException as exc:
            logger.warning(
                "Failed to initialize NSE session cookies: %s. "
                "API calls may fail.",
                exc,
            )

    def _rate_limit(self) -> None:
        """Enforce minimum delay between consecutive requests."""
        elapsed = time.time() - self._last_request_time
        delay = self._settings.nse_rate_limit_delay
        if elapsed < delay:
            sleep_time = delay - elapsed
            logger.debug("Rate limiting: sleeping %.2fs", sleep_time)
            time.sleep(sleep_time)

    def get(self, endpoint: str) -> Dict[str, Any]:
        """Make a GET request to an NSE API endpoint with retries.

        Args:
            endpoint: URL path relative to the base URL (e.g. '/api/live-analysis/gainers/allSec').

        Returns:
            Parsed JSON response as a dictionary.

        Raises:
            ConnectionError: After all retry attempts are exhausted.
            ValueError: If the response is not valid JSON.
        """
        url = f"{self._settings.nse_base_url}{endpoint}"
        session = self._get_session()
        last_exception: Optional[Exception] = None

        for attempt in range(1, self._settings.nse_retry_count + 1):
            self._rate_limit()

            try:
                logger.info(
                    "GET %s (attempt %d/%d)",
                    endpoint,
                    attempt,
                    self._settings.nse_retry_count,
                )
                self._last_request_time = time.time()

                response = session.get(
                    url,
                    timeout=self._settings.nse_request_timeout,
                )

                if response.status_code == 403:
                    logger.warning(
                        "HTTP 403 Forbidden for %s – NSE may be blocking automated access. "
                        "Not retrying (respecting access controls).",
                        endpoint,
                    )
                    raise ConnectionError(
                        f"HTTP 403 Forbidden: Access denied for {endpoint}. "
                        "NSE may restrict automated access to this endpoint."
                    )

                if response.status_code == 429:
                    logger.warning(
                        "HTTP 429 Too Many Requests for %s – rate limited.",
                        endpoint,
                    )
                    # Respect rate limit with longer backoff
                    if attempt < self._settings.nse_retry_count:
                        backoff = self._settings.nse_retry_backoff_factor ** attempt * 2
                        logger.info("Rate limit backoff: %.1fs", backoff)
                        time.sleep(backoff)
                        continue
                    raise ConnectionError(
                        f"Rate limited by NSE after {attempt} attempts for {endpoint}."
                    )

                response.raise_for_status()

                data = response.json()
                logger.info(
                    "Successfully fetched %s (%d bytes)",
                    endpoint,
                    len(response.content),
                )
                return data

            except requests.exceptions.Timeout as exc:
                last_exception = exc
                logger.warning(
                    "Timeout on attempt %d for %s: %s",
                    attempt,
                    endpoint,
                    exc,
                )

            except requests.exceptions.ConnectionError as exc:
                last_exception = exc
                logger.warning(
                    "Connection error on attempt %d for %s: %s",
                    attempt,
                    endpoint,
                    exc,
                )

            except requests.exceptions.HTTPError as exc:
                last_exception = exc
                logger.error(
                    "HTTP error on attempt %d for %s: %s",
                    attempt,
                    endpoint,
                    exc,
                )

            except ValueError as exc:
                # JSON decode error
                logger.error(
                    "Invalid JSON response from %s: %s",
                    endpoint,
                    exc,
                )
                raise ValueError(
                    f"Invalid JSON response from {endpoint}: {exc}"
                ) from exc

            # Exponential backoff before retry
            if attempt < self._settings.nse_retry_count:
                backoff = self._settings.nse_retry_backoff_factor ** attempt
                logger.info(
                    "Retrying in %.1fs (attempt %d/%d)",
                    backoff,
                    attempt + 1,
                    self._settings.nse_retry_count,
                )
                time.sleep(backoff)

        raise ConnectionError(
            f"Failed to fetch {endpoint} after {self._settings.nse_retry_count} "
            f"attempts. Last error: {last_exception}"
        )

    def close(self) -> None:
        """Close the HTTP session and release resources."""
        if self._session:
            self._session.close()
            self._session = None
            logger.debug("NSE client session closed.")

    def __enter__(self) -> "NSEClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"NSEClient(base_url={self._settings.nse_base_url!r})"

