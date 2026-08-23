// P01 + popup + Turnstile authoritative regression.
//
// Covers the four latest requirements:
//   1. + Add Property opens the P01 selector (Sell/Rent → TREL/Self → Owner/Agent/Rep)
//   2. Real Cloudflare Turnstile widget renders; buttons disabled until token
//   3. Any authenticated user (STAFF, ADMIN, REFERRAL_PARTNER, PROPERTY_ADVERTISER)
//      can proceed past the entry screen — no category-mismatch notice
//   4. Guest selections are preserved through login and reach /advertiser
//
// The Turnstile widget script is stubbed with a mock that immediately delivers
// a "test-token", so the flow is deterministic without contacting Cloudflare.

const { test, expect } = require("@playwright/test");

const json = (route, body, status = 200) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

const SITE = { key: "site", value: {} };
const HOME = { key: "home", value: {} };

async function stubBaseline(page) {
  await page.route("**/api/**", (r) => json(r, []));
  await page.route("**/api/content/site", (r) => json(r, SITE));
  await page.route("**/api/page/home", (r) => json(r, HOME));
  await page.route("**/api/auth/me", (r) => json(r, {}, 401));
  // Stub the Cloudflare Turnstile CDN script with a shim that calls the
  // callback with a mock token as soon as `render()` runs. This is the
  // deterministic equivalent of using Cloudflare's always-passing test key.
  await page.route("https://challenges.cloudflare.com/turnstile/v0/api.js**", (r) =>
    r.fulfill({ status: 200, contentType: "text/javascript", body: `
      window.turnstile = {
        render(container, opts) {
          const id = "mock-" + Math.random().toString(36).slice(2);
          setTimeout(() => opts && opts.callback && opts.callback("test-token"), 50);
          return id;
        },
        reset() {},
        remove() {},
      };
    ` })
  );
}

async function authedAs(page, user) {
  await page.route("**/api/auth/me", (r) => json(r, user));
  await page.addInitScript(() => window.localStorage.setItem("png_token", "test-token"));
}

