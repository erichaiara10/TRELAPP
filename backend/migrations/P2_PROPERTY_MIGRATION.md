# P2 Integrated Property Migration

This work package extends the verified P1 physical schema without replacing or
deleting the 14 legacy property documents.

## Controls

- Dry-run is the default and performs zero writes.
- Apply requires the exact confirmation `BACKFILL_TREL_DB_P2`.
- Target identifiers are deterministic UUIDv5 values, so retries are idempotent.
- Every valid legacy property is recorded in `migration_id_map`.
- Invalid source records are recorded in `migration_exceptions` without
  blocking other records.
- P2 writes only to the new integrated collections and migration control
  collections.
- The legacy `properties` collection remains the default read/write source.

## Feature flags

| Variable | Default | Purpose |
|---|---:|---|
| `TREL_PROPERTY_READ_MODE` | `legacy` | `legacy`, `compare`, or `integrated` |
| `TREL_PROPERTY_DUAL_WRITE` | `false` | Mirror successful legacy writes to the integrated graph |
| `TREL_PROPERTY_DUAL_WRITE_STRICT` | `false` | Fail an API write if the integrated mirror fails |

Recommended rollout:

1. Keep all defaults while running the P2 dry-run and reviewing exceptions.
2. Apply P2 and verify all 14 source property records are mapped or excepted.
3. Enable dual write in non-strict mode.
4. Enable compare reads and review mismatch logs.
5. Enable integrated reads only after parity and screen regression tests pass.

## Commands

```bash
python -m migrations.property_backfill \
  --mode dry-run \
  --uri "$MONGO_URL" \
  --username "$MONGO_USERNAME" \
  --database trel_db
```

```bash
python -m migrations.property_backfill \
  --mode apply \
  --confirmation BACKFILL_TREL_DB_P2 \
  --uri "$MONGO_URL" \
  --username "$MONGO_USERNAME" \
  --database trel_db
```

```bash
python -m migrations.property_backfill \
  --mode verify \
  --uri "$MONGO_URL" \
  --username "$MONGO_USERNAME" \
  --database trel_db
```

## Cutover gates

- P1 verification remains green.
- P2 dry-run reports 14 source documents and zero legacy writes/deletes.
- Every source property is mapped or has an explicit exception.
- Dual-write failures are zero for the observation window.
- Compare-read identifier sets match.
- Property create/edit/list/detail regression tests pass.
- Rollback is limited to resetting feature flags to legacy mode.
