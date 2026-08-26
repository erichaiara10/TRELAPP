const { test, expect } = require("@playwright/test");

const json = (route, body, status = 200) => route.fulfill({
  status, contentType: "application/json", body: JSON.stringify(body),
});

const completeDraft = {
  title: "Identity workflow test", description: "Complete controlled property",
  listing_type: "Sale", service: "Advertise only", relationship: "Owner / Joint Owner",
  property_class: "Residential", property_type: "House", currency: "PGK", price: "500000",
  province: "NCD", city: "Port Moresby", suburb: "Boroko", identity_scheme: "SERVICED",
  section: "42", lot: "15", bedrooms: "3", bathrooms: "2", parking: "1",
  photos: [{url:"/one.jpg",type:"image/jpeg",size:1000},{url:"/two.png",type:"image/png",size:1000}],
  documents: [], features: [], authority_confirmed: false, terms_accepted: false,
};

const accountProperty = {
  id:"submission-1", reference:"TREL-TEST100", record_type:"submission",
  data:completeDraft, submission_status:"UNDER_REVIEW", display_status:"Under Review",
  price_label:"PGK 500,000", lifecycle_id:"submission-1",
  created_at:"2026-08-26T00:00:00Z", updated_at:"2026-08-26T00:00:00Z",
};

const soldProperty = {
  ...accountProperty, id:"submission-sold", reference:"TREL-SOLD100",
  submission_status:"APPROVED", publication_status:"UNPUBLISHED",
  lifecycle_status:"SOLD", display_status:"Sold",
};

async function mockAdvertiser(page, identityDocuments, options = {}) {
  await page.addInitScript(() => window.localStorage.setItem("png_token", "test-advertiser-token"));
  await page.route("**/api/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/auth/me") return json(route, {
      id:"advertiser-1", name:"Test Advertiser", email:"advertiser@example.com",
      phone:"+67570000001", role:"property_advertiser", account_category:"PROPERTY_ADVERTISER",
      status:"ACTIVE", advertiser_profile:{relationship_type:"OWNER",status:"PENDING"},
      identity_documents:identityDocuments,
    });
    if (path.endsWith("/drafts/current") && request.method() === "GET") {
      return json(route, {data:completeDraft,current_step:5});
    }
    if (path.endsWith("/properties") && request.method() === "GET") return json(route, options.properties || [accountProperty]);
    if (path.endsWith("/workspace-records") && request.method() === "GET") {
      return json(route, options.workspace || {enquiries:[],inspections:[],documents:[],activity:[],reminders:[],notifications:[]});
    }
    if (path.endsWith("/submissions") && request.method() === "GET") return json(route, []);
    if (path.endsWith("/drafts/current") && request.method() === "PUT") return json(route, {ok:true});
    if (path.endsWith("/drafts/current/submit") && request.method() === "POST") {
      return json(route, {id:"submission-1",reference:"TREL-TEST100",status:"Under Review",data:completeDraft});
    }
    if (path === "/api/auth/logout" && request.method() === "POST") return json(route, {ok:true});
    return json(route, {});
  });
}

test("pending identity permits submission while no identity blocks it", async ({page}) => {
  await mockAdvertiser(page, [{id:"id-1",document_type:"NID_CARD",status:"PENDING"}]);
  await page.goto("/advertiser/add-property/review?resume=1");
  await expect(page.getByText("Identity document:")).toContainText("UNDER REVIEW");
  const submit = page.getByRole("button", {name:"Submit for Public Advertising"});
  await expect(submit).toBeEnabled();
  await page.getByRole("checkbox").nth(0).check();
  await page.getByRole("checkbox").nth(1).check();
  const sent = page.waitForRequest(req => req.method() === "POST" && req.url().endsWith("/drafts/current/submit"));
  await submit.click();
  await sent;
  await expect(page).toHaveURL(/\/advertiser\/properties$/);
});

test("advertiser can sign out and switch to another account", async ({page}) => {
  await mockAdvertiser(page, [{id:"id-1",document_type:"NID_CARD",status:"PENDING"}]);
  await page.goto("/advertiser");
  await page.getByRole("button", {name:"Sign out"}).click();
  await expect(page).toHaveURL(/\/$/);
  await expect.poll(() => page.evaluate(() => localStorage.getItem("png_token"))).toBeNull();
  await expect(page.getByTestId("account-access-dialog")).toHaveCount(0);
});

