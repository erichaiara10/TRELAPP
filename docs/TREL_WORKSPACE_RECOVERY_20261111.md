# TREL development workspace recovery — 11 November 2026

Status: code prepared and locally checked; Fly.io authorization is still required.
No deployment, database migration, DNS change or external-service configuration
change has been performed during this recovery.

## Verified source history

| Item | Verified result |
| --- | --- |
| Repository | `erichaiara10/TRELAPP` |
| PR #31 | “Complete Property Data Aggregation operational improvements”, merged as `690de8c789a9b541d6b0c77e351f29c4d492055e` |
| Direct successor | `e4e560c215ee0fa37c60d3f1af3939d2fa97f0ac`, “Add intelligent source discovery for market data sources” |
| e4e560c changes | Adaptive source navigation/layout discovery, sale/rent-aware price parsing, validated pagination and saved parser profiles in the source editor. Four files changed; no commission code changed. |
| e4e560c deployment | Successful Publish Test Site run #77, run ID `33259646386` |
| Latest successful test release | `526aa495cc1b8dedad84a1a41d1d754d4e8f2d57` on `codex/aggregation-18-improvements` |
| Latest deployment evidence | Run #114, ID `33335158324`, completed 31 August 2026 PNG time; one machine `781561da6e7038`; homepage and API verified successfully |
| Recovery branch | `restore/private-workspace-20261111`, based on that latest test release |

Sources:

- https://github.com/erichaiara10/TRELAPP/pull/31
- https://github.com/erichaiara10/TRELAPP/commit/e4e560c215ee0fa37c60d3f1af3939d2fa97f0ac
- https://github.com/erichaiara10/TRELAPP/actions/runs/33259646386
- https://github.com/erichaiara10/TRELAPP/actions/runs/33335158324

The production/default branch is not the newest successfully deployed test
version. Reverting to main or e4e560c would omit subsequent test-workspace work.

## Prepared fixes

1. Route Add Property directly into the account's editable property form.
   Advertisers reach `/advertiser/add-property`; staff reach the New Property
   dialog at `/admin/properties`. Existing account-category restrictions remain.
2. Preserve Sell/Rent, service and property relationship through sign-in,
   registration completion and initial draft creation. Consume the new-property
   flag once, so returning to the first step does not reset entered data.
3. Keep the Add Property action bar within the page's flow. Its previous fixed
   positioning intercepted clicks on the footer Privacy Policy and Terms links.
4. Make the Docker frontend install use the committed Yarn lockfile and exclude
   dependency folders, development caches and local secrets from build context.
5. Keep selectolax below 0.4: a fresh install otherwise selected 1.0, whose
   removed parser backend caused the existing collector tests to fail.
6. Add a test-only private access gate. All application pages, static assets,
   account routes and APIs require a signed secure session cookie, independently
   of the application's Bearer token. Missing/short access secrets fail closed.
   Only the minimal `/_preview/health` response is available without a session.
7. Update the test health check and deployment verification to check health and
   require unauthenticated application requests to return 401.

## Local validation

- Backend compilation and `git diff --check` pass.
- 45 backend checks pass, including private access, draft save/read, account
  isolation, submission policy and the existing aggregation regression suite.
- Frontend production build passes with existing unrelated hook warnings.
- 26 browser checks pass, covering public intake choices, login/registration routing,
  editable details, saved draft reload, legal and feature fields, workspace
  navigation, staff property creation, uploads, account boundaries and links.
- Browser fixtures intercept API calls; local API round-trip tests use an
  in-memory MongoDB double. These do not establish live database availability.
- The local build used the exact top-level package versions through npm and a
  local AJV 8 compatibility install because Yarn's network fetching stalled in
  this environment. Neither package.json nor yarn.lock was changed. The actual
  deployment must complete its frozen-lockfile build before being accepted.
- The browser test environment needed a TrueType-only font configuration and
  Playwright's headless shell. Those are temporary local QA settings.

## Live outage: established facts and remaining diagnosis

Current unauthenticated requests to `https://trelweb-test.fly.dev` timed out from
this environment. Browser navigation also timed out. This is an observation,
not proof of a particular Fly.io, MongoDB or billing failure.

No Fly CLI authentication is present in this workspace. The available browser
connector reported disconnected. Automatic approval review blocked opening
Fly.io until the user's explicit authorization is received.

After authorization, inspect the existing app's machine status, release,
health checks and recent startup logs, and verify required secret names without
printing values. Check MongoDB connectivity only against `trel_test`.
Do not restart an unprotected historical image into public availability.

## Deployment boundaries and acceptance

- Target app: `trelweb-test`; database: `trel_test`; config: `fly.test.toml`.
- Retain one shared CPU, 1 GB RAM, Sydney and automatic stop/start unless
  observed runtime evidence requires a change. Add no volume or extra machine.
- Configure a cryptographically random `TREL_PREVIEW_ACCESS_KEY` with at least
  32 characters securely before activating this release. Do not commit it or
  include it in a URL or log. Rotation invalidates old private-access cookies.
- Do not target production `trelweb`, production `trel_db`, DNS or other services.
- Accept only after the frozen build and Fly health checks pass, outsiders are
  denied application access, and the authorized browser can sign in, save and
  reload a clearly labelled test draft, and follow the Add Property links.
- Intended URL remains `https://trelweb-test.fly.dev/add-property`. It is not yet
  claimed as a working restored URL. Record the final Fly failure cause,
  recovery action, release and live test result after access is available.
