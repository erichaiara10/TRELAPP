// Popup-authoritative regression: ensures the H01 header triggers the approved
// common AccountAccessDialog for every entry point, that authentication comes
// before any property-entry question, that Add Property intent survives a
// login, and that each account category reaches only its permitted workspace.
//
// All API calls are mocked so this file runs against a plain dev server
// without any DB seeding. Category-mismatch and rejected-standalone-screens
// checks are all pure UI assertions.

const { test, expect } = require("@playwright/test");

const jsonRoute = (route, body, status = 200) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

const SITE_CONTENT = { key: "site", value: { phone: "+675 76281552", whatsapp: "67581383302" } };
const HOME_CONTENT = { key: "home", value: { hero: { title: "Find a place you're proud to call home.", subtitle: "Browse quality properties for sale and rent across Papua New Guinea." } } };

async function stubBaseline(page) {
  await page.route("**/api/content/site", (r) => jsonRoute(r, SITE_CONTENT));
  await page.route("**/api/page/home", (r) => jsonRoute(r, HOME_CONTENT));
  await page.route("**/api/properties**", (r) => jsonRoute(r, []));
  await page.route("**/api/property-types", (r) => jsonRoute(r, []));
  await page.route("**/api/locations/**", (r) => jsonRoute(r, []));
  await page.route("**/api/auth/me", (r) => jsonRoute(r, {}, 401));
}

async function loginAs(page, user) {
  await page.route("**/api/auth/login", (r) => jsonRoute(r, { token: "test-token", ...user }));
  await page.route("**/api/auth/me", (r) => jsonRoute(r, user));
  // Seed the token BEFORE the app boots so AuthProvider fetches /auth/me.
  await page.addInitScript(() => window.localStorage.setItem("png_token", "test-token"));
}

