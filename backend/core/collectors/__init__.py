"""Collector framework — pluggable scrapers/generators that feed the MATCH
pipeline via `core.runs.collection_run`.

Every collector is a subclass of `CollectorBase` that yields dict payloads
shaped like a `MarketListing` (only the strong-identifier fields need to be
present — MATCH-1.0 will fill in the rest).

Registration is by string key so the admin UI can pick which collector runs
for a given `MarketSource`. Adding a new collector = drop a file into
`core/collectors/` and register it.

We ship two collectors out of the box:

* **`seed`** — synthetic PNG-market generator. Always works, produces varied
  Port Moresby listings. Used for demos, load tests, matcher sanity checks.
* **`hausples_png`** — best-effort HTTP adapter for hausples.com.pg. Uses
  the collector framework's graceful-degradation: network errors go onto
  the run doc, listings that DO come back get ingested normally. Ships in
  "disabled by default" state so it never fires without an explicit switch.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional


class CollectorBase(ABC):
    """Contract every collector must fulfil. Kept tiny on purpose."""

    key: str = "base"
    label: str = "Base collector"
    requires_network: bool = False

    def __init__(self, source: dict):
        self.source = source

    @abstractmethod
    async def iter_listings(self) -> AsyncIterator[dict]:
        """Yield one listing payload at a time. Payload MUST contain
        `source_listing_id`; the framework injects `source_id`."""
        raise NotImplementedError
        yield {}                    # for typing


_REGISTRY: dict[str, type[CollectorBase]] = {}


def register(cls: type[CollectorBase]) -> type[CollectorBase]:
    _REGISTRY[cls.key] = cls
    return cls


def get_collector(key: str) -> Optional[type[CollectorBase]]:
    return _REGISTRY.get(key)


def registered() -> list[dict]:
    return [{"key": c.key, "label": c.label, "requires_network": c.requires_network}
            for c in _REGISTRY.values()]


# Import concrete collectors so their `@register` decorators run.
from core.collectors import hausples_png, seed         # noqa: F401,E402
