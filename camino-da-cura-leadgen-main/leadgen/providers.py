import json
import logging
import time
from typing import Protocol
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from .models import SearchResult
from .deadlines import bounded_call, DeadlineExceeded

log = logging.getLogger(__name__)

class SearchProvider(Protocol):
    def search(self, query: str, count: int) -> list[SearchResult]: ...

class MockSearchProvider:
    def search(self, query, count):
        return [
            SearchResult("Demo Retreat Company", "https://demo-retreat.example/retreats", "Synthetic fixture: organised yoga retreats."),
            SearchResult("Demo Retreat Company", "https://www.demo-retreat.example/contact", "Synthetic duplicate."),
            SearchResult("Demo Yoga Studio", "https://demo-studio.example", "Synthetic fixture: yoga classes; retreats unconfirmed."),
        ][:count]

class SearchError(RuntimeError): pass

def _search_job(provider,query,count):
    provider.isolated=False
    result=provider.search(query,count)
    return result,provider.attempts,provider.last_request

class BraveSearchProvider:
    def __init__(self, key, *, country="GB", max_requests=20, interval_seconds=1, retries=2, opener=urlopen, sleep=time.sleep, clock=time.monotonic):
        if not key:
            raise ValueError("Set BRAVE_SEARCH_API_KEY for live discovery")
        self.isolated=opener is urlopen and sleep is time.sleep and clock is time.monotonic
        self.country = country
        self.key, self.max_requests, self.interval, self.retries = key, max_requests, interval_seconds, retries
        self.opener, self.sleep, self.clock = opener, sleep, clock
        self.attempts, self.last_request = 0, None

    def search(self, query, count):
        if self.isolated:
            log.info('Search request running (45s total deadline)')
            try:
                result,self.attempts,self.last_request=bounded_call(_search_job,(self,query,count),45,'Brave search')
                return result
            except (DeadlineExceeded,SearchError) as exc:
                self.attempts=self.max_requests  # stop after an uncertain/failed request; no automatic extra charges
                raise SearchError(str(exc)) from None
        params = urlencode({"q": query, "count": count, "country": self.country})
        request = Request("https://api.search.brave.com/res/v1/web/search?" + params,
                          headers={"Accept": "application/json", "X-Subscription-Token": self.key})
        for retry in range(self.retries + 1):
            if self.attempts >= self.max_requests:
                raise SearchError("Search request budget exhausted (retries included)")
            if self.last_request is not None:
                self.sleep(max(0, self.interval - (self.clock() - self.last_request)))
            self.attempts += 1
            self.last_request = self.clock()
            try:
                with self.opener(request, timeout=20) as response:
                    data = json.load(response)
                results = data.get("web", {}).get("results", [])
                if not isinstance(results, list):
                    raise ValueError("Invalid results")
                return [SearchResult(item.get("title", ""), item["url"], item.get("description", "")) for item in results]
            except HTTPError as exc:
                if exc.code != 429 and not 500 <= exc.code < 600:
                    raise SearchError(f"Search API returned HTTP {exc.code}") from None
                delay = min(60, 2 ** retry)
                try:
                    delay = min(60, max(delay, float(exc.headers.get("Retry-After", delay))))
                except (ValueError, AttributeError):
                    pass
            except (URLError, TimeoutError, OSError):
                delay = min(60, 2 ** retry)
            except (ValueError, KeyError, TypeError, AttributeError):
                raise SearchError("Malformed search API response") from None
            if retry == self.retries:
                raise SearchError("Search API failed after bounded retries") from None
            log.warning("Search request failed; retrying (%s/%s)", retry + 1, self.retries)
            self.sleep(delay)