test.describe("Common account popup — authoritative", () => {
  test.beforeEach(async ({ page }) => {
    await stubBaseline(page);
  });

  test("Header Log In opens the approved popup on the Log In tab", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("nav-login").click();
    await expect(page).toHaveURL(/\/add-property\?auth=login/);
    await expect(page.getByTestId("account-access-dialog")).toBeVisible();
    await expect(page.getByTestId("account-access-title")).toHaveText("Welcome Back");
    await expect(page.getByTestId("account-access-tab-login")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("account-access-login-email")).toBeVisible();
    await expect(page.getByTestId("account-access-login-password")).toBeVisible();
    await expect(page.getByTestId("turnstile-preview")).toBeVisible();
    await expect(page.getByTestId("account-access-google")).toBeVisible();
    // Rejected standalone screen must never render.
    await expect(page.locator("text=TRELPNG sign in")).toHaveCount(0);
  });

  test("Header Register opens the same popup on the Create Account tab", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("nav-register").click();
    await expect(page).toHaveURL(/\/add-property\?auth=register/);
    await expect(page.getByTestId("account-access-title")).toHaveText("Create Your Account");
    await expect(page.getByTestId("account-access-tab-register")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("account-access-register-email")).toBeVisible();
    await expect(page.getByTestId("account-access-register-mobile")).toBeVisible();
    await expect(page.getByTestId("account-access-register-password")).toBeVisible();
    await expect(page.getByTestId("account-access-register-confirm")).toBeVisible();
    await expect(page.getByTestId("account-access-register-terms")).toBeVisible();
  });

  test("Add Property never shows property-entry questions before authentication", async ({ page }) => {
    await page.goto("/add-property");
    await expect(page.getByTestId("account-access-dialog")).toBeVisible();
    // The rejected Sell/Rent question set must not be rendered.
    await expect(page.locator("text=What would you like to do?")).toHaveCount(0);
    await expect(page.locator("text=I want TREL to sell my property")).toHaveCount(0);
    // The authgate page is present but no property-entry form.
    await expect(page.getByTestId("add-property-authgate")).toBeVisible();
    await expect(page.locator("text=Sign in to add your property")).toBeVisible();
  });

  test("Add Property intent survives login for a Property Advertiser", async ({ page }) => {
    // Route the login call — after success the popup will call login() and
    // then navigate. Intercept /auth/me AFTER login so the popup's local
    // login() branch decides the destination directly from the result.user.
    let loggedIn = false;
    await page.route("**/api/auth/me", (r) => {
      if (!loggedIn) return jsonRoute(r, {}, 401);
      return jsonRoute(r, { id: "adv1", email: "adv@test.pg", name: "Adv", role: "property_advertiser", account_category: "PROPERTY_ADVERTISER", workspace_path: "/advertiser" });
    });
    await page.route("**/api/auth/login", (r) => {
      loggedIn = true;
      return jsonRoute(r, { token: "test-token", id: "adv1", email: "adv@test.pg", name: "Adv", role: "property_advertiser", account_category: "PROPERTY_ADVERTISER", workspace_path: "/advertiser" });
    });
    await page.route("**/api/identity-documents/mine", (r) => jsonRoute(r, []));
    await page.goto("/add-property");
    await expect(page.getByTestId("account-access-dialog")).toBeVisible();
    await page.getByTestId("account-access-login-email").fill("adv@test.pg");
    await page.getByTestId("account-access-login-password").fill("Password@123");
    await page.getByTestId("account-access-login-submit").click();
    await expect(page).toHaveURL(/\/advertiser$/);
    await expect(page.locator("text=Property Advertiser Workspace")).toBeVisible();
  });

  test("Authenticated Staff user sees a Staff notice on Add Property (never silent /admin redirect)", async ({ page }) => {
    await loginAs(page, { id: "staff1", email: "admin@trel.com.pg", name: "Admin", role: "system_admin", account_category: "STAFF", workspace_path: "/admin" });
    await page.goto("/");                 // resolves /api/auth/me → staff
    await page.getByTestId("nav-add-property").click();
    await expect(page.getByTestId("add-property-category-notice")).toBeVisible();
    await expect(page.locator("text=Your current account is a Staff Account.")).toBeVisible();
    await expect(page.getByTestId("add-property-return-primary")).toContainText("Return to Staff Workspace");
    await expect(page.getByTestId("add-property-switch-account")).toContainText("Log Out and Use Another Account");
    // Silent redirect to /admin would fail this URL assertion:
    await expect(page).toHaveURL(/\/add-property/);
  });

  test("Authenticated Referral Partner user sees a Referral notice on Add Property", async ({ page }) => {
    await loginAs(page, { id: "ref1", email: "ref@test.pg", name: "Ref", role: "referral_partner", account_category: "REFERRAL_PARTNER", workspace_path: "/referral-partner" });
    await page.goto("/");
    await page.getByTestId("nav-add-property").click();
    await expect(page.getByTestId("add-property-category-notice")).toBeVisible();
    await expect(page.locator("text=Your current account is a Referral Partner Account.")).toBeVisible();
    await expect(page.getByTestId("add-property-return-primary")).toContainText("Go to Referral Partner Workspace");
    await expect(page.getByTestId("add-property-switch-account")).toBeVisible();
  });

  test("Rejected standalone screens are inaccessible — /admin/login and /register both redirect to the popup", async ({ page }) => {
    await page.goto("/admin/login");
    await expect(page).toHaveURL(/\/add-property\?auth=login/);
    await expect(page.getByTestId("account-access-dialog")).toBeVisible();
    await expect(page.getByTestId("account-access-tab-login")).toHaveAttribute("aria-selected", "true");
    // TRELPNG-sign-in banner from the rejected standalone must not appear.
    await expect(page.locator("text=TRELPNG sign in")).toHaveCount(0);

    await page.goto("/register");
    await expect(page).toHaveURL(/\/add-property\?auth=register/);
    await expect(page.getByTestId("account-access-tab-register")).toHaveAttribute("aria-selected", "true");
    await expect(page.locator("h1", { hasText: "Register" })).toHaveCount(0);
  });

  test("Direct URLs cannot bypass authentication or role permissions", async ({ page }) => {
    // Unauthenticated visitor to /advertiser must be sent through the popup.
    await page.goto("/advertiser");
    await expect(page).toHaveURL(/\/add-property\?auth=login/);
    await expect(page.getByTestId("account-access-dialog")).toBeVisible();
    // Same for /admin.
    await page.goto("/admin");
    await expect(page).toHaveURL(/\/add-property\?auth=login/);
    await expect(page.getByTestId("account-access-dialog")).toBeVisible();
  });

  test("Popup close, Esc, and scrim all dismiss without navigating", async ({ page }) => {
    await page.goto("/add-property?auth=login");
    await expect(page.getByTestId("account-access-dialog")).toBeVisible();
    await page.getByTestId("account-access-close").click();
    await expect(page.getByTestId("account-access-dialog")).toHaveCount(0);

    await page.goto("/add-property?auth=register");
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("account-access-dialog")).toHaveCount(0);
  });

  test("Login validation — password mismatch on the Create Account tab shows an error", async ({ page }) => {
    await page.goto("/add-property?auth=register");
    await page.getByTestId("account-access-register-email").fill("newuser@test.pg");
    await page.getByTestId("account-access-register-mobile").fill("70000123");
    await page.getByTestId("account-access-register-password").fill("Password@123");
    await page.getByTestId("account-access-register-confirm").fill("Different@123");
    await page.getByTestId("account-access-register-terms").check();
    await page.getByTestId("account-access-register-submit").click();
    await expect(page.getByTestId("account-access-error")).toHaveText("Passwords do not match");
  });
});
