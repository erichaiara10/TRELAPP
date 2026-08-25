const { test, expect } = require("@playwright/test");

const json=(route,body,status=200)=>route.fulfill({status,contentType:"application/json",body:JSON.stringify(body)});
const advertiser={id:"user-1",reference:"ADV-USER1",name:"Mary Kila",email:"mary@example.com",phone:"+675 7000 0000",relationship:"OWNER",profile_status:"VERIFIED",identity_status:"VERIFIED",account_status:"ACTIVE",property_count:1,assigned_staff:"System Admin",profile:{residential_address:"Waigani",preferred_communication:"Both"},identity_documents:[{id:"doc-1",document_type:"NID_CARD",original_filename:"mary-id.pdf",status:"VERIFIED",created_at:"2026-08-20T00:00:00Z"}],submissions:[]};
const submission={id:"sub-1",reference:"TREL-1001",user_id:"user-1",advertiser_reference:"ADV-USER1",advertiser_name:"Mary Kila",property_title:"Mary's Waigani Home",relationship:"OWNER",service:"Advertise only",submitted_at:"2026-08-20T00:00:00Z",review_due:"2026-08-25T00:00:00Z",sla:"DUE_TODAY",conflict_status:"CLEAR",conflict_resolution_stale:false,authority_status:"ACCEPTED",assigned_staff:"System Admin",status:"APPROVED",listing_reference:"LIST-1001",data:{title:"Mary's Waigani Home",description:"Family home",property_class:"Residential",property_type:"House",listing_type:"Sale",currency:"PGK",price:"900000",province:"NCD",city:"Port Moresby",suburb:"Waigani",street:"Independence Drive",section:"12",lot:"8",bedrooms:"3",bathrooms:"2",parking:"2",authority_confirmed:true,features:["Fenced"],photos:["/photo-1.jpg","/photo-2.jpg"]},documents:[{id:"doc-2",original_filename:"title.pdf",status:"SUBMITTED",created_at:"2026-08-20T00:00:00Z"}],audit:[]};
const publication={...submission,identity_status:"VERIFIED",readiness:"READY",blockers:[],publication_status:"DRAFT"};
const lifecycle={...publication,publication_status:"PUBLISHED",availability:"AVAILABLE",lifecycle_status:"CURRENT",last_confirmed:"2026-08-20T00:00:00Z",next_due:"2026-11-20T00:00:00Z",unpublish_due:"2027-02-20T00:00:00Z",archive_due:"2027-08-20T00:00:00Z",reminder_count:0,confirmation:{},audit:[]};

test.beforeEach(async({page})=>{
  await page.addInitScript(()=>window.localStorage.setItem("png_token","test-staff-token"));
  await page.route("**/api/**",async route=>{
    const req=route.request(),url=new URL(req.url()),path=url.pathname;
    if(path==="/api/auth/me")return json(route,{id:"staff-1",name:"System Admin",email:"admin@trelpng.com.pg",role:"system_admin",account_category:"STAFF",status:"ACTIVE"});
    if(path.endsWith("/capabilities"))return json(route,{role:"system_admin",capabilities:{account_management:true,identity:true,submission:true,authority:true,publication:true,lifecycle:true}});
    if(req.method()==="PUT")return json(route,{ok:true,status:"UPDATED"});
    if(path.endsWith("/overview"))return json(route,{stats:{advertisers:1,submissions:1,pending_identity:0,ready_to_publish:1},priorities:[{id:"task-1",priority:"HIGH",task:"Submission review",subject_label:"Mary's Waigani Home",assigned_staff_name:"System Admin",due_at:"2026-08-25T00:00:00Z",path:"/admin/property-advertising/submissions/TREL-1001"}]});
    if(path.endsWith("/advertisers"))return json(route,{items:[advertiser],total:1,page:1,limit:25});
    if(path.endsWith("/advertisers/ADV-USER1"))return json(route,advertiser);
    if(path.endsWith("/submissions"))return json(route,{items:[submission],total:1,page:1,limit:25});
    if(path.endsWith("/submissions/TREL-1001"))return json(route,submission);
    if(path.endsWith("/publications"))return json(route,{items:[publication],total:1,page:1,limit:25});
    if(path.endsWith("/publications/LIST-1001"))return json(route,publication);
    if(path.endsWith("/master-properties"))return json(route,[{id:"master-1",title:"Mary's Waigani Home"}]);
    if(path.endsWith("/lifecycle"))return json(route,{items:[lifecycle],total:1,page:1,limit:25});
    if(path.endsWith("/lifecycle/LIST-1001"))return json(route,lifecycle);
    return json(route,[]);
  });
});

