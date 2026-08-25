import React, { useMemo, useState } from "react";
import { Link, NavLink, useLocation, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  AlertTriangle, ArrowLeft, CheckCircle2, Clock3, Eye, FileCheck2,
  FileText, Filter, MapPin, MessageSquare, MoreHorizontal, Search,
  Send, ShieldCheck, UserCheck, XCircle,
} from "lucide-react";
import "./staff-property-advertising.css";

const B = "/admin/property-advertising";

const advertisers = [
  ["ADV-00931", "John Tano", "Owner", "Verified", "Pending review", "3", "Today, 10:42am", "Active", "Eric Haiara"],
  ["ADV-00924", "Mary Kila", "Joint owner", "Verified", "Verified", "1", "18 Aug", "Active", "John Tom"],
  ["ADV-00872", "PNG Homes Ltd", "Authorised agent", "Verified", "Verified", "8", "17 Aug", "Active", "Rebecca Wali"],
  ["ADV-00841", "Peter Wali", "Authorised representative", "Email only", "Not started", "1", "02 Jul", "Incomplete", "Unassigned"],
];

const submissions = [
  ["TREL-10428", "John's Family Home - Boroko", "John Tano", "Owner", "Advertise only", "18 Aug", "21 Aug", "Due today", "Clear", "Eric Haiara", "Under Review"],
  ["TREL-10461", "Family House - Waigani", "Mary Kila", "Owner", "TREL complete sale", "17 Aug", "20 Aug", "Due today", "Possible", "John Tom", "Conflict Review"],
  ["TREL-10422", "Two-Bedroom Unit - Boroko", "Lina Kora", "Landlord", "Find tenant only", "16 Aug", "19 Aug", "Overdue", "Clear", "Eric Haiara", "Information Required"],
  ["TREL-10376", "Vacant Land - 9 Mile", "Peter Wali", "Representative", "Advertise only", "15 Aug", "18 Aug", "Overdue", "Clear", "Rebecca Wali", "Ready"],
];

const publications = [
  ["LIST-10428", "John's Family Home - Boroko", "John Tano", "Sale", "Advertise only", "Approved", "Accepted", "Under review", "Required", "Ready", "Eric Haiara", "Draft"],
  ["LIST-10461", "Family House - Waigani", "Mary Kila", "Sale", "Complete sale", "Approved", "Accepted", "Verified", "None", "Blocked - conflict", "John Tom", "Changes Required"],
  ["LIST-10422", "Two-Bedroom Unit - Boroko", "Lina Kora", "Rent", "Find tenant only", "Approved", "Accepted", "Not submitted", "Shown", "Ready", "Eric Haiara", "Published"],
  ["LIST-10376", "Vacant Land - 9 Mile", "Peter Wali", "Sale", "Advertise only", "Approved", "Accepted", "Unable to verify", "Required", "Ready with disclosure", "John Tom", "Suspended"],
];

const locationRequests = [
  ["LOC-0081", "Sarah Kila", "John's Family Home - Boroko", "John Tano", "Buyer inspection", "18 Aug 10:21", "John Tano", "Pending", "Not shared", "Awaiting Advertiser"],
  ["LOC-0078", "PNG Bank Ltd", "Family House - Waigani", "Mary Kila", "Valuation", "17 Aug 14:10", "Mary Kila", "Share to 20 Aug", "Active", "Active"],
  ["LOC-0069", "Peter Wali", "Two-Bedroom Unit - Boroko", "Lina Kora", "Rental inspection", "15 Aug 11:32", "Lina Kora", "Inspection instead", "Not shared", "Closed"],
  ["LOC-0061", "Kila Moa", "Warehouse - Gordons", "TREL Staff", "Due diligence", "12 Aug 09:05", "Eric Haiara", "Share to 16 Aug", "Expired", "Expired"],
];

