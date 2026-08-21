const { chromium } = require("playwright");

async function fulfill(route, data, status = 200) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });
}

async function stub(ctx, user = null) {
  await ctx.route("**/api/**", (r) => fulfill(r, []));
  await ctx.route("**/api/content/site", (r) => fulfill(r, { key: "site", value: {} }));
  await ctx.route("**/api/page/home", (r) => fulfill(r, { key: "home", value: {} }));
  await ctx.route("**/api/auth/me", (r) => fulfill(r, user || {}, user ? 200 : 401));
  await ctx.route("https://challenges.cloudflare.com/turnstile/v0/api.js**", (r) =>
    r.fulfill({ status: 200, contentType: "text/javascript", body: `
      window.turnstile = { render(el, opts){ setTimeout(()=>opts.callback&&opts.callback("test-token"),80); return "m"; }, reset(){}, remove(){} };
    ` }));
  if (user) await ctx.addInitScript(() => window.localStorage.setItem("png_token", "t"));
}

async function shot(page, url, out, prep) {
  await page.goto(url, { waitUntil: "networkidle", timeout: 20000 });
  await page.waitForTimeout(600);
  if (prep) await prep(page);
  await page.screenshot({ path: out, fullPage: false });
  console.log("saved", out);
}

async function fillP01(page) {
  await page.getByTestId("p01-listing-sale").click();
  await page.getByTestId("p01-service-trel").click();
  await page.getByTestId("p01-relationship-owner").click();
  await page.waitForTimeout(200);
}

(async () => {
  const b = await chromium.launch();
  for (const [name, viewport] of [
    ["desktop", { width: 1440, height: 900 }],
    ["mobile", { width: 390, height: 844 }],
  ]) {
    const ctx = await b.newContext({ viewport });
    await stub(ctx);
    const page = await ctx.newPage();
    await shot(page, "http://127.0.0.1:3000/add-property", `/app/test_reports/p01_${name}.png`);
    await shot(page, "http://127.0.0.1:3000/add-property", `/app/test_reports/p01_${name}_filled.png`, fillP01);

    // Popup Log In (with real Turnstile widget)
    const ctx2 = await b.newContext({ viewport });
    await stub(ctx2);
    const p2 = await ctx2.newPage();
    await shot(p2, "http://127.0.0.1:3000/add-property", `/app/test_reports/popup_${name}_login.png`, async (pg) => {
      await fillP01(pg);
      await pg.getByTestId("p01-login").click();
      await pg.waitForTimeout(500);
    });
    await ctx2.close();

    // Popup Create Account
    const ctx3 = await b.newContext({ viewport });
    await stub(ctx3);
    const p3 = await ctx3.newPage();
    await shot(p3, "http://127.0.0.1:3000/add-property", `/app/test_reports/popup_${name}_register.png`, async (pg) => {
      await fillP01(pg);
      await pg.getByTestId("p01-create-account").click();
      await pg.waitForTimeout(500);
    });
    await ctx3.close();
    await ctx.close();
  }

  // Staff proceeds (no notice)
  const staffCtx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  await stub(staffCtx, { id: "s1", email: "admin@trel.com.pg", name: "Admin", role: "system_admin", account_category: "STAFF", workspace_path: "/admin" });
  const sp = await staffCtx.newPage();
  await shot(sp, "http://127.0.0.1:3000/add-property", "/app/test_reports/authed_staff.png", fillP01);
  await staffCtx.close();

  await b.close();
})();
