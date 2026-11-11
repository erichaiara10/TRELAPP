const { test, expect } = require("@playwright/test");

async function advertiserApi(page) {
  let draft = { data: {}, current_step: 1 };
  await page.addInitScript(() => localStorage.setItem("png_token", "controlled-intake-test"));
  await page.route("**/api/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    let body = [];
    if (path === "/api/auth/me") body = {
      id:"recovery-advertiser",name:"Recovery Test",email:"recovery@example.test",
      role:"property_advertiser",account_category:"PROPERTY_ADVERTISER",
      email_verified:true,profile_complete:true,
    };
    else if (path.endsWith("/drafts/current")) {
      if (request.method() === "PUT") draft = request.postDataJSON();
      body = draft;
    } else if (path.endsWith("/workspace-records")) body = {};
    await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(body)});
  });
  return () => draft;
}

test("P01 choices open editable property details and survive draft save and reload", async ({page}) => {
  const saved = await advertiserApi(page);
  await page.goto("/add-property");
  await page.getByTestId("p01-listing-rent").click();
  await page.getByTestId("p01-service-self").click();
  await page.getByTestId("p01-relationship-authorised_agent").click();
  await page.getByTestId("p01-proceed-authed").click();
  await expect(page).toHaveURL(/\/advertiser\/add-property$/);
  await expect(page.getByRole("button",{name:"Rent",exact:true})).toHaveClass(/selected/);
  await expect(page.getByRole("button",{name:"Advertise only — I will handle it"})).toHaveClass(/selected/);
  await expect(page.getByRole("button",{name:"Authorised Real Estate Agent",exact:true})).toHaveClass(/selected/);
  await page.getByLabel("Property Name / Listing Title *",{exact:true}).fill("Recovery draft — Boroko");
  await page.getByLabel("Price / Rent Amount",{exact:true}).fill("2800");
  await page.getByLabel("Property Description *",{exact:true}).fill("Controlled private workspace draft");
  await page.getByRole("button",{name:"Continue to Location"}).click();
  await expect(page).toHaveURL(/\/add-property\/location$/);
  expect(saved().data).toMatchObject({listing_type:"Rent",service:"Advertise only",relationship:"Authorised Real Estate Agent",title:"Recovery draft — Boroko",price:"2800"});
  await page.getByLabel("Section Number *",{exact:true}).fill("42");
  await page.getByLabel("Lot Number *",{exact:true}).fill("15");
  await page.getByRole("button",{name:"Continue to Features"}).click();
  await expect(page).toHaveURL(/\/add-property\/features$/);
  await page.getByLabel("Bedrooms",{exact:true}).fill("3");
  await page.getByRole("button",{name:"Save Draft",exact:true}).click();
  await expect.poll(() => saved().data.bedrooms).toBe("3");
  await page.reload();
  await expect(page.getByLabel("Bedrooms",{exact:true})).toHaveValue("3");
  await page.getByRole("button",{name:"Back",exact:false}).click();
  await expect(page).toHaveURL(/\/add-property\/location$/);
  await expect(page.getByLabel("Section Number *",{exact:true})).toHaveValue("42");
});

test("Add Property workspace navigation and step links resolve", async ({page}) => {
  await advertiserApi(page);
  await page.goto("/advertiser/add-property");
  const sidebar = page.locator(".adv-sidebar");
  for (const [name,path] of [["Dashboard","/advertiser"],["My Properties","/advertiser/properties"],
    ["Enquiries","/advertiser/enquiries"],["Inspections","/advertiser/inspections"],
    ["Documents","/advertiser/documents"],["Account Settings","/advertiser/account-settings"],
    ["Help","/advertiser/help"],["Add Property","/advertiser/add-property"]]) {
    await sidebar.getByRole("link",{name,exact:true}).click();
    await expect(page).toHaveURL(new RegExp(`${path}$`));
    await expect(page.getByRole("heading",{level:1})).toBeVisible();
  }
  for (const path of ["location","features","photos","review"]) {
    await page.goto(`/advertiser/add-property/${path}`);
    await expect(page).toHaveURL(new RegExp(`/add-property/${path}$`));
    await expect(page.getByRole("heading",{level:1})).toBeVisible();
  }
  await expect(page.getByRole("button",{name:"Submit for Public Advertising"})).toBeDisabled();
});

test("public links on Add Property reach the intended pages", async ({page}) => {
  await advertiserApi(page);
  await page.goto("/add-property");
  for (const target of ["home","buy","rent","wanted","management","corporate","about","contact"]) {
    await page.getByTestId(`nav-${target}`).click();
    await expect(page).toHaveURL(new RegExp(target === "home" ? "/$" : `/${target}$`));
    await page.goto("/add-property");
  }
  for (const target of ["privacy","terms"]) {
    await page.getByRole("link",{name:target === "privacy" ? "Privacy Policy" : "Terms of Use",exact:true}).click();
    await expect(page).toHaveURL(new RegExp(`/${target}$`));
    await page.goto("/add-property");
  }
});
