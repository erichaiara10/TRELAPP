import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, ChevronRight, RefreshCw, X, MapPin } from 'lucide-react';
import { api, formatError } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import MapPickerDialog from '@/components/MapPickerDialog';
import { screens, byKey, FAMILY, ENDPOINTS, DETAIL, slug, rowsOf, recordName, recordId, textValue, dateText, optionsFor, initialField, columnValue, isCommit } from './model';
import './workspace.css';

const Context = createContext(null);
export function StaffScreensProvider({children}) {
  const [forms,setForms]=useState({});
  const [columns,setColumns]=useState(null);
  const [cache,setCache]=useState({});
  const requests=useRef({});
  const ensure=useCallback((family)=>{
    if(!ENDPOINTS[family]||requests.current[family])return;
    requests.current[family]=true;
    setCache(c=>({...c,[family]:{...c[family],loading:true,error:null}}));
    api.get(ENDPOINTS[family]).then(({data})=>setCache(c=>({...c,[family]:{data,loading:false,error:null}}))).catch(e=>setCache(c=>({...c,[family]:{data:null,loading:false,error:formatError(e)}})));
  },[]);
  return <Context.Provider value={{forms,setForms,columns,setColumns,cache,setCache,ensure}}>{children}</Context.Provider>;
}
function useDataset(family) {
  const {cache,setCache}=useContext(Context);const [reload,setReload]=useState(0);
  useEffect(()=>{
    if(!family || !ENDPOINTS[family])return;
    let live=true;
    setCache(c=>({...c,[family]:{...c[family],loading:true,error:null}}));
    api.get(ENDPOINTS[family]).then(({data})=>{if(live)setCache(c=>({...c,[family]:{data,loading:false,error:null}}));}).catch(err=>{if(live)setCache(c=>({...c,[family]:{data:null,loading:false,error:formatError(err)}}));});
    return ()=>{live=false;};
  },[family,reload,setCache]);
  return {...(cache[family] || {loading:true}),refresh:()=>setReload(n=>n+1)};
}
function Popup({title,onClose,children}) {
  const box=useRef(null);const close=useRef(onClose);close.current=onClose;
  useEffect(()=>{
    const previous=document.activeElement;const root=box.current;
    const items=()=>Array.from(root.querySelectorAll('button:not(:disabled),input:not([readonly]),select,textarea,a[href],[tabindex="0"]')).filter(e=>e.offsetParent!==null);
    (items()[0]||root).focus();
    const key=e=>{if(e.key==='Escape'){e.preventDefault();close.current();}if(e.key==='Tab'){const a=items();if(!a.length){e.preventDefault();return;}const first=a[0],last=a[a.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}};
    root.addEventListener('keydown',key);return()=>{root.removeEventListener('keydown',key);previous?.focus();};
  },[]);
  return <div className="sw-dialog-backdrop"><section className="sw-dialog" ref={box} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="sw-dialog-title"><div className="sw-dialog-head"><h2 id="sw-dialog-title">{title}</h2><button className="sw-btn" aria-label="Close dialog" onClick={onClose}><X size={17}/></button></div>{children}</section></div>;
}
function FileField({label,id,value,onChange,photo=false}) {
  const [urls,setUrls]=useState([]);const [error,setError]=useState('');
  useEffect(()=>{if(!photo)return;const next=(Array.isArray(value)?value:[]).filter(x=>x instanceof File).map(x=>({name:x.name,url:URL.createObjectURL(x)}));setUrls(next);return()=>next.forEach(x=>URL.revokeObjectURL(x.url));},[value,photo]);
  const choose=e=>{
    const files=Array.from(e.target.files||[]);setError('');
    if(photo&&files.length>7){setError('Select at most seven property photographs.');return;}
    if(files.some(x=>x.size>10*1024*1024)){setError('Each file must be 10 MB or smaller.');return;}
    if(files.some(x=>!(photo?['image/jpeg','image/png','image/webp']:['application/pdf','image/jpeg','image/png','image/webp','text/csv','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']).includes(x.type))){setError('Select a supported file type.');return;}
    onChange(files);
  };
  return <><input id={id} type="file" multiple={photo||/documents/i.test(label)} accept={photo?'.jpg,.jpeg,.png,.webp':/import|source file/i.test(label)?'.csv,.xlsx':'.pdf,.jpg,.jpeg,.png,.webp'} onChange={choose}/>{error&&<span className="sw-error" role="alert">{error}</span>}<small>{photo?'1–7 photos · JPG, PNG or WebP · up to 10 MB each':'Files remain in this screen until the secure upload workflow is connected.'}</small><ul className="sw-file-list">{(Array.isArray(value)?value:[]).map((f,i)=><li key={f.name+i}>{f.name} <button type="button" className="sw-btn" onClick={()=>onChange(value.filter((_,n)=>n!==i))}>Remove</button></li>)}</ul>{photo&&<div className="sw-image-list">{urls.map((u,i)=><div key={u.url}><img src={u.url} alt={u.name}/><button type="button" className="sw-btn" disabled={i===0} onClick={()=>onChange([value[i],...value.filter((_,n)=>n!==i)])}>{i===0?'Primary photo':'Make primary'}</button>{i>0&&<button type="button" className="sw-btn" onClick={()=>{const a=[...value];[a[i-1],a[i]]=[a[i],a[i-1]];onChange(a);}}>Move earlier</button>}</div>)}</div>}</>;
}
function Field({field,screen,value,change,lookup,readonlyValue,draft={}}) {
  const [label,kind,example,required]=field;const id=`sw-${screen.key}-${slug(label)}`;
  let opts=optionsFor(label,example);
  if(label==='Property type' && draft['Property class']) {
    const types={Residential:['House','Apartment / Unit','Townhouse','Duplex','Block of Units','Bedsit / Room','Serviced Apartment','Other Residential'],Commercial:['Office','Retail / Shop','Hotel / Lodge','Mixed-use Property','Other Commercial'],Industrial:['Warehouse','Workshop / Factory','Industrial Yard / Compound','Other Industrial'],'Vacant Land':['Vacant land'],'Agricultural / Rural':['Agricultural / Rural'],'Other / Special Property':['Other / Special Property']};
    opts=types[draft['Property class']]||opts;
  }const val=value ?? (kind==='multi'?[]:kind==='check'?false:'');
  const set=v=>change(label,v);const isRead=kind==='readonly';
  const {ensure}=useContext(Context);
  const lookupFamily=/staff|assignee|reviewer/i.test(label)?'users':/customer|party|owner|requester|contact/i.test(label)?'customers':/requirement|brief/i.test(label)?'requirements':/suburb/i.test(label)?'suburbs':/city/i.test(label)?'cities':/province|location/i.test(label)?'locations':/property|master|listing/i.test(label)?'properties':null;
  useEffect(()=>{if(kind==='relation'&&lookupFamily)ensure(lookupFamily);},[kind,lookupFamily,ensure]);
  let choices=lookupFamily?rowsOf(lookup[lookupFamily]?.data):[];
  if(lookupFamily==='cities'&&draft.Province)choices=choices.filter(r=>r.province_id===draft.Province);
  if(lookupFamily==='suburbs'&&draft['City / town'])choices=choices.filter(r=>r.city_id===draft['City / town']);
  const photo=/photographs|photos/i.test(label);
  return <div className="sw-field"><label htmlFor={id}><span>{label}{required==='R'?' *':required==='S'?' *':''}</span></label>
    {isRead?<input id={id} readOnly value={textValue(readonlyValue)} aria-label={label}/>:
    kind==='textarea'?<textarea id={id} rows={4} value={val} onChange={e=>set(e.target.value)} required={required==='R'} maxLength={/description/i.test(label)?20000:10000}/>:
    kind==='check'?<label className="sw-check"><input id={id} type="checkbox" disabled={screen.key==='columns'&&required==='R'} checked={!!val} onChange={e=>set(e.target.checked)}/><span>{/state|active/i.test(label)?'Active':'Yes'}</span></label>:
    kind==='multi'?<fieldset id={id} aria-label={label}>{opts.map(option=><label className="sw-check" key={option}><input type="checkbox" checked={Array.isArray(val)&&val.includes(option)} onChange={e=>set(e.target.checked?[...(Array.isArray(val)?val:[]),option]:(Array.isArray(val)?val:[]).filter(x=>x!==option))}/>{option}</label>)}</fieldset>:
    kind==='file'||kind==='upload'?<FileField id={id} label={label} value={val} onChange={set} photo={photo}/>:
    kind==='relation'?<><select id={id} required={required==='R'} value={val} onChange={e=>set(e.target.value)}><option value="">Select a linked record</option>{choices.filter(r=>recordId(r)).map(r=><option value={recordId(r)} key={recordId(r)}>{recordName(r)} · {recordId(r)}</option>)}</select>{lookup[lookupFamily]?.error?<small role="alert">Linked records could not be loaded: {lookup[lookupFamily].error}</small>:!choices.length&&<small>{lookup[lookupFamily]?.loading?'Loading linked records…':'No linked choices are available.'}</small>}</>:
    kind==='select'?<select id={id} value={val} required={required==='R'} onChange={e=>set(e.target.value)}><option value="">Select {label.toLowerCase()}</option>{opts.map(x=><option key={x} value={x}>{x}</option>)}</select>:
    <input id={id} required={required==='R'} value={val} onChange={e=>set(e.target.value)} type={['integer','decimal','money'].includes(kind)?'number':kind==='datetime'?'datetime-local':kind==='tags'?'text':kind} step={kind==='integer'?'1':['decimal','money'].includes(kind)?'any':undefined} min={/latitude/i.test(label)?-90:/longitude/i.test(label)?-180:['integer','decimal','money'].includes(kind)?0:undefined} max={/latitude/i.test(label)?90:/longitude/i.test(label)?180:undefined} maxLength={kind==='text'?250:undefined}/>
    }{required==='C'&&<small>Required when applicable.</small>}{required==='S'&&<small>Required for completed submission.</small>}{kind==='tags'&&<small>Separate multiple values with commas.</small>}
  </div>;
}
const readFields={customers:['name','customer_type','email','phone','company','source','notes'],properties:['title','description','property_type','status','price','rent_period','suburb','city','province','section','lot'],leads:['name','source','status','email','phone','message','property_id','customer_id'],requirements:['customer_name','intent','property_type','min_price','max_price','min_bedrooms','status'],tasks:['title','description','priority','status','due_at'],inspections:['property_title','customer_name','status','preferred_date','scheduled_at']};
function RecordDetails({record,family}) {
  if(!record)return <p className="sw-empty">Select a record from the {family} list to view its information.</p>;
  return <dl className="sw-definitions">{(readFields[family]||['name','email','role','account_category','status']).map(k=><div className="sw-definition" key={k}><dt>{k.replaceAll('_',' ')}</dt><dd>{textValue(record[k])}</dd></div>)}</dl>;
}
export default function StaffWorkspace({parent,children}) {
  const location=useLocation();const navigate=useNavigate();const [params]=useSearchParams();const {user}=useAuth();
  const context=useContext(Context);const {forms,setForms,columns,setColumns,cache}=context;
  const requested=params.get('screen');const screen=byKey[requested||parent];const valid=screen&&screen.route===location.pathname;
  const family=FAMILY[parent];const dataset=useDataset(family);const collection=rowsOf(dataset.data);
  const rid=params.get('recordId');const rtype=params.get('recordType')||family;
  const record=rowsOf(cache[rtype]?.data).find(r=>String(recordId(r))===rid) || (rtype===family?collection.find(r=>String(recordId(r))===rid):null);
  const screenKey=screen?.key||parent;const bucket=`${family}:${rid||'new'}`;const form=forms[bucket]||{};
  const [notice,setNotice]=useState('');const [mapOpen,setMapOpen]=useState(false);const [pendingNavigation,setPendingNavigation]=useState(null);const [dirty,setDirty]=useState(false);const [page,setPage]=useState(1);
  const [related,setRelated]=useState({loading:false,rows:[],error:null});
  const isPopup=valid&&screen.kind==='popup';const from=byKey[params.get('from')]?.route===location.pathname?params.get('from'):parent;
  useEffect(()=>{setPage(1);setNotice('');},[screenKey,params.get('q'),params.get('status')]);
  useEffect(()=>{const stop=e=>{if(dirty){e.preventDefault();e.returnValue='';}};window.addEventListener('beforeunload',stop);return()=>window.removeEventListener('beforeunload',stop);},[dirty]);
  useEffect(()=>{
    if(!rid || !['customers','leads'].includes(rtype) || !['communications','logcommunication','sendcommunication'].includes(screenKey)){setRelated({loading:false,rows:[],error:null});return;}
    let live=true;setRelated({loading:true,rows:[],error:null});api.get(`/${rtype}/${encodeURIComponent(rid)}/communications`).then(({data})=>live&&setRelated({loading:false,rows:rowsOf(data),error:null})).catch(e=>live&&setRelated({loading:false,rows:[],error:formatError(e)}));return()=>{live=false;};
  },[rid,rtype,screenKey]);
  const change=(label,value)=>{setForms(f=>({...f,[bucket]:{...f[bucket],[label]:value}}));setDirty(true);};
  const valueFor=field=>form[field[0]] ?? (screen?.key==='columns'?(columns?columns.includes(field[0]):field[0]!=='Internal modified date'):initialField(record,field[0],field[1],params,user));
  const href=(key,extra={})=>{
    const target=byKey[key];if(!target)return null;
    const q=new URLSearchParams(params);q.set('screen',key);q.delete('mode');q.delete('from');
    if(target.route!==location.pathname){q.delete('q');q.delete('status');q.delete('page');}
    if(target.kind==='popup')q.set('from',isPopup?from:screenKey);
    for(const [k,v] of Object.entries(extra)){if(v===null)q.delete(k);else q.set(k,String(v));}
    return `${target.route}?${q}`;
  };
  const go=(key,extra)=>{if(key==='propertyprice'){const c=form['Property class']||record?.property_class;if(c==='Vacant Land')key='landfields';else if(['Commercial','Industrial'].includes(c))key='commercialfields';else if(['Agricultural / Rural','Other / Special Property'].includes(c))key='otherfields';}const url=href(key,extra);if(!url){setNotice('This destination is not available.');return;}navigate(url);};
  const closePopup=()=>go(from);
  const openTools=()=>{const q=new URLSearchParams(params);q.set('mode','records');q.delete('screen');const url=`${location.pathname}?${q}`;if(dirty)setPendingNavigation(url);else navigate(url);};
  const select=r=>{const q=new URLSearchParams(params);q.set('recordId',String(recordId(r)));q.set('recordType',family);navigate(`${location.pathname}?${q}`,{replace:true});};
  const openRecord=r=>go(DETAIL[parent]||parent,{recordId:recordId(r),recordType:family});
  const setFilter=(key,value)=>{const q=new URLSearchParams(params);if(value)q.set(key,value);else q.delete(key);navigate(`${location.pathname}?${q}`,{replace:true});};
  const filterRows=collection.filter(r=>(!params.get('q')||JSON.stringify(r).toLowerCase().includes(params.get('q').toLowerCase()))&&(!params.get('status')||r.status===params.get('status')));
  const commitButton=(label,target,index)=>{
    if(isCommit(label,target))return <button key={label+index} type="button" className="sw-btn" disabled title="This action awaits business-workflow integration.">{label}</button>;
    if(label==='Apply columns')return <button key={label} className="sw-btn primary" onClick={()=>{setColumns(screen.fields.filter(f=>!!valueFor(f)).map(f=>f[0]));closePopup();}}>Apply columns</button>;
    if(label==='Use property location')return <button key={label} className="sw-btn primary" onClick={()=>go(target)}>Use property location in form</button>;
    if(label==='Discard unsaved changes')return <button key={label} className="sw-btn" onClick={()=>{setForms(f=>{const n={...f};delete n[bucket];return n;});setDirty(false);go(target);}}>Discard unsaved changes</button>;
    const isNew=/^(add customer|new property|record enquiry|record office enquiry|new task|create brief|create request|create staff account)$/i.test(label);
    return <button key={label+index} type="button" className={`sw-btn ${index===0?'primary':''}`} onClick={()=>go(target,isNew?{recordId:null,recordType:null}:undefined)}>{label}</button>;
  };
  const actions=s=><div className="sw-actions">{s.buttons.map(([label,target],i)=>commitButton(label,target,i))}{s.buttons.some(([label,target])=>isCommit(label,target))&&<small>Disabled actions await business-workflow integration. Nothing is saved, approved, sent or exported from these new controls.</small>}</div>;
  const fields=s=><div className="sw-fields">{s.fields.map(f=><Field key={f[0]} field={f} screen={s} value={valueFor(f)} readonlyValue={valueFor(f)} change={change} lookup={cache} draft={form}/>)}</div>;
  const filters=()=> <div className="sw-filters"><label><span className="sr-only">Search records</span><input aria-label="Search records" placeholder="Search records…" value={params.get('q')||''} onChange={e=>setFilter('q',e.target.value)}/></label><select aria-label="Filter by status" value={params.get('status')||''} onChange={e=>setFilter('status',e.target.value)}><option value="">All statuses</option>{[...new Set(collection.map(r=>r.status).filter(Boolean))].map(x=><option key={x}>{x}</option>)}</select><button className="sw-btn" onClick={()=>{const q=new URLSearchParams(params);q.delete('q');q.delete('status');navigate(`${location.pathname}?${q}`);}}>Reset filters</button></div>;
  const table=(s,data=filterRows,canOpen=true)=>{
    let cols=s.cols.length?s.cols:['Reference','Name','Status','Action'];
    if(s.key==='O02'&&columns)cols=cols.filter(c=>{const map={'Property / type':['Property reference and title','Class and type'],'Purpose':['Sale or Rent'],'Location':['Location'],'Price / period':['Price and rental period'],'Handler':['Service handler'],'Publication':['Publication and authority states'],'Authority':['Publication and authority states'],'Public dates':['First Registered','Public Last Updated']};return c==='Action'||(map[c]||[]).some(x=>columns.includes(x));});
    const visible=data.slice((page-1)*20,page*20);
    return <><div className="sw-table-scroll"><table className="sw-table"><thead><tr><th aria-label="Select record"/>{cols.map(c=><th key={c}>{c}</th>)}</tr></thead><tbody>{visible.map((r,i)=><tr className={rid===String(recordId(r))?'selected':''} key={recordId(r)||i}><td>{canOpen&&recordId(r)&&<input type="radio" aria-label={`Select ${recordName(r)}`} checked={rid===String(recordId(r))} onChange={()=>select(r)}/>}</td>{cols.map((c,n)=><td key={c}>{/action|open|view/i.test(c)?canOpen&&recordId(r)?<button onClick={()=>openRecord(r)}>Open record</button>:<span className="sw-badge">Read only</span>:n===0&&canOpen&&recordId(r)?<button onClick={()=>openRecord(r)}>{textValue(columnValue(c,r))}</button>:textValue(columnValue(c,r))}</td>)}</tr>)}</tbody></table></div>{!data.length&&<div className="sw-empty">No records are available in this view.</div>}<div className="sw-pagination"><span>{data.length} loaded record{data.length===1?'':'s'}{params.get('q')||params.get('status')?' match these filters':''}</span><div className="sw-tools"><button className="sw-btn" disabled={page<=1} onClick={()=>setPage(n=>n-1)}>Previous</button><span>Page {page} of {Math.max(1,Math.ceil(data.length/20))}</span><button className="sw-btn" disabled={page*20>=data.length} onClick={()=>setPage(n=>n+1)}>Next</button></div></div></>;
  };
  const preview=s=>{
    const site=parent==='O12';const title=site?(form.Heading||form['Agency name']||dataset.data?.value?.agency_name):(form['Property name / listing title']||form['Property name']||record?.title);
    const body=site?(form['Body text']||''):(form['Property description']||record?.description);
    return <article className="sw-preview"><span className="sw-badge">Unpublished preview</span><h2>{title||'Enter a title to preview'}</h2><p className="sw-content-text">{body||'Complete the relevant information in the editing screen.'}</p>{!site&&record?.images?.[0]&&<img src={record.images[0]} alt={record.title||'Property'}/>}<p className="sw-help">This preview does not publish or approve the record. Public content, photographs, dates and exact location must pass the publication workflow.</p>{actions(s)}</article>;
  };
  const dashboard=()=>{
    const d=dataset.data||{};const metrics=[['Active properties','properties_active','O02'],['New leads','leads_new','O04'],['Open inspections','inspections_open','O07'],['Open tasks','tasks_open','O08'],['Customers','customers','O03'],['Active requirements','requirements_active','O05'],['Sold records','properties_sold','O02'],['Leased records','properties_leased','O02']];
    return <><div className="sw-stats">{metrics.map(([label,key,target])=><Link className="sw-stat" to={href(target)} key={key}><span>{label}</span><strong>{dataset.loading?'…':d[key]??'—'}</strong><small>Existing summary · final verification/scope rules pending</small></Link>)}</div><div className="sw-card"><h2>Recent leads and follow-up</h2><p className="sw-help">Open Leads for current requests, assigned staff and follow-up. The final recent-lead, source and overdue-task summaries will use the shared workflow.</p><div className="sw-tools"><Link className="sw-btn" to={href('O04')}>Open leads</Link><Link className="sw-btn" to={href('O08')}>Open tasks</Link></div>{actions(byKey.O01)}</div></>;
  };
  const pipeline=s=><><div className="sw-board">{['new','contacted','qualified','converted','lost'].map(stage=>{const records=filterRows.filter(r=>String(r.status).toLowerCase()===stage);return <section className="sw-column" key={stage}><h2>{stage[0].toUpperCase()+stage.slice(1)} ({records.length})</h2>{records.map(r=><button className="sw-lead-card" key={recordId(r)} onClick={()=>openRecord(r)}><b>{recordName(r)}</b><span>{r.source||'Source not recorded'}</span><span>{r.assigned_agent_id||'Unassigned'}</span><span>{dateText(r.created_at)}</span><span>Open lead →</span></button>)}{!records.length&&<p className="sw-help">No loaded leads at this stage.</p>}</section>;})}</div>{actions(s)}</>;
  const permissions=s=><><div className="sw-card"><h2>Staff account</h2><RecordDetails record={record} family="users"/></div><div className="sw-card"><h2>Role and access proposal</h2><div className="sw-fields">{[['Roles','multi','', 'R'],['Record scope','select','', 'R'],['Change reason','textarea','', 'C']].map(f=><Field key={f[0]} screen={s} field={f} value={form[f[0]]||''} change={change} lookup={cache}/>)}</div><div className="sw-table-scroll"><table className="sw-table"><thead><tr><th>Capability</th><th>Current authority</th><th>Proposed access</th></tr></thead><tbody>{['Customer records','Submission review','Identity verification','Property authority','Publication','Reports','Export','User administration','Website content'].map(cap=><tr key={cap}><td>{cap}</td><td>{record?.permissions?textValue(record.permissions[slug(cap)]):'Not supplied by the existing account service'}</td><td><select aria-label={`Proposed access ${cap}`} disabled><option>Awaiting permission integration</option></select></td></tr>)}</tbody></table></div><p className="sw-help">Role, explicit capability and assignment checks will be enforced together. This screen cannot grant permissions, suspend accounts or start recovery.</p>{actions(s)}</div></>;
  const handoffs=s=>{
    const enc=encodeURIComponent;const adv=record?.advertiser_reference||params.get('advertiserRef');const sub=record?.submission_reference||params.get('submissionRef');const listing=record?.listing_reference||params.get('listingRef');const B='/admin/property-advertising';
    const links=[['Advertiser profile',adv?`${B}/advertisers/${enc(adv)}`:null,`${B}/advertisers`],['Identity review',adv?`${B}/advertisers/${enc(adv)}/identity`:null,`${B}/advertisers`],['Submission review',sub?`${B}/submissions/${enc(sub)}`:null,`${B}/submissions`],['Property authority',sub?`${B}/authority/${enc(sub)}`:null,`${B}/submissions`],['Publication',listing?`${B}/publications/${enc(listing)}`:null,`${B}/publications`],['Listing lifecycle',listing?`${B}/lifecycle/${enc(listing)}`:null,`${B}/lifecycle`],['Sale Progression',null,`${B}/sale-progression`]];
    return <><div className="sw-table-scroll"><table className="sw-table"><thead><tr><th>Review / outcome</th><th>Linked record</th><th>Working queue</th></tr></thead><tbody>{links.map(([label,detail,queue])=><tr key={label}><td>{label}</td><td>{detail?<Link to={detail}>Open linked record</Link>:'No related reference supplied'}</td><td><Link to={queue}>Open {label.toLowerCase()} queue</Link></td></tr>)}</tbody></table></div><p className="sw-help">These links use the existing review screens. A walk-in customer does not require an advertiser login. Missing record links must be resolved through the shared record model; no advertiser reference is invented.</p>{actions(s)}</>;
  };
  const mainReports=s=><><div className="sw-fields">{[['Customer services','reportdetail','Leads, requirements, inspections, tasks and verified outcomes'],['Advertising','advertisingreport','Advertiser verification, submission review, publication and lifecycle'],['Market intelligence','marketreport','Source health and evidence coverage']].map(([label,target,desc])=><div className="sw-card" key={label}><h2>{label}</h2><p className="sw-help">{desc}</p><Link className="sw-btn" to={href(target)}>Open report</Link></div>)}</div>{actions(s)}</>;
  const content=s=>{
    if(s.kind==='dashboard')return dashboard();
    if(s.kind==='pipeline')return pipeline(s);
    if(s.key==='O06')return <div className="sw-card"><h2>Select a requirement</h2><label className="sw-field"><span>Customer requirement</span><select value={params.get('requirementId')||''} onChange={e=>setFilter('requirementId',e.target.value)}><option value="">Select a saved requirement</option>{collection.map(r=><option value={recordId(r)} key={recordId(r)}>{r.customer_name||recordName(r)} · {recordId(r)}</option>)}</select></label><p className="sw-help">No matching run has been performed. Eligibility, scores, reasons and saved shortlists will be connected through the shared matching workflow.</p>{table(s,[],false)}{actions(s)}</div>;
    if(s.kind==='permissions')return permissions(s);
    if(s.key==='handoffs')return <div className="sw-card">{handoffs(s)}</div>;
    if(s.key==='O13')return mainReports(s);
    if(s.key==='reportdetail')return <div className="sw-card"><h2>Current stored summary</h2><dl className="sw-definitions">{Object.entries(dataset.data||{}).filter(([,v])=>typeof v==='number').map(([k,v])=><div className="sw-definition" key={k}><dt>{k.replaceAll('_',' ')}</dt><dd>{v}</dd></div>)}</dl><p className="sw-help">The detailed service, staff, period and verified-outcome breakdown awaits report integration. Current counts are from the existing summary service.</p>{actions(s)}</div>;
    if(s.key==='advertisingreport'||s.key==='marketreport')return <div className="sw-card"><h2>{s.title}</h2><p className="sw-empty">The detailed report connection is pending. No report results have been generated.</p><Link className="sw-btn" to={s.key==='advertisingreport'?'/admin/property-advertising':'/admin/market'}>Open current {s.key==='advertisingreport'?'advertising':'market'} overview</Link>{actions(s)}</div>;
    if(s.key==='reportonly')return <div className="sw-card"><h2>Reports access</h2><p>Access to reports shall be independent of Users & Permissions, Website Content & Settings and Locations.</p><p className="sw-help">This screen describes the reports-only access path. It does not change the current staff member’s permissions or simulate a restricted account.</p>{actions(s)}</div>;
    if(s.kind==='states')return <div className="sw-card"><h2>{s.key==='nomatch'?'Matching result states':'Interface state examples'}</h2><div className="sw-ui-states">{(s.key==='nomatch'?['Brief incomplete','No eligible matches','Matching request failed']:['Loading','No eligible records','Validation failed','Request failed','Access denied or missing record','Session expired or stale version']).map(t=><div className="sw-card" key={t}><h3>{t}</h3><p>{s.key==='nomatch'?'A matching run has not been performed in this screen.':'Example state for interface review; it is not the result of a current action.'}</p></div>)}</div>{actions(s)}</div>;
    if(s.kind==='preview')return <div className="sw-card">{preview(s)}</div>;
    if(s.kind==='map')return <div className="sw-card"><h2>Place the exact property marker</h2><p className="sw-help">Search for the property and move the marker. The selected coordinates are held in the editing form; publication and saving remain separate.</p>{fields(s)}<button className="sw-btn primary" onClick={()=>setMapOpen(true)}><MapPin size={16}/> Open interactive property map</button>{actions(s)}</div>;
    if(['form','media'].includes(s.kind))return <form className="sw-card" onSubmit={e=>e.preventDefault()} aria-label={s.title}>{fields(s)}{s.key==='propertymedia'&&<p className="sw-help">Photograph selection, primary-image selection and ordering work within this form. Files are not uploaded or optimised until the secure media workflow is connected.</p>}{actions(s)}</form>;
    if(s.kind==='list'){
      const isMain=s.key===parent;
      const detail=['customerdetail','propertydetail','leaddetail'].includes(s.key);
      const empty=['matchdetail','onlineauthority','dispatchresult','duplicate','importpreview','importresult','shortlist','invite','recoverresult','contenthistory','locationuse','exportresult'].includes(s.key);
      const communication=s.key==='communications';
      const users=s.key==='externalaccounts'?collection.filter(r=>r.account_category!=='STAFF'):s.key==='O10'?collection.filter(r=>r.account_category==='STAFF'):filterRows;
      return <div className="sw-card">{detail?<RecordDetails record={record} family={rtype}/>:null}{(isMain||s.key==='externalaccounts')&&filters()}{communication?(related.loading?<p>Loading communication history…</p>:related.error?<p className="sw-error" role="alert">{related.error}</p>:table(s,related.rows,false)):detail?<p className="sw-help">Use the linked workflow actions below. Related activity is shown only when the shared service provides linked records.</p>:table(s,empty?[]:users,!empty)}{empty&&<p className="sw-help">This view is connected for screen navigation. Its decision results or linked records await business-workflow integration.</p>}{actions(s)}</div>;
    }
    return null;
  };
  if(params.get('mode')==='records')return <div className="staff-ws"><div className="sw-title"><div><h1>{byKey[parent].title} record tools</h1><p className="sw-help">Existing connected record actions. The new screen workflow is available separately for review.</p></div><button className="sw-btn" onClick={()=>{const q=new URLSearchParams(params);q.delete('mode');navigate(`${location.pathname}?${q}`);}}>Back to workspace</button></div>{children}</div>;
  if(!valid)return <section className="staff-ws"><h1>Screen unavailable</h1><p>The requested screen does not belong to this menu.</p><Link className="sw-btn" to={byKey[parent].route}>Return to {byKey[parent].title}</Link></section>;
  const base=isPopup?byKey[from]||byKey[parent]:screen;
  return <div className="staff-ws" data-testid="staff-screen-workspace" data-screen={screen.key}>
    <div className="sw-title"><div><div className="sw-crumb"><Link to={byKey[parent].route}>{byKey[parent].title}</Link>{screen.key!==parent&&<> <ChevronRight className="inline" size={11}/> {screen.title}</>}</div><h1>{isPopup?base.title:screen.title}</h1></div><div className="sw-tools">{screen.key!==parent&&<button className="sw-btn" onClick={()=>go(parent)}><ArrowLeft size={14}/> Back to {byKey[parent].title}</button>}<button className="sw-btn" onClick={openTools}>Record tools</button><button className="sw-btn" aria-label="Refresh records" onClick={dataset.refresh}><RefreshCw size={15}/></button></div></div>
    <p className="sw-notice" role="note"><b>Screen layout review.</b> Menus, forms, previews and dialogs are connected. New save, approval, messaging and export actions await business-workflow integration. Use Record tools for existing connected actions.</p>
    <div className="sw-related"><label htmlFor="workflow-screen">Workflow screens</label><select id="workflow-screen" className="sw-screen-select" aria-label="Open workflow screen" value={screen.key} onChange={e=>go(e.target.value)}>{screens.filter(s=>s.parent===parent).map(s=><option key={s.key} value={s.key}>{s.title}</option>)}</select><span className="sw-badge">{screen.group}</span>{dirty&&<span className="sw-pending">Unsaved form changes · held in this workspace</span>}</div>
    {rid&&<p className="sw-context">Record context: {rtype} / {rid}{record?' · '+recordName(record):' · No loaded record matches this reference'}</p>}
    {dataset.error&&<div className="sw-card"><p className="sw-error" role="alert">Records could not be loaded: {dataset.error}</p><button className="sw-btn" onClick={dataset.refresh}>Retry loading records</button></div>}
    {dataset.loading&&<p role="status">Loading current records…</p>}
    {notice&&<p className="sw-error" role="alert">{notice}</p>}
    {content(base)}
    {isPopup&&<Popup title={screen.title} onClose={closePopup}><p className="sw-modal-note">Review this decision. Confirmation is disabled until its workflow is connected.</p><form onSubmit={e=>e.preventDefault()}>{fields(screen)}{screen.key==='unsaved'&&<p className="sw-help">Keep editing retains the in-memory form. Save Draft is not yet connected.</p>}{actions(screen)}</form></Popup>}
    <MapPickerDialog open={mapOpen} onOpenChange={setMapOpen} initialCoords={form.Latitude!==undefined&&form.Longitude!==undefined?`${form.Latitude},${form.Longitude}`:''} city={record?.city||''} suburb={record?.suburb||''} province={record?.province||''} onConfirm={coords=>{const [lat,lng]=coords.split(',').map(Number);change('Latitude',lat);change('Longitude',lng);}}/>
    {pendingNavigation&&<Popup title="Leave unsaved form changes" onClose={()=>setPendingNavigation(null)}><p>Your new form changes have not been saved. Record tools use their own connected forms.</p><div className="sw-actions"><button className="sw-btn primary" onClick={()=>setPendingNavigation(null)}>Keep editing</button><button className="sw-btn" onClick={()=>{setDirty(false);navigate(pendingNavigation);setPendingNavigation(null);}}>Open record tools</button></div></Popup>}
  </div>;
}
