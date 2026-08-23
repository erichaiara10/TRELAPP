const { test, expect } = require("@playwright/test");

const json = (route, body, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

async function mockApi(page, capture = {}) {
  await page.addInitScript(() => localStorage.setItem("png_token", "e2e-token"));
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/auth/me") return json(route, { id:"staff-1", name:"QA Staff", email:"qa@trel.test", role:"system_admin", account_category:"STAFF", workspace_path:"/admin" });
    if (path === "/api/properties" && request.method() === "GET") return json(route, []);
    if (path === "/api/properties" && request.method() === "POST") { capture.created = request.postDataJSON(); return json(route, { id:"property-1", ...capture.created }); }
    if (path === "/api/properties/duplicate-check") return json(route, { has_possible_duplicates:false, candidates:[] });
    if (path === "/api/admin/market/summary") return json(route, { active_listings:1, market_listings:1, matches_active:1, master_properties:1, active_sources:1, sources:1 });
    if (path === "/api/admin/market/listings") return json(route, [{
      id:"source-link-1", source_site_id:"source-1", source_name:"Example Market",
      source_listing_id:"ad-10", source_url:"https://example.test/ad-10",
      transaction_type:"SALE", property_type_name:"House", province_name:"National Capital District",
      city_name:"Port Moresby", suburb_name:"Waigani", street_name:"Waigani Drive",
      lot:"15", section:"42", price_amount:900000, current_status:"ACTIVE",
      first_seen_at:"2026-08-20T01:00:00Z", last_seen_at:"2026-08-20T01:00:00Z",
      master_property_id:"property-1", match_status:"MATCHED", match_confidence:100,
      match_rule:"DIRECT_TREL_ID", origin_kind:"EXTERNAL", comparable_eligible:true,
    }]);
    if (path === "/api/documents/upload") return json(route, { id:"doc-1", url:"https://files.test/title.pdf", name:"title.pdf", content_type:"application/pdf" });
    if (path === "/api/property-types") return json(route, [
      { id:"type-house", name:"House", legal_scheme:"lot_section_street", is_active:true },
      { id:"type-land", name:"Customary Land", legal_scheme:"portion", is_active:true },
    ]);
    if (path === "/api/locations/provinces") return json(route, [{ id:"province-1", name:"National Capital District" }]);
    if (path === "/api/locations/cities") return json(route, [{ id:"city-1", province_id:"province-1", name:"Port Moresby" }]);
    if (path === "/api/locations/suburbs") return json(route, [{ id:"suburb-1", city_id:"city-1", name:"Waigani" }]);
    return json(route, []);
  });
}

test("all Add Property fields connect to the integrated create request", async ({ page }) => {
  const capture = {};
  await mockApi(page, capture);
  await page.goto("/admin/properties");
  await page.getByTestId("new-property-btn").click();
  await page.getByTestId("property-title-input").fill("E2E Waigani House");
  await page.getByTestId("property-bedrooms-input").fill("3");
  await page.getByTestId("property-bathrooms-input").fill("2");
  await page.getByTestId("property-parking-input").fill("2");
  await page.getByTestId("property-area_sqm-input").fill("180");
  await page.getByTestId("property-description").fill("Complete field connection test");
  await page.getByTestId("property-features").fill("Air conditioning, Security fence");
  await page.getByTestId("property-type").selectOption("House");
  await page.getByTestId("property-total-area-ha").fill("0.08");
  await page.getByTestId("property-location-province").selectOption("province-1");
  await page.getByTestId("property-location-city").selectOption("city-1");
  await page.getByTestId("property-location-suburb").selectOption("suburb-1");
  await page.getByTestId("property-allotment-number").fill("15");
  await page.getByTestId("property-section-number").fill("42");
  await page.getByTestId("property-street-name").fill("Waigani Drive");
  await page.getByTestId("property-local-area").fill("Waigani Central");
  await page.getByTestId("property-title-reference").fill("VOL-10/FOL-20");
  await page.getByTestId("property-tenure-type").selectOption("STATE_LEASE");
  await page.getByTestId("property-owner-name").fill("Test Owner");
  await page.getByTestId("property-owner-email").fill("owner@example.test");
  await page.getByTestId("property-owner-phone").fill("70000000");
  await page.getByTestId("property-authority-status").selectOption("VERIFIED");
  await page.getByTestId("property-document-type").selectOption("TITLE_DOCUMENT");
  await page.getByTestId("property-document-input").setInputFiles({ name:"title.pdf", mimeType:"application/pdf", buffer:Buffer.from("x".repeat(200)) });
  await expect(page.getByText("title.pdf")).toBeVisible();
  await page.getByTestId("property-price-input").fill("900000");
  await page.getByTestId("property-address").fill("12 Waigani Drive");
  await page.getByTestId("property-nearby-landmark").fill("Vision City");
  await page.getByTestId("property-map-coords-input").fill("-9.4438,147.1803");
  await page.getByTestId("property-photos-url-input").fill("https://images.test/house.jpg");
  await page.getByTestId("property-photos-url-add").click();
  await page.getByTestId("property-status").selectOption("active");
  await page.getByTestId("property-duplicate-check").click();
  await expect(page.getByText("No matching property found")).toBeVisible();
  await page.getByTestId("prop-save").click();
  await expect(page.getByTestId("prop-modal")).toHaveCount(0);
  expect(capture.created).toMatchObject({
    title:"E2E Waigani House", property_type_id:"type-house",
    province_id:"province-1", city_id:"city-1", suburb_id:"suburb-1",
    allotment_number:"15", section_number:"42", street_name:"Waigani Drive",
    owner_name:"Test Owner", owner_email:"owner@example.test", owner_phone:"70000000",
    authority_status:"VERIFIED", status:"active", tenure_type:"STATE_LEASE",
    address:"12 Waigani Drive", nearby_landmark:"Vision City", map_coords:"-9.4438,147.1803",
    bedrooms:3, bathrooms:2, parking:2, area_sqm:180,
  });
  expect(capture.created.features).toEqual(["Air conditioning", "Security fence"]);
  expect(capture.created.images).toEqual(["https://images.test/house.jpg"]);
  expect(capture.created.documents[0]).toMatchObject({ document_type:"TITLE_DOCUMENT", url:"https://files.test/title.pdf" });
});

