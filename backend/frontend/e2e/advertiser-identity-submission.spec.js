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

async function mockAdvertiser(page, identityDocuments) {
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
    if (path.endsWith("/submissions") && request.method() === "GET") return json(route, []);
    if (path.endsWith("/drafts/current") && request.method() === "PUT") return json(route, {ok:true});
    if (path.endsWith("/drafts/current/submit") && request.method() === "POST") {
      return json(route, {id:"submission-1",reference:"TREL-TEST100",status:"Under Review",data:completeDraft});
    }
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
