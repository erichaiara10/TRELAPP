const { test, expect } = require("@playwright/test");

const json = (route, body, status = 200) => route.fulfill({
  status,
  contentType: "application/json",
  body: JSON.stringify(body),
});

const listing = (id, listingType = "sale") => ({
  id,
  title: `Family Home ${id}`,
  listing_type: listingType,
  property_type: "House",
  price: listingType === "sale" ? 780000 : 3200,
  currency: "PGK",
  province: "National Capital District",
  location: "Port Moresby",
  suburb: "Boroko",
  bedrooms: 3,
  bathrooms: 2,
  parking: 2,
  area_sqm: 650,
  description: "Authoritative H01 test listing",
  images: ["https://images.test/house.jpg"],
  status: "active",
  featured: true,
});

async function mockPublicApi(page) {
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path === "/api/content/site") return json(route, { key: "site", value: {
      logo_url: "https://images.test/trel-logo.png",
      phone: "+675 76281552",
      whatsapp: "+675 8138 3302",
    }});
    if (path === "/api/page/home") return json(route, { page: "home", sections: { hero: { image: "https://images.test/h01-hero.jpg" } } });
    if (path.startsWith("/api/page/")) return json(route, { sections: {} });
    if (path === "/api/locations/cities") return json(route, [{ id: "city-1", name: "Port Moresby" }]);
    if (path === "/api/locations/suburbs") return json(route, [{ id: "suburb-1", name: "Boroko" }]);
    if (path === "/api/property-types") return json(route, [{ id: "type-1", name: "House" }]);
    if (path === "/api/properties/p-1") return json(route, listing("p-1"));
    if (path === "/api/properties") {
      if (url.searchParams.get("q")) return json(route, [listing("p-1")]);
      const mode = url.searchParams.get("listing_type") || "sale";
      return json(route, Array.from({ length: 12 }, (_, index) => listing(`p-${index + 1}`, mode)));
    }
    if (path === "/api/ai/price-analysis") return json(route, {
      verdict: "fair", range_min: 740000, range_max: 820000, average: 780000, comparables: [],
    });
    return json(route, []);
  });
}

test.beforeEach(async ({ page }) => {
  await mockPublicApi(page);
});

test("H01 header and footer preserve the authoritative order, wording and live destinations", async ({ page }) => {
  await page.goto("/");
  const header = page.getByTestId("public-header");
  await expect(header.getByRole("link", { name: "TRELPNG Home" })).toHaveAttribute("href", "/");
  for (const [label, href] of [
    ["Home", "/"], ["Buy", "/buy"], ["Rent", "/rent"], ["Property Wanted", "/wanted"],
    ["Property Management", "/management"], ["Corporate Services", "/corporate"],
    ["Add Property", "/add-property"], ["Log In", "/add-property?auth=login"], ["Register", "/add-property?auth=register"],
    ["About", "/about"], ["Contact", "/contact"],
  ]) await expect(header.getByRole("link", { name: label, exact: true })).toHaveAttribute("href", href);
  await expect(page.getByTestId("header-phone")).toHaveAttribute("href", "tel:+67576281552");
  await expect(page.getByTestId("header-whatsapp")).toHaveAttribute("href", "https://wa.me/67581383302");

  const footer = page.getByTestId("public-footer");
  for (const [label, href] of [["About", "/about"], ["Contact", "/contact"], ["Privacy Policy", "/privacy"], ["Terms of Use", "/terms"]]) {
    await expect(footer.getByRole("link", { name: label, exact: true })).toHaveAttribute("href", href);
  }
  await expect(footer.locator('[aria-disabled="true"]')).toHaveCount(3);
  await expect(footer).toContainText("© 2025 TRELPNG. All rights reserved.");
});

test("H01 live property area expands to twelve listings and all principal actions work", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("featured-properties").locator("article")).toHaveCount(12);
  await expect(page.getByRole("heading", { name: "How TRELPNG Helps" })).toBeVisible();

  await page.getByTestId("hero-search-input").fill("Bor");
  await page.getByRole("option").filter({ hasText: "Boroko" }).click();
  await expect(page).toHaveURL(/\/buy\?q=Boroko$/);

  await page.goto("/");
  await page.getByRole("button", { name: "Compare Price", exact: true }).first().click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("dialog", { name: "Compare Price" })).toBeVisible();

  await page.goto("/");
  await page.getByTestId("nav-add-property").click();
  await expect(page).toHaveURL(/\/add-property/);
  // + Add Property now lands on the P01 selector (Sell/Rent → Service → Relationship).
  await expect(page.getByTestId("p01-title")).toHaveText("Add Your Property");
});