test("portion/customary screen prevents save without required district", async ({ page }) => {
  await mockApi(page);
  await page.goto("/admin/properties");
  await page.getByTestId("new-property-btn").click();
  await page.getByTestId("property-title-input").fill("E2E Portion");
  await page.getByTestId("property-type").selectOption("Customary Land");
  await page.getByTestId("property-total-area-ha").fill("10");
  await page.getByTestId("property-location-province").selectOption("province-1");
  await page.getByTestId("property-location-city").selectOption("city-1");
  await page.getByTestId("property-location-suburb").selectOption("suburb-1");
  await page.getByTestId("property-full-portion-number").fill("2145C");
  await page.getByTestId("property-owner-name").fill("Customary Owner");
  await page.getByTestId("property-price-input").fill("500000");
  await page.getByTestId("prop-save").click();
  await expect(page.getByText("District is required")).toBeVisible();
});

test("admin screen links resolve to their expected routes", async ({ page }) => {
  await mockApi(page);
  await page.goto("/admin");
  for (const target of ["properties", "customers", "leads", "requirements", "matching", "inspections", "tasks", "pipeline", "users", "locations", "content", "reports", "market/evidence"]) {
    await page.getByTestId(`sidebar-${target}`).click();
    await expect(page).toHaveURL(new RegExp(`/admin/${target}$`));
  }
});

test("Market Evidence shows the link to the advertised Master Property", async ({ page }) => {
  await mockApi(page);
  await page.goto("/admin/market/evidence");
  await expect(page.getByTestId("kpi-evidence-linked")).toContainText("1");
  await page.getByTestId("evidence-row-source-link-1").click();
  await expect(page.getByTestId("inspector-master-property")).toHaveText("property-1");
  await expect(page.getByText("DIRECT_TREL_ID")).toBeVisible();
});

test("common login routes a Referral Partner to the referral workspace", async ({ page }) => {
  await page.addInitScript(() => {
    window.turnstile = {
      render: (_element, options) => {
        options.callback("e2e-turnstile-token");
        return "e2e-widget";
      },
      reset: () => {},
      remove: () => {},
    };
  });
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/auth/login") return json(route, { id:"ref-1", name:"Referral QA", email:"ref@trel.test", role:"referral_partner", account_category:"REFERRAL_PARTNER", workspace_path:"/referral-partner", token:"ref-token" });
    if (path === "/api/referrals/mine") return json(route, []);
    return json(route, []);
  });
  await page.goto("/admin/login");
  await expect(page.getByTestId("account-access-dialog")).toBeVisible();
  await page.getByTestId("account-access-login-email").fill("ref@trel.test");
  await page.getByTestId("account-access-login-password").fill("Password@123");
  await page.getByTestId("account-access-login-submit").click();
  await expect(page).toHaveURL(/\/referral-partner$/);
  await expect(page.getByRole("heading", { name:"Referral Partner Workspace" })).toBeVisible();
});
