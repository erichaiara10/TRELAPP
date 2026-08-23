import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { Link, NavLink, Navigate, Route, Routes, useNavigate, useSearchParams } from "react-router-dom";
import {
  Bell, Building2, CalendarDays, Camera, Check, CheckCircle2, ChevronDown,
  ChevronRight, CircleHelp, Clock3, FileCheck2, FileText, FolderOpen, HelpCircle,
  Home, House, Image, Inbox, Info, LayoutDashboard, ListChecks, Mail, MapPin,
  MessageCircle, MoreVertical, Paperclip, Pencil, Phone, Plus, Search, Send,
  Settings, ShieldCheck, SlidersHorizontal, Sparkles, Upload, UserRound, Users,
  X, ZoomIn
} from "lucide-react";
import { toast } from "sonner";
import { api, formatError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import "./advertiser-workspace.css";

const SKY = "#0398FC";
const logo = "https://customer-assets.emergentagent.com/job_req-to-web-1/artifacts/uh12vkjw_TREL%20Logo.png";
const photos = [
  "https://images.pexels.com/photos/259588/pexels-photo-259588.jpeg?auto=compress&cs=tinysrgb&w=700",
  "https://images.pexels.com/photos/106399/pexels-photo-106399.jpeg?auto=compress&cs=tinysrgb&w=700",
  "https://images.pexels.com/photos/261327/pexels-photo-261327.jpeg?auto=compress&cs=tinysrgb&w=700",
  "https://images.pexels.com/photos/440731/pexels-photo-440731.jpeg?auto=compress&cs=tinysrgb&w=700",
  "https://images.pexels.com/photos/1974596/pexels-photo-1974596.jpeg?auto=compress&cs=tinysrgb&w=700",
];

const nav = [
  ["/advertiser", "Dashboard", LayoutDashboard, true],
  ["/advertiser/add-property", "Add Property", Plus],
  ["/advertiser/properties", "My Properties", Home],
  ["/advertiser/enquiries", "Enquiries", MessageCircle],
  ["/advertiser/inspections", "Inspections", CalendarDays],
  ["/advertiser/documents", "Documents", FolderOpen],
  ["/advertiser/account-settings", "Account Settings", Settings],
  ["/advertiser/help", "Help", HelpCircle],
];

const properties = [
  ["Executive Office Space — Waigani", "Waigani, NCD", "PGK 8,500 / month", photos[0], "Live", "7"],
  ["3 Bedroom House — Boroko", "Boroko, NCD", "PGK 1,650,000", photos[1], "Live", "4"],
  ["Residential Land — 1/4 Acre", "Kokopo, East New Britain", "PGK 180,000", photos[3], "Under Review", "2"],
  ["Warehouse — Gordons", "Gordons, NCD", "PGK 12,000 / month", photos[4], "Draft", ""],
];

const LISTING_STATS = { all: 18, live: 8, review: 2, draft: 5, inactive: 3 };
const ENQUIRY_STATS = { total: 32, newToday: 8, awaiting: 14, inProgress: 18, closed: 6 };
const PROPERTY_STATUSES = [
  "Live", "Live", "Under Review", "Draft", "Live", "Live", "Under Review", "Draft",
  "Live", "Live", "Draft", "Draft", "Live", "Live", "Draft", "Inactive", "Inactive", "Inactive",
];
const DRAFT_ROUTES = [
  "/advertiser/add-property",
  "/advertiser/add-property/location",
  "/advertiser/add-property/features",
  "/advertiser/add-property/photos",
  "/advertiser/add-property/review",
];
const ENQUIRY_ROWS = [
  ["ENQ-2024-1032", "Executive 3 Bedroom House", "For Rent", "John Tari", "Today", "New"],
  ["ENQ-2024-1031", "Modern 2 Bedroom Unit", "For Rent", "Michael Tau", "Today", "New"],
  ["ENQ-2024-1030", "Family Home 4 Bedroom", "For Sale", "Grace Yali", "Today", "In Progress"],
  ["ENQ-2024-1029", "Commercial Space", "For Rent", "Peter Kave", "Yesterday", "Closed"],
  ["ENQ-2024-1028", "3 Bedroom Apartment", "For Rent", "Linda Masi", "Yesterday", "New"],
];
const DOCUMENT_ROWS = [
  ["Title Deed — Executive Office Space", "Property Ownership", "Executive Office Space — Waigani", "PDF", "Verified"],
  ["Authority Letter — Boroko House", "Authority Document", "3 Bedroom House — Boroko", "PDF", "Under Review"],
  ["Valuation Report — Residential Land", "Valuation Report", "Residential Land — Kokopo", "PDF", "Verified"],
  ["NID — Kumul Agencies Director", "Identity Document", "Account Verification", "PDF", "Verified"],
  ["Lease Agreement — Warehouse", "Property Document", "Warehouse — Gordons", "PDF", "Action Required"],
];
const INSPECTION_ITEMS = [
  ["INS-2025-042", "3 Bedroom House — Boroko", "John Tau", "24 May 2025", "10:00 AM", "Pending", 1],
  ["INS-2025-041", "Executive Office Space — Waigani", "Maria Kua", "26 May 2025", "2:00 PM", "Confirmed", 0],
  ["INS-2025-040", "Family Home — Ela Beach", "Peter Naru", "27 May 2025", "11:30 AM", "Pending", 2],
  ["INS-2025-039", "Warehouse — Gordons", "Helen Ume", "21 May 2025", "9:00 AM", "Completed", 3],
];

function buildPropertyRows() {
  return PROPERTY_STATUSES.map((status, i) => {
    const property = properties[i % properties.length];
    return { property: [...property.slice(0, 4), status, property[5]], id: 1024 + i, listingType: i % 3 === 0 ? "For Rent" : "For Sale", photoNeedsUpdate: i < 5 };
  });
}

function syncSubmissionProperties(items) {
  const live = (items || []).map((item) => {
    const d=item.data||{}; const amount=String(d.price||"0").replace(/^PGK\s*/i,"");
    return [d.title||item.reference, `${d.suburb||""}, ${d.province||""}`, `PGK ${amount}${d.listing_type==="Rent"?" / month":""}`, photos[0], item.status||item.row?.[10]||"Submitted", ""];
  });
  properties.splice(0, properties.length, ...live, ...properties.filter((p)=>!live.some((x)=>x[0]===p[0])));
}

const DEFAULT_DRAFT = {
  listing_type: "Sale", service: "TREL to sell/manage", relationship: "Owner / Joint Owner",
  property_class: "Residential", property_type: "House", currency: "PGK",
  title: "Executive Office Space — Waigani", price: "8,500",
  description: "A well-positioned property with generous space, quality finishes and convenient access to services.",
  province: "NCD", city: "Port Moresby", suburb: "Waigani", local_area: "Waigani Heights Estate",
  street: "Sir John Guise Drive", address: "Lot 48, Hibiscus Avenue", landmark: "Opposite Waigani Secondary School",
  section: "Section 23", lot: "Lot 48", building_name: "Executive Office Space — Waigani",
  latitude: "-9.44380", longitude: "147.18092", bedrooms: "3", bathrooms: "2", parking: "2",
  land_size: "1,200 m²", building_area: "450 m²", furnished: "Unfurnished", condition: "Good",
  year_built: "2018", special_features: "A recently renovated premium office, with parking, street-front visibility and secure access.",
  features: ["Air Conditioning", "Security / Fencing", "Balcony", "Water Tank", "Backup Generator", "Solar", "Swimming Pool"],
  photos: 7, documents: 3, authority_confirmed: true, terms_accepted: true,
};

const DraftContext = createContext(null);
function DraftProvider({ children }) {
  const [draft, setDraft] = useState(DEFAULT_DRAFT);
  const [currentStep, setCurrentStep] = useState(1);
  const [submissions, setSubmissions] = useState([]);
  const [saving, setSaving] = useState(false);
  const update = (name, value) => setDraft((current) => ({ ...current, [name]: value }));
  const load = async () => {
    try {
      const [{ data: saved }, { data: submitted }] = await Promise.all([
        api.get("/property-advertising/advertiser/drafts/current"),
        api.get("/property-advertising/advertiser/submissions"),
      ]);
      if (saved?.data) setDraft({ ...DEFAULT_DRAFT, ...saved.data });
      setCurrentStep(Math.min(5, Math.max(1, Number(saved?.current_step) || 1)));
      const submittedItems = Array.isArray(submitted) ? submitted : [];
      setSubmissions(submittedItems);
      syncSubmissionProperties(submittedItems);
    } catch (err) { toast.error(formatError(err)); }
  };
  useEffect(() => { load(); }, []);
  const save = async (step = 1, quiet = false) => {
    setSaving(true);
    try {
      await api.put("/property-advertising/advertiser/drafts/current", { data: draft, current_step: step });
      setCurrentStep(step);
      if (!quiet) toast.success("Draft saved");
      return true;
    } catch (err) { toast.error(formatError(err)); return false; }
    finally { setSaving(false); }
  };
  const submit = async () => {
    setSaving(true);
    try {
      const { data } = await api.post("/property-advertising/advertiser/drafts/current/submit", { data: draft, current_step: 5 });
      toast.success(`Property submitted as ${data.reference}`);
      setSubmissions((current) => [data, ...current]);
      syncSubmissionProperties([data]);
      return data;
    } catch (err) { toast.error(formatError(err)); return null; }
    finally { setSaving(false); }
  };
  return <DraftContext.Provider value={{ draft, update, save, submit, submissions, saving, currentStep }}>{children}</DraftContext.Provider>;
}
const useDraft = () => useContext(DraftContext);

function AppShell({ children }) {
  const { user } = useAuth();
  const flow = useDraft();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState("");
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const displayName = user?.name || "Property Advertiser";
  const initials = displayName.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase();
  const submitSearch = (event) => {
    event.preventDefault();
    const query = searchQuery.trim();
    if (query) navigate(`/advertiser/search?q=${encodeURIComponent(query)}`);
  };
  useEffect(()=>{
    const wanted=[flow.draft.listing_type==="Rent"?"Rent":"Sell",flow.draft.service==="Advertise only"?"Advertise only":"TREL to sell/manage",flow.draft.relationship==="Authorised Real Estate Agent"?"Authorised Real Estate Agent":flow.draft.relationship==="Authorised representative"?"Authorised to act":"Owner / Joint Owner"];
    document.querySelectorAll(".adv-choice-row").forEach((row)=>row.querySelectorAll("button").forEach((button)=>button.classList.toggle("selected",wanted.some((text)=>button.textContent.trim().startsWith(text)))));
  },[flow.draft.listing_type,flow.draft.service,flow.draft.relationship]);
  const captureChoice = (event) => {
    const button=event.target.closest(".adv-choice-row button"); if(!button)return;
    const text=button.textContent.trim(); const mapping=text.startsWith("Sell")?["listing_type","Sale"]:text.startsWith("Rent")?["listing_type","Rent"]:text.startsWith("TREL to sell/manage")?["service","TREL to sell/manage"]:text.startsWith("Advertise only")?["service","Advertise only"]:text.startsWith("Owner / Joint Owner")?["relationship","Owner / Joint Owner"]:text.startsWith("Authorised Real Estate Agent")?["relationship","Authorised Real Estate Agent"]:text.startsWith("Authorised to act")?["relationship","Authorised representative"]:null;
    if(mapping){button.parentElement.querySelectorAll("button").forEach((item)=>item.classList.remove("selected"));button.classList.add("selected");flow.update(mapping[0],mapping[1]);}
  };
  const captureChecks = (event) => {
    const input=event.target; if(input.type!=="checkbox")return;
    const label=input.closest("label"); const text=label?.textContent||"";
    if(label?.closest(".adv-check-grid")){const feature=text.trim();const next=input.checked?[...new Set([...(flow.draft.features||[]),feature])]:(flow.draft.features||[]).filter((item)=>item!==feature);flow.update("features",next);label.classList.toggle("checked",input.checked);}
    if(text.includes("information is accurate"))flow.update("authority_confirmed",input.checked);
    if(text.includes("Terms of Use"))flow.update("terms_accepted",input.checked);
  };
  return <div className="adv-app">
    <aside className="adv-sidebar">
      <Link to="/" className="adv-logo"><img src={logo} alt="TRELPNG" /></Link>
      <nav>{nav.map(([to, label, Icon, end]) => <NavLink key={to} to={to} end={end}
        className={({isActive}) => `adv-nav-link ${isActive ? "active" : ""}`}>
        <Icon size={19}/><span>{label}</span>
      </NavLink>)}</nav>
      <div className="adv-help-card"><MessageCircle size={21}/><b>Need help?</b><p>Visit our Help Centre or contact our support team.</p><Link to="/advertiser/help">Go to Help Centre <ChevronRight size={14}/></Link></div>
    </aside>
    <div className="adv-body">
      <header className="adv-header">
        <div className="adv-mobile-brand"><img src={logo} alt="TRELPNG" /></div>
        <form className="adv-global-search" role="search" onSubmit={submitSearch}><Search size={18}/><input value={searchQuery} onChange={(event)=>setSearchQuery(event.target.value)} placeholder="Search properties, enquiries, or documents..." aria-label="Search advertiser workspace" /></form>
        <div className="adv-notifications-wrap">
          <button className="adv-icon-button" aria-label="Notifications" aria-expanded={notificationsOpen} onClick={()=>setNotificationsOpen((open)=>!open)}><Bell size={21}/><i>3</i></button>
          {notificationsOpen && <div className="adv-notifications" role="menu"><b>Notifications</b><Link to="/advertiser/enquiries?search=ENQ-2024-1032" onClick={()=>setNotificationsOpen(false)}>New enquiry received<small>Executive 3 Bedroom House</small></Link><Link to="/advertiser/properties?status=under-review" onClick={()=>setNotificationsOpen(false)}>Listing awaiting review<small>Residential Land — 1/4 Acre</small></Link><Link to="/advertiser/documents?status=action-required" onClick={()=>setNotificationsOpen(false)}>Document requires attention<small>Lease Agreement — Warehouse</small></Link></div>}
        </div>
        <Link className="adv-user" to="/advertiser/account-settings" aria-label="Open account settings"><span>{initials}</span><div><b>{displayName}</b><small>Property Advertiser</small></div><ChevronDown size={16}/></Link>
      </header>
      <main className="adv-main" onClick={captureChoice} onChange={captureChecks}>{children}</main>
    </div>
  </div>;
}

function PageHead({ title, sub, action }) { return <div className="adv-page-head"><div><h1>{title}</h1>{sub && <p>{sub}</p>}</div>{action}</div>; }
function Card({ children, className="" }) { return <section className={`adv-card ${className}`}>{children}</section>; }
function Status({ children, tone="blue" }) { return <span className={`adv-status ${tone}`}>{children}</span>; }
function Button({ children, secondary=false, className="", ...props }) { return <button className={`adv-button ${secondary ? "secondary" : ""} ${className}`} {...props}>{children}</button>; }
const FIELD_KEYS={"What kind of property is it?":"property_class","Property type":"property_type","Price / Rent Asking":"currency","Property Name / Listing Title *":"title","Price / Rent Amount":"price","Property Description *":"description","Province *":"province","City / Town *":"city","Suburb *":"suburb","Local Area / Stage / Estate":"local_area","Street":"street","Street Address":"address","Landmark":"landmark","Section Number *":"section","Lot Number *":"lot","Property Name / Building Name":"building_name","Latitude":"latitude","Longitude":"longitude","Bedrooms":"bedrooms","Bathrooms":"bathrooms","Parking":"parking","Land Size":"land_size","Building / Floor Area":"building_area","Furnished / Unfurnished":"furnished","Property Condition":"condition","Year Built or Age":"year_built","Add any special features":"special_features"};
function Field({ label, name, value, placeholder, className="", children, textarea=false }) { const ctx=useDraft(); const key=name||FIELD_KEYS[label]; const current=key?(ctx?.draft?.[key] ?? value):value; const control=key?{value:current,onChange:(e)=>ctx.update(key,e.target.value)}:{defaultValue:value}; return <label className={`adv-field ${className}`}><span>{label}</span>{children || (textarea ? <textarea {...control} placeholder={placeholder}/> : <input {...control} placeholder={placeholder}/>)}</label>; }
function SelectField({ label, name, value, options=[] }) { const ctx=useDraft(); const key=name||FIELD_KEYS[label]; const current=key?(ctx?.draft?.[key] ?? value):value; return <label className="adv-field"><span>{label}</span><select value={current} onChange={(e)=>key&&ctx.update(key,e.target.value)}>{[value,...options.filter(x=>x!==value)].map(x=><option key={x}>{x}</option>)}</select></label>; }

const RECENT_ACTIVITY = [
  ["New enquiry received", "Executive Office Space — Waigani", "1h ago", "/advertiser/enquiries?search=ENQ-2024-1032"],
  ["Listing submitted for review", "3 Bedroom House — Boroko", "3h ago", "/advertiser/properties?status=under-review"],
  ["Photos updated", "Residential Land — 1/4 Acre", "1d ago", "/advertiser/properties?property=1026"],
  ["Draft saved", "Warehouse — Gordons", "2d ago", "draft"],
  ["Listing approved and live", "Executive Office Space — Waigani", "3d ago", "/advertiser/properties?status=live"],
];

function Dashboard() {
  const { user } = useAuth();
  const { currentStep } = useDraft();
  const navigate = useNavigate();
  const continueDraftPath = DRAFT_ROUTES[currentStep - 1] || DRAFT_ROUTES[0];
  const activity = RECENT_ACTIVITY.map((item)=>item[3] === "draft" ? [...item.slice(0,3), continueDraftPath] : item);
  const stats = [
    [House, LISTING_STATS.live, "Active Listings", "View active", "/advertiser/properties?status=live"],
    [FileText, LISTING_STATS.draft, "Draft Listings", "View drafts", "/advertiser/properties?status=draft"],
    [Clock3, LISTING_STATS.review, "Awaiting Review", "View pending", "/advertiser/properties?status=under-review"],
    [MessageCircle, ENQUIRY_STATS.total, "Total Enquiries", "View enquiries", "/advertiser/enquiries"],
  ];
  const reminders = [
    [ShieldCheck, "Verify listing details", "2 listings have incomplete or unverified details.", "Review", "/advertiser/properties?status=under-review"],
    [Camera, "Update property photos", "5 listings could perform better with more photos.", "Update", "/advertiser/properties?needs=photos"],
    [FileText, "Pending documents", "2 listings require additional documents.", "View", "/advertiser/documents?status=action-required"],
  ];
  return <>
    <PageHead title="Dashboard" />
    <Card className="adv-welcome"><div className="adv-welcome-icon"><Building2/></div><div><h2>Welcome back, {user?.name || "Property Advertiser"}!</h2><p>Here's what's happening with your properties today.</p><small><MapPin size={14}/> Port Moresby, National Capital District</small></div><img src={photos[0]} alt="Modern property"/></Card>
    <div className="adv-dashboard-grid"><div className="adv-dashboard-main">
      <div className="adv-stat-grid">{stats.map(([Icon,n,t,l,to],i)=><Card className="adv-stat" key={t}><Icon className={`stat-${i}`}/><div><b>{n}</b><span>{t}</span><Link to={to}>{l} <ChevronRight size={14}/></Link></div></Card>)}</div>
      <div className="adv-two-col"><div><Card><h3>Quick Actions</h3>{[[Plus,"Add New Property","Create a new listing","/advertiser/add-property"],[FileText,"Continue Draft",`Resume at step ${currentStep}`,continueDraftPath],[Home,"View My Properties","Manage your listings","/advertiser/properties"]].map(([Icon,a,b,to])=><Link className="adv-action-row" to={to} key={a}><Icon/><span><b>{a}</b><small>{b}</small></span><ChevronRight/></Link>)}</Card><Card className="adv-activity"><h3>Recent Activity <Link to="/advertiser/activity">View all</Link></h3>{activity.map((x,i)=><Link className="adv-activity-row" to={x[3]} key={`${x[0]}-${i}`}><i className={`dot d${i}`}/><span><b>{x[0]}</b><small>{x[1]}</small></span><time>{x[2]}</time></Link>)}</Card></div>
        <Card><h3>My Listings Snapshot <Link to="/advertiser/properties">View all properties <ChevronRight size={15}/></Link></h3>{properties.slice(0,4).map((p,i)=><Link className="adv-listing-row" to={`/advertiser/properties?property=${1024+i}`} key={`${p[0]}-${i}`}><img src={p[3]} alt=""/><div><b>{p[0]}</b><small>{p[1]}</small><strong>{p[2]}</strong></div><div><Status tone={p[4]==="Live"?"green":p[4]==="Draft"?"gray":"orange"}>{p[4]}</Status><small>{p[5] && `Enquiries ${p[5]}`}</small></div><ChevronRight/></Link>)}<Link className="adv-card-link" to="/advertiser/properties">View all properties <ChevronRight size={15}/></Link></Card></div>
    </div><aside className="adv-dashboard-side"><Card><h3><Bell size={17}/> Reminders</h3>{reminders.map(([Icon,a,b,c,to])=><div className="adv-reminder" key={a}><Icon/><span><b>{a}</b><small>{b}</small></span><Button secondary onClick={()=>navigate(to)}>{c}</Button></div>)}</Card><Card><h3><CalendarDays size={17}/> Inspection Requests <Status tone="red">2</Status></h3>{INSPECTION_ITEMS.slice(0,2).map((item)=><div className="adv-inspection-mini" key={item[0]}><img src={properties[item[6]][3]} alt=""/><div><b>{item[1]}</b><small>Requested by {item[2]}</small><small><CalendarDays size={13}/> {item[3]}, {item[4]}</small></div><Status tone={item[5]==="Confirmed"?"green":"orange"}>{item[5]}</Status></div>)}<Link className="adv-card-link" to="/advertiser/inspections">Manage inspections <ChevronRight size={15}/></Link></Card></aside></div>
  </>;
}

const steps=["Property Details","Location & Identification","Features","Photos & Documents","Review & Submit"];
function Stepper({active}) { return <div className="adv-stepper">{steps.map((s,i)=><React.Fragment key={s}><div className={i<=active?"on":""}><i>{i<active?<Check size={12}/>:i+1}</i><span>{s}</span></div>{i<4&&<b/>}</React.Fragment>)}</div>; }
function TipPanel({type="property"}) { const tips={property:["Use a clear and specific property name","Add an accurate property description","Choose the correct property type","Your draft is saved automatically"],location:["Be as specific as possible with the exact address and landmark","Place the marker on the exact location","Exact coordinates stay private"],features:["Select only features that apply","Keep factual details accurate","You can edit all features before submitting"],photos:["Use clear, high-quality photos","Your first photo becomes the cover image","Upload supporting documents as PDF"],review:["Review your listing carefully","Check location and property details","You can return to edit any section"]}; return <Card className="adv-tip-panel"><h3><Info size={17}/> {type[0].toUpperCase()+type.slice(1)} Tips</h3>{tips[type].map(x=><p key={x}><CheckCircle2 size={15}/>{x}</p>)}</Card>; }
function FormFooter({back, next, label="Continue", step}) { const n=useNavigate(); const flow=useDraft(); const inferredStep=step||({"/advertiser/add-property/location":1,"/advertiser/add-property/features":2,"/advertiser/add-property/photos":3,"/advertiser/add-property/review":4}[next]||5); const isSubmit=label==="Submit Listing"; const proceed=async()=>{if(isSubmit){const result=await flow.submit();if(result)n("/advertiser/properties");return;}const ok=await flow.save(inferredStep,true);if(ok&&next)n(next);}; return <div className="adv-form-footer"><Button secondary onClick={()=>back&&n(back)}>‹ Back</Button><span/><Button secondary disabled={flow.saving} onClick={()=>flow.save(inferredStep)}><FileText size={15}/> Save Draft</Button><Button disabled={flow.saving} onClick={proceed}>{flow.saving?"Saving…":label} <ChevronRight size={15}/></Button></div>; }

function PropertyDetails(){return <><PageHead title="Add Property" sub="Step 1 of 5 — Property Details"/><Stepper active={0}/><div className="adv-form-layout"><Card><h3>1. Listing Purpose</h3><div className="adv-choice-row"><button className="selected"><House/> Sell</button><button><Home/> Rent</button></div><h3>2. How would you like TREL to help?</h3><div className="adv-choice-row three"><button className="selected"><Sparkles/> TREL to sell/manage my property<small>We handle marketing, negotiation and coordination for you.</small></button><button><ShieldCheck/> Advertise only — I will handle it<small>List my property and manage enquiries directly.</small></button></div><h3>3. Relationship to the property</h3><div className="adv-choice-row three"><button className="selected"><UserRound/> Owner / Joint Owner</button><button><Users/> Authorised Real Estate Agent</button><button><FileCheck2/> Authorised to act for owner</button></div><h3>4. Property Category</h3><div className="adv-form-grid three"><SelectField label="What kind of property is it?" value="Residential" options={["Commercial","Industrial","Agricultural / Rural","Vacant Land","Other"]}/><SelectField label="Property type" value="House" options={["Apartment / Unit","Townhouse","Land"]}/><SelectField label="Price / Rent Asking" value="PGK" options={["Negotiable","Contact for price"]}/></div><div className="adv-form-grid two"><Field label="Property Name / Listing Title *" value="Executive Office Space — Waigani"/><Field label="Price / Rent Amount" value="8,500"/></div><Field label="Property Description *" textarea value="A well-positioned property with generous space, quality finishes and convenient access to services."/><FormFooter next="/advertiser/add-property/location" label="Continue to Location"/></Card><div><TipPanel/><Card className="adv-summary"><h3>Selections from P01</h3><p><b>Sale or Rent</b><Status>Sell</Status></p><p><b>TREL Help</b><Status>TREL to sell/manage</Status></p><p><b>Relationship</b><Status>Owner / Joint Owner</Status></p></Card></div></div></>}

function LocationPage(){return <><PageHead title="Add Property" sub="Step 2 of 5 — Location & Identification"/><Stepper active={1}/><div className="adv-form-layout"><Card><div className="adv-split"><div><h3>1. Location Details</h3><div className="adv-form-grid three"><SelectField label="Province *" value="NCD" options={["Central","Morobe"]}/><SelectField label="City / Town *" value="Port Moresby"/><SelectField label="Suburb *" value="Waigani"/></div><div className="adv-form-grid two"><Field label="Local Area / Stage / Estate" value="Waigani Heights Estate"/><Field label="Street" value="Sir John Guise Drive"/></div><div className="adv-form-grid two"><Field label="Street Address" value="Lot 48, Hibiscus Avenue"/><Field label="Landmark" value="Opposite Waigani Secondary School"/></div><div className="adv-form-grid two"><Field label="Section Number *" value="Section 23"/><Field label="Lot Number *" value="Lot 48"/></div><Field label="Property Name / Building Name" value="Executive Office Space — Waigani" textarea/></div><div><h3>2. Pin the Property Location</h3><div className="adv-map"><MapPin/><span>Waigani</span><button><SlidersHorizontal size={15}/> Map controls</button></div><div className="adv-form-grid two"><Field label="Latitude" value="-9.44380"/><Field label="Longitude" value="147.18092"/></div><div className="adv-note"><ShieldCheck/> Exact location is encrypted and visible only to authorised TREL staff or permitted viewers.</div></div></div><FormFooter back="/advertiser/add-property" next="/advertiser/add-property/features" label="Continue to Features"/></Card><div><TipPanel type="location"/><Card className="adv-summary"><h3>Listing Identity Summary</h3><p><b>Property</b>Executive Office Space</p><p><b>Location</b>Waigani, NCD</p><p><b>Section / Lot</b>23 / 48</p><p><b>Duplicate check</b><Status tone="green">No match found</Status></p></Card></div></div></>}

function FeaturesPage(){const features=["Air Conditioning","Security / Fencing","Balcony","Water Tank","Backup Generator","Solar","Swimming Pool","Office Fitout","Storage","Disabled Access","Waterfront / View","Close to Shops / Public Transport"];return <><PageHead title="Add Property" sub="Step 3 of 5 — Features"/><Stepper active={2}/><div className="adv-form-layout"><Card><h3>Key Facts</h3><div className="adv-form-grid six"><Field label="Asking Price" value="PGK 850,000"/><Field label="Bedrooms" value="3"/><Field label="Bathrooms" value="2"/><Field label="Parking" value="2"/><Field label="Land Size" value="1,200 m²"/><Field label="Building / Floor Area" value="450 m²"/></div><h3>Living & Condition</h3><div className="adv-form-grid three"><SelectField label="Furnished / Unfurnished" value="Unfurnished"/><SelectField label="Property Condition" value="Good"/><Field label="Year Built or Age" value="2018"/></div><h3>Amenities & Features</h3><div className="adv-check-grid">{features.map((f,i)=><label key={f} className={i<7?"checked":""}><input type="checkbox" defaultChecked={i<7}/><Check size={13}/>{f}</label>)}</div><h3>Other / Special Features</h3><Field label="Add any special features" textarea value="A recently renovated premium office, with parking, street-front visibility and secure access."/><div className="adv-note"><Info/> Optional details improve price comparison accuracy and search quality.</div><FormFooter back="/advertiser/add-property/location" next="/advertiser/add-property/photos" label="Continue to Photos & Documents"/></Card><div><TipPanel type="features"/><Card className="adv-summary"><h3>Selected property summary</h3>{[["Property Type","Executive Office Space"],["Purpose","Sale"],["Bedrooms","3"],["Bathrooms","2"],["Parking","2 spaces"],["Available now","Yes"]].map(x=><p key={x[0]}><b>{x[0]}</b>{x[1]}</p>)}</Card></div></div></>}

function PhotosPage(){return <><PageHead title="Add Property" sub="Step 4 of 5 — Photos & Documents"/><Stepper active={3}/><div className="adv-form-layout"><Card><h3>1. Property Photos <Status tone="gray">1 of 7 photos</Status></h3><div className="adv-upload-zone"><Upload/><b>Drag and drop photos here, or click to browse</b><small>JPG or PNG • Max 5 MB each</small></div><div className="adv-photo-grid">{[...photos,...photos.slice(0,2)].map((p,i)=><div key={i}><img src={p} alt={`Property ${i+1}`}/>{i===0&&<Status>Cover photo</Status>}<span><Pencil size={13}/><X size={13}/></span></div>)}</div><h3>2. Documents</h3><div className="adv-note"><ShieldCheck/> Documents help us verify and review your listing faster. Clear and valid documents may speed up approval.</div><div className="adv-document-grid">{["Title / Ownership Document","Authority Letter / Approval","National ID / Passport","Valuation Report","Other Supporting Documents"].map((x,i)=><div key={x}><FileText/><b>{x}</b><small>{i<3?"Required when applicable":"Optional"}</small><Button secondary><Upload size={14}/> Upload file</Button></div>)}</div><p className="adv-privacy"><ShieldCheck size={14}/> Documents are private, encrypted and visible only to authorised TREL staff.</p><FormFooter back="/advertiser/add-property/features" next="/advertiser/add-property/review" label="Continue to Review"/></Card><div><TipPanel type="photos"/><Card><h3>Current listing completeness</h3><div className="adv-progress-ring">78%</div>{["Property Details","Location & Identification","Features","Photos & Documents","Review & Submit"].map((x,i)=><p className="adv-complete" key={x}>{i<3?<CheckCircle2/>:<Clock3/>}{x}</p>)}</Card></div></div></>}

function ReviewPage(){return <><PageHead title="Add Property" sub="Step 5 of 5 — Review & Submit"/><Stepper active={4}/><div className="adv-form-layout"><Card><div className="adv-review-hero"><img src={photos[0]} alt="Listing"/><div><h2>Executive Office Space — Waigani</h2><b>PGK 8,500 / month</b><p><MapPin size={14}/> Waigani, NCD</p></div><Status tone="green">Ready to submit</Status></div><div className="adv-review-grid">{[["1. Listing Purpose & TREL Help",["Purpose: Rent","Service: TREL to sell/manage","Relationship: Owner / Joint Owner"]],["2. Property Details",["Executive Office Space","Commercial / Office Space","PGK 8,500 / month"]],["3. Location & Identification",["Waigani, NCD","Section 23, Lot 48","Map location saved"]],["4. Features",["3 Rooms • 2 Bathrooms","2 Parking spaces","Air conditioning • Security"]],["5. Photos & Documents",["7 property photos","3 supporting documents"]],["6. TREL Help & Contact",["TREL manages the listing","Email and WhatsApp notifications"]]].map(([h,items])=><Card key={h}><h3>{h}<button><Pencil/> Edit</button></h3>{items.map(x=><p key={x}>{x}</p>)}</Card>)}</div><div className="adv-declaration"><label><input type="checkbox" defaultChecked/> I confirm the information is accurate and I am authorised to submit this property.</label><label><input type="checkbox" defaultChecked/> I accept TRELPNG's Terms of Use and Privacy Policy.</label></div><FormFooter back="/advertiser/add-property/photos" label="Submit Listing"/></Card><div><TipPanel type="review"/><Card className="adv-ready"><CheckCircle2/><h3>Ready to submit</h3><p>Your listing is complete and ready for TREL review.</p></Card></div></div></>}


function PropertiesPage(){
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const status = params.get("status") || "all";
  const selectedProperty = params.get("property");
  const needs = params.get("needs");
  const query = params.get("search") || "";
  const rows = buildPropertyRows();
  const statusName = { live:"Live", draft:"Draft", "under-review":"Under Review", inactive:"Inactive" }[status];
  const filtered = rows.filter((row)=>{
    const p=row.property;
    if (selectedProperty && String(row.id)!==selectedProperty) return false;
    if (statusName && p[4]!==statusName) return false;
    if (status==="sale" && row.listingType!=="For Sale") return false;
    if (status==="rent" && row.listingType!=="For Rent") return false;
    if (needs==="photos" && !row.photoNeedsUpdate) return false;
    if (query && !`${p[0]} ${p[1]} ${row.id}`.toLowerCase().includes(query.toLowerCase())) return false;
    return true;
  });
  const setStatus = (next) => { const updated=new URLSearchParams(params); if(next==="all")updated.delete("status");else updated.set("status",next);updated.delete("property");updated.delete("needs");setParams(updated); };
  const statCards = [
    [LISTING_STATS.all,"All Listings","blue","all"], [LISTING_STATS.live,"Live","green","live"],
    [LISTING_STATS.review,"Under Review","orange","under-review"], [LISTING_STATS.draft,"Drafts","purple","draft"],
    [LISTING_STATS.inactive,"Inactive","gray","inactive"],
  ];
  return <><PageHead title="My Properties" sub="Manage your listings and track their status" action={<Button onClick={()=>navigate("/advertiser/add-property")}><Plus/> Add New Property</Button>}/><div className="adv-stat-grid five">{statCards.map(x=><Card className="adv-mini-stat" key={x[1]}><b className={x[2]}>{x[0]}</b><span>{x[1]}</span><Link to={x[3]==="all"?"/advertiser/properties":`/advertiser/properties?status=${x[3]}`}>View {x[1].toLowerCase()} <ChevronRight/></Link></Card>)}</div><Card><div className="adv-table-tools"><label><Search/><input value={query} onChange={(event)=>{const updated=new URLSearchParams(params);if(event.target.value)updated.set("search",event.target.value);else updated.delete("search");updated.delete("property");setParams(updated,{replace:true});}} placeholder="Search by property name, location..."/></label>{["All Locations","Property Categories","All Listing Types"].map(x=><select key={x}><option>{x}</option></select>)}<Button secondary><SlidersHorizontal/> More filters</Button></div><div className="adv-tabs">{[["all","All"],["sale","For Sale"],["rent","For Rent"],["live","Live"],["under-review","Under Review"],["draft","Draft"],["inactive","Inactive"]].map(([key,label])=><button className={status===key?"active":""} onClick={()=>setStatus(key)} key={key}>{label}</button>)}</div><div className="adv-table-wrap"><table><thead><tr><th>No.</th><th>Description</th><th>Rent/Sell</th><th>Location</th><th>Price</th><th>First Registered</th><th>Last Updated</th><th>Status</th><th>Action</th></tr></thead><tbody>{filtered.slice(0,10).map((row,i)=>{const p=row.property;return <tr key={row.id} className={selectedProperty===String(row.id)?"selected":""}><td>{i+1}</td><td><div className="adv-property-cell"><img src={p[3]} alt=""/><div><b>{p[0]}</b><small>Property #{row.id}</small></div></div></td><td><Status>{row.listingType}</Status></td><td>{p[1]}</td><td><b>{p[2]}</b></td><td>{`${18+(i%10)} May 2025`}</td><td>{i%2?"21 May 2025":"1 day ago"}</td><td><Status tone={p[4]==="Live"?"green":p[4]==="Draft"||p[4]==="Inactive"?"gray":"orange"}>{p[4]}</Status></td><td><button aria-label={`Open property ${row.id}`}><MoreVertical/></button></td></tr>})}</tbody></table></div><div className="adv-pagination"><span>{filtered.length ? `Showing 1 to ${Math.min(10,filtered.length)} of ${filtered.length} listings` : "No matching listings"}</span>{filtered.length>10&&<><button>‹</button><button className="active">1</button><button>2</button><button>›</button></>}</div></Card></>}

function EnquiriesPage(){
  const [params,setParams]=useSearchParams();
  const query=params.get("search")||"";
  const rows=ENQUIRY_ROWS.filter((row)=>!query||row.join(" ").toLowerCase().includes(query.toLowerCase()));
  const selected=rows[0]||ENQUIRY_ROWS[0];
  return <><PageHead title="Enquiries" sub="Manage property enquiries from buyers and tenants."/><div className="adv-enquiry-layout"><div><div className="adv-stat-grid three">{[[ENQUIRY_STATS.total,"Total Enquiries","Across all properties"],[ENQUIRY_STATS.newToday,"New Today","Since midnight"],[ENQUIRY_STATS.awaiting,"Awaiting Response","Older than 24 hours"]].map(x=><Card className="adv-stat-number" key={x[1]}><b>{x[0]}</b><span>{x[1]}</span><small>{x[2]}</small></Card>)}</div><Card><div className="adv-tabs"><button className="active">All</button><button>New {ENQUIRY_STATS.newToday}</button><button>In Progress {ENQUIRY_STATS.inProgress}</button><button>Closed {ENQUIRY_STATS.closed}</button></div><div className="adv-table-tools"><label><Search/><input value={query} onChange={(event)=>{const updated=new URLSearchParams(params);if(event.target.value)updated.set("search",event.target.value);else updated.delete("search");setParams(updated,{replace:true});}} placeholder="Search by property, enquirer or ID..."/></label><Button secondary><SlidersHorizontal/> Filters</Button><select><option>Sort by: Newest</option></select></div><div className="adv-table-wrap"><table><thead><tr><th>Enquiry ID</th><th>Property</th><th>Listing Type</th><th>Enquirer</th><th>Contact</th><th>Date</th><th>Status</th><th>Action</th></tr></thead><tbody>{rows.map((r,i)=><tr key={r[0]} className={i===0?"selected":""}><td><b>{r[0]}</b></td><td><b>{r[1]}</b><small>Gordons, Port Moresby</small></td><td><Status>{r[2]}</Status></td><td>{r[3]}</td><td><Phone size={14}/> <Mail size={14}/></td><td>{r[4]}</td><td><Status tone={r[5]==="Closed"?"gray":r[5]==="New"?"blue":"orange"}>{r[5]}</Status></td><td><MoreVertical/></td></tr>)}</tbody></table></div>{!rows.length&&<p className="adv-empty">No matching enquiries.</p>}</Card></div><Card className="adv-detail-panel"><div className="adv-panel-title"><span>Enquiry Details</span><X/></div><small>{selected[0]} <Status>{selected[5]}</Status></small><div className="adv-contact"><span>SK</span><div><h3>{selected[3]}</h3><small>Enquirer</small></div></div><h4>Contact Information</h4><p><Phone/> +675 7123 4567</p><p><Mail/> sarah.kila@gmail.com</p><h4>Property Enquired About</h4><div className="adv-side-property"><img src={photos[0]} alt=""/><div><b>{selected[1]}</b><small>Gordons, Port Moresby</small><Status>{selected[2]}</Status><strong>PGK 2,800 / week</strong></div></div><h4>Message</h4><blockquote>Hi, I'm interested in this property. Please could you provide more details on availability and inspection times?</blockquote><small>Received: Today at 9:45 AM</small><h4>Preferred Contact Method</h4><p><MessageCircle/> WhatsApp</p><Button><Send/> Reply</Button><Button secondary><Phone/> Record Call</Button><Button secondary>Mark Closed</Button></Card></div></>}

function InspectionsPage(){return <><PageHead title="Inspections" sub="Manage inspection requests and appointments." action={<Button><Plus/> Schedule Inspection</Button>}/><div className="adv-stat-grid four">{[["6","Upcoming","blue"],["2","Pending Confirmation","orange"],["4","Confirmed","green"],["18","Completed","purple"]].map(x=><Card className="adv-stat-number" key={x[1]}><b className={x[2]}>{x[0]}</b><span>{x[1]}</span></Card>)}</div><Card><div className="adv-calendar-strip">{["MON 19","TUE 20","WED 21","THU 22","FRI 23","SAT 24","SUN 25"].map((x,i)=><button className={i===5?"active":""} key={x}><span>{x.split(" ")[0]}</span><b>{x.split(" ")[1]}</b>{[2,5].includes(i)&&<i/>}</button>)}</div><div className="adv-table-tools"><label><Search/><input placeholder="Search inspections..."/></label><select><option>All Properties</option></select><select><option>All Statuses</option></select></div><div className="adv-inspection-list">{INSPECTION_ITEMS.map((x)=><div key={x[0]}><time><b>{x[4]}</b><small>{x[3]}</small></time><img src={properties[x[6]][3]} alt=""/><div><b>{x[1]}</b><small><UserRound/> Requested by {x[2]}</small><small><MapPin/> {properties[x[6]][1]}</small></div><Status tone={x[5]==="Confirmed"?"green":x[5]==="Completed"?"gray":"orange"}>{x[5]}</Status><div><Button secondary>View Details</Button><MoreVertical/></div></div>)}</div></Card></>}

function DocumentsPage(){const [params,setParams]=useSearchParams();const status=params.get("status");const query=params.get("search")||"";const docs=DOCUMENT_ROWS.filter((d)=>(!status||status!=="action-required"||d[4]==="Action Required")&&(!query||d.join(" ").toLowerCase().includes(query.toLowerCase())));return <><PageHead title="Documents" sub="Upload and manage property and account documents." action={<Button><Upload/> Upload Document</Button>}/><div className="adv-stat-grid four">{[["24","All Documents"],["18","Verified"],["3","Under Review"],["3","Action Required"]].map((x,i)=><Card className="adv-stat-number" key={x[1]}><b className={["blue","green","orange","red"][i]}>{x[0]}</b><span>{x[1]}</span></Card>)}</div><Card><div className="adv-tabs"><button className={!status?"active":""} onClick={()=>setParams({})}>All Documents</button><button>Property Documents</button><button>Identity Documents</button><button className={status==="action-required"?"active":""} onClick={()=>setParams({status:"action-required"})}>Action Required</button></div><div className="adv-table-tools"><label><Search/><input value={query} onChange={(event)=>{const updated=new URLSearchParams(params);if(event.target.value)updated.set("search",event.target.value);else updated.delete("search");setParams(updated,{replace:true});}} placeholder="Search documents..."/></label><select><option>All Properties</option></select><select><option>All Document Types</option></select><Button secondary><SlidersHorizontal/> Filters</Button></div><div className="adv-table-wrap"><table><thead><tr><th>Document</th><th>Type</th><th>Related To</th><th>Uploaded</th><th>Status</th><th>Action</th></tr></thead><tbody>{docs.map((d,i)=><tr key={d[0]}><td><div className="adv-doc-cell"><FileText/><span><b>{d[0]}</b><small>{d[3]} • {(1.2+i*.4).toFixed(1)} MB</small></span></div></td><td>{d[1]}</td><td>{d[2]}</td><td>{18+i} May 2025<small>by Kumul Agencies</small></td><td><Status tone={d[4]==="Verified"?"green":d[4]==="Under Review"?"orange":"red"}>{d[4]}</Status></td><td><button><MoreVertical/></button></td></tr>)}</tbody></table></div>{!docs.length&&<p className="adv-empty">No matching documents.</p>}</Card><div className="adv-note"><ShieldCheck/> Your documents are stored securely and only accessible to you and authorised TREL staff.</div></>}

function AccountSettings(){return <><PageHead title="Account Settings" sub="Manage your profile, verification and preferences."/><div className="adv-settings-layout"><aside><button className="active"><UserRound/> Profile Information</button><button><ShieldCheck/> Identity Verification</button><button><Building2/> Business Details</button><button><Bell/> Notifications</button><button><Settings/> Security</button></aside><div><Card><h2>Profile Information</h2><p>Keep your personal and contact information up to date.</p><div className="adv-profile-row"><span>KA</span><div><b>Kumul Agencies</b><small>Property Advertiser</small></div><Button secondary>Change photo</Button></div><div className="adv-form-grid two"><Field label="Full Name *" value="Kumul Agencies"/><Field label="Mobile Number *" value="+675 7123 4567"/><Field label="Email Address *" value="info@kumulagencies.com.pg"/><SelectField label="Preferred Communication" value="WhatsApp" options={["Email","Both"]}/></div><Field label="Residential Address *" value="Section 23, Lot 48, Waigani, Port Moresby"/><Button>Save Changes</Button></Card><Card><div className="adv-section-head"><div><h2>Identity Verification</h2><p>One valid government-issued ID is required for identity verification.</p></div><Status tone="green"><ShieldCheck/> Verified</Status></div><div className="adv-id-card"><FileCheck2/><div><b>PNG National Identification Card</b><small>ID ending in •••• 821</small><small>Verified on 15 May 2025</small></div><Button secondary>View Document</Button></div><p className="adv-muted">Accepted IDs include a passport, driver licence or National Identification (NID) Card. Only one valid ID is required.</p></Card><Card><h2>Business Details</h2><p>Required for authorised agents and business advertisers.</p><div className="adv-form-grid two"><Field label="Business / Agency Name" value="Kumul Agencies Limited"/><Field label="IPA Registration Number" value="1-123456"/><Field label="Position / Role" value="Managing Director"/><Field label="Business Phone" value="+675 325 4567"/></div><Button>Save Business Details</Button></Card></div></div></>}

function ActivityPage(){const {currentStep}=useDraft();const continueDraftPath=DRAFT_ROUTES[currentStep-1]||DRAFT_ROUTES[0];return <><PageHead title="Recent Activity" sub="Open the enquiry, listing or draft connected to each update."/><Card className="adv-activity adv-activity-page">{RECENT_ACTIVITY.map((item,i)=>{const to=item[3]==="draft"?continueDraftPath:item[3];return <Link className="adv-activity-row" to={to} key={`${item[0]}-${i}`}><i className={`dot d${i}`}/><span><b>{item[0]}</b><small>{item[1]}</small></span><time>{item[2]}</time><ChevronRight size={15}/></Link>})}</Card></>}

function SearchResultsPage(){const [params]=useSearchParams();const query=(params.get("q")||"").trim();const needle=query.toLowerCase();const propertyResults=buildPropertyRows().filter((row)=>`${row.property[0]} ${row.property[1]} ${row.id}`.toLowerCase().includes(needle)).slice(0,5);const enquiryResults=ENQUIRY_ROWS.filter((row)=>row.join(" ").toLowerCase().includes(needle));const documentResults=DOCUMENT_ROWS.filter((row)=>row.join(" ").toLowerCase().includes(needle));const total=propertyResults.length+enquiryResults.length+documentResults.length;return <><PageHead title="Search Results" sub={query?`${total} result${total===1?"":"s"} for “${query}”`:"Enter a search from the dashboard header."}/><div className="adv-search-results">{propertyResults.length>0&&<Card><h3>Properties</h3>{propertyResults.map((row)=><Link to={`/advertiser/properties?property=${row.id}`} key={row.id}><House/><span><b>{row.property[0]}</b><small>{row.property[1]} • Property #{row.id}</small></span><ChevronRight/></Link>)}</Card>}{enquiryResults.length>0&&<Card><h3>Enquiries</h3>{enquiryResults.map((row)=><Link to={`/advertiser/enquiries?search=${encodeURIComponent(row[0])}`} key={row[0]}><MessageCircle/><span><b>{row[0]}</b><small>{row[1]} • {row[3]}</small></span><ChevronRight/></Link>)}</Card>}{documentResults.length>0&&<Card><h3>Documents</h3>{documentResults.map((row)=><Link to={`/advertiser/documents?search=${encodeURIComponent(row[0])}`} key={row[0]}><FileText/><span><b>{row[0]}</b><small>{row[1]} • {row[4]}</small></span><ChevronRight/></Link>)}</Card>}{query&&!total&&<Card className="adv-empty">No properties, enquiries or documents match “{query}”.</Card>}</div></>}

function HelpPage(){return <><PageHead title="Help Centre" sub="Find answers, guides and support for your property advertising workspace."/><Card className="adv-help-hero"><CircleHelp/><h2>How can we help you?</h2><label><Search/><input placeholder="Search help articles and guides..."/></label></Card><div className="adv-help-grid">{[[Plus,"Adding a Property",["How to create a new listing","Required property information","Saving and continuing a draft"]],[Home,"Managing Listings",["Understanding listing statuses","Editing a published listing","Making a property unavailable"]],[MessageCircle,"Enquiries & Inspections",["Responding to enquiries","Managing inspection requests","Recording calls and messages"]],[FolderOpen,"Documents & Verification",["Accepted identity documents","Uploading property documents","Why verification is required"]],[Settings,"Account & Security",["Updating account details","Changing contact preferences","Password and account security"]],[Sparkles,"TREL Services",["TREL managed sale or rental","Advertising-only listings","How TREL review works"]]].map(([Icon,h,links])=><Card key={h}><Icon/><h3>{h}</h3>{links.map(x=><button key={x}>{x}<ChevronRight/></button>)}<Link to="#">View all articles <ChevronRight/></Link></Card>)}</div><Card className="adv-support-card"><div><MessageCircle/><span><h3>Still need help?</h3><p>Our support team is available Monday to Friday, 8:00 AM–5:00 PM.</p></span></div><Button><MessageCircle/> Chat with Support</Button><Button secondary><Mail/> Email Support</Button><Button secondary><Phone/> Call +675 325 7900</Button></Card><Card><h3>Frequently Asked Questions</h3>{["How long does TREL review take?","Can I edit my listing after it is published?","Who can see my exact property location?","How many property photos can I upload?","What documents do I need to provide?"].map(x=><details key={x}><summary>{x}<ChevronDown/></summary><p>Open the relevant workspace section to review or update this information. Contact TREL support if you need further assistance.</p></details>)}</Card></>}

export default function AdvertiserWorkspace(){return <DraftProvider><AppShell><Routes><Route index element={<Dashboard/>}/><Route path="add-property" element={<PropertyDetails/>}/><Route path="add-property/location" element={<LocationPage/>}/><Route path="add-property/features" element={<FeaturesPage/>}/><Route path="add-property/photos" element={<PhotosPage/>}/><Route path="add-property/review" element={<ReviewPage/>}/><Route path="properties" element={<PropertiesPage/>}/><Route path="enquiries" element={<EnquiriesPage/>}/><Route path="inspections" element={<InspectionsPage/>}/><Route path="documents" element={<DocumentsPage/>}/><Route path="account-settings" element={<AccountSettings/>}/><Route path="activity" element={<ActivityPage/>}/><Route path="search" element={<SearchResultsPage/>}/><Route path="help" element={<HelpPage/>}/><Route path="*" element={<Navigate to="/advertiser" replace/>}/></Routes></AppShell></DraftProvider>}
