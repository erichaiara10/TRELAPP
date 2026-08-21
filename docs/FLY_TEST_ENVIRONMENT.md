# TRELPNG Fly.io test environment

This environment publishes a selected Git branch or commit to a separate Fly
application. It does not deploy to the production Fly app or use the production
database.

## Separation rules

- Production Fly app: `trelweb`
- Test Fly app: `trelweb-test`
- Production database: `trel_db`
- Test database: `trel_test`
- Test URL: `https://trelweb-test.fly.dev`
- Test configuration: `fly.test.toml`
- Manual workflow: `.github/workflows/publish-test-site.yml`

Never copy production database credentials into the test environment. Create a
separate, least-privilege MongoDB user restricted to `trel_test`.

## One-time setup

1. Create the Fly application `trelweb-test` in the Sydney region. Do not create
   or attach a Fly volume; MongoDB and R2 hold persistent application data.
2. Create the MongoDB database `trel_test` and a dedicated test user with access
   only to that database.
3. Create a Fly deploy token scoped to `trelweb-test`.
4. In GitHub, create an environment named `fly-test` and add the repository or
   environment secret `FLY_API_TOKEN` containing that scoped deploy token.
5. Add the runtime secrets directly to the `trelweb-test` Fly application.

## Required Fly runtime secrets

- `MONGO_URL`
- `MONGO_USERNAME`
- `MONGO_PASSWORD`
- `MONGO_AUTH_DATABASE`
- `JWT_SECRET`

`DB_NAME=trel_test` and `TREL_PROPERTY_STORAGE_MODE=integrated` are non-secret
values defined in `fly.test.toml`.

## Optional feature secrets

Add these only when the corresponding test feature is ready:

- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_ENDPOINT`
- `R2_BUCKET_NAME`
- `R2_PUBLIC_URL`
- `R2_REGION`
- `EMERGENT_LLM_KEY` (temporary legacy AI-price-analysis dependency)

Use a separate R2 test bucket. Do not reuse the production bucket.

## Publishing from GitHub

1. Open the repository's **Actions** page.
2. Select **Publish Test Site**.
3. Select **Run workflow**.
4. Enter the branch name or exact commit in `source_ref`.
5. Enter `PUBLISH_TRELWEB_TEST` in the confirmation field.
6. Run the workflow and open the URL shown in its summary.

The workflow compiles the backend, installs the locked frontend dependencies,
builds the React application, deploys the combined Docker image, and verifies
both `/api/` and `/` on the test site.

## Safety gates

- Deployment is manual only.
- The workflow checks that `fly.test.toml` names `trelweb-test`, not `trelweb`.
- The workflow checks that the configured database name is `trel_test`.
- Deployments are serialized so two test releases cannot overlap.
- Production deployment is not part of this workflow.
- Database migrations and backfills are not part of this workflow.
