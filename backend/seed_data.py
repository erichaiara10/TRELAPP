"""Static default data (page content, sample properties, users) — no side effects."""

DEMO_PROPERTIES = [
    {"title": "Modern 4BR Beachfront Villa, Ela Beach", "listing_type": "sale", "property_type": "house", "price": 1450000, "bedrooms": 4, "bathrooms": 3, "parking": 2, "area_sqm": 420, "location": "Port Moresby", "suburb": "Ela Beach", "address": "12 Ela Beach Road", "featured": True, "verified": True,
     "description": "Elegant villa steps from Ela Beach with tropical gardens, pool, and secure compound.", "features": ["Pool", "Secure Compound", "Ocean View", "Backup Generator"],
     "images": ["https://images.pexels.com/photos/1974596/pexels-photo-1974596.jpeg", "https://images.pexels.com/photos/12081268/pexels-photo-12081268.jpeg"]},
    {"title": "Executive Apartment, Touaguba Hill", "listing_type": "rent", "property_type": "apartment", "price": 6500, "bedrooms": 3, "bathrooms": 2, "parking": 1, "area_sqm": 180, "location": "Port Moresby", "suburb": "Touaguba Hill", "featured": True, "verified": True,
     "description": "Fully furnished executive apartment with panoramic harbour views, 24/7 security, and gym.", "features": ["Furnished", "Harbour View", "Gym", "24/7 Security"],
     "images": ["https://images.pexels.com/photos/23669334/pexels-photo-23669334.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940", "https://images.unsplash.com/photo-1760067537639-0fb475c87657"]},
    {"title": "Family Home in Gordons", "listing_type": "sale", "property_type": "house", "price": 780000, "bedrooms": 3, "bathrooms": 2, "parking": 2, "area_sqm": 260, "location": "Port Moresby", "suburb": "Gordons", "verified": True,
     "description": "Well-maintained family home in quiet Gordons cul-de-sac. Large garden, servant quarters.", "features": ["Garden", "Servant Quarters", "Fenced"],
     "images": ["https://images.pexels.com/photos/12081268/pexels-photo-12081268.jpeg"]},
    {"title": "Lae CBD Commercial Space", "listing_type": "rent", "property_type": "commercial", "price": 12000, "bedrooms": 0, "bathrooms": 2, "parking": 6, "area_sqm": 320, "location": "Lae", "suburb": "CBD",
     "description": "Ground floor retail/office space in Lae CBD with high foot traffic.", "features": ["Ground Floor", "Parking", "A/C"],
     "images": ["https://images.unsplash.com/photo-1760067537639-0fb475c87657"]},
    {"title": "Land 1200sqm, 9-Mile", "listing_type": "sale", "property_type": "land", "price": 220000, "bedrooms": 0, "bathrooms": 0, "parking": 0, "area_sqm": 1200, "location": "Port Moresby", "suburb": "9-Mile",
     "description": "Flat block ready to build, close to Jackson's Airport. Fenced perimeter.", "features": ["Flat", "Fenced", "Titled"],
     "images": ["https://images.pexels.com/photos/1974596/pexels-photo-1974596.jpeg"]},
    {"title": "Townhouse, Boroko", "listing_type": "rent", "property_type": "townhouse", "price": 4200, "bedrooms": 2, "bathrooms": 2, "parking": 1, "area_sqm": 140, "location": "Port Moresby", "suburb": "Boroko", "featured": True,
     "description": "Modern 2BR townhouse in gated community, close to shopping and schools.", "features": ["Gated Community", "Pool", "Pet Friendly"],
     "images": ["https://images.pexels.com/photos/23669334/pexels-photo-23669334.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"]},
]

DEFAULT_PROPERTY_TYPES = [
    ("House",                              "lot_section_street", 10),
    ("Apartment",                          "lot_section_street", 20),
    ("Town House",                         "lot_section_street", 30),
    ("Commercial",                         "lot_section_street", 40),
    ("Vacant Land – Urban Subdivided",     "lot_section_street", 50),
    ("Large Land – Portion / Customary",   "portion",            60),
]

LEGACY_PROPERTY_TYPE_NAME_MAP = {
    "house": "House",
    "apartment": "Apartment",
    "townhouse": "Town House",
    "town_house": "Town House",
    "commercial": "Commercial",
    "land": "Vacant Land – Urban Subdivided",
}

