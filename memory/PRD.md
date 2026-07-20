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
- Admin: `admin@pngrealty.pg` / `Admin@123`
- All other staff: `Password@123`

## Testing
- Iteration 1: 23/23 backend tests passed, 100% of tested frontend flows verified (see `/app/test_reports/iteration_1.json`).

## Backlog (deferred to V2)
- P1 — Real email provider (Resend/SendGrid) for confirmations
- P1 — WhatsApp Business API integration (currently `wa.me` deep links)
- P1 — Image upload (currently image URLs entered manually; object storage available)
- P1 — Communication history log per customer/lead (calls, notes, timeline)
- P2 — Advanced reporting (revenue, agent performance, conversion funnel)
- P2 — Data export (CSV/Excel)
- P2 — Audit log UI (records currently written to Mongo but no UI yet)
- P2 — SEO metadata per property, search-friendly URLs
- P2 — Mobile app, tenant/owner portals, online rent payment (explicitly out-of-scope in V1)

## Next Actions
1. Provide branded logo/photography if not using placeholders
2. Add real email + WhatsApp Business API integration when keys available
3. Add object-storage image uploads to the property editor
4. Implement Communication History module (calls/notes timeline)
