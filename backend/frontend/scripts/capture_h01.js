const { chromium, devices } = require("playwright");

(async () => {
  const browser = await chromium.launch();
  // Desktop
  const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const dp = await desktop.newPage();
  await dp.goto("http://127.0.0.1:3000/", { waitUntil: "networkidle", timeout: 30000 });
  await dp.waitForTimeout(1500);
  await dp.screenshot({ path: "/app/test_reports/h01_desktop.png", fullPage: true });
  console.log("desktop saved");
  await desktop.close();
  // Mobile (iPhone 12)
  const mobile = await browser.newContext({ ...devices["iPhone 12"] });
  const mp = await mobile.newPage();
  await mp.goto("http://127.0.0.1:3000/", { waitUntil: "networkidle", timeout: 30000 });
  await mp.waitForTimeout(1500);
  await mp.screenshot({ path: "/app/test_reports/h01_mobile.png", fullPage: true });
  console.log("mobile saved");
  await mobile.close();
  await browser.close();
})();