test("property totals and rows come from the signed-in advertiser account", async ({page}) => {
  await mockAdvertiser(page, [{id:"id-1",document_type:"NID_CARD",status:"PENDING"}]);
  await page.goto("/advertiser/properties");
  const cards=page.locator(".adv-mini-stat");
  await expect(cards.nth(0)).toContainText("1All Listings");
  await expect(cards.nth(1)).toContainText("0Live");
  await expect(cards.nth(2)).toContainText("1Under Review");
  await expect(cards.nth(3)).toContainText("0Drafts");
  await expect(cards.nth(4)).toContainText("0Inactive");
  await expect(page.getByRole("cell", {name:/Identity workflow test/})).toBeVisible();
  await page.getByRole("row", {name:/Identity workflow test/}).click();
  await expect(page.getByRole("dialog", {name:"Property #TREL-TEST100"})).toBeVisible();
});

test("new advertiser has no shared enquiries inspections documents or activity", async ({page}) => {
  await mockAdvertiser(page, []);
  await page.goto("/advertiser");
  await expect(page.locator(".adv-stat").filter({hasText:"Total Enquiries"})).toContainText("0");
  await expect(page.getByText("No recent activity.")).toBeVisible();
  await expect(page.getByText("No reminders.")).toBeVisible();
  await expect(page.getByText("No inspection requests.")).toBeVisible();
  await page.goto("/advertiser/enquiries");
  await expect(page.getByText("No matching enquiries.")).toBeVisible();
  await page.goto("/advertiser/documents");
  await expect(page.getByText("No matching documents.")).toBeVisible();
});

test("sold records are read-only and notifications are account scoped", async ({page}) => {
  await mockAdvertiser(page, [], {properties:[soldProperty]});
  await page.goto("/advertiser");
  await expect(page.locator(".adv-icon-button i")).toHaveCount(0);
  await page.getByRole("button", {name:"Notifications"}).click();
  await expect(page.getByText("No notifications.")).toBeVisible();
  await page.goto("/advertiser/properties?status=inactive");
  await page.getByRole("row", {name:/TREL-SOLD100/}).click();
  await page.getByRole("button", {name:"View Record"}).click();
  const record = page.getByRole("dialog", {name:"Property Record #TREL-SOLD100"});
  await expect(record.getByRole("button", {name:"Edit Listing"})).toHaveCount(0);
  await expect(record.getByRole("button", {name:"Close Record"})).toBeVisible();
});

test("inactive advertiser is warned, can continue, and is then signed out automatically", async ({page}) => {
  await mockAdvertiser(page, [{id:"id-1",document_type:"NID_CARD",status:"PENDING"}]);
  await page.clock.install({time:new Date("2026-08-26T00:00:00Z")});
  await page.goto("/advertiser");
  await page.clock.fastForward(13 * 60 * 1000);
  await expect(page.getByRole("dialog", {name:"Still using TRELPNG?"})).toBeVisible();
  await page.getByRole("button", {name:"Continue session"}).click();
  await expect(page.getByRole("dialog", {name:"Still using TRELPNG?"})).toBeHidden();
  await page.clock.fastForward(13 * 60 * 1000);
  await expect(page.getByRole("dialog", {name:"Still using TRELPNG?"})).toBeVisible();
  await page.clock.fastForward(2 * 60 * 1000);
  await expect(page).toHaveURL(/\/$/);
  await expect.poll(() => page.evaluate(() => localStorage.getItem("png_token"))).toBeNull();
  await expect(page.getByTestId("account-access-dialog")).toHaveCount(0);
});

test("identity link saves the draft and provides a return path", async ({page}) => {
  await mockAdvertiser(page, []);
  await page.goto("/advertiser/add-property/review?resume=1");
  await expect(page.getByRole("button", {name:"Submit for Public Advertising"})).toBeDisabled();
  const saved = page.waitForRequest(req => req.method() === "PUT" && req.url().endsWith("/drafts/current"));
  await page.getByRole("link", {name:"Complete Identity Verification"}).click();
  await saved;
  await expect(page).toHaveURL(/account-settings\?section=identity&return=property-review$/);
  await expect(page.getByRole("button", {name:"Return to Property Review"})).toBeVisible();
});
