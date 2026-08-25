const { test, expect } = require("@playwright/test");

const json=(route,body,status=200)=>route.fulfill({status,contentType:"application/json",body:JSON.stringify(body)});
const advertiser={id:"user-1",reference:"ADV-USER1",name:"Mary Kila",email:"mary@example.com",phone:"+675 7000 0000",relationship:"OWNER",profile_status:"VERIFIED",identity_status:"VERIFIED",account_status:"ACTIVE",property_count:1,assigned_staff:"System Admin",profile:{residential_address:"Waigani",preferred_communication:"Both"},identity_documents:[{id:"doc-1",document_type:"NID_CARD",original_filename:"mary-id.pdf",status:"VERIFIED",created_at:"2026-08-20T00:00:00Z"}],submissions:[]};
const submission={id:"sub-1",reference:"TREL-1001",user_id:"user-1",advertiser_reference:"ADV-USER1",advertiser_name:"Mary Kila",property_title:"Mary's Waigani Home",relationship:"OWNER",service:"Advertise only",submitted_at:"2026-08-20T00:00:00Z",sla:"DUE_TODAY",conflict_status:"CLEAR",authority_status:"ACCEPTED",assigned_staff:"System Admin",status:"APPROVED",listing_reference:"LIST-1001",data:{title:"Mary's Waigani Home",description:"Family home",property_class:"Residential",property_type:"House",listing_type:"Sale",currency:"PGK",price:"900000",province:"NCD",city:"Port Moresby",suburb:"Waigani",street:"Independence Drive",section:"12",lot:"8",bedrooms:"3",bathrooms:"2",parking:"2",authority_confirmed:true,features:["Fenced"],photos:[]},documents:[],audit:[]};
const publication={...submission,identity_status:"VERIFIED",readiness:"READY",blockers:[],publication_status:"DRAFT"};
const location={id:"loc-1",reference:"LOC-1001",requester_name:"Peter Tau",contact_verified:true,property_title:"Mary's Waigani Home",advertiser_name:"Mary Kila",advertiser_reference:"ADV-USER1",submission_reference:"TREL-1001",reason:"Inspection",message:"Inspection request",decision_authority:"Mary Kila",status:"PENDING",created_at:"2026-08-24T00:00:00Z",assigned_staff_name:"System Admin",audit:[]};
const lifecycle={...publication,publication_status:"PUBLISHED",availability:"AVAILABLE",lifecycle_status:"CURRENT",confirmation:{},audit:[]};

test.beforeEach(async({page})=>{
  await page.addInitScript(()=>window.localStorage.setItem("png_token","test-staff-token"));
  await page.route("**/api/**",async route=>{
    const req=route.request(),url=new URL(req.url()),path=url.pathname;
    if(path==="/api/auth/me")return json(route,{id:"staff-1",name:"System Admin",email:"admin@trel.com.pg",role:"system_admin",account_category:"STAFF",status:"ACTIVE"});
    if(req.method()==="PUT")return json(route,{ok:true,status:"UPDATED"});
    if(path.endsWith("/overview"))return json(route,{stats:{advertisers:1,submissions:1,pending_identity:0,ready_to_publish:1,location_pending:1},priorities:[{id:"task-1",priority:"HIGH",task:"Submission review",subject_label:"Mary's Waigani Home",assigned_staff_name:"System Admin",due_at:"2026-08-25T00:00:00Z",path:"/admin/property-advertising/submissions/TREL-1001"}]});
    if(path.endsWith("/advertisers"))return json(route,{items:[advertiser],total:1,page:1,limit:25});
    if(path.endsWith("/advertisers/ADV-USER1"))return json(route,advertiser);
    if(path.endsWith("/submissions"))return json(route,{items:[submission],total:1,page:1,limit:25});
    if(path.endsWith("/submissions/TREL-1001"))return json(route,submission);
    if(path.endsWith("/publications"))return json(route,{items:[publication],total:1,page:1,limit:25});
    if(path.endsWith("/publications/LIST-1001"))return json(route,publication);
    if(path.endsWith("/exact-location"))return json(route,{items:[location],total:1,page:1,limit:25});
    if(path.endsWith("/exact-location/LOC-1001"))return json(route,location);
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
    ["/admin/property-advertising/submissions/TREL-1001/property-location","S03A-property-location"],
    ["/admin/property-advertising/submissions/TREL-1001/price-features","S03A-price-features"],
    ["/admin/property-advertising/submissions/TREL-1001/photos-documents","S03A-photos-documents"],
    ["/admin/property-advertising/submissions/TREL-1001/public-content","S03A-public-content"],
    ["/admin/property-advertising/conflicts/TREL-1001","S03B"],
    ["/admin/property-advertising/authority/TREL-1001","S03C"],
    ["/admin/property-advertising/publications","S07"],
    ["/admin/property-advertising/publications/LIST-1001","S07A"],
    ["/admin/property-advertising/exact-location","S08"],
    ["/admin/property-advertising/exact-location/LOC-1001","S08A"],
    ["/admin/property-advertising/lifecycle","S09"],
    ["/admin/property-advertising/lifecycle/LIST-1001","S09A"],
  ];
  for(const [path,id] of routes){await page.goto(path);await expect(page.getByRole("heading",{level:1})).toContainText(id);await expect(page.locator("main")).not.toContainText("John Tano");}
});

test("filters work and decisions require a reason before a write",async({page})=>{
  await page.goto("/admin/property-advertising/advertisers");
  await page.getByLabel("Search records").fill("Mary");
  await page.getByLabel("Filter by status").selectOption("VERIFIED");
  await expect(page.getByText("Mary Kila").first()).toBeVisible();

  await page.goto("/admin/property-advertising/publications/LIST-1001");
  await page.getByRole("button",{name:"Publish"}).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button",{name:"Confirm"}).click();
  await expect(page.getByText("Please enter a reason")).toBeVisible();
  await page.getByLabel("Reason *").fill("All publication requirements reviewed");
  const write=page.waitForRequest(r=>r.method()==="PUT"&&r.url().includes("/publications/LIST-1001/decision"));
  await page.getByRole("button",{name:"Confirm"}).click();
  expect((await write).postDataJSON().action).toBe("PUBLISH");
});
