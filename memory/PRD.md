# PNG Realty — Digital Real Estate Agency Platform (V1)

## Original Problem Statement
Build a fully-fledged Digital Real Estate Agency Platform for Papua New Guinea based on the attached requirements document. The platform combines a public marketing/property discovery website with an internal operating system (CRM/pipeline/reporting) used by staff.

## Architecture
- **Backend**: FastAPI (single `server.py`) + MongoDB (motor) + JWT auth (bcrypt/PyJWT)
- **Frontend**: React 19 + React Router 7 + Tailwind + shadcn/ui + Recharts + Sonner toasts
- **Auth**: JWT Bearer tokens (localStorage `png_token`); role-based access (7 roles seeded)
- **Design**: Playfair Display (public headings) + Outfit (body/CRM); pine-green primary, terracotta accent, sand backdrop

## User Personas
- Public browsers (buyers, tenants, sellers, landlords, corporates)
- System Admin, Managing Director, Sales Manager, Sales Agent, Leasing Agent, Property Manager, Marketing Officer

## What's Been Implemented (Feb 2026)

### Iter-42 — Scraper Diagnostics Overhaul: Accounting Invariant + MarketMeri Fix + Sources Admin RunRow UI (Feb 28, 2026)

**Backend — Scraper engine overhaul completed & verified (13/13 pytest green):**
- `_walk_category` in `/app/backend/core/collectors/_common.py` enforces the new acceptance contract (must have a detail URL AND a numeric sale/rent price), pagination is discovered from live HTML (`<link rel=next>` / `<a rel=next>` / next-controls / configured selector — no `?page=N` fabrication), and every accepted card fires a polite (concurrency=2) detail-page fetch for enrichment.
- Structured diagnostics now live on every `CollectionRun`: `pages_visited` (list of `{url, cards_seen, cards_accepted, cards_rejected, final}`), `rejection_reasons` breakdown, `detail_pages_attempted/succeeded/failed`, `pagination_end_reason`, `duplicate_source_ids_within_run`, `records_passed_to_ingestion/inserted/updated`.
- **Accounting invariant now guaranteed**: `RunContext.record_diag` no longer double-bumps `cards_accepted`/`cards_rejected`; `record_page` recomputes run-level counters from per-page sums on every `final=True` and `_finalise_run` runs one more reconciliation pass — so `cards_seen == cards_accepted + cards_rejected` always holds at run and page level.
- **MarketMeri collector selector drift fixed**: card selector updated from stale `.listing, .ad, ...` to `.listing-wrapper-grid` — fresh run: 1257 cards seen, 769 accepted, 62/70 pages productive.

**Frontend — `Sources.jsx` `RunRow` component (P0 handoff item):**
- Recent Collection Runs table now has a per-row expand toggle (data-testid `run-toggle-<id>`) that reveals the structured diagnostics: 8 counter cards (Cards seen/accepted/rejected/Duplicates in-run/Pages followed/Detail attempted/succeeded/failed), rejection-reason badges (`rejection-<reason>`), pagination-end line, pages_visited sub-table, and error tails.
- Legacy runs (whose diagnostics is null or was recorded before the refactor) show a clear "diagnostics unavailable" note instead of crashing the row.

### TREL Data Management Suite — Phase 1 (validation) + Phase 2 (CSV I/O) + Phase 3 (seed protection) (Feb 27, 2026)

**Phase 1 — Field validation standardised (frontend labels + backend rules 100% aligned):**
- **Properties** — always required: `title`, `listing_type` (`sale` or `rent`), `property_type`, `price` (> 0), `province`, `location` (city), `suburb`; conditional Lot/Section/Street when scheme = lot_section_street, Portion Number when scheme = portion, Total Area (ha) for sale listings. `_enforce_scheme` in `routes/properties.py` now enforces every rule server-side; Listing Type label gained a red `*` on the admin modal.
- **Customers** — always required: `name`, `email`, `phone`, `customer_type` (one of buyer / seller / tenant / landlord / corporate). New `_validate_customer` gate runs on POST + PUT (merged-view for partial updates). Admin customer modal shows red `*` on Email, Phone, and Type; Save is disabled until all 4 are valid.
- **Leads** — untouched by explicit user request.

**Phase 2 — CSV Import/Export suite for Properties + Customers only:**
- New router `/app/backend/routes/csv_io.py` — endpoints:
  - `GET /api/admin/{entity}/csv/schema` — single source of truth for the Import Guide (field, type, explanation, required_headers)
  - `GET /api/admin/{entity}/csv/template` — empty CSV with just the header row
  - `GET /api/admin/{entity}/csv` — full export, date-stamped filename
  - `POST /api/admin/{entity}/csv` — multipart upload, **append-only**
- Import rules: header check first (400 with the missing-header list if any required header is missing), row-level errors are collected and returned in `{inserted, skipped, errors, received}`, rows with an existing `id` are **skipped never overwritten**, per-row validation reuses the SAME `enforce_scheme` / `_validate_customer` used by the interactive UI so CSV and UI behave identically.
- New shared React component `/app/frontend/src/components/admin/CsvToolbar.jsx` — 4 buttons (Import CSV / Export CSV / Download template / Import Guide toggle) + expandable Import Guide table (color-coded mandatory / conditional / optional / auto badges) + upload modal with a "Required headers" hint pulled from the schema endpoint + result modal with per-row errors + auto-clears the file input between imports.
- Wired into both `Properties.jsx` and `Customers.jsx` admin pages.
- Property schema exposes **30 fields** (6 mandatory + 6 conditional = 12 required headers); Customer schema exposes **10 fields** (4 required headers).