const lifecycle = [
  ["LIST-10428", "John's Family Home - Boroko", "John Tano", "Sale", "Advertise only", "Published", "Available", "14 Feb", "14 May", "17 Aug", "18 Aug", "0 months", "Confirmation Due", "Eric Haiara"],
  ["LIST-10361", "Family Home - Waigani", "Mary Kila", "Sale", "Complete sale", "Published", "Under Offer", "12 Jan", "12 May", "16 Aug", "12 Aug", "3 months", "Awaiting Advertiser", "John Tom"],
  ["LIST-10142", "Boroko Unit", "Lina Kora", "Rent", "Find tenant only", "Published", "Available", "18 Feb", "18 Feb", "18 Feb", "18 Aug", "6 months", "Six-Month Notice", "Eric Haiara"],
  ["LIST-09912", "Warehouse - Gordons", "PNG Homes Ltd", "Rent", "Advertise only", "Suspended", "Unknown", "10 Aug 2025", "10 Aug 2025", "10 Aug 2025", "10 Aug 2026", "12 months", "Removal Due", "Rebecca Wali"],
];

function Badge({ children }) {
  const text = String(children || "");
  const tone = /verified|approved|ready|published|active|available|clear|current|accepted/i.test(text)
    ? "ok" : /overdue|removal|rejected|declined|blocked|suspended/i.test(text)
      ? "bad" : /pending|review|due|awaiting|required|possible|information|notice/i.test(text) ? "warn" : "neutral";
  return <span className={`spa-badge ${tone}`}>{children}</span>;
}

function Page({ id, title, subtitle, children, actions }) {
  return <div className="spa-page" data-testid={`screen-${id.toLowerCase()}`}>
    <div className="spa-page-head">
      <div><div className="spa-eyebrow">Staff Workspace / Property Advertising</div><h1>{id} - {title}</h1><p>{subtitle}</p></div>
      <div className="spa-head-actions">{actions}</div>
    </div>
    {children}
  </div>;
}

function Stats({ items }) {
  return <div className="spa-stats">{items.map(([value, label, tone]) => <div className={`spa-stat ${tone || ""}`} key={label}><strong>{value}</strong><span>{label}</span></div>)}</div>;
}

function Toolbar({ placeholder = "Search records", children, value, onChange }) {
  return <div className="spa-toolbar"><label><Search size={16}/><input value={value} onChange={e=>onChange(e.target.value)} placeholder={placeholder}/></label><button className="spa-button"><Filter size={15}/> Filters</button>{children}</div>;
}

