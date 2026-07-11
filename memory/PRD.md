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
