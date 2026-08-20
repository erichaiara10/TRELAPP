# P3 — Integrated Property Write Path

## Objective

P3 makes the Add Property administration flow write one transactional Property
graph instead of a single legacy `properties` document. Legacy collections remain
untouched and available as a rollback path.

## Five completed implementation areas

1. **Schema extension** — field-level strict validators and relationship/duplicate
   indexes for the eleven core Property and Listing collections.
2. **Transactional write service** — create, update, read, duplicate check and
   soft-delete across the integrated graph in a MongoDB transaction.
3. **Add Property screen integration** — stable location/type IDs, owner and
   authority capture, supporting-document upload, and duplicate confirmation.
4. **Controlled activation** — `TREL_PROPERTY_STORAGE_MODE=integrated` selects
   the final repository path and is now the default; integrated-mode
   startup skips legacy Property migration and demo-property seeding.
5. **Verification and rollback** — unit tests, frontend production build, Atlas
   schema dry-run/apply/verify, and a non-production relationship smoke test.

## Integrated graph

- `master_properties` is the durable Property identity.
- `property_addresses`, `property_parcels`, and `property_attributes`
  contain canonical location, legal parcel, and descriptive attributes.
- `parties` and `property_parties` represent owner/agent relationships.
- `property_documents` stores uploaded evidence references and review status.
- `listings` is the publishable sale/rent record.
- `listing_prices`, `listing_media`, `listing_features`, and
  `listing_status_history` retain price, media, features, and lifecycle history.
- `advertiser_authorities` and `audit_events` record authority and actions.

## Activation

The final integrated path is the application default. Set this explicitly in deployment configuration for clarity:

```text
TREL_PROPERTY_STORAGE_MODE=integrated
```

Use `legacy` only as the documented rollback switch.

## Database migration

Dry-run:

```bash
python migrations/p3_integrated_property.py --mode dry-run
```

Apply:

```bash
python migrations/p3_integrated_property.py \
  --mode apply --confirmation APPLY_TREL_DB_P3
```

Verify:

```bash
python migrations/p3_integrated_property.py --mode verify
```

The normal apply path uses `collMod`. If the migration role cannot use
`collMod`, the controlled fallback below is permitted only while every target
collection is empty:

```bash
python migrations/p3_integrated_property.py \
  --mode recreate-empty --confirmation RECREATE_EMPTY_TREL_DB_P3
```

The fallback checks all target counts before making changes, refuses to run if any
target contains a document, recreates only the empty target collections, restores
their existing indexes, and adds the P3 indexes. Neither path modifies or deletes
business documents.

## Non-production relationship smoke test

```bash
TREL_PROPERTY_STORAGE_MODE=integrated \
python tests/p3_relationship_smoke.py --confirmation RUN_TREL_P3_SMOKE
```

The smoke test creates a uniquely marked Property graph, verifies the relationship
chain, updates and reads it, then soft-deletes the Property and withdraws its
Listing. It performs no writes to the legacy `properties` collection.

## Rollback

Set `TREL_PROPERTY_STORAGE_MODE=legacy` and redeploy. This immediately returns
application CRUD traffic to the legacy repository. Do not delete integrated or
legacy records during rollback. Validator/index rollback is unnecessary for the
application switch and requires a separately reviewed migration if ever needed.
