from dataclasses import dataclass, field
import json
from pathlib import Path

@dataclass
class Campaign:
    name: str = "yoga-uk"
    niche: str = "yoga retreat"
    locations: list[str] = field(default_factory=lambda: ["United Kingdom"])
    terms: list[str] = field(default_factory=lambda: ["organiser", "retreat holidays"])
    target_qualified: int = 100  # legacy campaigns only
    target_prospects: int | None = None
    search_country: str = "GB"
    filter_candidates: bool = False
    organiser_mode: bool = False
    require_retreat_signal: bool = False
    minimum_queries: int = 1
    query_exclusions: list[str] = field(default_factory=list)
    query_groups: list[dict] = field(default_factory=list)
    max_requests: int = 20
    results_per_query: int = 20
    interval_seconds: float = 1.0
    retries: int = 2

    def __post_init__(self):
        if not self.name.strip() or not self.niche.strip() or not self.locations or not self.terms:
            raise ValueError("Campaign name, niche, locations and terms are required")
        if any(not isinstance(s, str) or not s.strip() for s in self.locations + self.terms):
            raise ValueError("Locations and terms must be nonempty strings")
        if not 1 <= self.minimum_queries <= self.max_requests:
            raise ValueError("minimum_queries must fit the request budget")
        if self.target_prospects is not None and self.target_prospects < 1:
            raise ValueError("Prospect target must be positive")
        if len(self.search_country) != 2 or not self.search_country.isalpha():
            raise ValueError("search_country must be a two-letter country code")
        for group in self.query_groups:
            if not group.get("niche") or not group.get("terms") or any(not isinstance(t,str) or not t.strip() for t in group["terms"]):
                raise ValueError("Query groups require niche and terms")
        if self.target_qualified < 1 or not 1 <= self.max_requests <= 10000 or not 1 <= self.results_per_query <= 20:
            raise ValueError("Invalid target, request budget or results count")
        if not 0 <= self.retries <= 5 or self.interval_seconds < 0.1:
            raise ValueError("Retries must be 0–5 and interval at least 0.1 seconds")

    @classmethod
    def load(cls, path: str):
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))

    def queries(self):
        groups = self.query_groups or [{"niche":self.niche,"terms":self.terms}]
        # Round-robin across niches so a small request budget covers every priority.
        batches = [[f"{g['niche']} {location} {term}" for location in self.locations for term in g["terms"]] for g in groups]
        queries = list(dict.fromkeys(batch[i] for i in range(max(map(len,batches))) for batch in batches if i < len(batch)))
        return [query + (' ' + ' '.join(self.query_exclusions) if self.query_exclusions else '') for query in queries]
