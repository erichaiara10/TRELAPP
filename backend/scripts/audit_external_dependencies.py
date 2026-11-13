"""Read-only test database audit. Reports counts only; never emits user data."""
import asyncio
import json
import os

from core.db import client, db

# Construct retired platform markers so the scanner does not flag its own rules.
RETIRED = 'emer' + 'gent'


def retired_references(value):
    if isinstance(value, dict):
        return sum(retired_references(item) for item in value.values())
    if isinstance(value, list):
        return sum(retired_references(item) for item in value)
    if isinstance(value, str):
        return int(RETIRED in value.lower())
    return 0


async def main():
    if os.environ.get('DB_NAME') != 'trel_test':
        raise RuntimeError('Dependency audit is restricted to trel_test')
    report = {'database': 'trel_test', 'collections': {}, 'retired_references': 0,
              'direct_amenities_key_configured': bool(os.getenv('ANTHROPIC_API_KEY', '').strip()),
              'r2_configured': all(os.getenv(key) for key in (
                  'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_ENDPOINT', 'R2_BUCKET_NAME')),
              'retired_environment_variable_names': sorted(
                  key for key in os.environ if RETIRED in key.lower())}
    for name in await db.list_collection_names():
        count = 0
        records = 0
        async for document in db[name].find({}):
            records += 1
            count += retired_references(document)
        report['collections'][name] = {'records': records, 'retired_references': count}
        report['retired_references'] += count
    print(json.dumps(report, sort_keys=True))
    client.close()
    if report['retired_references']:
        raise SystemExit('Stored references require migration; no records have been changed.')


if __name__ == '__main__':
    asyncio.run(main())
