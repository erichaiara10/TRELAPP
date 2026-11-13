import screens from './screens.json';
export { screens };
export const byKey = Object.fromEntries(screens.map(s => [s.key, s]));
export const MAIN = screens.filter(s => /^O\d+$/.test(s.key));
export const FAMILY = { O01:'dashboard', O02:'properties', O03:'customers', O04:'leads', O05:'requirements', O06:'requirements', O07:'inspections', O08:'tasks', O09:'leads', O10:'users', O11:'locations', O12:'content', O13:'reports' };
export const ENDPOINTS = { cities:'/locations/cities', suburbs:'/locations/suburbs', customers:'/customers', properties:'/properties', leads:'/leads', requirements:'/requirements', inspections:'/inspections', tasks:'/tasks', users:'/users', locations:'/locations/provinces', content:'/content/site', reports:'/reports/summary', dashboard:'/reports/summary' };
export const DETAIL = { O02:'propertydetail', O03:'customerdetail', O04:'leaddetail', O05:'requirementform', O06:'requirementform', O07:'inspectionform', O08:'taskform', O09:'leaddetail', O10:'staffpermissions', O11:'locationuse' };
export const slug = s => s.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
export const textValue = v => v === null || v === undefined || v === '' ? 'Not recorded' : Array.isArray(v) ? v.map(textValue).join(', ') : typeof v === 'object' ? 'Linked record' : String(v);
export const rowsOf = d => Array.isArray(d) ? d : Array.isArray(d?.items) ? d.items : Array.isArray(d?.results) ? d.results : [];
export const recordName = r => r?.name || r?.title || r?.reference || r?.id || 'Record';
export const recordId = r => r?.id || r?.reference;
export const dateText = x => x && !Number.isNaN(Date.parse(x)) ? new Intl.DateTimeFormat('en-GB',{dateStyle:'medium',timeZone:'Pacific/Port_Moresby'}).format(new Date(x)) : 'Not recorded';
export const MUTATION = /^(save|confirm|record authorised|record linked|use existing|create distinct|commit|restore unpublished|export filtered|add to shortlist|remove selected|run \/ rerun|retry matching|run report|validate without saving|review and initiate recovery)/i;
export function isCommit(label,target) { return byKey[target]?.kind !== 'popup' && MUTATION.test(label); }
const CHOICES = {
 'Customer purposes':['Buyer','Seller','Tenant','Landlord','Corporate'], 'Preferred external channel':['Email','WhatsApp'], 'Source channel':['Office','Website','Phone','Email','WhatsApp','Referral','Staff outreach','Other approved'], 'Responsible handler':['TREL','Approved advertiser'], 'Requested service':['Sell my property','Find a property to buy','Find a rental property','Find a tenant and manage my property','Advertise only'], 'Listing purpose':['Sale','Rent'], 'Public price choice':['Exact amount','Negotiable','Contact for price / rent'], 'Currency':['PGK'], 'Rental period':['Week','Month','Year'], 'Priority':['Low','Medium','High'], 'Account category':['STAFF'], 'Account status':['Active','Suspended','Disabled'], 'Role':['System Administrator','Managing Director','Sales Manager','Sales Agent','Leasing Agent','Property Manager','Marketing Officer'], 'Roles':['System Administrator','Managing Director','Sales Manager','Sales Agent','Leasing Agent','Property Manager','Marketing Officer'], 'Record scope':['Assigned','Team','All permitted'], 'Purpose':['Buy','Rent','Either'], 'Class':['Residential','Commercial','Industrial','Vacant Land','Agricultural / Rural','Other / Special Property'], 'Property class':['Residential','Commercial','Industrial','Vacant Land','Agricultural / Rural','Other / Special Property'], 'Property type':['House','Apartment / Unit','Townhouse','Duplex','Block of Units','Bedsit / Room','Serviced Apartment','Other Residential','Office','Retail / Shop','Hotel / Lodge','Mixed-use Property','Other Commercial','Warehouse','Workshop / Factory','Industrial Yard / Compound','Other Industrial','Vacant land','Agricultural / Rural','Other / Special Property'],'Listing service':['TREL sells my property','Advertise only — I will handle the sale','TREL finds a tenant and manages my property','Advertise only — I will manage the rental'],'Advertiser capacity':['Owner / Joint Owner','Authorised Real Estate Agent','Authorised Representative of the Owner'],'Tenure':['State lease','Freehold','Customary','Other'],'Location review':['Pending review','Reviewed','Clarification required'],'Requested function':['Sell my property','Find a property to buy','Find a rental property','Find a tenant and manage my property','Advertise only'],'Public price display':['Exact amount','Negotiable','Contact for price / rent'],'Land unit':['m²','ha'],'Floor unit':['m²'],'Condition':['New','Excellent','Good','Fair','Needs renovation'],'Furnishing':['Furnished','Partly furnished','Unfurnished'],'Output format':['CSV','PDF'], 'Page':['Home','Buy','Rent','Property Wanted','Property Management','Corporate Services','About','Contact','Privacy','Terms'], 'Section':['Introduction','Hero','Main content','Call to action','Metadata'], 'Contact consent':['Email','WhatsApp'], 'Features':['Fence','Water tank','Covered parking','Air conditioning','Backup power'], 'Activation method':['Secure invitation'], 'Level':['Province','City / Town / District','Suburb','Local area / Estate','Street'], 'Decision':['Approve','Return for changes'],
};
export function optionsFor(label,example='') {
 const name=label.replace(/ \[if applicable\]/g,'');
 if(CHOICES[name])return CHOICES[name];
 if(/rental period/i.test(label))return CHOICES['Rental period'];
 if(/currency/i.test(label))return ['PGK'];
 if(/purpose/i.test(label))return ['Sale','Rent'];
 if(/class/i.test(label))return CHOICES.Class;
 if(/role/i.test(label))return CHOICES.Role;
 if(/source channel/i.test(label))return CHOICES['Source channel'];
 if(/channel/i.test(label))return ['Office','Phone','Email','WhatsApp','Internal note'];
 if(/stage/i.test(label))return ['New','Contacted','Qualified'];
 if(example.includes(' / ') && !/Sample|existing|recorded|permitted|pending|approved.*revision/i.test(example))return example.split(' / ');
 if(example.includes(';') && !/Sample|server|recorded/i.test(example))return example.split(';').map(x=>x.trim());
 if(/contact|email|location|reference|file|property|staff|select|recorded|unknown|sample|pending|approved|current/i.test(example))return [];
 return example && !/\d|\||:/.test(example) ? [example] : [];
}
export const FIELD_MAP = { 'Full name':'name','Customer name':'name','Email':'email','Unique email':'email','Telephone':'phone','Property name / listing title':'title','Property description':'description','Description':'description','Notes':'notes','Task title':'title','Priority':'priority','Property class':'property_class','Property name':'title','Actual asking amount':'price','Parking spaces':'parking','Land size':'land_size','Floor size':'building_area','Property type':'property_type','Bedrooms':'bedrooms','Bathrooms':'bathrooms','Parking':'parking','Section':'section','Lot':'lot','Street':'street','Suburb':'suburb','Province':'province','City / town':'city','Latitude':'latitude','Longitude':'longitude','Organisation':'company','Asking amount':'price','Land area':'land_size','Floor area':'building_area','Heading':'heading','Body text':'body','Agency name':'agency_name','Short name':'short_name','WhatsApp':'whatsapp','Office address':'address' };
export function initialField(record,label,kind,params,user) {
 if(label==='Account category')return 'STAFF';
 const key=FIELD_MAP[label];
 if(key && record?.[key] !== undefined)return record[key];
 if(kind==='readonly') {
  if(/^(customer|property|inspection|task|lead|staff|target account|target staff|record|reference)$/i.test(label))return params.get('recordId') || '';
  if(/creator|actor|signed-in/i.test(label))return user?.name || '';
  return '';
 }
 return kind==='check'?false:kind==='multi'?[]:'';
}
export function columnValue(label,r) {
 const l=label.toLowerCase();
 if(/action|open|view/.test(l))return '';
 if(l==='property / type')return [recordName(r),r.property_type].filter(Boolean).join(' · ');
 if(l==='public dates')return `First: ${dateText(r.first_registered_at||r.created_at)} · Updated: ${dateText(r.public_updated_at)}`;
 if(/first registered/.test(l))return dateText(r.first_registered_at || r.created_at);
 if(/public last updated/.test(l))return dateText(r.public_updated_at);
 if(/received|created|date|updated/.test(l))return dateText(r.created_at || r.updated_at);
 if(/customer|enquirer|lead|staff \/|name|property|title|description/.test(l) && !/type|purpose|linked|class|source|status|authority/.test(l))return recordName(r);
 if(/contact|email/.test(l))return [r.phone,r.email].filter(Boolean).join(' · ');
 if(/purpose|type|class|rent\/sell/.test(l))return r.customer_type || r.intent || r.listing_type || r.property_type || r.property_class;
 if(/source/.test(l))return r.source;
 if(/location/.test(l))return [r.suburb,r.city,r.province].filter(Boolean).join(', ');
 if(/price|rent|amount/.test(l))return r.price_label || (r.price != null ? `${r.currency || 'PGK'} ${r.price}${r.rent_period ? ' / '+r.rent_period : ''}` : null);
 if(/role/.test(l))return r.role;
 if(/categor/.test(l))return r.account_category;
 if(/assign|handler/.test(l))return r.assigned_agent_id || r.assigned_to || r.handler_id;
 if(/priority/.test(l))return r.priority;
 if(/due/.test(l))return dateText(r.due_date || r.due_at);
 if(/status|state|engagement|authority|publication/.test(l))return r.status;
 if(/id|reference/.test(l))return recordId(r);
 return r[slug(label).replaceAll('-','_')];
}
