const { chromium, devices } = require("playwright");

async function fulfillJson(route, data, status = 200) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });
}

async function stubBaseline(context) {
  await context.route("**/api/content/site", (r) => fulfillJson(r, { key: "site", value: {} }));
  await context.route("**/api/page/home", (r) => fulfillJson(r, { key: "home", value: {} }));
  await context.route("**/api/**", (r) => fulfillJson(r, []));
  await context.route("**/api/auth/me", (r) => fulfillJson(r, {}, 401));
}

async function capture(page, url, out) {
  await page.goto(url, { waitUntil: "networkidle", timeout: 20000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: out, fullPage: false });
  console.log("saved", out);
}

(async () => {
  const b = await chromium.launch();

  for (const [name, viewport] of [
    ["desktop", { width: 1440, height: 900 }],
    ["mobile", { width: 390, height: 844 }],
  ]) {
    const ctx = await b.newContext({ viewport });
    await stubBaseline(ctx);
    const page = await ctx.newPage();
    await capture(page, "http://127.0.0.1:3000/add-property?auth=login", `/app/test_reports/popup_${name}_login.png`);
    await capture(page, "http://127.0.0.1:3000/add-property?auth=register", `/app/test_reports/popup_${name}_register.png`);
    await ctx.close();
  }

  // Staff notice
  const staffCtx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  await staffCtx.route("**/api/**", (r) => fulfillJson(r, []));
  await staffCtx.route("**/api/content/**", (r) => fulfillJson(r, { key: "site", value: {} }));
  await staffCtx.route("**/api/auth/me", (r) => fulfillJson(r, { id: "s1", email: "admin@trel.com.pg", name: "Admin", role: "system_admin", account_category: "STAFF", workspace_path: "/admin" }));
  await staffCtx.addInitScript(() => window.localStorage.setItem("png_token", "test-token"));
  const staffPage = await staffCtx.newPage();
  await capture(staffPage, "http://127.0.0.1:3000/add-property", "/app/test_reports/notice_staff.png");
  await staffCtx.close();

  // Referral partner notice
  const refCtx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  await refCtx.route("**/api/**", (r) => fulfillJson(r, []));
  await refCtx.route("**/api/content/**", (r) => fulfillJson(r, { key: "site", value: {} }));
  await refCtx.route("**/api/auth/me", (r) => fulfillJson(r, { id: "r1", email: "ref@trel.com.pg", name: "Ref", role: "referral_partner", account_category: "REFERRAL_PARTNER", workspace_path: "/referral-partner" }));
  await refCtx.addInitScript(() => window.localStorage.setItem("png_token", "test-token"));
  const refPage = await refCtx.newPage();
  await capture(refPage, "http://127.0.0.1:3000/add-property", "/app/test_reports/notice_referral.png");
  await refCtx.close();

  await b.close();
  console.log("all captures done");
})();