**Phase 3 — Data Protection (idempotent seeds):**
- `seed.py` refactored: every `seed_*` function now **skips entirely if the target collection has ≥1 document**. Existing docs are NEVER overwritten (previous versions could reset a user's password back to `Password@123` on every restart — fixed).
- Legacy one-off migrations (`migrate_legacy_user_emails`, `migrate_land_category`) kept — they are idempotent and only touch legacy records that need renaming.

**Tests: iteration 27 — 40/40 new pytest + 14/14 regression GETs + full frontend flows verified. Zero critical/minor issues.**

### Admin Property modal — grouped 5-step layout (Feb 27, 2026)
- Mirrored the Sell page grouped layout onto the Admin `PropertyModalFields`:
  1. **Basics** (FileText) — Title, Listing type, Bedrooms/Bathrooms/Parking, Area (sqm), Description, Features
  2. **Legal Description** (ScrollText) — Property Type + Total Area (ha) side-by-side, Province → City → Suburb, then dynamic Lot/Section/Street OR Portion Number based on the type's `legal_scheme`
  3. **Pricing & Valuation** (Wallet) — Price (PGK) with sale/rent-aware hint
  4. **Location Details** (MapPin) — Street address, Nearby landmark, Google Maps picker, Photos
  5. **Status & Visibility** (ShieldCheck) — Status dropdown + Featured + Verified checkboxes
- Cleaned up the legacy `property_type: "house"` and hard-coded `location: "Port Moresby"` defaults on `Properties.jsx` — new properties now start blank so the type-selection UX drives the legal-fields rendering cleanly
- Small internal refactor of `PropertyModalFields.jsx`: extracted repeated `TextField` + `SelectField` helpers to keep the file readable (~155 lines vs the previous 194)
- All existing `data-testid`s preserved: `property-title-input`, `property-type`, `property-price`, `property-allotment-number`, `property-full-portion-number`, `property-total-area-ha`, `property-featured`, `property-verified`, etc.
- New section `data-testid`s: `prop-section-basics`, `prop-section-legal`, `prop-section-pricing`, `prop-section-location`, `prop-section-status`
- Verified via screenshots: House shows Lot/Section/Street; Large Land Portion shows only Portion Number; backend POST /properties round-trip returns the correct wiped/kept legal fields.

### Sell page — grouped section layout (Feb 27, 2026)
- **4-step grouped card layout** replaces the flat grid:
  1. **Owner Information** (User icon) — Full Name, Email, Phone
  2. **Legal Description** (ScrollText icon) — Property Type + Total Area (ha) side-by-side; Province → City → Suburb; then dynamic legal fields:
     - `legal_scheme = "portion"`: **Portion Number** only (Lot/Section/Street hidden)
     - `legal_scheme = "lot_section_street"` (default): Lot Number + Section Number + Street Name (Portion Number hidden)
  3. **Pricing & Valuation** (Wallet icon) — Expected Price (PGK) with inline AI Price Analysis
  4. **Location Details** (MapPin icon) — Nearby Landmark + Google Maps + Photos
- New shared `<FormSection>` component (`/app/frontend/src/components/FormSection.jsx`) renders numbered "STEP N" kicker + serif title + icon tile (BRAND_BLUE #0d50e0 with 15% alpha)
- `LeadFormPage` gained an optional `sectionsMode` prop; when true it wraps Name/Email/Phone in Section 1 and moves "Tell us more" + CAPTCHA + Submit into a final card. Other pages (Contact, Wanted, Corporate, Management) are unchanged.
- All existing `data-testid`s preserved (sell_form-type, sell_form-price, sell_form-allotment-number, etc.); new test IDs added: `sell_form-section-owner`, `sell_form-section-legal`, `sell_form-section-pricing`, `sell_form-section-location`
- Verified: House → shows Lot/Section/Street; Large Land Portion → shows only Portion Number; Total Area placeholder auto-adjusts (0.0824 vs 12.5)
- Self-tested via screenshot; no backend changes.

### Backend refactor + Customer Communications (Feb 27, 2026)
- **Server refactor** — `server.py` shrunk **1850 → 60 lines**. Broken out into:
  - `/app/backend/core/` — `db.py` (mongo + helpers), `security.py` (JWT + bcrypt + captcha + honeypot), `notify.py` (auto-assign + in-DB email sim)
  - `/app/backend/models.py` — all Pydantic schemas (single file, 341 lines)
  - `/app/backend/routes/` — 15 focused router files (auth, properties, property_types, customers, requirements, leads, inspections, tasks, matching, locations, ai, content, reports, public, files) averaging ~110 lines each
  - `/app/backend/seed.py` — startup migrations & seeding (`run_startup()`)
  - `/app/backend/seed_data.py` — static defaults (page content, sample properties, users)
  - Absolute imports throughout (uvicorn command unchanged: `server:app`)
- **Customer Communications** — extended existing lead-only communications to also work for customers:
  - Backend: added `GET/POST /api/customers/{cid}/communications`. `Communication` schema now uses `parent_type` + `parent_id` (with `lead_id` / `customer_id` mirror fields kept for convenience + backward compat).
  - Legacy-doc fallback: `GET /api/leads/{lid}/communications` matches both new (`parent_type='lead', parent_id`) AND legacy docs (`lead_id` only) via `$or`.
  - Cascade delete: deleting a customer removes their communications; deleting a lead removes both legacy + new-schema comms.
  - Frontend: `CommunicationsPanel` now accepts a generic `parent={type,id,name,subtitle}` prop in addition to the legacy `lead={...}`. Admin Customers page renders a per-row `MessageSquare` icon (`data-testid=customer-comms-{id}`) that opens the drawer targeting `/api/customers/{cid}/communications`.
- **Fixes this iteration**:
  - Backend `POST /api/property-types` `TypeError` (duplicate `name` kwarg) — refactored dict build.
  - `Wanted.jsx` legacy `property_type: "house"` default reset to blank.
- Tests: iteration 26 — **28/28 pytest** (`test_iter26_communications.py`) + **62/62 regression** across all previously-passing suites. **100% frontend flows** for customer + lead communications drawer with cross-parent isolation verified.

### Property Type consolidation — dynamic property_types + legal_scheme (Feb 27, 2026)
- **`land_category` REMOVED** — replaced by a single dynamic `property_types` MongoDB collection. Each type carries a `legal_scheme` of `"lot_section_street"` (requires allotment_number + section_number + street_name) OR `"portion"` (requires full_portion_number).
- **6 default types seeded idempotently on startup**: House, Apartment, Town House, Commercial, Vacant Land – Urban Subdivided (all lot_section_street); Large Land – Portion / Customary (portion).
- **Startup backfill migration** maps legacy lowercase `property_type` values (house/apartment/townhouse/commercial/land) to the new titled names, converts old `land_category=='large_portion'` rows to the new portion type, and `$unset`s the `land_category` field from every property document.
- **Backend endpoints**: `GET /api/property-types` (public, active only), `GET /api/property-types/all` (admin), `POST /api/property-types` (admin, unique name → 409 on dup), `DELETE /api/property-types/{id}` (admin).
- **Scheme enforcement**: `_enforce_scheme(payload)` on every POST/PUT `/properties` looks up the type's legal_scheme, requires the correct legal fields, and **wipes the ones that don't apply** so the DB stays consistent. `land_category` is stripped from PUT payloads for safety.
- **New shared components**:
  - `/app/frontend/src/lib/usePropertyTypes.js` — tiny module-level cache + `usePropertyTypes()` hook + `isPortionScheme(types, name)` helper.
  - `/app/frontend/src/components/PropertyTypeSelect.jsx` — shared dropdown; when `admin` prop is set, exposes an inline "＋ Add new type…" option (opens `property-type-add-modal` with name + lss/portion radio) and per-type × chips with confirm-delete.
- **Frontend wiring**: `PropertyModalFields.jsx` (admin), `Sell.jsx`, `Wanted.jsx`, and `Search.jsx` (Buy/Rent filter) all use `PropertyTypeSelect`. Sell + Admin modal use `isPortionScheme` to switch the legal-fields UI (Lot/Section/Street vs Portion) and require the right fields.
- **AI Vicinity Awareness**: `AIPriceAnalysis.jsx` now includes `street_name` + `nearby_landmark` in the payload for tighter Claude localization.
- **Fixes this iteration**:
  - Backend `POST /api/property-types` had a duplicate `name` kwarg crash (`TypeError: got multiple values for keyword argument 'name'`) — refactored to build the doc dict cleanly.
  - `Wanted.jsx` initial state had legacy `property_type: "house"` (no matching option after refactor) — reset to `""`.
- Tests: iteration 25 — **12/12 pytest backend** (`/app/backend/tests/test_property_types_refactor.py`) + **100% frontend flows** (public Sell / Wanted / Buy filter / admin Property modal add + scheme switching + inline add-type modal + delete chips). Zero critical/minor issues.

### Lead lock + Property legal fields + Phone formatting (Feb 22, 2026)
- **AU phone updated to 9 digits** (leading `0` dropped). PhoneInput now displays formatted groups: PNG `7628 1552` (4-4), AU `4 1234 5678` (1-4-4). Digit-only storage on the wire.
- **Property legal & location fields** added: `land_category` (large_portion / subdivided_town_land), `full_portion_number`, `allotment_number`, `section_number`, `total_area_ha`, `street_name`, `nearby_landmark`. Total area (hectares) is required only when `listing_type='sale'`. Admin Property modal conditionally shows the appropriate mandatory fields.
- **Public PropertyDetail** now renders a "Legal & location details" block with allotment/section OR full portion, total area (up to 4 dp), street name, and nearby landmark.
- **Lead lock** on conversion:
  - Backend `PUT /api/leads/{id}` on a converted lead → **409 Conflict**. Same for `DELETE`.
  - Backend auto-stamps `converted_at` + `converted_property_id` when a PUT transitions status→`converted` with a `property_id`.
  - Admin Leads UI shows a 🔒 chip on locked rows, replaces the status dropdown with **Read-only**, hides the Convert button, and shows **Go to Property** + **View** buttons.
  - Locked-lead modal (`LockedLeadModal`) is a plain read-only summary card — banner + `dl` list, no form inputs.
- Tests: iter-24 backend 6/6 pytest pass; frontend 100% functional pass. LOW-priority precision fix on total_area_ha display applied post-report.

### Global Data Validation (Feb 22, 2026)
- **Shared validators** at `/app/frontend/src/lib/validators.js`: `sanitizeName`, `sanitizeDigits`, `sanitizePrice`, `parsePhone/joinPhone/isValidPhone`, `validateForm`, `isPlaceholder`, `warnOnce` (throttled toast, 1 per 2 s).
- **Shared inputs**: `NameInput.jsx` (A–Z + spaces + `'` + `-`, max 25 chars); `PhoneInput.jsx` (country dropdown PNG +675 (8 digits) / AU +61 (9 digits), digit-only, country selection preserved on empty digits); `PriceInput.jsx` (K prefix, digits only, 0..K100M cap, live formatted preview).
- **Wanted form**: min/max PriceInputs with `max ≥ min` inline validation, `intent`/`min_price`/`province`/`city` required, submit blocked on any missing.
- **Sell form**: PriceInput + LocationPicker `required`, `extraRequired` uses `isPlaceholder`.
- **PropertyDetail** contact + inspection forms use NameInput + PhoneInput.
- **Admin** Customer modal and Property modal both use the shared sanitised inputs; Bed/Bath/Parking/Area strip non-digits.
- Tests: iteration 23 — 100% functional pass across every form + edge cases (25-char truncation, PNG/AU country switch, max<min error, blank submit blocked, no API request on invalid).

### AI Price Analysis — Audience-aware copy + repositioned badge (Feb 22, 2026)
- Added `audience: 'buyer' | 'seller' | 'admin'` prop to `AIPriceAnalysis`.
- Recommendation text is now **replaced** with cautious, audience-specific canned copy (matrix of 9 sentences) — Claude's raw recommendation is intentionally overridden to keep tone consistent and safe.
- Universal disclaimer *"This analysis is based on available data and should be used as a guide only."* appended to every panel/modal (italic, muted, `data-testid=*-disclaimer`).
- Softer verdict labels: buyer sees "Below market / Above market / In line with market"; seller sees "Below market range / Above market range / Aligned with market"; admin keeps raw analyst labels.
- **PropertyCard restructured (variant B1)**: AI badge moved from `absolute top-3 right-3` (floating over image) to **inline right-aligned in the price row** (`flex items-baseline justify-between`). The Price + AI wrapper is a **sibling to the `<Link>`** — preserves nested-anchor bug fix.
- Wired `audience` at all call sites: PropertyCard/PropertyDetail = "buyer", Sell = "seller".
- Tested: iteration 22 — 100% pass across Buy/Rent card layout, PropertyDetail buyer copy, Sell seller copy, mobile viewport, no nested anchors, no regression on Nearby Amenities/Map link.

### AI Nearby Amenities (Feb 21, 2026)
- Backend `POST /api/ai/nearby-amenities` powered by Claude Sonnet 4.5 via `emergentintegrations`.
- Returns 6 possible categories (schools, hospitals, shopping, beaches, transport, recreation) with `{name, distance_hint, note}` items — capped at 4 items/cat, 6 cats, and length-clamped.
- Defence-in-depth server-side sanitiser strips URLs and long digit runs (phone numbers) from names/notes.
- Frontend `NearbyAmenities.jsx` — collapsible panel on PropertyDetail under Description/Features, blue `#0d50e0` theming, category icons (GraduationCap, HeartPulse, ShoppingBag, Waves, Bus, TreePine).
- Lazy fetch on first open; cached in component state; disclaimer at bottom.
- `canRun` guard hides the panel entirely on properties without suburb or city.
- Tests: `/app/backend/tests/test_nearby_amenities.py` (6/6). Iteration 21: 100% pass on backend + frontend + mobile + edge cases.

### Interactive Map Picker + "No coords" empty state (Feb 21, 2026)
- **Global `MapPickerDialog.jsx`** — Leaflet + OpenStreetMap picker (no API key). Blue `#0d50e0` "Pick on Map" button on every `MapCoordsField` (Sell page, Admin PropertyModal, Contact, Content). Click-to-drop-pin, draggable pin, Nominatim search box.
- **Smart auto-center chain**: existing coords → `suburb, city, province` → `city, province` → `province` → Port Moresby fallback (all geocoded via Nominatim).
- **Responsive**: full-screen dialog on mobile with sticky header/footer; 44px min-tap-target buttons; 640×85vh on desktop.
- **`MapCoordsField` API extended** with optional `city`/`suburb`/`province` props. Sell.jsx + PropertyModalFields.jsx pass them from their form state.
- **Bundle-friendly**: `MapPickerDialog` is `React.lazy`-loaded — Leaflet only downloads when the picker is opened.
- **"Not registered" empty state** on public Buy/Rent PropertyCards and PropertyDetail: when `map_coords` is missing/unparseable, show a dashed "Google location not registered for this property" note (`card-map-empty-{id}` / `detail-map-empty`) instead of a broken fallback URL. Properties with coords show the pine-green "View on Google Maps" pill.
- Deps: `leaflet@1.9.4`, `react-leaflet@5.0.0` (React 19 compatible).
- Tested: iteration 20 — 100% functional pass on Sell/Buy/Rent/Detail/Admin edit + mobile viewport.

### Unified AI Price Analysis — Claude Sonnet 4.5 (Feb 21, 2026)
- Backend endpoint `POST /api/ai/price-analysis` powered by `emergentintegrations` + Claude Sonnet 4.5 via the Emergent LLM key
- Returns structured schema: `{range_min, range_max, average, verdict, recommendation, comparables[], sample_size}`
- Deterministic statistical fallback if LLM call fails or no comparables — never surfaces a 500
- Server-side sanitisation: strips PII (agent/owner/id/urls) from comparables, caps title 120ch, recommendation 280ch, comparables to 5
- Frontend component `AIPriceAnalysis.jsx` (203 LOC, dual-variant: inline expandable panel + compact modal)
- Wired into: Sell page (inline), Buy/Rent PropertyCards (compact modal, absolute-positioned with `preventDefault` to avoid link click-through), PropertyDetail page (inline next to price)
- `canRun` guard: requires property_type AND (city||suburb) AND price>0 — hides button on zero-price/incomplete listings
- Full data-testid coverage: `ai-price-btn|-panel|-modal|-body|-verdict|-range|-average|-recommendation|-comparables|-error|-loading|-close|-container`
- Backend tests: `/app/backend/tests/test_ai_price_analysis.py` (6/6) — valid sale, valid rent, zero-price 400, missing-location 400, missing-required 422, no-PII assertion
- Regression tested via iteration_19: 100% pass across backend AI + all critical frontend flows

### Customers admin page — full CRUD (Feb 20, 2026)
- Added **"Add Customer"** button + per-row **Edit** (pencil) and **Delete** (trash) actions
- Modal form updates: name (required), email, phone, type (Buyer/Seller/Tenant/Landlord/Corporate), company, notes
- Type badges use distinct colors (buyer=blue, seller=emerald, tenant=purple, landlord=amber, corporate=pine)
- Case-insensitive search across name/email/phone/company
- Save-in-flight guard: button shows "Saving…" and modal backdrop close is blocked mid-request
- Backend endpoints (POST/PUT/DELETE `/api/customers`) unchanged — already existed and wired correctly
- Backend tests: `/app/backend/tests/test_customers.py` (6/6)

### Convert Sell-Form Lead → Property (Feb 20, 2026)
- Admin Leads page: for every lead where `source === 'sell_form'`, shows a new **"Convert to Property"** button
- Clicking it opens the PropertyModal PRE-FILLED with the lead's payload:
  - title = `<suburb> <property_type>` (editable), listing_type = 'sale'
  - property_type, price, province, location (city), suburb, map_coords all copied from `lead.payload`
  - photos array preserved
  - description auto-composed from lead.message + "Original seller: name (email) — phone" so admins retain the source
- On Save: creates the property AND updates the lead with `status='converted'`, `property_id=<new id>`, `property_title=<new title>`. Property creation is rolled back if the lead-link PUT fails
- Save button disables while in-flight to prevent double-submits
- Lead is **NOT deleted** — appears under the Converted filter with a clickable link to `/property/{new_id}` (opens in new tab)
- Convert button auto-hides on already-converted leads
- Backend tests: `/app/backend/tests/test_lead_convert.py` (9/9) + 46/46 regression

### Unified Location System — Province → City → Suburb (Feb 20, 2026)
- **Backend collections**: `provinces` (unique name), `cities` (name+province_id unique, references province), `suburbs` (name+city_id unique, references city + province, `source: 'admin'|'user'`).
- **Public read endpoints**: `GET /api/locations/{provinces|cities?province_id=|suburbs?city_id=}`.
- **Public write** (no auth): `POST /api/locations/suburbs` — idempotent by name+city, tags new records `source='user'`.
- **Admin CRUD**: `POST/PUT/DELETE /api/admin/locations/{provinces|cities|suburbs}/[id]` with cascade delete.
- **Seed**: 8 PNG provinces (NCD/Morobe/Madang/WHP/ENB/SHP/E.Sepik/Enga) + Port Moresby + Lae + Madang + Mount Hagen + Kokopo cities + 21 suburbs — all idempotent on restart.
- **Backfill migration**: existing property records get their `province` filled in by matching their `location` (city name) at startup.
- **New reusable `<LocationPicker>`** with cascading dropdowns and inline "➕ Add a new suburb…" (`sell_form-location`, `wanted_form-location`, `property-location` prefixes).
- **New Admin sub-page** `/admin/locations` — 3-column master-detail with rename/delete + user-added badges. Sidebar entry added between Users and Content.
- **Property model** gains `province`. Sell / Wanted / Admin Property forms all use `LocationPicker` (old free-text fields removed).
- **Tests**: `/app/backend/tests/test_locations.py` (13/13) + 33/33 regression = **46/46 all backend suites pass**.

### Sell page redesign — blue theme + icons + valuation CTA (Feb 20, 2026)
- Blue theme (`#0d50e0`): kicker "WHY SELL WITH TREL", heading, and CTA button
- Four benefits (up from 3) with uniform lucide SVG icons in soft blue tiles:
  - Professional valuation (BadgeCheck) — paid service, 2–3 day turnaround
  - Professional photography (Camera)
  - Verified marketing (Megaphone)
  - Dedicated agent support (Headphones)
- New **"Request a Valuation"** CTA button — blue background, white text, subtext "Get your property valuation within 2–3 days.", smooth-scrolls to the form
- All "Free appraisal" wording replaced with "Professional valuation" / "Request a Valuation"
- Backend migration in `_seed_page_content` idempotently overwrites legacy Sell benefits on startup
- Admin Content editor for Sell benefits now includes an `icon` field (lucide name)
- Verified by testing agent iteration 12: 36/36 backend, 100% frontend, responsive 375px→1440px

### Sell page 'refused to connect' re-fix (Feb 17, 2026)
- Root cause: users naturally pasted the FULL Google Maps URL into the coords field. The previous code URL-encoded the whole thing and re-appended it after `?q=`, producing broken nested URLs like `.../maps?q=https%3A%2F%2Fwww.google.com%2Fmaps%3Fq%3D...` that Google refused.
- Fix: `MapCoordsField` now runs a `parseCoords()` regex on whatever the user types/pastes and extracts `lat,lng` from any of these formats:
  1. Raw coords `-9.4438,147.1803` (with/without spaces)
  2. Full Google URL `https://www.google.com/maps?q=lat,lng`
  3. Place URL `.../maps/@lat,lng,17z/...`
  4. Place URL `.../maps/place/lat,lng`
- The preview link is now ALWAYS a clean `https://www.google.com/maps?q=lat,lng`.
- Invalid input shows an inline warning; empty input shows nothing.
- Renamed link from "Preview on Google Maps" → **"View on Google Maps"** and switched to `rel="noopener noreferrer"`.
- `mapsUrlFromCoords()` now normalizes internally, so even legacy stored `map_coords` values that contain full URLs render correctly on Property Detail + Contact.
- Verified in testing agent iteration 11 by actually opening the new tab and confirming successful navigation to google.com/maps.

### 'Refused to connect' fix — Maps iframe removed (Feb 17, 2026)
- Contact page no longer embeds Google Maps in an `<iframe>` (Google blocks embedding via X-Frame-Options / CSP → "refused to connect").
- Replaced with a single big **"View on Google Maps"** button (`[data-testid=contact-view-map-btn]`, `target=_blank rel=noreferrer`) that opens the exact location in a new tab.
- Coords priority preserved: `contact.map_coords` → `site.map_coords` → encoded `site.address`.
- Removed the now-unused `mapsEmbedFromCoords` helper.
- Verified by testing agent iteration 10: 0 Google Maps iframes on all 12 public pages.

### Google Maps Coordinate Input System (Feb 17, 2026)
- **New reusable `<MapCoordsField>`** component at `/app/frontend/src/components/MapCoordsField.jsx` with:
  - Hard-coded read-only prefix `https://www.google.com/maps?q=`
  - Coordinate text input (e.g. `-9.4438,147.1803`)
  - Standard instruction text ("Open Google Maps, drop a pin on your property, right-click the pin, copy the coordinates, and paste them after the link above.")
  - Live "Preview on Google Maps" link
  - Exported helpers: `MAPS_BASE`, `mapsUrlFromCoords(coords)`, `mapsEmbedFromCoords(coords)`
- **Property model** gains `map_coords: Optional[str]`
- Wired into:
  - Admin Property form (add/edit) — with new `address` text field above it
  - Public Sell form (extras section, optional)
  - Admin Content → Branding & Site (office coords)
  - Admin Content → Contact page (overrides branding coords)
- **All "View on Map" buttons/iframes** now use `https://www.google.com/maps?q={coords}` when coords are set, falling back to the same base with an encoded address search otherwise:
  - Property Detail "View on Google Maps" pill
  - Contact page Google Maps iframe + "Open in Google Maps" link
- Backend tests: `/app/backend/tests/test_map_coords.py` (4/4) + 29/29 regression tests still pass.

### PageContent architecture (Feb 17, 2026)
- **New `page_content` MongoDB collection** — one doc per public page (`home`, `about`, `sell`, `buy`, `rent`, `wanted`, `management`, `corporate`, `contact`, `legal_privacy`, `legal_terms`). Deep-merge with server-side defaults so callers always get a fully-populated object.
- **New API endpoints** (all `/api`): `GET /page/{slug}` (public), `PUT /page/{slug}` (admin), `POST /page/{slug}/list/{section}` (admin — append), `DELETE /page/{slug}/list/{section}/{index}` (admin — remove).
- **Admin `/admin/content` rebuilt** as a 12-tab editor (Branding & Site + 11 pages) with grouped section editors, list add/remove for team/values/services/benefits, and integrated single-image uploader (`ImageField`) that pushes to Emergent object storage.
- **Public pages fully rewritten to consume page content** via `usePage(slug)` hook: Home (hero + featured intro + why-us + wanted teaser + CTA band), About (hero + story + mission + vision + values + team), Sell (hero + benefits), Buy/Rent (hero over search), Wanted (hero + active-requirements), Management/Corporate (hero + services grid), Contact (hero + business hours + map + action buttons), Privacy/Terms (title + body).
- **LeadFormPage** gains `heroImage` prop and a "Submit another" button on the success card.
- Backend tests: `/app/backend/tests/test_page_content.py` (21/21 pass).

### Phase 1 Fixes (Feb 17, 2026)
- Math CAPTCHA replaced with alphanumeric CAPTCHA (5-char, case-insensitive, excludes 0/O/1/I/l, 15-min JWT expiry)
- HumanVerification widget shows code with obfuscated wavy strikethrough styling
- Contact page: Google Maps iframe (dynamic from `site.address`) + Call Now / Email Us / WhatsApp Chat action buttons + "Open in Google Maps" link
- PropertyDetail: "View on Google Maps" pill next to the address (opens google.com/maps/search in new tab)
- PropertyDetail sidebar contact-enquiry and inspection forms now show inline success cards (not just toasts)
- LeadFormPage already renders a clean "Thank you" success view for Sell/Contact/Wanted/Management/Corporate
- PublicFooter: removed redundant duplicate backgroundColor style

### Brand assets & SEO (rebranded to TREL)
- Logo, favicon, OG/social share image, og:description, agency_name, short_name, tagline, phone, WhatsApp, email, address — all editable via `/admin/content`
- URL fields render a live preview in the admin form
- `BrandingHead` component applies favicon + OG tags + document title dynamically from site content on every route (also baked into `index.html` for first-paint SEO)
- Startup migration backfills favicon_url / og_image_url / og_description on existing DBs

### Public website
- Home (hero with dual-tab search, featured properties, why-us, wanted preview, CTA)
- Buy / Rent search with filters (type, location, price range, bedrooms, keyword)
- Property Detail (gallery, features, WhatsApp/phone CTAs, inspection request, enquiry form)
- Sell, Property Wanted (with public anonymous requirements listing), Property Management, Corporate Services forms
- About, Contact, Privacy, Terms

### Internal CRM (`/admin/*`)
- Dashboard (KPIs, leads by source bar chart, recent leads)
- Properties (CRUD, modal editor with features/images/status/featured/verified)
- Customers (CRM view, auto-created from public forms)
- Leads (status pipeline, filter, inline status change)
- Requirements (buyer/tenant briefs, run-matching shortcut)
- Property Matching (rule-based scoring engine)
- Inspections (status + feedback)
- Tasks (create, due date, priority, mark done)
- Pipeline (kanban with sales / leasing tabs, move cards across statuses)
- User Management (admin can create/delete staff; RBAC)
- Website Content Management (site details + About page)
- Reports (bar + pie charts, KPI grid)

### Backend integrations & workflows
- Public form submission → auto-creates Lead + Customer (+ Requirement for wanted/corporate)
- Auto-assignment of Sales/Leasing agents by source
- Rule-based matching engine (intent, type, price, beds, location weighting)
- In-app notification log ("email_sim") for every public submission
- Seed script (idempotent) — 6 properties, 5 users, 2 requirements, site/about/why content

## Test Credentials
- Admin: `admin@trel.com.pg` / `Admin@123`
- All other staff: `Password@123`

## Testing
- Iteration 1: 23/23 backend tests passed, 100% of tested frontend flows verified (see `/app/test_reports/iteration_1.json`).
- Iteration 19 (Feb 21, 2026): Full regression on Unified AI Price Analysis — 6/6 new AI tests + 100% frontend flow coverage (Sell/Buy/Rent/Detail/Admin/Leads/Maps). No issues.

## Backlog (deferred to V2)
- P1 — Real email provider (Resend/SendGrid) for confirmations
- P1 — WhatsApp Business API integration (currently `wa.me` deep links)
- P1 — Communication history — external channels (auto-log outbound email/SMS/WhatsApp once providers wired)
- P2 — Advanced reporting (revenue, agent performance, conversion funnel)
- P2 — Data export (CSV/Excel)
- P2 — Audit log UI (records currently written to Mongo but no UI yet)
- P2 — SEO metadata per property, search-friendly URLs
- P2 — Mobile app, tenant/owner portals, online rent payment (explicitly out-of-scope in V1)
- P2 — Test hygiene: update `/app/backend/tests/backend_test.py` stale admin creds (`admin@pngrealty.pg` → `admin@trel.com.pg`); make `test_lead_convert.py` / `test_locations.py` use `os.environ.get(...)` at import time; add `total_area_ha` to sale-property fixtures in `test_lead_convert.py`, `test_iter24_lock_and_legal.py`, `test_map_coords.py`

## Next Actions
1. Provide branded logo/photography if not using placeholders
2. Add real email + WhatsApp Business API integration when keys available
3. Split `server.py` into modular routers for maintainability
4. Implement Communication History module (calls/notes timeline)

---

## Phase 1 — Market Intelligence Data Aggregation (Feb 2026)

Foundational schema for the PNG Property Market Intelligence platform built
against the two TRELPNG algorithm specs:
- MATCH-1.0 — Duplicate Matching & Property Identity
- GUIDE-1.0 — Comparable Property Selection & Market Price Guidance

### New collections (all with idempotent indexes)
- `market_sources` — configured scrapers/feeds (unique `name`)
- `collection_runs` — scrape audit log per source
- `market_listings` — raw source ads (unique `(source_id, source_listing_id)`)
- `market_listing_snapshots` — price/status history per listing
- `master_properties` — persistent parcel/site identity (indexed on
  `(lot_number, section_number, suburb)` + `trel_property_id`)
- `property_units` — child sub-units under a master
- `property_matches` — reversible listing→master/unit link (history preserved
  via `status: active|detached|superseded`)
- `market_review_cases` — manual queue for probable/possible/conflict
- `market_audit_events` — immutable audit trail (every write emits one)
- `location_reference` — canonical province → district → suburb → local_area
  → street hierarchy + aliases (bootstrapped from existing province/city/
  suburb data)
- `market_configuration` — versioned params (baseline `COMBINED-1.0` seeded
  with every threshold/weight/tolerance from the algo specs — 34 param
  sections). Versioning enforced by `(version, algorithm)` unique index; one
  active row per algorithm.
- `valuation_requests` + `guidance_results` + `guidance_comparables` —
  guidance-engine schemas modeled now, populated in Phase C.

### Backfill migration (idempotent)
- `migrate_backfill_master_properties`: any `properties` row without a
  `master_property_id` gets a 1:1 master auto-created (class inferred from
  property type, area converted ha→m², portion/lot/section carried across).
  Ran on first boot — 9/9 existing properties linked.

### New API endpoints (all under `/api/admin/market/*`)
- Sources: GET / POST / PUT / DELETE
- Collection runs: GET
- Market listings: GET (list, single)
- Master properties: GET (list, single), POST, PUT
- Property units: GET, POST, PUT
- Property matches: GET, POST `/matches/{id}/detach`
- Review cases: GET, PUT
- Audit events: GET
- Configuration: GET (list, active), POST (new version), POST `/config/{id}/activate`
- Location reference: GET, POST
- Dashboard summary: GET `/summary`

### Test status (Phase 1)
- ✅ curl smoke tests: source CRUD, dedup rejection, audit trail growth,
  config versioning + activation swap, master-property list, location
  reference bootstrap, property→master linkage (9/9)
- Not blocked. Ready to proceed to Phase B (matching engine).

## Next Actions (updated)
1. Phase B — Manual Master Property + Match UX (Admin UI)
2. Phase B — Deterministic-rule matcher (D1–D6) + weighted scorer implementation
3. Phase C — Rule-based Guidance Engine (Comparable selection + CQS + weighted P25/P75)
4. Phase D — 4 customer-facing Price Compare screens
5. Phase E — Public listing collectors/scrapers (per-source modules)
6. Phase F — Admin aggregation dashboard + evidence inspector
7. Phase G — Location dictionaries expansion + parameter tuning governance

## Phase 1 UI — Admin Menu & 10 Skeleton Screens (Feb 2026, later same day)

Grouped sidebar (Operations · Property Data Aggregation · Administration).
Every menu item from the user-provided mockup is now navigable at
`/admin/market/*`:

| # | Route                              | Data source (Phase 1) |
|---|------------------------------------|-----------------------|
| 1 | `/admin/market`                    | Live — /summary + /runs + /review-cases |
| 2 | `/admin/market/evidence`           | Live — /listings (empty until Phase E) |
| 3 | `/admin/market/comparables`        | Placeholder — Phase C |
| 4 | `/admin/market/trends`             | Placeholder — Phase C/F |
| 5 | `/admin/market/sources`            | **Full CRUD** — verified end-to-end |
| 6 | `/admin/market/duplicates`         | Live — /matches + /review-cases |
| 7 | `/admin/market/price-compare`      | Placeholder — Phase C |
| 8 | `/admin/market/review-cases`       | Live — list + mark-in-review/resolve/dismiss |
| 9 | `/admin/market/config`             | **Full CRUD** — view + publish new version + activate |
| 10| `/admin/market/audit`              | Live — read-only with entity filter |

Shared UI: `_shared.jsx` (PageHeader, KpiCard, Section, PhaseBanner).
Every interactive element has a `data-testid`. Live smoke test:
Add-Source flow → toast → KPIs update → table populated → audit event emitted.

## Phase B + C — Matcher & Guidance Engines Live (Feb 2026, same day)

### MATCH-1.0 pipeline (`/app/backend/core/matcher.py`)
- Public entry: `ingest_market_listing(payload, actor_id)` — used by
  POST `/api/admin/market/listings` and `/{id}/rematch`.
- Stages: eligibility → dedup upsert by (source_id, source_listing_id) →
  candidate generation (5 keyed queries) → D1–D6 deterministic rules →
  weighted 100-pt scoring → decision band → auto-attach, review case, or new
  master. Every write emits an audit event with `algorithm_version` +
  `config_version`.
- Hard conflicts (lot conflict / suburb conflict / class vacant-vs-improved /
  gps >500m) block deterministic rules and subtract 30 per conflict from the
  weighted score.

### GUIDE-1.0 pipeline (`/app/backend/core/guidance.py`)
- Public entry: `generate_guidance(subject, workflow, actor_id)` — used by
  POST `/api/admin/market/guidance/run`.
- Pools observations from BOTH `market_listings` (external) AND linked TREL
  `properties` (internal fallback via `trel_property_id`) so Phase 1 already
  produces meaningful ranges without scrapers.
- Computes per-comparable Comparable Quality Score (0-100) using class-
  specific baselines, applies recency + tier factors → `effective_weight`,
  IQR outlier filter (≥ 6 comps), weighted P25/P75 range, weighted median,
  confidence label with quantity gate.
- Persists `valuation_requests`, `guidance_results`, `guidance_comparables`
  with full breakdown so every result is reproducible + auditable.

### Config UI (`/app/frontend/src/pages/admin/market/Config.jsx`)
- 5 tabs: Duplicate Matching · Comparable Selection · Price Guidance · CQS
  Baseline · Advanced JSON.
- Threshold sliders, GPS/size numeric inputs, per-signal weight tables,
  editable size-similarity bands, per-class CQS allocation.
- Publish button creates a new version row + activates it in one call
  (deactivates prior). Any prior version is one click away via "Activate".

### Comparables UI (`/app/frontend/src/pages/admin/market/Comparables.jsx`)
- Subject property form (purpose/class/subtype/location/beds/baths/area/asking).
- Live "Run Guidance" → KPI cards (count, weighted median, TREL indicative
  range, confidence), Included / Outliers / Excluded tabs, per-row tier +
  CQS + recency + effective weight + value.
- Recent runs history reloads any past run into the view.

### Duplicates UI (`/app/frontend/src/pages/admin/market/Duplicates.jsx`)
- Confirmed / Probable / Possible / Conflicts tabs.
- Signal-breakdown detail panel per row: method, band, per-signal weight
  contributions, conflicts, algo+config version, "Detach match" action.
- "+ Ingest Test Listing" utility button opens a form so admins can drive
  the matcher end-to-end without needing the scraper.

### Test status (iter-28)
- Backend: 10/10 pytest pass (`/app/backend/tests/test_iter28_market_matching_guidance.py`)
- Frontend: 3 admin market screens verified via Playwright — Config, Duplicates, Comparables
- No critical or minor issues. DB restored clean.

## Phase 1 (expanded) — Source/Run Infrastructure (Feb 2026, later same day)

Full scraper-facing plumbing on top of the existing ERD.

### ERD field parity
- `MarketSource` +collection_frequency (manual/hourly/daily/weekly),
  +parser_version, +last_run_at, +last_successful_run_at,
  +consecutive_failures.
- `CollectionRun` +run_type (scheduled/manual/backfill), +triggered_by,
  +duration_ms, +matches_created, +review_cases_created, +parser_version;
  status enum extended with "partial".

### Scraper contract (`/app/backend/core/runs.py`)
```python
async with collection_run(source_id, triggered_by=user_id) as run:
    for raw in scraper.iter():
        await run.ingest(raw)     # runs MATCH-1.0, credits counters
```
`RunContext.ingest` never raises — per-item errors go onto the run doc.
Context exit auto-finishes with success/partial/failed, updates
source-health counters, emits `run_success|partial|failed` audit event.

### New endpoints
- `POST /api/admin/market/runs/start` — manual run start
- `POST /api/admin/market/runs/{id}/listings` — batch ingest
- `POST /api/admin/market/runs/{id}/finish` — explicit finish
- `GET  /api/admin/market/runs/{id}` — single run detail
- `GET  /api/admin/market/sources/health?window=10` — per-source rolling
  success/error/partial rates, avg duration, streak of failures
- `GET  /api/admin/market/listings/{id}/snapshots` — price/status history

### UI updates
- Data Sources page: Frequency, Parser, Success %, Runs, Fail streak, Last
  run columns; per-row "Run" button; frequency dropdown + parser input in
  the source modal.
- Configuration page: new "Data Retention" tab (raw / normalized / review /
  audit retention in days + soft-delete-only switch).
- Retention params seeded into every existing config on boot
  (idempotent migration in `seed.py`).

### Test status (iter-29)
- 14/14 pytest pass (`/app/backend/tests/test_iter29_source_runs.py`)
- 6/6 frontend UI verifications pass
- Zero critical or minor issues. DB restored clean.

## Phase E + F — Collectors, Charts, Public Price Compare, Scheduler (Feb 2026)

### Collector Framework (`core/collectors/`)
- `CollectorBase` abstract class + `@register` decorator + `registered()` list
- Ships 2 concrete collectors:
  - `seed` — synthetic PNG-market generator (12 varied listings across 8
    suburbs, deterministic per `source_id`, zero network deps). Powers all
    demos + CI.
  - `hausples_png` — real HTTP adapter scaffold for hausples.com.pg (uses
    httpx, best-effort probe, safe to enable when the collector's parser is
    firmed up).
- `MarketSource.collector` field selects which implementation runs.
- `POST /api/admin/market/sources/{id}/collect` — one-shot: opens a
  `collection_run`, drives the source's collector, closes the run. Returns
  the final run doc.

### Scheduler (`core/scheduler.py`)
- Single asyncio background task started from server.py startup event
- Ticks every `SCHEDULER_TICK_SECONDS` (default 60s), enforces per-source
  cooldowns (hourly/daily/weekly) with exponential back-off on failure
  streaks (cap 6x)
- Admin controls: `GET/POST /admin/market/scheduler` and `/scheduler/pause`
- Sources UI shows a live "Running/Paused" toggle button

### Analytics endpoints (`routes/market.py`)
- `GET /admin/market/analytics/source-strip` — per-source health snapshot
- `GET /admin/market/analytics/price-trends?purpose=sale&months=12`
- `GET /admin/market/analytics/median-by-suburb?purpose=sale`
- `GET /admin/market/analytics/heatmap?purpose=sale&months=12`
- `GET /admin/market/analytics/quick-insights` — donut breakdowns

### Overview UI (`Overview.jsx`)
- 6 KPI cards + Source Health strip (color-coded LEDs)
- Recharts line chart for 12-month sale price trend
- 3 mini donuts: By Class / By Purpose / Match Bands
- Latest Open Review Cases feed

### Trends UI (`Trends.jsx`)
- For Sale / For Rent toggle
- Horizontal bar chart — median by suburb
- Line chart — 12-month trend
- Suburb × month heatmap table with color-intensity fill

### Public Price Compare (`/price-compare/*`)
- Landing page with 4 workflow tiles (Seller / Buyer / Landlord / Renter)
- `/price-compare/:workflow` — subject form + result cards:
  - **TREL Indicative Range** (p25 → p75) + weighted median + confidence chip
  - **YOUR PRICE IS BELOW / WITHIN / ABOVE** card with workflow-tailored advice
  - Top comparables table (tier / CQS / recency / value)
- Backed by public (no-auth) endpoint `POST /api/public/guidance/run`

### Robustness improvement
- `Sources.jsx` uses `Promise.allSettled` — a single failing endpoint
  no longer blanks the entire admin page (widget-level degradation).

### Test status
- iter-30: 17/17 backend pytest + 5/5 frontend flows verified. 1 critical
  bug fixed (list_runs decorator).
- iter-31: 2/2 targeted regression checks pass. DB clean.

## Iter-32 — Retention Cron, Hausples Parser, Health LED, CQS Deep-Dive, Homepage CTA, Rent Data (Feb 2026)

### Retention Enforcement (`core/retention.py`)
- `run_retention()` soft-deletes rows whose `created_at` is older than each
  collection's window (from the Retention tab): snapshots=365d, listings=
  730d, review_cases=365d, audit_events=2555d, collection_runs=365d.
- Every soft-delete sets `archived_at + archived_by='retention_policy' +
  retention_days` — row stays queryable, hard-delete only when
  `soft_delete_only=false` (audit events always soft-only).
- Scheduler tick calls `run_retention_if_due()` — runs at most every 24h,
  cadence controlled by `RETENTION_EVERY_SECONDS`.
- Manual trigger: `POST /admin/market/retention/run`.

### Hausples Parser (`core/collectors/hausples_png.py`)
- Real HTTP via httpx + selectolax HTML parsing
- Configurable CSS selectors in `DEFAULT_PARSER_CONFIG`, overridable per
  source via `MarketSource.parser_config`
- Address auto-splitting (street/suburb/city), price/beds/baths/area
  extraction with regex fallbacks
- Graceful degradation: unreachable → empty iter, unparseable page →
  captured on run doc, missing fields → row still emitted for MATCH-1.0

### Aggregation Health LED (`components/AggregationHealthLed.jsx`)
- Small badge in the admin sidebar header on every screen
- Polls `/admin/market/analytics/source-strip` every 60s
- Colours: green (all sources ≥90% success), amber (any <90%), red (any
  streak ≥2 consecutive failures), grey (no sources)
- Animated ping ring, tooltip with per-source breakdown, clicking navigates
  to /admin/market

### Comparables CQS Deep-Dive (`ComparableDetail` in Comparables.jsx)
- `guidance_comparables` now persists `cqs_breakdown` + `months_since` on
  every row (model + guidance engine updated)
- Click any comp row → modal opens with:
  - 4 KPIs: Total CQS · Recency Factor · Effective Weight · Months since
  - Horizontal bar chart per signal (location / class_subtype / size /
    features / condition / recency) with distinct colours

### Public Homepage CTA
- Amber "Get Free Price Guidance" button on hero next to standard CTAs
- BarChart3 icon (lucide), links to `/price-compare` landing

### Trend Rent-View Fix (`collectors/seed.py`)
- Seed RNG choice tuple changed from `["sale","sale","sale","rent"]` (25%
  rent) to `["sale","sale","sale","rent","rent"]` (40% rent) so the
  Trends "For Rent" view populates once a seed collector runs.

### Test status (iter-32)
- 7/7 backend pytest pass (`test_iter32_batch.py`)
- 4/4 frontend flows verified via Playwright (LED / CQS modal / homepage
  CTA / rent view)
- Zero issues. DB clean.

## Iter-33 — Retention Preview UI (Feb 2026)

### Backend
- `GET /api/admin/market/retention/preview` — dry-run counterpart to
  `/run`. Returns per-collection `{candidates, window_days, action:'soft_delete'|'hard_delete'|'disabled'}`
  without touching any data.

### Frontend (Configuration → Data Retention tab)
- Two new buttons at top-right: **Preview Impact** (safe dry-run) and
  **Run Now** (confirmation dialog + live execution).
- Result panel renders below the retention windows: table of collection ×
  window × action × would-archive/archived × candidates. Toggles between
  "would soft-delete now" and "Retention run — result" headers based on
  which button was clicked. Timestamp footer.
- Verified: 3 seeded old market_listings + 1 old snapshot correctly
  reported as candidates; unchanged after Preview.

## Iter-34 — Hausples Selector Tester (Feb 2026)

### Backend (`core/collectors/hausples_tester.py`)
- `probe_hausples(url, selectors?)` — fetches an arbitrary URL, runs every
  configured CSS selector against the returned HTML, reports:
  - HTTP status + response bytes
  - Card selector + cards_found count
  - Per-field: {selector, matches, match_rate, samples[≤3]}
- Non-fatal: network / HTTP errors return `{ok:false, error:"..."}` instead
  of raising, so the UI stays interactive.
- Endpoint: `POST /api/admin/market/collectors/hausples_png/test`.

### Frontend (`Sources.jsx` + new `HausplesSelectorTester.jsx`)
- Every row with `collector='hausples_png'` gains an **Inspect** action
  (data-testid=`inspect-source-{id}`) that opens the tester modal.
- Modal: URL input · 9 editable selector inputs · Test button · Reset to
  defaults · result panel with per-field match count table + samples ·
  contextual guidance when 0 cards match. Nothing is auto-saved — operator
  copies working selectors into the source's parser_config when happy.

### Verified via screenshot
- Created Hausples PNG source → Inspect opens modal → default selectors
  populated · probing example.com correctly reports HTTP 200 · 559 bytes ·
  0 cards found. Error state (real Hausples 404) also renders cleanly.


## Iter-35 — Analytics Cache · Lead Capture · CQS Compare · LED Thresholds (Feb 2026)

Six-in-one polish batch — two items ("Retention Preview" + "Hausples Selector
Tester") were already shipped in iter-33/34, four are new:

### Backend

**Analytics 60 s TTL cache (`routes/market.py`)**
- New `_ANALYTICS_CACHE` dict + `_cache_get / _cache_set / _cache_bust` helpers.
- Wraps all five analytics endpoints: `source-strip`, `price-trends`,
  `median-by-suburb`, `heatmap`, `quick-insights`. Cache keys include every
  query parameter (`purpose`, `days`, `months`, `limit`).
- 60 s TTL is fresh enough (scraper cycles are minute-scale) and stops repeat
  admin poll from hammering `market_listings` on every tick of the Overview /
  Trends pages.

**`snapshot` on `guidance_comparables` (`core/guidance.py` + `models.py`)**
- New optional `snapshot: dict = {}` field on `GuidanceComparable`.
- Populated during `generate_guidance` with `property_subtype`, `bedrooms`,
  `bathrooms`, `land_area_m2`, `building_area_m2`, `suburb`, `street`,
  `local_area` — enough to render subject-vs-comp side-by-side in the CQS
  deep-dive modal.

**Configurable Pipeline Health LED thresholds**
- `DEFAULT_MARKET_CONFIG_PARAMS.health_led` added
  (`amber_min_success_pct: 90`, `red_consecutive_failures: 2`).
- `seed_market_configuration` backfills the block on every startup so existing
  configs inherit defaults.
- New endpoint `GET /admin/market/health-led/config` reads from the active
  configuration and returns the two thresholds (with sane fallbacks).

**Lead capture — new source `price_compare` (`routes/public.py`)**
- `public_create_lead` now accepts `source="price_compare"` and:
  - maps `customer_type` to `buyer`.
  - routes to `leasing_agent` if `payload.workflow ∈ {landlord, renter}`,
    otherwise `sales_agent` (all other sources unchanged).

### Frontend

**Public Price Compare — Lead Capture card (`pages/public/PriceCompare.jsx`)**
- New `LeadCaptureCard` mounts under every result panel. Two-stage flow:
  1. Dashed CTA card: "Book a full valuation" (`pc-lead-cta` /
     `pc-lead-open-btn`).
  2. Expanded form with Name / Email / Phone / Notes + native captcha challenge
     (`pc-lead-form`, `input-lead-*`, `pc-lead-submit-btn`).
- On submit → `POST /public/leads` with source `price_compare`, message
  auto-composed from the guidance result (range, weighted median, confidence,
  position, comparable count), payload persisting workflow + purpose + numbers.
- Success state (`pc-lead-thanks`) replaces the card entirely; no re-submit.

**Comparables — "Compare with subject" toggle (`admin/market/Comparables.jsx`)**
- New checkbox in `ComparableDetail` (`toggle-compare-subject`).
- When active: 8-row side-by-side table (Suburb / Subtype / Bedrooms /
  Bathrooms / Land m² / Building m² / Street / Local area) driven off
  `comp.snapshot`, with per-row Δ calculation:
  - numeric → % diff with green (≤10%), amber (≤25%), red otherwise
  - textual → `=` (match) or `≠` (mismatch)

**Retention tab — LED thresholds section (`admin/market/Config.jsx`)**
- `HEALTH_LED_DEFAULTS` constant + `params.health_led` shape-fixer on load.
- New "Pipeline Health LED thresholds" subsection under Deletion Policy in the
  Data Retention tab: two `NumInput`s bound to `patchNested("health_led", …)`.
- Publishing a new config version rolls the thresholds into the active config
  → the `AggregationHealthLed` component re-polls within 60 s and picks them
  up.

**AggregationHealthLed — dynamic thresholds (`components/AggregationHealthLed.jsx`)**
- Fetches `/admin/market/health-led/config` alongside the source strip.
- Colour bands now: green when `worstStreak < red_consecutive_failures` AND
  `lowest_success_pct ≥ amber_min_success_pct`; amber below the min pct; red at
  or above the streak threshold.
- Tooltip now surfaces the active thresholds in addition to the per-source
  summary.

### Verified end-to-end (curl)
- `POST /admin/market/guidance/run` returns comparables with the new
  `snapshot` block populated.
- `GET /admin/market/health-led/config` → `{amber_min_success_pct: 90.0,
  red_consecutive_failures: 2}`.
- Analytics `source-strip` served twice in ~200 ms combined (cache confirmed).
- `POST /public/leads` with `source=price_compare` returns `{ok:true,
  lead_id:…}` and a matching Lead + Customer are visible in the admin CRM.


## Iter-36 — 6 Live Scrapers · `lot_number` → `allotment_number` Rename (Feb 2026)

### Backend

**Common scraper primitives (`core/collectors/_common.py` — new)**
- `HttpListingCollector` base class — every network-backed collector inherits
  fetch, pagination (query- or template-mode), card-grid extraction, and the
  common address / allotment / bedroom parsing.
- Text extractors: `parse_allotment_section` handles both `Allotment X Section
  Y` and reverse `Section Y Allotment X` orderings + abbreviations
  (Allot/Alloc/Lot, Sec). `parse_portion` for customary-land portion numbers.
  `parse_price` copes with `PGK`, `K`, `$` prefixes + commas + decimals.
  `parse_address` splits `street, suburb, city, province`. `infer_subtype`
  guesses class/subtype from title/description hints (with warehouse ordered
  before "house" so it isn't shadowed).

**Six live scrapers (`core/collectors/*.py`)**
- `hausples_png.py` — refactored to ~35 lines; inherits the shared base.
- New: `ljhookerpng.py`, `mypnghome.py`, `sre.py`, `dac.py`, `marketmeri.py`.
- Every scraper ships with best-effort default CSS selectors + PNG-typical
  paths (`/property-for-sale`, `/property-for-rent`, etc.). All ship
  `active=false` — an operator flips the switch after tuning selectors via
  the Hausples-style tester or `parser_config` edit.
- `MarketSource.parser_config` now on the pydantic model so parser tweaks
  round-trip through the admin UI.

**Full `lot_number → allotment_number` rename**
- Every mention across `models.py`, `core/matcher.py` (deterministic rules,
  candidate generation, hard-conflict detection, weighted-score signals),
  `core/collectors/seed.py`, `seed.py` indexes, `seed_data.py`,
  `routes/market.py` (master-property search), plus admin UI
  `Duplicates.jsx` mock data.
- New `migrate_lot_to_allotment` runs on every startup: `$rename` across
  `market_listings`, `market_listing_snapshots`, `master_properties`,
  `property_units`. Idempotent (`$rename` no-ops when source field absent).

**Live scraper source seeding (`seed.py` — new `seed_market_sources`)**
- On first boot, inserts one `MarketSource` per collector
  (`hausples_png`, `ljhookerpng`, `mypnghome`, `sre`, `dac`, `marketmeri`,
  plus the always-on `TREL Seed Generator`).
- All 6 live sources start `active=False` so no scrape fires without an
  explicit operator flip. Existing sources are NEVER overwritten
  (idempotent by name).

### Frontend
- No new screens needed — the existing **Data Sources** admin page already
  supports arbitrary collectors, and the **Run** button on every row already
  routes to `POST /admin/market/sources/{sid}/collect` which now dispatches
  to the correct scraper implementation.

### Verified end-to-end (curl + pytest)
- `GET /api/admin/market/collectors` returns 7 collectors including the 6
  new ones.
- `GET /api/admin/market/sources` shows all 6 new sources seeded, each
  wired to its collector.
- Running the seed source still produces 12 listings; sample listing has
  `allotment_number` populated, no `lot_number` key.
- Activating Hausples + running it against the live URL returns `success`
  with 0 listings (default selectors don't match production DOM — expected;
  ops tunes via the Hausples Selector Tester). No crashes, no errors.
- Guidance run still ranks 3 comparables → `limited` confidence (matches
  previously seeded data).
- New pytest suite (`tests/test_collectors_common.py`): **24 tests pass**
  covering allot/section extraction (both orderings + abbreviations), price
  parsing (PGK/K/$ prefixes + decimals), portion detection, address split,
  subtype inference (warehouse-vs-house shadowing), and registry
  completeness.



## Iter-37 — Selector Tester goes generic (all 6 HTTP collectors) (Feb 2026)

### Backend

**`core/collectors/selector_tester.py` (new)**
- `probe_collector(key, url, selectors)` — replaces the Hausples-only probe.
  Given any registered `HttpListingCollector` key it fetches the URL and
  reports per-field match counts + up to 3 sample values.
- `collector_defaults(key)` — returns the collector's `DEFAULT_CONFIG` or
  `None` if the collector isn't an HTTP scraper (i.e. `seed`).
- Field list expanded to include `description` alongside url/title/price/
  address/beds/baths/land/building, so the tester renders every field the
  common parser actually reads.

**`core/collectors/hausples_tester.py` (rewritten as shim)**
- Now a 15-line backward-compatibility wrapper that delegates to
  `selector_tester.probe_collector("hausples_png", …)`. Existing imports
  (`DEFAULT_PARSER_CONFIG`, `probe_hausples`) still resolve.

**`routes/market.py`**
- `GET /admin/market/collectors` now returns each entry with its
  `default_config` inlined (or `null` for non-HTTP collectors).
- New `GET /admin/market/collectors/{key}/defaults` — used by the modal to
  re-hydrate defaults on Reset without a page reload.
- New `POST /admin/market/collectors/{key}/test` — generic tester endpoint.
  Returns `404` for unknown keys or non-HTTP collectors (`seed`), `400` for
  invalid URLs.
- Legacy `POST /admin/market/collectors/hausples_png/test` kept as an alias
  and defined BEFORE the parametric route (FastAPI would otherwise shadow
  it) — the lint enforcer caught this immediately and forced the correct
  ordering.

### Frontend

**`pages/admin/market/SelectorTester.jsx` (new, generic)**
- Renders for any HTTP collector — takes `source` + `collectorMeta` props.
- Hydrates default selectors from `collectorMeta.default_config` (returned
  by the collectors registry) or falls back to `GET /collectors/{key}/defaults`.
- Auto-populates the URL from the source's base_url + first search_path
  (respecting `page_url_template` if set).
- New "Quick paths" row (`tester-quick-paths`) — one clickable link per
  configured search path so ops can flip between `/for-sale` and `/for-rent`
  in one click.
- Reset now shows a `Reset to {collector label} defaults` toast so the user
  sees which template they landed on.
- Same result panel (per-field match counts + sample rows), same
  graceful-degradation UX.

**`pages/admin/market/Sources.jsx`**
- Old `HausplesSelectorTester` import + JSX **removed** (file deleted).
- Inspect button now renders for **any** row whose collector has a
  `default_config` in the registry response — i.e. all 6 live scrapers.
- Seed sources (including the always-on TREL Seed Generator) correctly
  omit the button.
- Modal opened with `<SelectorTester source={row}
  collectorMeta={collectors.find((c) => c.key === row.collector)} … />`
  so no extra fetch is needed on open.

### Verified end-to-end (curl + Playwright)
- 19/19 backend cases pass: registry defaults, `/defaults` endpoint,
  generic `/test` on all 6 HTTP keys, `seed` → 404, invalid URL → 400,
  legacy `/hausples_png/test` alias, user-supplied selector overrides.
- Frontend: exactly 6 `inspect-source-*` buttons render (one per HTTP
  collector); seed rows omit it. Clicking LJ Hooker → modal opens with
  correct label, pre-populated URL, LJ-specific default selectors, quick
  paths present. Reset restores defaults + toast fires. Probing example.com
  returns `cards_found=0` without JS errors. Hausples row regression
  still works.



## Iter-38 — Live Listing-Page Discovery + Save-to-Source Selectors (Feb 2026)

### The problem this fixes
Previous scrapers hard-coded/guessed listing paths (`/property-for-sale`,
`/property-for-rent`, `/for-sale/`, `/rent/`) and concatenated them onto the
base URL. That produced wrong URLs like
`https://www.hausples.com.pg/buy/property-for-sale`; the real path is just
`https://www.hausples.com.pg/buy/`. Now the scraper NEVER reconstructs a URL.

### Backend

**`core/collectors/discovery.py` (new)**
- `discover_listing_pages(base_url, collector_key, parser_config?)` fetches
  the homepage, walks `<a href>` links inside the site's own navigation,
  filters against a keyword-based `CATEGORY_RULES` table (Buy/For Sale,
  Rent/Lease, Residential, Commercial, Land, Projects, Apartments, Houses)
  + `_BLACKLIST_KEYWORDS` (about, contact, login, socials, etc), follows
  each candidate with redirects, verifies HTTP status and counts cards +
  detail-links against the collector's card selector.
- `_extract_candidates` dedupes by cleaned URL, keeping the most-specific
  category rule when two rules match.
- `_grade` per-candidate is fanned out with `asyncio.Semaphore(4)` so a full
  discovery on Hausples finishes in ~3 s end-to-end.
- Every candidate returns a `listing_url` that is the FINAL URL after
  redirect resolution — used verbatim by the scraper. No path assembly.

**`_common.HttpListingCollector.iter_listings` (rewritten)**
- Now iterates `source.listing_pages` (populated by discovery); the
  per-page-purpose is either the entry's stored purpose or a best-effort
  guess off the category label / URL fragment.
- Sole helper for pagination: given the exact page-1 URL, page N appends
  `?page=N` (or uses the operator-configured `parser_config.page_url_template`
  if set). No `search_paths` array anywhere.
- If `listing_pages` is empty the scraper logs a warning and yields nothing
  → the run is reported partial (0 listings), never crashes.
- `_pagination_url` helper deleted.

**Per-collector `DEFAULT_CONFIG`**
- Removed `search_paths` from all 6 HTTP collectors
  (hausples_png/ljhookerpng/mypnghome/sre/dac/marketmeri).
- Removed the WordPress-style `page_url_template: '{base}{path}/page/{page}/'`
  guesses from ljhookerpng/mypnghome/dac.
- Every collector now only ships default CSS selectors + base_url.

**`MarketSource` model**
- New `listing_pages: List[dict]` on both `MarketSource` and
  `MarketSourceCreate`. Each entry is `{category, category_label, purpose,
  listing_url, cards_found, detail_links}`.

**New endpoints (`routes/market.py`)**
- `POST /admin/market/collectors/{key}/discover` — body
  `{base_url, parser_config?}` returns the discovery response.
- `POST /admin/market/sources/{sid}/parser-config` — body
  `{parser_config: {...}}`, merges into the existing config (used by the
  Selector Tester's Save-to-source button, emits `source_parser_config_saved`
  audit event).

**Idempotent DB migration (`seed.migrate_strip_legacy_search_paths`)**
- Removes `search_paths`, `page_url_template`, `purpose_by_path` from every
  existing `market_sources.parser_config`.
- Ensures every source has a `listing_pages: []` field so the UI never sees
  `undefined`.

### Frontend

**`SourceModal.jsx` (new, replaces the inline modal in Sources.jsx)**
- Redesigned 2-column layout per the mock:
  - LEFT: Source Name, Base URL (with inline "Discover Pages" button),
    Description (200-char cap with counter).
  - RIGHT: `DiscoveryPanel` — the results table with columns Category /
    Detected URL / Status / Cards Found / Detail Links / Confirm.
    Category icons come from `lucide-react`. Empty/loading/error states
    handled inline.
- Bottom row: Active + Allow-auto-match toggles, Collector Type / Frequency /
  Parser Version panel, plus the "What happens next?" reassurance card that
  spells out that the scraper uses ONLY confirmed URLs.
- Save action collects the ticked `listing_pages` and PUTs the whole record.

**`SelectorTester.jsx`**
- New `tester-save-to-source` button next to Reset — pushes the current
  selectors into `MarketSource.parser_config` via the new endpoint. Toast
  confirms the target source name.

**`Sources.jsx`**
- Old inline modal + old `Field` helper deleted; replaced by
  `<SourceModal editing={…} initial={…} collectors={…}
                onClose={…} onSaved={…} />`.
- No visual change to the top-of-page KPIs / sources table / runs feed.

### Acceptance test verified (curl + Playwright)
- `POST /admin/market/collectors/hausples_png/discover` with
  `base_url='https://www.hausples.com.pg/'` returns 12 candidates in ~3 s;
  Buy → `https://www.hausples.com.pg/buy/` (20 cards, 200) and Rent →
  `https://www.hausples.com.pg/rent/` (20 cards, 200) are both present, both
  auto-confirmed. No candidate URL contains `/property-for-sale` or
  `/property-for-rent`.
- Saving the source persists the two `listing_url` values EXACTLY as
  returned. Re-opening the Edit modal shows the same two URLs.
- Running the collector then hits those two URLs verbatim — no path
  appending, no reconstruction. Confirmed via code grep: zero occurrences
  of `/property-for-sale`, `/property-for-rent`, `for-sale`, `for-rent`,
  or base_url-plus-search_path patterns remain in the backend.
- 10/10 backend pytest cases pass; full frontend acceptance flow (modal
  layout, discovery, save, edit round-trip, Save-to-source selectors)
  passes.



## Iter-39 — Bulk Rediscover · Per-Source Diff · One-Click Apply (Feb 2026)

### Backend

**`POST /admin/market/sources/rediscover-all` (new)**
- Loads every `MarketSource`, fans out `discover_listing_pages` across them
  behind `asyncio.Semaphore(3)` so the round-trip stays polite.
- Sources whose collector isn't HTTP (or whose base_url doesn't start with
  `http`) are returned as `{ok:false, skipped:true, reason}` — never
  attempted.
- Per source, diffs the previously-persisted `listing_pages` against the
  new auto-confirmed candidates (`c.auto_confirm == True`):
  - `added`   — URLs in new only
  - `removed` — URLs in old only
  - `unchanged` — URLs in both
- Response also carries top-level counters (`total`, `with_changes`,
  `no_changes`, `errored`, `skipped`) so the UI can render summary pills
  in one shot.
- Emits `sources_rediscover_all` audit event with the counters.
- **NOTHING is persisted here** — the diff is presentational; ops choose
  what to apply.

**`PUT /admin/market/sources/{sid}/listing-pages` (new)**
- Full REPLACE of a source's `listing_pages` (no merge). Body:
  `{listing_pages: [{...}]}`.
- Validates array shape; every entry stored **verbatim** (no URL rewriting).
- Returns the updated source doc.
- Emits `source_listing_pages_updated` audit event with count_before /
  count_after.

**Route ordering**
- The new literal route sits before `/sources/{sid}` parametric routes — no
  route-shadow conflicts (they're all different HTTP methods anyway).

### Frontend

**`BulkRediscoverModal.jsx` (new)**
- Opens with a big "Run scan" CTA; while scanning shows a spinner and
  disables re-entry.
- Post-scan header shows five `SummaryPill`s: Total, Changed, No changes,
  Errors, Skipped.
- Body is a per-source table (sorted: changed → errored → unchanged →
  skipped). Columns: Source · Base URL · Status pill · Added · Removed ·
  Unchanged · Action.
- Every row is expandable via a chevron → shows an inner `DiffDetail`:
  Added URLs (green), Removed URLs (red), Unchanged URLs (muted). Each URL
  is copy-friendly (monospace) with category label + card count metadata.
- Per-row `Apply` button (visible only for rows with real added/removed)
  → replaces that source's `listing_pages` via the new PUT endpoint,
  emits toast, locally marks the row as unchanged so the button hides.
- Footer has "Re-run scan" + "Apply all changed (N)" for one-click cleanup
  across the entire catalogue.

**`Sources.jsx`**
- New `rediscover-all-btn` in the header alongside `add-source-btn`.
  Outline-style green button with a rotating ↻ prefix so it doesn't compete
  with the primary "+ Add Source" CTA.
- `bulkOpen` state gates the modal; the modal's `onApplied` reloads the
  sources list so the row reflects the newly-applied URLs.

### Verified end-to-end
- 12/12 review scenarios pass (curl + Playwright).
- Bulk scan of the live catalogue completes in ~30–60 s across 10 sources.
- Hausples PNG appears in the diff with `/buy/` + `/rent/` as suggested
  URLs; no candidate URL contains `/property-for-sale` or
  `/property-for-rent`.
- Applying a single row via `rediscover-apply-{sid}` persists the URLs
  verbatim (round-tripped through `GET /admin/market/sources`).
- Bad payloads on the PUT endpoint return 404 (unknown sid) or 400
  (non-array). Empty array clears the source's `listing_pages`.
- Errored sources (unreachable hosts) surface with `ok=false` + a clear
  error string; the rest of the scan still returns.



## Iter-40 — Evidence Record Inspector (Feb 2026)

### What changed
The Market Evidence admin page (`/admin/market/evidence`) had a Phase-1
skeleton table with no row interaction — the PhaseBanner explicitly said
the inspector was deferred to Phase E. Users clicked and nothing happened.

### Frontend (`Evidence.jsx` — full rewrite of the file)

**Main table** (deliberately untouched)
- Same 8 columns in the same order: Record ID · Source · Purpose · Class ·
  Location · Price · Last Seen · Status. No columns added or removed.
- Every `<tr>` now has `cursor-pointer`, hover highlight, and an
  `onClick={() => setSelected(l)}` handler. Selected row keeps its
  highlight while the inspector is open.
- Small "Click any row to open the full record inspector." caption below
  the table body so ops don't miss the affordance.
- KPI cards and PhaseBanner unchanged (banner copy updated to reflect
  inspector shipping).

**`RecordInspector` (new component in the same file)**
- Right-hand slide-out, 720px, sticky header with `inspector-title` +
  record ID + `inspector-close` (X).
- Six field groups rendered via `FieldGroup` (2-column Field / Value table
  each, muted background on the label column):
  - Identifiers (Record ID full, Source ID full, Source listing ID,
    Listing URL — clickable anchor with target=_blank)
  - Classification (Property subtype, Currency, Rent period)
  - Parcel (Allotment / Section / Portion)
  - Size / Rooms (Bedrooms, Bathrooms, Land area m², Building area m²)
  - Location detail (Street, Suburb, Local area, City, Province, Latitude,
    Longitude, GPS accuracy)
  - Timestamps / ops (First seen, Created, Updated, Exclusion reason,
    Alias map version)
- Two collapsed `<details>` blocks at the bottom: `inspector-raw-toggle`
  dumps the scraper's `raw_fields`, `inspector-normalized-toggle` shows
  `normalized_fields` (only if non-empty).
- Empty values render as em-dash so gaps in scraper coverage are obvious.

**Interaction UX**
- Backdrop is a purely decorative dim overlay with `pointer-events: none`
  so table clicks pass straight through — clicking another row while the
  inspector is open **switches the inspected record without closing**.
- Close paths: X button, Escape key. Helper hint under the title tells
  ops both paths + row-switching.
- Field slug function handles unicode superscripts (m² → m2) and strips
  leading/trailing dashes so every testid resolves cleanly.

### Verified end-to-end (Playwright, iter-38 + iter-39 + iter-40)
- Table columns unchanged.
- 100 rows clickable; hover + selected highlight fire correctly.
- Inspector opens with all 6 group headers + all 14+ required field
  testids populated with real seed data (e.g. Allotment 33, Section 28,
  Bed 2, Bath 2, Land 513 m², Building 217 m², Street "Sabama Road",
  Province NCD).
- Row-switching verified across 3 different rows without closing.
- ESC + X close paths both work.
- `inspector-source-url` is a real anchor with target=_blank; raw
  payload toggle expands to the JSON blob.