DEFAULT_LOCATIONS = [
    {"province": "National Capital District", "cities": {
        "Port Moresby": ["Waigani", "Boroko", "Gordons", "Gerehu", "Ela Beach", "Downtown", "Konedobu", "Hohola"],
    }},
    {"province": "Morobe", "cities": {"Lae": ["Eriku", "Milfordhaven", "Top Town", "Bumbu", "China Town"]}},
    {"province": "Madang", "cities": {"Madang": ["Newtown", "Coronation", "Modilon"]}},
    {"province": "Western Highlands", "cities": {"Mount Hagen": ["Kagamuga", "Newtown"]}},
    {"province": "East New Britain", "cities": {"Kokopo": ["Ralum", "Kenabot"]}},
    {"province": "Southern Highlands", "cities": {"Mendi": []}},
    {"province": "East Sepik", "cities": {"Wewak": []}},
    {"province": "Enga", "cities": {"Wabag": []}},
]

LEGACY_EMAIL_MAP = {
    "admin@pngrealty.pg": "admin@trel.com.pg",
    "director@pngrealty.pg": "director@trel.com.pg",
    "sales@pngrealty.pg": "sales@trel.com.pg",
    "leasing@pngrealty.pg": "leasing@trel.com.pg",
    "marketing@pngrealty.pg": "marketing@trel.com.pg",
}

LEGACY_AGENCY_NAMES = {"PNG Realty"}

DEFAULT_CONTENT = {
    "site": {"agency_name": "Triumph Real Estate Limited", "short_name": "TREL",
             "tagline": "We Care To Share",
             "logo_url": "https://customer-assets.emergentagent.com/job_req-to-web-1/artifacts/uh12vkjw_TREL%20Logo.png",
             "favicon_url": "https://customer-assets.emergentagent.com/job_req-to-web-1/artifacts/uh12vkjw_TREL%20Logo.png",
             "og_image_url": "https://customer-assets.emergentagent.com/job_req-to-web-1/artifacts/uh12vkjw_TREL%20Logo.png",
             "og_description": "Triumph Real Estate Limited — verified homes, apartments, land and commercial properties across Papua New Guinea. We Care To Share.",
             "phone": "+675 76281552", "whatsapp": "+675 8138 3302", "email": "sales101.trel@gmail.com",
             "address": "Lot 33, Section 38, Unity Mall, Steamships Compound, Waigani Rd. P.O. Box 1061, Vision City, National Capital District, PNG"},
    "about": {"heading": "About Triumph Real Estate Limited", "body": "Triumph Real Estate Limited (TREL) is a Papua New Guinea-owned real estate agency helping families, investors and corporates find the right home, tenant or asset. We combine deep local knowledge with modern, transparent processes — because we care to share."},
    "why": {"heading": "Why choose TREL", "items": [
        {"title": "Local expertise", "body": "Born and raised in PNG — we know every suburb, security landscape, and school catchment."},
        {"title": "Verified listings", "body": "Every property is checked by our team before it goes live."},
        {"title": "Corporate ready", "body": "We handle expat relocations, corporate leases and portfolio management end-to-end."},
    ]},
}

SAMPLE_REQUIREMENTS = [
    {"customer_name": "Family of 5", "intent": "buy", "property_type": "house", "min_price": 600000, "max_price": 900000, "min_bedrooms": 3, "locations": ["Port Moresby"], "notes": "Prefers Gordons or Waigani, secure compound"},
    {"customer_name": "Mining Corporate", "intent": "rent", "property_type": "apartment", "min_price": 5000, "max_price": 8000, "min_bedrooms": 2, "locations": ["Port Moresby"], "notes": "Executive housing for FIFO staff", "is_corporate": True},
]

PAGE_SLUGS = {"home", "about", "sell", "buy", "rent", "wanted", "management",
              "corporate", "contact", "legal_privacy", "legal_terms"}