function Table({ headers, rows, renderAction }) {
  return <div className="spa-table-wrap"><table className="spa-table"><thead><tr>{headers.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{rows.map((row,ri)=><tr key={row[0] || ri}>{row.map((v,ci)=><td key={ci}>{ci > 2 && /verified|pending|active|overdue|ready|review|published|suspended|due|clear|possible|closed|expired|available|offer|notice|removal|unknown|required|shared|draft/i.test(String(v)) ? <Badge>{v}</Badge> : v}</td>)}{renderAction && <td>{renderAction(row)}</td>}</tr>)}</tbody></table></div>;
}

function Card({ title, children, className="" }) { return <section className={`spa-card ${className}`}><h2>{title}</h2>{children}</section>; }
function KV({ items }) { return <dl className="spa-kv">{items.map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>; }
function Action({ children, tone="", onClick, icon:Icon }) { return <button className={`spa-button ${tone}`} onClick={onClick}>{Icon&&<Icon size={15}/>} {children}</button>; }
function Notice({ tone="info", children }) { return <div className={`spa-notice ${tone}`}>{children}</div>; }

function Overview() {
  const nav=useNavigate();
  return <Page id="S01" title="Property Advertising Overview" subtitle="Operational control centre for advertiser and listing activity."
    actions={<Action tone="primary" onClick={()=>nav(`${B}/advertisers`)} icon={UserCheck}>Open Advertisers</Action>}>
    <Stats items={[["24","Awaiting review"],["7","SLA due today","warn"],["11","Documents pending"],["8","New enquiries"],["5","Inspections"]]}/>
    <Card title="Priority work queue"><Table headers={["Priority","Task","Property / Advertiser","Assigned","Due","Action"]} rows={[
      ["High","Submission review","TREL-10428 - John's Family Home","Eric Haiara","Today"],
      ["High","Identity document","John Tano - ADV-00931","Eric Haiara","Today"],
      ["Normal","Duplicate match","TREL-10461 - Waigani","John Tom","Tomorrow"],
      ["Normal","Exact location request","LOC-0081 - Boroko","Eric Haiara","20 Aug"],
    ]} renderAction={(r)=><Link className="spa-link" to={r[1]==="Identity document"?`${B}/advertisers/ADV-00931/identity`:r[1]==="Duplicate match"?`${B}/conflicts/TREL-10461`:r[1].startsWith("Exact")?`${B}/exact-location/LOC-0081`:`${B}/submissions/TREL-10428`}>Open</Link>}/></Card>
  </Page>;
}

function Advertisers() {
  const [q,setQ]=useState(""); const rows=advertisers.filter(r=>r.join(" ").toLowerCase().includes(q.toLowerCase()));
  return <Page id="S02" title="Advertisers" subtitle="Search, verify and manage Property Advertiser Accounts.">
    <Stats items={[["142","Registered"],["118","Contact verified"],["96","Identity verified"],["17","Agents / firms"],["6","Restricted","warn"]]}/>
    <Toolbar value={q} onChange={setQ} placeholder="Search advertiser, capacity or reference"/>
    <Card title="Advertiser accounts"><Table headers={["Reference","Advertiser","Capacity","Contact","Identity","Properties","Last active","Account","Assigned","Action"]} rows={rows} renderAction={r=><Link className="spa-link" to={`${B}/advertisers/${r[0]}`}>View profile</Link>}/></Card>
  </Page>;
}

function AdvertiserProfile() {
  const { advertiserId="ADV-00931" }=useParams();
  return <Page id="S02A" title="Advertiser Profile" subtitle={`${advertiserId} - John Tano`} actions={<Link className="spa-button primary" to={`${B}/advertisers/${advertiserId}/identity`}><ShieldCheck size={15}/> Review Identity</Link>}>
    <div className="spa-record-head"><div className="spa-avatar">JT</div><div><h2>John Tano</h2><p>{advertiserId} · Owner · Registered 17 August 2026</p><Badge>Active</Badge></div><KV items={[["Assigned staff","Eric Haiara"],["Last active","Today, 10:42am"]]}/></div>
    <div className="spa-grid two"><Card title="Personal and contact information"><KV items={[["Full name","John Tano"],["Email","john.tano@email.com - Verified"],["Mobile","+675 7xx 2194 - Verified"],["Residential address","Waigani, Port Moresby"],["Communication","WhatsApp and email"],["Advertiser roles","Owner"]]}/></Card>
    <Card title="Account and verification summary"><KV items={[["Email","Verified"],["Mobile","Verified"],["Profile","Complete"],["Identity","Pending review"],["Account","Active"]]}/><div className="spa-actions"><Link className="spa-button primary" to={`${B}/advertisers/${advertiserId}/identity`}>Review identity</Link><Link className="spa-button" to={`${B}/submissions`}>View properties</Link></div></Card></div>
    <Card title="Recent account activity"><Table headers={["Date & time","Activity","Related record","Performed by / channel","Outcome"]} rows={[["18 Aug, 13:21","Identity document submitted","DOC-2031","John Tano / portal","Awaiting review"],["17 Aug, 15:42","Property submitted","TREL-10428","John Tano / portal","Under review"],["17 Aug, 14:18","Mobile verified","Account verification","SMS verification","Verified"]]}/></Card>
  </Page>;
}

function IdentityVerification() {
  const { advertiserId="ADV-00931" }=useParams();
  const decide=(m)=>toast.success(m);
  return <Page id="S02B" title="Advertiser Identity Verification" subtitle={`${advertiserId} - John Tano`} actions={<Link className="spa-button" to={`${B}/advertisers/${advertiserId}`}><ArrowLeft size={15}/> Profile</Link>}>
    <Notice tone="warn"><Clock3 size={17}/> One valid government-issued ID is required. The submitted PNG NID is awaiting staff review.</Notice>
    <div className="spa-grid two"><Card title="Advertiser and contact verification"><KV items={[["Advertiser","John Tano"],["Email","Verified"],["Mobile","Verified"],["Profile","Complete"],["Risk rating","Low"]]}/></Card><Card title="Government-issued ID"><KV items={[["Document type","PNG National ID"],["Document number","NID-****-2194"],["Issuing country","Papua New Guinea"],["Name match","Exact"],["Expiry","14 June 2031"],["Secure file","DOC-2031"]]}/><Action icon={Eye} onClick={()=>toast.info("Secure document viewer opened")}>Open secure document</Action></Card></div>
    <Card title="Verification checks"><Table headers={["Verification item","Submitted information","System check","Staff decision"]} rows={[["Full legal name","John Tano","Exact match","Pending"],["Document validity","PNG NID","Format accepted","Pending"],["Contact ownership","Email and mobile","Both verified","Accepted"],["Duplicate identity","No candidate","Clear","Accepted"]]}/></Card>
    <div className="spa-actions end"><Action onClick={()=>decide("Document request sent")} icon={Send}>Request documents</Action><Action tone="warn" onClick={()=>decide("Resubmission requested")}>Request resubmission</Action><Action tone="bad" onClick={()=>decide("Identity rejected")}>Reject</Action><Action tone="primary" onClick={()=>decide("Identity verified")} icon={CheckCircle2}>Verify identity</Action></div>
  </Page>;
}

function Submissions() {
  const [q,setQ]=useState(""); const rows=submissions.filter(r=>r.join(" ").toLowerCase().includes(q.toLowerCase()));
  return <Page id="S03" title="Advertiser Properties and Submissions" subtitle="Review advertiser submissions within the three-day target.">
    <Stats items={[["18","Submitted"],["7","Due today","warn"],["4","Changes required"],["3","Conflicts detected","bad"],["5","Ready","ok"]]}/><Toolbar value={q} onChange={setQ} placeholder="Search reference, property or advertiser"/>
    <Card title="Submission queue"><Table headers={["Reference","Property","Advertiser","Relationship","Service","Submitted","Review due","SLA","Conflict","Assigned","Status","Action"]} rows={rows} renderAction={r=><Link className="spa-link" to={r[8]==="Possible"?`${B}/conflicts/${r[0]}`:`${B}/submissions/${r[0]}`}>{r[8]==="Possible"?"Resolve":"Open"}</Link>}/></Card>
  </Page>;
}

const submissionTabs=[
  ["Overview", ""], ["Property & Location","property-location"], ["Price & Features","price-features"], ["Photos & Documents","photos-documents"], ["Public Content","public-content"],
];

function SubmissionShell({ tab="overview" }) {
  const { submissionRef="TREL-10428" }=useParams();
  const id=tab==="overview"?"S03A":tab==="property-location"?"S03A-T1":tab==="price-features"?"S03A-T2":tab==="photos-documents"?"S03A-T3":"S03A-T4";
  const title=tab==="overview"?"Submission Review - Overview":tab==="property-location"?"Property and Location":tab==="price-features"?"Price and Features":tab==="photos-documents"?"Photos and Documents":"Public Content Review";
  return <Page id={id} title={title} subtitle={`${submissionRef} - John's Family Home - Boroko`} actions={<Link className="spa-button" to={`${B}/submissions`}><ArrowLeft size={15}/> Queue</Link>}>
    <div className="spa-record-strip"><KV items={[["Advertiser","John Tano"],["Relationship","Owner"],["Service","Advertise only"],["Assigned","Eric Haiara"],["Status","Under Review"],["SLA","Due today"]]}/></div>
    <nav className="spa-tabs">{submissionTabs.map(([label,path])=><NavLink key={label} end={!path} to={`${B}/submissions/${submissionRef}${path?`/${path}`:""}`}>{label}</NavLink>)}</nav>
    {tab==="overview"&&<SubmissionOverview refNo={submissionRef}/>} {tab==="property-location"&&<PropertyLocation/>} {tab==="price-features"&&<PriceFeatures/>} {tab==="photos-documents"&&<PhotosDocuments/>} {tab==="public-content"&&<PublicContent/>}
  </Page>;
}

function SubmissionOverview({refNo}) { return <><Notice><CheckCircle2 size={17}/> Contact verified. Identity review and title/authority review remain open.</Notice><div className="spa-grid two"><Card title="Submission readiness"><KV items={[["Property details","Complete"],["Location identifiers","Complete"],["Price and features","Complete"],["Photos","7 uploaded"],["Documents","2 under review"],["Public content","Ready for review"]]}/></Card><Card title="Review progress"><KV items={[["Duplicate check","Clear"],["Advertiser identity","Pending review"],["Title / authority","Under review"],["Exact location","Protected"],["Current version","v3"]]}/><div className="spa-actions"><Link className="spa-button" to={`${B}/advertisers/ADV-00931/identity`}>Identity</Link><Link className="spa-button" to={`${B}/authority/${refNo}`}>Authority</Link></div></Card></div><Card title="Recent actions"><Table headers={["Date","Action","By","Result"]} rows={[["18 Aug 13:21","Submission opened","Eric Haiara","Under review"],["18 Aug 10:02","Property submitted","John Tano","Received"],["17 Aug 16:44","Draft saved","John Tano","v3"]]}/></Card></>; }
function PropertyLocation(){return <div className="spa-grid two"><Card title="Property details"><KV items={[["Property name","John's Family Home"],["Property class","Residential"],["Property type","House"],["Purpose","Sale"],["Description","Well-maintained family home with secure yard."] ]}/></Card><Card title="Location and identifiers"><KV items={[["Section","54"],["Lot","12"],["Street","Magi Street"],["Suburb / town","Boroko / Port Moresby"],["Province","National Capital District"],["Exact location","Protected"],["Duplicate rule","Section + Lot + Suburb/Town"]]}/><Link className="spa-button" to={`${B}/conflicts/TREL-10428`}>Review identifier match</Link></Card></div>}
function PriceFeatures(){return <div className="spa-grid two"><Card title="Price and availability"><KV items={[["Asking price","K1,200,000"],["Display","Show price"],["Negotiable","Yes"],["Availability","Available"],["Occupancy","Owner occupied"],["Inspection","By appointment"]]}/></Card><Card title="Features"><KV items={[["Bedrooms","4"],["Bathrooms","2"],["Parking","2"],["Land area","840 m²"],["Building area","210 m²"],["Tenure","State lease"]]}/></Card></div>}
function PhotosDocuments(){return <><Card title="Listing photographs"><div className="spa-photo-grid">{[1,2,3,4,5,6,7].map(n=><div key={n}><div className="spa-photo-placeholder">Photo {n}</div><Badge>{n<6?"Approved":"Review"}</Badge></div>)}</div></Card><Card title="Supporting documents"><Table headers={["Document","Status","Uploaded","Action"]} rows={[["Government-issued ID","Verified","17 Aug","Open S02B"],["Title / State Lease","Under review","17 Aug","Open S03C"],["Owner authority","Not required","-","-"],["Property plan","Not submitted","-","Request"]]}/></Card></>}
function PublicContent(){return <><div className="spa-grid two"><Card title="Approved public copy"><KV items={[["Public title","John's Family Home - Boroko"],["Description","Spacious four-bedroom family residence in Boroko."],["Price","K1,200,000"],["Location display","Boroko, Port Moresby"],["Contact routing","Advertiser - monitored by TREL"]]}/></Card><Card title="Disclosure and readiness"><KV items={[["Exact location","Hidden"],["Photos","7 selected"],["Title disclosure","Under review"],["Content version","v3"],["Publication readiness","Ready after authority review"]]}/></Card></div><div className="spa-actions end"><Action onClick={()=>toast.info("Returned for correction")}>Return for changes</Action><Link className="spa-button primary" to={`${B}/publications/LIST-10428`}>Open publication review</Link></div></>}

function ConflictResolution(){const {submissionRef="TREL-10461"}=useParams(); return <Page id="S03B" title="Property Identifier Conflict Resolution" subtitle={`${submissionRef} - Possible master-property match`} actions={<Link className="spa-button" to={`${B}/submissions/${submissionRef}`}><ArrowLeft size={15}/> Submission</Link>}><Notice tone="bad"><AlertTriangle size={17}/> Section, Lot and Suburb/Town all match an existing master property. Resolution is required.</Notice><Card title="Identifier comparison"><Table headers={["Identifier","New submission","Existing master property","Result"]} rows={[["Section","32","32","Match"],["Lot","18","18","Match"],["Suburb / Town","Waigani","Waigani","Match"],["Owner","Mary Kila","M. Kila","Supporting review"],["Street","Hohola Road","Hohola Rd","Supporting review"]]}/></Card><div className="spa-grid two"><Card title="New submission"><KV items={[["Submission",submissionRef],["Advertiser","Mary Kila"],["Relationship","Owner"],["Property","Family House - Waigani"]]}/></Card><Card title="Existing master property"><KV items={[["Master reference","PROP-00984"],["Registered owner","Mary Kila"],["Active listings","1"],["Last verified","12 July 2026"]]}/></Card></div><div className="spa-actions end"><Action onClick={()=>toast.info("Clarification requested")}>Request clarification</Action><Action onClick={()=>toast.success("New property confirmed")}>Confirm new property</Action><Action tone="primary" onClick={()=>toast.success("Submission linked to master property")}>Link to master property</Action></div></Page>}

function AuthorityReview(){const {submissionRef="TREL-10428"}=useParams(); return <Page id="S03C" title="Title and Property Authority Review" subtitle={`${submissionRef} - John Tano - Owner`} actions={<Link className="spa-button" to={`${B}/submissions/${submissionRef}`}><ArrowLeft size={15}/> Submission</Link>}><div className="spa-grid two"><Card title="Title / lease evidence"><KV items={[["Document","State Lease"],["Title reference","Volume 24 / Folio 118"],["Registered owner","John Tano"],["Verification status","Under review"],["Secure document","DOC-2042"]]}/><Action icon={Eye} onClick={()=>toast.info("Secure title opened")}>Open secure document</Action></Card><Card title="Advertiser authority"><KV items={[["Relationship","Owner"],["Identity","Verified"],["Registered owner","John Tano"],["Name comparison","Same"],["Owner confirmation","Received 17 Aug"],["Additional authority","Not required"]]}/></Card></div><Card title="Authority checks"><Table headers={["Check","Evidence","Result"]} rows={[["Advertiser identity","PNG NID","Verified"],["Owner name","Title vs account","Exact match"],["Property identifiers","Section 54 / Lot 12","Match"],["Right to advertise","Owner declaration","Accepted"]]}/></Card><div className="spa-actions end"><Action onClick={()=>toast.info("Evidence requested")}>Request evidence</Action><Action tone="bad" onClick={()=>toast.error("Authority held")}>Hold authority</Action><Action tone="primary" onClick={()=>toast.success("Authority accepted")}>Accept authority</Action></div></Page>}

function PublicationQueue(){const [q,setQ]=useState(""); const rows=publications.filter(r=>r.join(" ").toLowerCase().includes(q.toLowerCase())); return <Page id="S07" title="Publication Control Queue" subtitle="Preview, approve and manage public listings."><Stats items={[["12","Ready to publish"],["4","Draft"],["3","Suspended","warn"],["2","Unpublished"],["68","Published"]]}/><Toolbar value={q} onChange={setQ}/><Card title="Publication queue"><Table headers={["Listing","Property","Advertiser","Sale/Rent","Service","Submission","Acceptance","Authority","Location","Readiness","Assigned","Status","Action"]} rows={rows} renderAction={r=><Link className="spa-link" to={`${B}/publications/${r[0]}`}>Review</Link>}/></Card></Page>}

function PublicationReview(){const {listingRef="LIST-10428"}=useParams(); return <Page id="S07A" title="Individual Listing Publication Review" subtitle={`${listingRef} - John's Family Home - Boroko`} actions={<Link className="spa-button" to={`${B}/publications`}><ArrowLeft size={15}/> Queue</Link>}><div className="spa-linkbar"><Link to={`${B}/submissions/TREL-10428`}>Submission S03A</Link><Link to={`${B}/submissions/TREL-10428/public-content`}>Public Content S03A-T4</Link><Link to={`${B}/submissions/TREL-10428/photos-documents`}>Photos S03A-T3</Link><Link to={`${B}/authority/TREL-10428`}>Authority S03C</Link><Link to={`${B}/lifecycle/${listingRef}`}>Lifecycle S09A</Link></div><div className="spa-grid two"><Card title="Public listing preview"><div className="spa-preview"><div className="spa-preview-image"><BuildingIcon/></div><h3>John's Family Home - Boroko</h3><strong>K1,200,000</strong><p>4 bedrooms · 2 bathrooms · 2 parking</p><p>Boroko, Port Moresby · Exact location protected</p></div></Card><Card title="Publication readiness"><KV items={[["Submission","Approved"],["Advertiser acceptance","Accepted"],["Identity","Verified"],["Title / authority","Accepted"],["Exact location","Protected"],["Photos","7 approved"],["Content version","v3"],["Result","Ready"]]}/></Card></div><div className="spa-actions end"><Action onClick={()=>toast.info("Returned for changes")}>Return</Action><Action tone="warn" onClick={()=>toast.warning("Listing suspended")}>Suspend</Action><Action tone="bad" onClick={()=>toast.error("Listing unpublished")}>Unpublish</Action><Action tone="primary" onClick={()=>toast.success("Listing published")} icon={CheckCircle2}>Publish</Action></div></Page>}
function BuildingIcon(){return <FileText size={46}/>}

function ExactLocationQueue(){const [q,setQ]=useState("");const rows=locationRequests.filter(r=>r.join(" ").toLowerCase().includes(q.toLowerCase()));return <Page id="S08" title="Exact Location Requests" subtitle="Control consent, secure sharing and access history."><Stats items={[["7","Pending","warn"],["5","Awaiting advertiser"],["18","Active secure shares"],["4","Inspection instead"],["3","Expired"]]}/><Toolbar value={q} onChange={setQ}/><Card title="Location access requests"><Table headers={["Reference","Requester","Property","Advertiser","Reason","Requested","Authority","Decision","Secure access","Status","Action"]} rows={rows} renderAction={r=><Link className="spa-link" to={`${B}/exact-location/${r[0]}`}>Review</Link>}/></Card></Page>}

function ExactLocationReview(){const {requestRef="LOC-0081"}=useParams();return <Page id="S08A" title="Individual Exact Location Request Review" subtitle={`${requestRef} - Sarah Kila requests John's Family Home`} actions={<Link className="spa-button" to={`${B}/exact-location`}><ArrowLeft size={15}/> Queue</Link>}><div className="spa-linkbar"><Link to={`${B}/submissions/TREL-10428`}>Property S03A</Link><Link to={`${B}/advertisers/ADV-00931`}>Advertiser S02A</Link><span>Related enquiry deferred to O-series</span><Link to={`${B}/lifecycle/LIST-10428`}>Lifecycle S09A</Link></div><div className="spa-grid two"><Card title="Request details"><KV items={[["Requester","Sarah Kila"],["Verified contact","Email and mobile verified"],["Property","John's Family Home - Boroko"],["Advertiser","John Tano"],["Reason","Buyer inspection"],["Message","I would like to inspect the property this week."] ]}/></Card><Card title="Authority and decision"><KV items={[["Decision authority","John Tano - private advertiser"],["Current status","Awaiting advertiser"],["Requested","18 Aug 2026, 10:21am"],["Assigned staff","Eric Haiara"]]}/><div className="spa-actions"><Action onClick={()=>toast.info("Request sent to advertiser")} icon={Send}>Send to John Tano</Action></div></Card></div><Card title="Secure share controls"><KV items={[["Recipient","Sarah Kila"],["Start","After approval"],["Expiry","Required"],["Maximum views","Optional"],["Secure access link","Generated after approval"],["Last access","Not accessed"]]}/></Card><div className="spa-actions end"><Action onClick={()=>toast.info("More information requested")}>Request information</Action><Action onClick={()=>toast.success("Inspection offered")}>Arrange inspection</Action><Action tone="bad" onClick={()=>toast.error("Request declined")}>Decline</Action><Action tone="primary" onClick={()=>toast.success("Secure location approved")}>Share exact location</Action></div></Page>}

function LifecycleQueue(){const [q,setQ]=useState("");const rows=lifecycle.filter(r=>r.join(" ").toLowerCase().includes(q.toLowerCase()));return <Page id="S09" title="Listing Lifecycle and Confirmation Queue" subtitle="Monitor confirmations, inactivity, suspension, removal and archiving."><Stats items={[["9","Confirmation due","warn"],["6","Awaiting advertiser"],["3","Six-month notice","warn"],["2","Removal due","bad"],["5","Suspended"]]}/><Toolbar value={q} onChange={setQ}/><Card title="Lifecycle queue"><Table headers={["Listing","Property","Advertiser","Sale/Rent","Service","Publication","Availability","First published","Last confirmed","Last update","Next due","Inactivity","Alert","Assigned","Action"]} rows={rows} renderAction={r=><Link className="spa-link" to={`${B}/lifecycle/${r[0]}`}>Review</Link>}/></Card></Page>}

function LifecycleReview(){const {listingRef="LIST-10428"}=useParams();return <Page id="S09A" title="Individual Listing Lifecycle and Audit History" subtitle={`${listingRef} - John's Family Home - Boroko`} actions={<Link className="spa-button" to={`${B}/lifecycle`}><ArrowLeft size={15}/> Queue</Link>}><div className="spa-record-strip"><KV items={[["Submission","TREL-10428"],["Advertiser","John Tano"],["Service","Advertise only"],["Publication","Published"],["Availability","Available"],["Last confirmed","14 May 2026"],["Next due","18 Aug 2026"],["Version","v3"]]}/></div><div className="spa-linkbar"><Link to={`${B}/submissions/TREL-10428`}>Property S03A</Link><Link to={`${B}/advertisers/ADV-00931`}>Advertiser S02A</Link><Link to={`${B}/publications/${listingRef}`}>Publication S07A</Link><Link to={`${B}/exact-location`}>Location requests S08</Link></div><div className="spa-grid two"><Card title="Confirmation checklist"><KV items={[["Still available","Awaiting confirmation"],["Price correct","Awaiting confirmation"],["Description correct","Awaiting confirmation"],["Photos current","Awaiting confirmation"],["Contact routing","Awaiting confirmation"],["Inspection arrangements","Awaiting confirmation"]]}/></Card><Card title="Lifecycle controls"><div className="spa-actions stack"><Action icon={Send} onClick={()=>toast.success("Confirmation request sent")}>Send quarterly confirmation</Action><Action onClick={()=>toast.success("Advertiser response recorded")}>Record advertiser response</Action><Action tone="warn" onClick={()=>toast.warning("Listing suspended")}>Suspend listing</Action><Action tone="bad" onClick={()=>toast.error("Listing archived")}>Remove / archive</Action></div></Card></div><Card title="Immutable audit history"><Table headers={["Date & time","Event","Previous status","New status","Performed by / channel","Reason / result","Related record","Version","Communication"]} rows={[["18 Aug 09:00","Confirmation due","Current","Due","System / scheduler","Quarterly confirmation reached","CONF-0318","v3","Sent"],["14 May 15:42","Advertiser confirmed","Due","Current","John Tano / portal","Available; no changes","CONF-0244","v3","Acknowledged"],["14 May 15:41","Price updated","K1.18m","K1.20m","Eric Haiara / staff","Advertiser instruction","S03A-T4","v3","Delivered"],["14 Feb 11:03","Listing published","Draft","Published","Eric Haiara / staff","All checks passed","S07A","v2","Delivered"]]}/></Card><Notice>Audit records cannot be edited or deleted. Corrections create a new linked event.</Notice></Page>}

export {
  Overview, Advertisers, AdvertiserProfile, IdentityVerification, Submissions,
  ConflictResolution, AuthorityReview, PublicationQueue, PublicationReview,
  ExactLocationQueue, ExactLocationReview, LifecycleQueue, LifecycleReview,
};
export const SubmissionOverviewPage=()=> <SubmissionShell tab="overview"/>;
export const PropertyLocationPage=()=> <SubmissionShell tab="property-location"/>;
export const PriceFeaturesPage=()=> <SubmissionShell tab="price-features"/>;
export const PhotosDocumentsPage=()=> <SubmissionShell tab="photos-documents"/>;
export const PublicContentPage=()=> <SubmissionShell tab="public-content"/>;