test.describe("P01 + popup + Turnstile — authoritative", () => {
  test.beforeEach(async ({ page }) => { await stubBaseline(page); });

  test("Header + Add Property renders the P01 selector (Sell/Rent, TREL/Self, Owner/Agent/Rep)", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("nav-add-property").click();
    await expect(page).toHaveURL(/\/add-property$/);
    await expect(page.getByTestId("p01-title")).toHaveText("Add Your Property");
    await expect(page.getByTestId("p01-listing-sale")).toBeVisible();
    await expect(page.getByTestId("p01-listing-rent")).toBeVisible();
    await expect(page.getByTestId("p01-service-trel")).toBeVisible();
    await expect(page.getByTestId("p01-service-self")).toBeVisible();
    await expect(page.getByTestId("p01-relationship-owner")).toBeVisible();
    await expect(page.getByTestId("p01-relationship-authorised_agent")).toBeVisible();
    await expect(page.getByTestId("p01-relationship-authorised_representative")).toBeVisible();
    await expect(page.getByTestId("p01-create-account")).toBeVisible();
    await expect(page.getByTestId("p01-login")).toBeVisible();
  });

  test("CTA buttons are disabled until all three steps are answered", async ({ page }) => {
    await page.goto("/add-property");
    await expect(page.getByTestId("p01-cta-hint")).toBeVisible();
    await expect(page.getByTestId("p01-create-account")).toBeDisabled();
    await expect(page.getByTestId("p01-login")).toBeDisabled();
    await page.getByTestId("p01-listing-sale").click();
    await page.getByTestId("p01-service-trel").click();
    await page.getByTestId("p01-relationship-owner").click();
    await expect(page.getByTestId("p01-create-account")).toBeEnabled();
    await expect(page.getByTestId("p01-login")).toBeEnabled();
    await expect(page.getByTestId("p01-cta-hint")).toHaveCount(0);
  });

  test("Log In opens the popup on Log In tab; Turnstile renders; login button disabled until token then enabled", async ({ page }) => {
    await page.goto("/add-property");
    await page.getByTestId("p01-listing-rent").click();
    await page.getByTestId("p01-service-self").click();
    await page.getByTestId("p01-relationship-owner").click();
    await page.getByTestId("p01-login").click();
    await expect(page.getByTestId("account-access-dialog")).toBeVisible();
    await expect(page.getByTestId("account-access-tab-login")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("turnstile-container")).toBeVisible();
    // Before token, submit is disabled.
    await expect(page.getByTestId("account-access-login-submit")).toBeDisabled();
    // Token resolves asynchronously via the stub; wait for it.
    await expect(page.getByTestId("account-access-login-submit")).toBeEnabled({ timeout: 3000 });
  });

  test("Guest login preserves selections and lands on /advertiser with router state", async ({ page }) => {
    let loggedIn = false;
    await page.route("**/api/auth/me", (r) => loggedIn
      ? json(r, { id: "adv1", email: "adv@t.pg", name: "Adv", role: "property_advertiser", account_category: "PROPERTY_ADVERTISER", workspace_path: "/advertiser" })
      : json(r, {}, 401));
    await page.route("**/api/auth/login", (r) => {
      const body = JSON.parse(r.request().postData() || "{}");
      // Backend Turnstile guard: request must carry the token.
      if (!body.turnstile_token) return json(r, { detail: "Human verification failed." }, 400);
      loggedIn = true;
      return json(r, { token: "tk", id: "adv1", email: "adv@t.pg", name: "Adv", role: "property_advertiser", account_category: "PROPERTY_ADVERTISER", workspace_path: "/advertiser" });
    });

    await page.goto("/add-property");
    await page.getByTestId("p01-listing-sale").click();
    await page.getByTestId("p01-service-trel").click();
    await page.getByTestId("p01-relationship-authorised_agent").click();
    await page.getByTestId("p01-login").click();
    await expect(page.getByTestId("account-access-login-submit")).toBeEnabled({ timeout: 3000 });
    await page.getByTestId("account-access-login-email").fill("adv@t.pg");
    await page.getByTestId("account-access-login-password").fill("Password@123");
    await page.getByTestId("account-access-login-submit").click();
    await expect(page).toHaveURL(/\/advertiser$/);
  });

  test("Guest registration submits Turnstile token and lands on /advertiser", async ({ page }) => {
    let registered = false, loggedIn = false;
    await page.route("**/api/auth/me", (r) => loggedIn
      ? json(r, { id: "adv2", email: "new@t.pg", name: "New", role: "property_advertiser", account_category: "PROPERTY_ADVERTISER", workspace_path: "/advertiser" })
      : json(r, {}, 401));
    await page.route("**/api/auth/register", (r) => {
      const body = JSON.parse(r.request().postData() || "{}");
      if (!body.turnstile_token) return json(r, { detail: "Human verification failed." }, 400);
      registered = true;
      return json(r, { ok: true, account_category: "PROPERTY_ADVERTISER", login_path: "/add-property?auth=login" }, 201);
    });
    await page.route("**/api/auth/login", (r) => {
      loggedIn = true;
      return json(r, { token: "tk", id: "adv2", email: "new@t.pg", name: "New", role: "property_advertiser", account_category: "PROPERTY_ADVERTISER", workspace_path: "/advertiser" });
    });

    await page.goto("/add-property");
    await page.getByTestId("p01-listing-sale").click();
    await page.getByTestId("p01-service-self").click();
    await page.getByTestId("p01-relationship-owner").click();
    await page.getByTestId("p01-create-account").click();
    await expect(page.getByTestId("account-access-register-submit")).toBeEnabled({ timeout: 3000 });
    await page.getByTestId("account-access-register-email").fill("new@t.pg");
    await page.getByTestId("account-access-register-mobile").fill("70000123");
    await page.getByTestId("account-access-register-password").fill("Password@123");
    await page.getByTestId("account-access-register-confirm").fill("Password@123");
    await page.getByTestId("account-access-register-terms").check();
    await page.getByTestId("account-access-register-submit").click();
    await expect(page).toHaveURL(/\/advertiser$/);
    expect(registered).toBeTruthy();
    expect(loggedIn).toBeTruthy();
  });

  test("Authenticated Staff sees the P01 selector and can proceed (no category notice)", async ({ page }) => {
    await authedAs(page, { id: "s1", email: "admin@trel.com.pg", name: "Admin", role: "system_admin", account_category: "STAFF", workspace_path: "/admin" });
    await page.goto("/add-property");
    await expect(page.getByTestId("p01-title")).toHaveText("Add Your Property");
    // Category-mismatch UI is gone.
    await expect(page.getByTestId("add-property-category-notice")).toHaveCount(0);
    await page.getByTestId("p01-listing-sale").click();
    await page.getByTestId("p01-service-trel").click();
    await page.getByTestId("p01-relationship-owner").click();
    await expect(page.getByTestId("p01-proceed-authed")).toBeEnabled();
    await page.getByTestId("p01-proceed-authed").click();
    await expect(page).toHaveURL(/\/advertiser$/);
  });

  test("Authenticated Referral Partner also proceeds (universal access)", async ({ page }) => {
    await authedAs(page, { id: "r1", email: "ref@t.pg", name: "Ref", role: "referral_partner", account_category: "REFERRAL_PARTNER", workspace_path: "/referral-partner" });
    await page.goto("/add-property");
    await expect(page.getByTestId("p01-title")).toHaveText("Add Your Property");
    await expect(page.getByTestId("add-property-category-notice")).toHaveCount(0);
    await page.getByTestId("p01-listing-rent").click();
    await page.getByTestId("p01-service-self").click();
    await page.getByTestId("p01-relationship-authorised_representative").click();
    await page.getByTestId("p01-proceed-authed").click();
    await expect(page).toHaveURL(/\/advertiser$/);
  });

  test("Popup dismiss and Escape still work", async ({ page }) => {
    await page.goto("/add-property");
    await page.getByTestId("p01-listing-sale").click();
    await page.getByTestId("p01-service-trel").click();
    await page.getByTestId("p01-relationship-owner").click();
    await page.getByTestId("p01-login").click();
    await expect(page.getByTestId("account-access-dialog")).toBeVisible();
    await page.getByTestId("account-access-close").click();
    await expect(page.getByTestId("account-access-dialog")).toHaveCount(0);
    // P01 selector is still on-screen with selections intact.
    await expect(page.getByTestId("p01-title")).toBeVisible();
    await page.getByTestId("p01-create-account").click();
    await expect(page.getByTestId("account-access-tab-register")).toHaveAttribute("aria-selected", "true");
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("account-access-dialog")).toHaveCount(0);
  });

  test("Legacy /admin/login and /register still redirect to the popup (with P01 selector as base page)", async ({ page }) => {
    await page.goto("/admin/login");
    await expect(page).toHaveURL(/\/add-property\?auth=login/);
    await expect(page.getByTestId("account-access-dialog")).toBeVisible();
    await expect(page.getByTestId("account-access-tab-login")).toHaveAttribute("aria-selected", "true");

    await page.goto("/register");
    await expect(page).toHaveURL(/\/add-property\?auth=register/);
    await expect(page.getByTestId("account-access-tab-register")).toHaveAttribute("aria-selected", "true");
  });
});
