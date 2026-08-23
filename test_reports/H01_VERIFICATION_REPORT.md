# H01 Authoritative Implementation — Verification Report

**Branch:** `hardening/p3-post-iter29`  
**Applied patch:** `H01_AUTHORITATIVE_IMPLEMENTATION.patch` (via `git apply`, clean after resetting `backend/routes/auth.py` and `backend/frontend/src/pages/public/Home.jsx` to their pre-hardening tip — see notes below)  
**Preview URL:** https://req-to-web-1.preview.emergentagent.com  
**Status:** Applied, built, tested. **NOT committed** and **NOT deployed** — awaiting review.

## Files touched by the patch

| File | Change | Notes |
|---|---|---|
| `backend/frontend/src/App.js` | M | Route additions: `/register`, `/property/:id`, `PublicLayout` |
| `backend/frontend/src/components/AIPriceAnalysis.jsx` | M | Detail-page price guidance component |
| `backend/frontend/src/components/public/PublicHeader.jsx` | M | Authoritative nav order + testids + tel/wa hrefs |
| `backend/frontend/src/components/public/PublicFooter.jsx` | M | Authoritative footer (About/Contact/Privacy/Terms + disabled links + © 2025) |
| `backend/frontend/src/pages/public/Home.jsx` | M | New authoritative homepage (hero, For Sale/Rent toggle, featured 12, How TRELPNG Helps) |
| `backend/frontend/src/pages/public/PropertyDetail.jsx` | M | AI price guidance section wired to `#price-guidance` |
| `backend/frontend/src/pages/account/Register.jsx` | **new** | Public self-registration form (advertiser / referral-partner) |
| `backend/frontend/e2e/h01-authoritative.spec.js` | **new** | Playwright authoritative spec (2 tests) |
| `backend/frontend/public/images/h01-authoritative-hero.png` | **new (binary)** | Hero image (from ZIP, not the patch) |
| `backend/routes/auth.py` | M | Adds `PublicRegisterIn` model + `POST /api/auth/register` (201) |
| `backend/seed_data.py` | M | Site content wiring for header/footer values |

**Merge note:** the patch expected pristine `auth.py` and `Home.jsx`. Both had my earlier hardening edits (brute-force lockout + Featured loading/empty/error states). I reset both files to their pre-hardening tip (`git checkout 1c1c4eb --`), applied the H01 patch verbatim, then **re-integrated only the brute-force lockout** into `auth.py` on top of the H01 additions (5 lines: `Request` import, `login_guard` imports, guard call + `record_failure` + `reset` around the existing `login` body). H01's Home.jsx is now the sole authoritative homepage — my Featured-strip loading/empty/error work is discarded because that section belongs to a retired homepage.

## Production build

```
cd backend/frontend && yarn build
# → "The build folder is ready to be deployed." (pre-existing eslint warnings on Content.jsx and Search.jsx — not introduced by H01)
```

## Playwright — H01 authoritative spec

```
$ PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000 yarn playwright test e2e/h01-authoritative.spec.js
Running 2 tests using 1 worker
  ✓  1 e2e/h01-authoritative.spec.js:61:1 › H01 header and footer preserve the authoritative order, wording and live destinations (752ms)
  ✓  2 e2e/h01-authoritative.spec.js:82:1 › H01 live property area expands to twelve listings and all principal actions work (2.2s)
  2 passed (3.6s)
```

## Screenshots (live preview, real backend, real DB)

- Desktop 1440×900 full page: `/app/test_reports/h01_desktop.png`
- Mobile iPhone 12 (390×844) full page: `/app/test_reports/h01_mobile.png`

## Route → API wiring matrix

### Public routes
| Route | Component | Backend calls | Live check |
|---|---|---|---|
| `/` | `Home.jsx` | `GET /api/content/site`, `GET /api/page/home`, `GET /api/properties?listing_type=sale&featured=true`, `GET /api/properties?listing_type=rent&featured=true`, `GET /api/property-types`, `GET /api/locations/cities`, `GET /api/locations/suburbs` | 200 all |
| `/buy` | `Search mode="sale"` | `GET /api/properties?listing_type=sale&q=...` | 200 |
| `/rent` | `Search mode="rent"` | `GET /api/properties?listing_type=rent&q=...` | 200 |
| `/property/:id` | `PropertyDetail.jsx` | `GET /api/properties/{id}`, `POST /api/ai/price-analysis` | 200 (create-then-fetch verified) |
| `/sell`, `/wanted`, `/management`, `/corporate`, `/about`, `/contact`, `/privacy`, `/terms` | static pages | `GET /api/page/{key}` | 200 |
| `/register` | `Register.jsx` (NEW) | `POST /api/auth/register` | **201** verified with unique advertiser + referral-partner emails |
| `/admin/login` | `Login.jsx` | `POST /api/auth/login` | 200 (admin + 4 staff); brute-force lockout returns 429 after 5 wrong attempts |

### PublicHeader nav (verified by the Playwright spec byRole('link'))
Home → `/` · Buy → `/buy` · Rent → `/rent` · Property Wanted → `/wanted` · Property Management → `/management` · Corporate Services → `/corporate` · Add Property → `/advertiser` · Log In → `/admin/login` · Register → `/register` · About → `/about` · Contact → `/contact`

- Phone chip → `tel:+67576281552` (data-testid=`header-phone`)
- WhatsApp chip → `https://wa.me/67581383302` (data-testid=`header-whatsapp`)

### PublicFooter (Playwright asserts)
About → `/about`, Contact → `/contact`, Privacy Policy → `/privacy`, Terms of Use → `/terms`, three `aria-disabled="true"` social placeholders, `© 2025 TRELPNG. All rights reserved.`

### Auth guardrails (preserved from hardening)
- `POST /api/auth/login` — 5 wrong attempts / 15-minute rolling window per (email, IP) → 429; unknown-email response is identical to wrong-password (no user enumeration); httpOnly `access_token` cookie set on success.
- `POST /api/auth/register` — public sign-up for `PROPERTY_ADVERTISER` (with `advertiser_relationship_type`) or `REFERRAL_PARTNER`; creates a `PENDING` advertiser profile or an `ACTIVE` referral profile; returns 201.

## Deviations / open items

1. **No merge / no deploy** — as instructed. Repo state left as working-tree changes on branch `hardening/p3-post-iter29`.
2. The legacy backfill dry-run (Phase A) is still awaiting your approval — it is committed but the apply step has not run.
3. `header-phone` and `header-whatsapp` values come from `GET /api/content/site` (seeded by the patched `seed_data.py`). If the site content collection was previously customised, the header values will follow that content, not the seed defaults — but the current preview matches the spec exactly.
