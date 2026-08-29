"""Collector framework — pluggable scrapers/generators that feed the MATCH
pipeline via `core.runs.collection_run`.

Every collector is a subclass of `CollectorBase` that yields dict payloads
shaped like a `MarketListing` (only the strong-identifier fields need to be
present — MATCH-1.0 will fill in the rest).

Registration is by string key so the admin UI can pick which collector runs
for a given `MarketSource`. Adding a new collector = drop a file into
`core/collectors/` and register it.

We ship a full stable of collectors out of the box:

* **`seed`** — synthetic PNG-market generator. Always works, produces varied
  Port Moresby listings. Used for demos, load tests, matcher sanity checks.
* **`hausples_png`**  — hausples.com.pg
* **`ljhookerpng`**   — ljhookerpng.com
* **`mypnghome`**     — mypnghome.com
* **`sre`**           — sre.com.pg (Strickland Real Estate)
* **`dac`**           — dac.com.pg (Devine & Associates)
* **`marketmeri`**    — marketmeri.com

All HTTP collectors use the common `HttpListingCollector` base in
`_common.py` — fetch/pagination/allotment+section parsing is centralised so
adding a new site is a ~30-line file.

Every HTTP collector inherits the same graceful-degradation contract: network
errors are captured on the run doc, missing individual fields are still
yielded (MATCH-1.0 handles gaps), and DOM changes only require operators to
edit `parser_config` — no code deploy.
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
    async def iter_listings(self, run=None) -> AsyncIterator[dict]:
        """Yield one listing payload at a time. Payload MUST contain
        `source_listing_id`; the framework injects `source_id`. The
        optional `run` argument is a RunContext-shaped object exposing
        `record_diag`/`record_page`/`record_pagination_end` (see
        `core.runs.RunContext`)."""
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
from core.collectors import (                                              # noqa: F401,E402
    dac,
    hausples_png,
    ljhookerpng,
    marketmeri,
    mypnghome,
    seed,
    sre,
)