test("all Property Advertising menus and screens load selected record data",async({page})=>{
  const routes=[
    ["/admin/property-advertising","S01"],
    ["/admin/property-advertising/advertisers","S02"],
    ["/admin/property-advertising/advertisers/ADV-USER1","S02A"],
    ["/admin/property-advertising/advertisers/ADV-USER1/identity","S02B"],
    ["/admin/property-advertising/submissions","S03"],
    ["/admin/property-advertising/submissions/TREL-1001","S03A"],
    ["/admin/property-advertising/submissions/TREL-1001/property-location","S03A"],
    ["/admin/property-advertising/submissions/TREL-1001/price-features","S03A"],
    ["/admin/property-advertising/submissions/TREL-1001/photos-documents","S03A"],
    ["/admin/property-advertising/submissions/TREL-1001/public-content","S03A"],
    ["/admin/property-advertising/conflicts/TREL-1001","S03B"],
    ["/admin/property-advertising/authority/TREL-1001","S03C"],
    ["/admin/property-advertising/publications","S07"],
    ["/admin/property-advertising/publications/LIST-1001","S07A"],
    ["/admin/property-advertising/lifecycle","S08"],
    ["/admin/property-advertising/lifecycle/LIST-1001","S08A"],
  ];
  for(const [path,id] of routes){await page.goto(path);await expect(page.getByRole("heading",{level:1})).toContainText(id);await expect(page.getByTestId("admin-main")).not.toContainText("John Tano");}
});

test("single-destination table rows open their record",async({page})=>{
  await page.goto("/admin/property-advertising/advertisers");
  await expect(page.getByText("Mary Kila").first()).toBeVisible();
  await page.locator(".spa-table tbody tr").first().click({position:{x:20,y:20}});
  await expect(page).toHaveURL(/advertisers\/ADV-USER1$/);

  await page.goto("/admin/property-advertising/publications");
  await expect(page.getByText("LIST-1001").first()).toBeVisible();
  await page.locator(".spa-table tbody tr").first().click({position:{x:20,y:20}});
  await expect(page).toHaveURL(/publications\/LIST-1001$/);
});

test("removed exact-location workflow is absent",async({page})=>{
  await page.goto("/admin/property-advertising");
  await expect(page.getByText("Exact Location Requests",{exact:true})).toHaveCount(0);
  await page.goto("/property/property-1");
  await expect(page.getByTestId("exact-location-form")).toHaveCount(0);
});

test("filters work and decisions require a reason before a write",async({page})=>{
  await page.goto("/admin/property-advertising/advertisers");
  await page.getByLabel("Search records").fill("Mary");
  await page.getByLabel("Filter by status").selectOption("VERIFIED");
  await expect(page.getByText("Mary Kila").first()).toBeVisible();

  await page.goto("/admin/property-advertising/publications/LIST-1001");
  await page.getByRole("button",{name:"Publish",exact:true}).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("button",{name:"Confirm"})).toBeDisabled();
  await page.getByLabel("Reason *").fill("All publication requirements reviewed");
  const write=page.waitForRequest(r=>r.method()==="PUT"&&r.url().includes("/publications/LIST-1001/decision"));
  await page.getByRole("button",{name:"Confirm"}).click();
  expect((await write).postDataJSON().action).toBe("PUBLISH");
});