DEFAULT_PAGE_CONTENT = {
    "home": {
        "hero": {
            "image": "/images/h01-authoritative-hero.png",
            "kicker": "PAPUA NEW GUINEA REAL ESTATE",
            "heading": "Find a place you're proud to call home.",
            "sub": "Verified listings, honest advice, and end-to-end support — from families to corporates across PNG.",
            "cta_primary": {"label": "Browse homes for sale", "href": "/buy"},
            "cta_secondary": {"label": "Explore rentals", "href": "/rent"},
        },
        "featured_intro": {
            "kicker": "FEATURED",
            "heading": "Handpicked homes ready to inspect",
            "sub": "A rotating selection of our most-loved listings — refreshed weekly by our sales team.",
        },
        "why_us": {
            "heading": "Why families and corporates choose TREL",
            "items": [
                {"title": "Local expertise", "body": "Born and raised in PNG — we know every suburb, security landscape and school catchment.", "icon": "MapPin"},
                {"title": "Verified listings", "body": "Every property is inspected and photographed by our team before going live.", "icon": "ShieldCheck"},
                {"title": "Corporate ready", "body": "Expat relocation, corporate leases, and portfolio management — all handled in-house.", "icon": "Briefcase"},
            ],
        },
        "wanted_preview": {
            "kicker": "PROPERTY WANTED",
            "heading": "Buyers and tenants actively searching",
            "sub": "Have a property that might match? Submit it and we'll shortlist you within 24 hours.",
        },
        "cta_band": {
            "heading": "Ready to list, buy, or rent?",
            "sub": "Talk to a TREL agent today — we typically reply within one business day.",
            "button_label": "Get in touch",
        },
    },
    "about": {
        "hero": {
            "image": "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=1600&q=80",
            "kicker": "ABOUT TREL",
            "heading": "A PNG-owned real estate agency built on trust.",
            "intro": "Triumph Real Estate Limited helps families, investors and corporates buy, sell, rent and manage property across Papua New Guinea.",
        },
        "story": {
            "heading": "Our story",
            "body": "TREL was founded to bring transparent, professional real estate services to Papua New Guinea. From day one we've focused on verified listings, honest pricing, and long-term relationships — with families, corporates, and government clients alike.\n\nToday we serve buyers, sellers, tenants, landlords and corporate clients across Port Moresby and beyond — combining local knowledge with modern digital tools.",
        },
        "mission": {
            "heading": "Our mission",
            "body": "To make property in Papua New Guinea accessible, transparent, and rewarding for everyone we serve — because we care to share.",
        },
        "vision": {
            "heading": "Our vision",
            "body": "To be the most trusted real estate partner in the Pacific, known for integrity, local expertise and lasting relationships.",
        },
        "values": [
            {"title": "Integrity", "body": "Straight-talking advice, honest pricing, no surprises."},
            {"title": "Local knowledge", "body": "We know PNG's suburbs, schools, and security landscape inside-out."},
            {"title": "Care", "body": "We treat every client's home like our own — because we care to share."},
        ],
        "team": [
            {"name": "Managing Director", "role": "Managing Director", "photo": "", "bio": "Leads TREL's strategy, corporate partnerships, and community programmes."},
            {"name": "Sales Manager", "role": "Head of Sales", "photo": "", "bio": "Oversees residential and commercial sales across Port Moresby."},
            {"name": "Leasing Manager", "role": "Head of Leasing", "photo": "", "bio": "Manages rentals, corporate leases and expat relocation."},
        ],
    },
    "sell": {
        "hero": {
            "image": "https://images.unsplash.com/photo-1560518883-ce09059eeffa?auto=format&fit=crop&w=1600&q=80",
            "kicker": "SELL WITH TREL",
            "heading": "List your property",
            "intro": "Tell us about your property — a TREL agent will schedule a valuation and walk you through our marketing plan. Adding photos speeds up valuation by 2–3 days.",
        },
        "benefits": [
            {"title": "Professional valuation", "body": "An accurate, market-based price backed by recent comparable sales. Paid service — turnaround 2–3 days.", "icon": "BadgeCheck"},
            {"title": "Professional photography", "body": "Every listing gets a professional photo shoot before going live.", "icon": "Camera"},
            {"title": "Verified marketing", "body": "Featured on our homepage, WhatsApp broadcasts and partner networks.", "icon": "Megaphone"},
            {"title": "Dedicated agent support", "body": "A single point of contact from listing to keys-in-hand — replies within one business day.", "icon": "Headphones"},
        ],
    },
    "buy": {
        "hero": {
            "image": "https://images.unsplash.com/photo-1568605114967-8130f3a36994?auto=format&fit=crop&w=1600&q=80",
            "kicker": "BUY WITH TREL",
            "heading": "Homes and investments across Papua New Guinea",
            "intro": "Browse verified houses, apartments, land and commercial properties. Every listing is inspected by our team.",
        },
    },
    "rent": {
        "hero": {
            "image": "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?auto=format&fit=crop&w=1600&q=80",
            "kicker": "RENT WITH TREL",
            "heading": "Rentals for families, expats and corporates",
            "intro": "From compact apartments to executive housing — search verified rentals updated weekly.",
        },
    },
    "wanted": {
        "hero": {
            "image": "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=1600&q=80",
            "kicker": "PROPERTY WANTED",
            "heading": "Tell us what you're looking for",
            "intro": "Post your requirements — our team will shortlist matching properties within 24 hours and notify you when new ones list.",
        },
    },
    "management": {
        "hero": {
            "image": "https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&w=1600&q=80",
            "kicker": "PROPERTY MANAGEMENT",
            "heading": "End-to-end management for landlords",
            "intro": "We tenant, inspect, collect rent and maintain your property — so you can focus on the return.",
        },
        "services": [
            {"title": "Tenant sourcing", "body": "Vetted tenants, reference checks, and secure lease drafting.", "icon": "Users"},
            {"title": "Rent collection", "body": "Automated invoicing, receipting, and monthly owner statements.", "icon": "Wallet"},
            {"title": "Maintenance", "body": "24/7 emergency response with trusted local trade partners.", "icon": "Wrench"},
            {"title": "Inspections", "body": "Quarterly condition reports with photos, delivered to your inbox.", "icon": "ClipboardCheck"},
        ],
    },
    "corporate": {
        "hero": {
            "image": "https://images.unsplash.com/photo-1554469384-e58fac16e23a?auto=format&fit=crop&w=1600&q=80",
            "kicker": "CORPORATE SERVICES",
            "heading": "Housing solutions for expat and corporate clients",
            "intro": "From single executive lets to full portfolio management for mining, energy and government clients.",
        },
        "services": [
            {"title": "Expat relocation", "body": "Housing search, lease negotiation, orientation tours, and settlement support.", "icon": "Plane"},
            {"title": "Corporate leases", "body": "Bulk residential and commercial leasing with consolidated invoicing.", "icon": "Building2"},
            {"title": "Portfolio management", "body": "Multi-property management, KPI reporting, and quarterly reviews.", "icon": "BarChart3"},
            {"title": "Serviced housing", "body": "Fully furnished, all-inclusive executive residences.", "icon": "Home"},
        ],
    },
    "contact": {
        "hero": {
            "kicker": "CONTACT",
            "heading": "Get in touch",
            "intro": "Reach us during business hours (Mon–Fri, 8am–5pm PGT), or leave a message and we'll respond within one business day.",
        },
        "business_hours": "Mon–Fri, 8am–5pm PGT",
        "map_query": "",
    },
    "legal_privacy": {
        "title": "Privacy Policy",
        "body": "Triumph Real Estate Limited (TREL) values your privacy. This policy explains what information we collect, how we use it, and the choices you have.\n\nWe only collect personal data that you provide to us via our forms (name, email, phone, message, property preferences). We use it to respond to your enquiries, match you with properties, and improve our service.\n\nWe do not sell your data. Your data may be shared with our internal staff and third-party service providers strictly for the purposes above. You can request deletion of your data at any time by emailing sales101.trel@gmail.com.",
    },
    "legal_terms": {
        "title": "Terms of Service",
        "body": "By using the TREL website (\"the Site\"), you agree to these terms.\n\nProperty listings and information on the Site are provided in good faith. While we verify every listing, TREL makes no warranty of accuracy or availability. All prices are indicative and subject to change.\n\nSubmitting a form on the Site does not create a contract of sale or lease. Any transaction must be formalised in a separate written agreement.\n\nAll content on the Site is © Triumph Real Estate Limited and may not be reproduced without permission.",
    },
}
