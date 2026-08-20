# TRELPNG additive database migrations

## P1 schema extension

`schema_extension.py` implements the approved additive physical foundation.

- Dry-run is the default and performs no writes.
- Apply creates missing integrated collections, their initial strict validators,
  approved indexes, and one migration-ledger record.
- Existing business documents are not updated, copied, or deleted in P1.
- Re-running an applied migration with the same checksum is a no-op.
- A checksum mismatch stops execution.

### Local dry-run

```bash
MONGO_PASSWORD='<temporary-password>' python -m migrations.schema_extension \
  --mode dry-run \
  --uri 'mongodb+srv://cluster0.hwzmeqs.mongodb.net/trel_db' \
  --username 'trel_schema_migration_20260820' \
  --database trel_db
```

Apply is intentionally performed through the protected GitHub Actions workflow
after its dry-run output is reviewed.

