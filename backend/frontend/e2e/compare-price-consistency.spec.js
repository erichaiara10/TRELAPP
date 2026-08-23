const { test, expect } = require("@playwright/test");

const json = (route, body, status = 200) => route.fulfill({
  status,
  contentType: "application/json",
  body: JSON.stringify(body),
});

const subject = (listingType = "sale") => ({
  id: `subject-${listingType}`,
  title: listingType === "sale" ? "Boroko Family Home" : "Boroko Rental Home",
  listing_type: listingType,
  property_type: "House",
  price: listingType === "sale" ? 780000 : 3200,
  currency: "PGK",
  province: "National Capital District",
  location: "Port Moresby",
  suburb: "Boroko",
  local_area: "Stage 3",
  bedrooms: 3,
  bathrooms: 2,
  parking: 2,
  area_sqm: 650,
  property_condition: "Good",
  tenure_type: "State Lease",
  street_name: "Angau Drive",
  nearby_landmark: "Boroko Foodworld",
  images: ["https://images.test/house.jpg"],
  status: "active",
  featured: true,
});

const analysis = {
  verdict: "fair",
  range_min: 740000,
  range_max: 820000,
  median: 780000,
  sample_size: 8,
  internal_count: 5,
  external_count: 3,
  evidence_strength: "MODERATE",
  formal_range_available: true,
  comparables: [{ title: "Comparable Home", suburb: "Boroko", price: 775000 }],
};

async function mockApi(page, payloads) {
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path === "/api/content/site") return json(route, { key: "site", value: {} });
    if (path.startsWith("/api/page/")) return json(route, { sections: {} });
    if (path === "/api/property-types") return json(route, [{ id: "house", name: "House" }]);
    if (path === "/api/locations/provinces") return json(route, [{ id: "ncd", name: "National Capital District" }]);
    if (path === "/api/locations/cities") return json(route, [{ id: "pom", name: "Port Moresby", province_id: "ncd" }]);
    if (path === "/api/locations/suburbs") return json(route, [{ id: "boroko", name: "Boroko", city_id: "pom" }]);
    if (path === "/api/auth/me") return json(route, null, 401);
    if (path === "/api/properties/subject-sale") return json(route, subject("sale"));
    if (path === "/api/properties/subject-rent") return json(route, subject("rent"));
    if (path === "/api/properties") {
      const mode = url.searchParams.get("listing_type") || "sale";
      return json(route, [subject(mode)]);
    }
    if (path === "/api/ai/price-analysis") {
      payloads.push(request.postDataJSON());
      return json(route, analysis);
    }
    return json(route, []);
  });
}

async function expectApprovedPopup(page, expectedUrl) {
  const dialog = page.getByRole("dialog", { name: "Compare Price" });
  await expect(dialog).toBeVisible();
  await expect(page).toHaveURL(expectedUrl);
  await expect(page.locator('[data-testid$="-panel"]')).toHaveCount(0);
  for (const wording of [
    "Compare Price",
    "Indicative price range",
    "Median comparable",
    "Comparables",
    "TREL Internal",
    "External Market",
    "Evidence",
    "Recommendation:",
    "Similar properties",
    "This analysis is based on available data and should be used as a guide only.",
  ]) await expect(dialog).toContainText(wording);
}

test("Home, Buy, Rent and Property Details use the same Compare Price popup", async ({ page }) => {
  const payloads = [];
  await mockApi(page, payloads);

  for (const scenario of [
    { path: "/", url: /\/$/ },
    { path: "/buy", url: /\/buy$/ },
    { path: "/rent", url: /\/rent$/ },
    { path: "/property/subject-sale", url: /\/property\/subject-sale$/ },
    { path: "/property/subject-rent", url: /\/property\/subject-rent$/ },
  ]) {
    await page.goto(scenario.path);
    await page.getByRole("button", { name: "Compare Price", exact: true }).first().click();
    await expectApprovedPopup(page, scenario.url);
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog", { name: "Compare Price" })).toHaveCount(0);
  }

  await page.goto("/sell");
  await page.getByTestId("sell_form-type").selectOption("House");
  await page.getByTestId("sell_form-location-province").selectOption("ncd");
  await page.getByTestId("sell_form-location-city").selectOption("pom");
  await page.getByTestId("sell_form-location-suburb").selectOption("boroko");
  await page.getByTestId("sell_form-street-name").fill("Angau Drive");
  await page.getByTestId("sell_form-price-input").fill("780000");
  await page.getByRole("button", { name: "Compare Price", exact: true }).click();
  await expectApprovedPopup(page, /\/sell$/);
  await page.getByRole("button", { name: "Close", exact: true }).click();

  expect(payloads).toHaveLength(6);
  for (const payload of payloads.slice(0, 5)) {
    expect(payload).toMatchObject({
      property_type: "House",
      province: "National Capital District",
      city: "Port Moresby",
      suburb: "Boroko",
      local_area: "Stage 3",
      bedrooms: 3,
      bathrooms: 2,
      parking: 2,
      property_condition: "Good",
      tenure_type: "State Lease",
      street_name: "Angau Drive",
      nearby_landmark: "Boroko Foodworld",
    });
  }
  expect(payloads[5]).toMatchObject({
    property_type: "House",
    listing_type: "sale",
    price: 780000,
    province: "National Capital District",
    city: "Port Moresby",
    suburb: "Boroko",
    street_name: "Angau Drive",
  });
  expect(payloads.map((p) => p.listing_type)).toEqual(["sale", "sale", "rent", "sale", "rent", "sale"]);
});

test("popup closes using X, backdrop and Escape on desktop and mobile", async ({ page }) => {
  const payloads = [];
  await mockApi(page, payloads);
  await page.goto("/buy");
  const trigger = page.getByRole("button", { name: "Compare Price", exact: true }).first();

  await trigger.click();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Compare Price" })).toHaveCount(0);

  await trigger.click();
  await page.locator('[data-testid$="-overlay"]').click({ position: { x: 5, y: 5 } });
  await expect(page.getByRole("dialog", { name: "Compare Price" })).toHaveCount(0);

  await page.setViewportSize({ width: 390, height: 844 });
  await trigger.click();
  await expectApprovedPopup(page, /\/buy$/);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Compare Price" })).toHaveCount(0);
});
