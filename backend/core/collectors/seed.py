"""TREL Seed Collector — synthetic Port Moresby listings.

Deterministic per (source_id, run_index) so demo data stays stable and every
run produces varied but recognisable rows. Zero network dependencies —
perfect for the CI environment.
"""
from __future__ import annotations

import random
from typing import AsyncIterator

from core.collectors import CollectorBase, register


SUBURBS = [
    ("Gordons",       "NCD",  "Port Moresby",   "Angau Drive"),
    ("Boroko",        "NCD",  "Port Moresby",   "Sabama Road"),
    ("Waigani",       "NCD",  "Port Moresby",   "Independence Drive"),
    ("Tokarara",      "NCD",  "Port Moresby",   "Waigani Drive"),
    ("Ela Beach",     "NCD",  "Port Moresby",   "Ela Beach Road"),
    ("Korobosea",     "NCD",  "Port Moresby",   "Nita Street"),
    ("Kokopo",        "ENB",  "Kokopo",         "Williams Highway"),
    ("Lae Top Town",  "MPL",  "Lae",            "3rd Street"),
]

SUBTYPES_RESI = ["House", "Apartment", "Townhouse", "Duplex"]
SUBTYPES_CI = ["Warehouse", "Office", "Retail Space"]


@register
class SeedCollector(CollectorBase):
    key = "seed"
    label = "TREL Seed Generator (synthetic PNG data)"
    requires_network = False

    async def iter_listings(self) -> AsyncIterator[dict]:
        # Stable RNG per source so re-runs update the same set of listings
        rng = random.Random(f"{self.source['id']}-{self.source.get('parser_version', '1.0')}")
        target = int(self.source.get("seed_count") or 12)
        for i in range(target):
            suburb, prov, city, street = rng.choice(SUBURBS)
            purpose = rng.choice(["sale", "sale", "sale", "rent", "rent"])
            if rng.random() < 0.75:
                cls, subtype = "residential", rng.choice(SUBTYPES_RESI)
            elif rng.random() < 0.5:
                cls, subtype = "commercial_industrial", rng.choice(SUBTYPES_CI)
            else:
                cls, subtype = "vacant_land", "Vacant Land"

            lot = str(rng.randint(1, 60))
            section = str(rng.randint(1, 30))
            beds = rng.randint(2, 5) if cls == "residential" else None
            baths = rng.randint(1, 3) if cls == "residential" else None
            land = rng.randint(300, 1200)
            bldg = None
            if cls == "residential":
                bldg = rng.randint(90, 320)
            elif cls == "commercial_industrial":
                bldg = rng.randint(200, 1500)

            if purpose == "sale":
                base = {"residential": 850_000, "commercial_industrial": 2_400_000,
                        "vacant_land": 380_000}[cls]
                price = int(base * rng.uniform(0.75, 1.25))
            else:
                base = {"residential": 4_500, "commercial_industrial": 12_000,
                        "vacant_land": 1_500}[cls]
                price = int(base * rng.uniform(0.75, 1.30))

            yield {
                "source_listing_id": f"SEED-{i:03d}",
                "source_url": f"https://seed.trel.pg/{self.source['id']}/{i}",
                "purpose": purpose,
                "price": price,
                "rent_period": "monthly" if purpose == "rent" else None,
                "property_class": cls,
                "property_subtype": subtype,
                "lot_number": lot,
                "section_number": section,
                "street": street,
                "suburb": suburb,
                "city": city,
                "province": prov,
                "bedrooms": beds,
                "bathrooms": baths,
                "land_area_m2": land,
                "building_area_m2": bldg,
            }
