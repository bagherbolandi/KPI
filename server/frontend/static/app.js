/* KPI-MS SPA — React (UMD) + htm, no build step */
const { useState, useEffect, useRef, useCallback, createContext, useContext } = React;

/* allow string `style="a:b;c:d"` attributes by converting to React style objects */
const _ce = React.createElement;
function styleToObj(s){
  const o={};
  s.split(";").forEach(r=>{
    const i=r.indexOf(":"); if(i<0) return;
    const k=r.slice(0,i).trim(); let v=r.slice(i+1).trim();
    if(!k) return;
    o[k.replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=v;
  });
  return o;
}
function h(type, props, ...children){
  if(props && typeof props.style === "string") props={...props, style:styleToObj(props.style)};
  /* لنگرهای عملیاتی بدون href در برخی مرورگرها/موتورها باعث ناوبری می‌شوند؛
     اینجا به دکمه‌مانند ایمن تبدیل می‌شوند */
  if(type === "a" && props && typeof props.onClick === "function" && props.href === undefined){
    const fn = props.onClick;
    props = {...props, href: "#", role: "button",
      onClick: (e) => { if(e && e.preventDefault) e.preventDefault(); return fn(e); }};
  }
  return _ce(type, props, ...children);
}
const html = htm.bind(h);

/* ---------------- helpers ---------------- */
const FA = "۰۱۲۳۴۵۶۷۸۹";
const fa = (v) => (v === null || v === undefined || v === "") ? "—" :
  String(v).replace(/[0-9]/g, d => FA[+d]);
const pct = (v) => v === null || v === undefined ? "—" : fa(v) + "٪";
const fmt = (v) => v === null || v === undefined ? "—" :
  (typeof v === "number" ? fa(Number.isInteger(v) ? v : v.toFixed(1)) : fa(v));
const STATUS = { green:{t:"مطلوب",c:"green"}, yellow:{t:"نیازمند توجه",c:"yellow"},
                 red:{t:"بحرانی",c:"red"}, null:{t:"بدون داده",c:"gray"} };
const STATE_FA = { draft:"پیش‌نویس", submitted:"ثبت‌شده (منتظر بررسی)", qc_reviewed:"بررسی کیفیت‌شده",
                   approved:"تأیید نهایی", rejected:"رد شده" };
const clsStatus = (s) => (STATUS[s]||STATUS.null).c;

/* ---------------- offline-parity helpers ---------------- */
const canDo = (u, k) => !!(u && Array.isArray(u.permissions) && u.permissions.includes(k));
const periodLbl = (n) => (n === null || n === undefined) ? "—"
  : fa(`${Math.floor(n/12)}/${String(n%12+1).padStart(2,"0")}`);
const per = (v) => (v === null || v === undefined) ? "—" : pct(Math.round(v*1000)/10);
const ACTION_STATE = {planned:"برنامه‌ریزی‌شده", in_progress:"در حال اجرا", done:"انجام‌شده", canceled:"لغو‌شده"};
const RULE_LBL = {always:"همیشه", behind:"عقب‌ماندگی از برنامه", below:"کمتر از حد", above:"بیشتر از حد"};
const LINK_MODE = {maintain:"حفظ وضعیت فعلی", improve:"بهبود نسبت به خط مبنا"};
const GSTATUS = {"شروع نشده":"gray", "عقب از برنامه":"red", "محقق‌شده":"green",
  "نیازمند تکمیل یا بازنگری داده":"yellow", "در مسیر":"blue",
  "بایگانی":"gray", "بدون شاخص مرتبط":"gray"};
const gcls = (s) => GSTATUS[s] || "gray";
const todayJ = () => { const d = new Date(); return {y: d.getFullYear(), m: d.getMonth()+1}; };
/* آیا ماه شمسی، دوره سررسید این تناوب است؟ (هم‌ارز effective.is_due) */
const isDue = (freq, month) => {
  switch (freq) {
    case "quarterly": return month % 3 === 0;
    case "semiannual": return month === 6 || month === 12;
    case "annual": return month === 12;
    case "event": return true;
    default: return true;   /* monthly */
  }
};

/* ---------------- API ---------------- */
const detailMsg = (d) => {
  const x = d && d.detail;
  if (typeof x === "string") return x;
  if (Array.isArray(x)) return x.map(e => e && e.msg ? `${(e.loc||[]).slice(-1)[0]}: ${e.msg}` : String(e)).join("؛ ");
  return "خطای سرور";
};

const api = {
  token: localStorage.getItem("kpi_token") || null,
  async req(path, opts={}) {
    const h = opts.headers || {};
    if (this.token) h["Authorization"] = "Bearer " + this.token;
    if (opts.json) { h["Content-Type"]="application/json"; opts.body=JSON.stringify(opts.json); delete opts.json; }
    const r = await fetch("/api"+path, {...opts, headers:h});
    if (r.status === 401) { this.token=null; localStorage.removeItem("kpi_token"); location.hash="#/login"; throw new Error("unauthorized"); }
    if (!r.ok) { let d; try{d=await r.json()}catch{d={detail:"خطای سرور"}} throw new Error(detailMsg(d)); }
    const ct = r.headers.get("content-type")||"";
    return ct.includes("json") ? r.json() : r;
  },
  get(p){return this.req(p)},
  post(p,body){return this.req(p,{method:"POST",json:body})},
  put(p,body){return this.req(p,{method:"PUT",json:body})},
  del(p){return this.req(p,{method:"DELETE"})},
  async login(u,p){
    const b=new URLSearchParams({username:u,password:p});
    const r=await fetch("/api/auth/login",{method:"POST",body:b});
    if(!r.ok){const d=await r.json();throw new Error(detailMsg(d))}
    const d=await r.json(); this.token=d.access_token; localStorage.setItem("kpi_token",d.access_token); return d;
  },
  async download(path, filename){
    const r=await this.req(path); const blob=await r.blob();
    const url=URL.createObjectURL(blob); const a=document.createElement("a");
    a.href=url; a.download=filename; a.click(); URL.revokeObjectURL(url);
  }
};

/* ---------------- toast ---------------- */
let _setToast=()=>{};
const toast=(msg,type="ok")=>_setToast({msg,type,id:Date.now()});

/* ---------------- UI atoms ---------------- */
const Spinner=()=>html`<div class="spinner"></div>`;
const StatusBadge=({s})=>{const o=STATUS[s]||STATUS.null;return html`<span class="badge ${o.c}"><span class="dot ${o.c}"></span>${o.t}</span>`};
const Card=({title,extra,children,cls=""})=>html`<div class="card ${cls}">${title&&html`<div class="hd"><h3>${title}</h3><div class="spacer"></div>${extra}</div>`}<div class="bd">${children}</div></div>`;
const Stat=({lbl,val,sub,tone="blue",ic})=>html`<div class="card stat ${tone}"><div class="ic">${ic}</div><div class="lbl">${lbl}</div><div class="val">${val}</div>${sub&&html`<div class="sub">${sub}</div>`}</div>`;
function Progress({v,color}){const c=color||(v>=85?"var(--green)":v>=60?"var(--yellow)":"var(--red)");
  return html`<div class="progress"><div class="fill" style=${{width:Math.min(100,Math.max(3,v||0))+"%",background:c}}></div></div>`}

function Modal({title,onClose,children,footer,wide}){
  return html`<div class="modal-ov" onClick=${e=>{if(e.target.classList.contains('modal-ov'))onClose()}}>
    <div class="modal ${wide?'wide':''}"><div class="mh"><h3>${title}</h3><button class="x" onClick=${onClose}>×</button></div>
    <div class="mb">${children}</div>${footer&&html`<div class="mf">${footer}</div>`}</div></div>`;
}

/* ---------------- Chart wrapper ---------------- */
Chart.defaults.font.family = "Vazir";
Chart.defaults.color = "#475569";
function ChartBox({type,data,options,cls=""}){
  const ref=useRef(); const inst=useRef();
  useEffect(()=>{
    if(inst.current) inst.current.destroy();
    inst.current=new Chart(ref.current,{type,data,options:{responsive:true,maintainAspectRatio:false,...options}});
    return ()=>{if(inst.current)inst.current.destroy()};
  },[JSON.stringify(data),JSON.stringify(options),type]);
  return html`<div class="chart-box ${cls}"><canvas ref=${ref}></canvas></div>`;
}
const C={green:"#16a34a",yellow:"#d97706",red:"#dc2626",blue:"#2563eb",navy:"#12315b",gray:"#cbd5e1"};

/* ---------------- Auth context ---------------- */
const Ctx=createContext();
const useApp=()=>useContext(Ctx);

/* ================= LOGIN / RECOVERY / FORCE CHANGE ================= */
function PwInput({label,value,onChange,autoFocus}){
  const [show,setShow]=useState(false);
  return html`<div class="field"><label>${label}</label>
    <div style="display:flex;gap:6px">
      <input type=${show?"text":"password"} value=${value} onChange=${e=>onChange(e.target.value)}
             placeholder="••••••••" autoFocus=${autoFocus}/>
      <button type="button" class="btn btn-ghost btn-sm" onClick=${()=>setShow(!show)}>${show?"پنهان":"نمایش"}</button>
    </div></div>`;
}

function Login(){
  const [mode,setMode]=useState("login");            /* login | recover | setup */
  const [u,setU]=useState(""),[p,setP]=useState(""),[err,setErr]=useState(""),[busy,setBusy]=useState(false);
  const [confirmTxt,setConfirmTxt]=useState(""),[setupToken,setSetupToken]=useState(""),
        [nw,setNw]=useState(""),[nw2,setNw2]=useState("");
  const {reload}=useApp();
  const submit=async(e)=>{e.preventDefault();setErr("");setBusy(true);
    try{const r=await api.login(u,p);
      if(r.must_change){await reload();return;}            /* App shows force-change */
      await reload();location.hash="#/dashboard";}
    catch(ex){setErr(ex.message)}finally{setBusy(false)}};
  const quick=(un)=>{setU(un);setP("Passw0rd!")};
  const doRecover=async(e)=>{e.preventDefault();setErr("");setBusy(true);
    try{const r=await api.post("/auth/admin-recovery",{confirm:confirmTxt});
      setSetupToken(r.setup_token);setMode("setup");}
    catch(ex){setErr(ex.message)}finally{setBusy(false)}};
  const doSetup=async(e)=>{e.preventDefault();setErr("");setBusy(true);
    try{const r=await api.post("/auth/complete-setup",{token:setupToken,password:nw,password2:nw2});
      api.token=r.access_token;localStorage.setItem("kpi_token",r.access_token);
      await reload();location.hash="#/dashboard";}
    catch(ex){setErr(ex.message)}finally{setBusy(false)}};

  if(mode==="recover") return html`<div class="login-wrap"><div class="login-card">
    <div class="login-logo">🔑</div>
    <h1>بازیابی دسترسی مدیر</h1>
    <div class="sub">بدون حذف داده‌ها؛ فقط رمز حساب admin بازنشانی می‌شود</div>
    <form onSubmit=${doRecover}>
      <div style="font-size:12.5px;color:var(--muted);margin-bottom:10px;line-height:1.9">
        برای تأیید، عبارت <b class="mono">RESET</b> را تایپ کنید. سپس رمز جدیدی برای <b>admin</b> تعیین می‌کنید.
        این عملیات در «لاگ تغییرات» ثبت می‌شود.</div>
      <div class="field"><label>عبارت تأیید</label>
        <input value=${confirmTxt} onChange=${e=>setConfirmTxt(e.target.value)} placeholder="RESET" autoFocus/></div>
      ${err&&html`<div class="err">${err}</div>`}
      <button class="btn btn-red btn-block" disabled=${busy}>${busy?"در حال انجام…":"بازنشانی رمز مدیر"}</button>
    </form>
    <div style="text-align:center;margin-top:12px"><a onClick=${()=>{setMode("login");setErr("")}}>بازگشت به ورود</a></div>
  </div></div>`;

  if(mode==="setup") return html`<div class="login-wrap"><div class="login-card">
    <div class="login-logo">✓</div>
    <h1>تعیین رمز جدید مدیر</h1>
    <div class="sub">رمز باید حداقل ۸ کاراکتر و شامل حرف و عدد باشد</div>
    <form onSubmit=${doSetup}>
      <${PwInput} label="رمز جدید" value=${nw} onChange=${setNw} autoFocus=${true}/>
      <${PwInput} label="تکرار رمز جدید" value=${nw2} onChange=${setNw2}/>
      ${err&&html`<div class="err">${err}</div>`}
      <button class="btn btn-primary btn-block" disabled=${busy}>${busy?"در حال ذخیره…":"ذخیره رمز و ورود"}</button>
    </form>
    <div style="text-align:center;margin-top:12px"><a onClick=${()=>{setMode("login");setErr("")}}>بازگشت به ورود</a></div>
  </div></div>`;

  return html`<div class="login-wrap"><div class="login-card">
    <div class="login-logo">K</div>
    <h1>سامانه پایش شاخص‌های عملکرد</h1>
    <div class="sub">KPI Management & Monitoring System</div>
    <form onSubmit=${submit}>
      <div class="field"><label>نام کاربری</label><input value=${u} onChange=${e=>setU(e.target.value)} placeholder="admin" autoFocus/></div>
      <${PwInput} label="رمز عبور" value=${p} onChange=${setP}/>
      ${err&&html`<div class="err">${err}</div>`}
      <button class="btn btn-primary btn-block" disabled=${busy}>${busy?"در حال ورود…":"ورود به سامانه"}</button>
    </form>
    <div style="text-align:center;margin-top:10px;font-size:12px"><a onClick=${()=>{setMode("recover");setErr("")}}>رمز مدیر را فراموش کرده‌اید؟</a></div>
    <div class="hint-box">
      <b>حساب‌های نمونه</b> (رمز همه: <span class="mono">Passw0rd!</span>)<br/>
      <a onClick=${()=>quick("admin")}>admin</a> مدیر سیستم ·
      <a onClick=${()=>quick("ceo")}>ceo</a> مدیریت ارشد ·
      <a onClick=${()=>quick("quality")}>quality</a> مدیر کیفیت ·
      <a onClick=${()=>quick("owner_pln")}>owner_pln</a> مالک فرایند
      <div style="margin-top:6px;color:var(--muted)">در نخستین ورود با رمز پیش‌فرض، تغییر رمز اجباری است.</div>
    </div>
  </div></div>`;
}

/* ورود با رمز پیش‌فرض ⇒ تغییر اجباری رمز (offline renderForceChange) */
function ForceChange(){
  const {user,reload,logout}=useApp();
  const [cur,setCur]=useState(""),[nw,setNw]=useState(""),[nw2,setNw2]=useState(""),
        [err,setErr]=useState(""),[busy,setBusy]=useState(false);
  const submit=async(e)=>{e.preventDefault();setErr("");
    if(nw!==nw2){setErr("رمز جدید و تکرار آن یکسان نیست");return}
    if(nw.length<8||!/[A-Za-z]/.test(nw)||!/\d/.test(nw)){
      setErr("رمز باید حداقل ۸ کاراکتر و شامل حرف و عدد باشد");return}
    setBusy(true);
    try{const r=await api.post("/auth/change-password",{current_password:cur,new_password:nw});
      api.token=r.access_token;localStorage.setItem("kpi_token",r.access_token);
      toast("رمز عبور تغییر کرد");await reload();location.hash="#/dashboard";}
    catch(ex){setErr(ex.message)}finally{setBusy(false)}};
  return html`<div class="login-wrap"><div class="login-card">
    <div class="login-logo">🔒</div>
    <h1>تغییر رمز عبور</h1>
    <div class="sub">${user.full_name} · برای ادامه، رمز پیش‌فرض را تغییر دهید</div>
    <form onSubmit=${submit}>
      <${PwInput} label="رمز فعلی" value=${cur} onChange=${setCur} autoFocus=${true}/>
      <${PwInput} label="رمز جدید" value=${nw} onChange=${setNw}/>
      <${PwInput} label="تکرار رمز جدید" value=${nw2} onChange=${setNw2}/>
      <div style="font-size:11.5px;color:var(--muted);margin:-4px 0 10px">
        حداقل ۸ کاراکتر، شامل حرف و عدد، متفاوت از رمز فعلی و رمزهای پیش‌فرض.</div>
      ${err&&html`<div class="err">${err}</div>`}
      <button class="btn btn-primary btn-block" disabled=${busy}>${busy?"در حال ذخیره…":"ذخیره و ادامه"}</button>
    </form>
    <div style="text-align:center;margin-top:12px"><a onClick=${logout}>خروج از حساب</a></div>
  </div></div>`;
}

/* ================= DASHBOARD (Executive) ================= */
function Dashboard(){
  const {year,company}=useApp();
  const [ov,setOv]=useState(null),[procs,setProcs]=useState([]),[strat,setStrat]=useState([]),
        [trend,setTrend]=useState(null),[pareto,setPareto]=useState([]),[crit,setCrit]=useState([]),
        [rank,setRank]=useState(null),[radar,setRadar]=useState(null);
  useEffect(()=>{const c=company?`&company=${company}`:"";
    (async()=>{
    setOv(await api.get(`/dashboard/overview?year=${year}${c}`));
    setProcs(await api.get(`/dashboard/by-process?year=${year}${c}`));
    setStrat(await api.get(`/dashboard/strategic?year=${year}${c}`));
    setTrend(await api.get(`/dashboard/trend?months=12${c}`));
    setPareto(await api.get(`/dashboard/pareto?year=${year}${c}`));
    setCrit(await api.get(`/dashboard/critical?year=${year}${c}`));
    setRank(await api.get(`/dashboard/top?year=${year}&limit=8${c}`));
    setRadar(await api.get(`/dashboard/radar?year=${year}${c}`));
  })().catch(e=>toast(e.message,"err"))},[year,company]);
  if(!ov) return html`<${Spinner}/>`;
  const cc=ov.counts;
  const donut={labels:["مطلوب (سبز)","نیازمند توجه (زرد)","بحرانی (قرمز)","بدون داده"],
    datasets:[{data:[cc.green,cc.yellow,cc.red,cc.nodata],backgroundColor:[C.green,C.yellow,C.red,C.gray],borderWidth:2,borderColor:"#fff"}]};
  const procBar={labels:procs.map(p=>p.name),datasets:[
    {label:"سبز",data:procs.map(p=>p.counts.green),backgroundColor:C.green,stack:"s"},
    {label:"زرد",data:procs.map(p=>p.counts.yellow),backgroundColor:C.yellow,stack:"s"},
    {label:"قرمز",data:procs.map(p=>p.counts.red),backgroundColor:C.red,stack:"s"}]};
  const trendData=trend&&{labels:trend.labels,datasets:[{label:"میانگین تحقق سازمان (٪)",data:trend.achievement,
    borderColor:C.blue,backgroundColor:"rgba(37,99,235,.12)",fill:true,tension:.35,pointRadius:3,borderWidth:2.5}]};
  const paretoData={labels:pareto.map(p=>p.name),datasets:[
    {type:"bar",label:"شاخص‌های بحرانی (وزنی)",data:pareto.map(p=>p.value),backgroundColor:C.red,order:2},
    {type:"line",label:"درصد تجمعی",data:pareto.map(p=>p.cum_pct),borderColor:C.navy,backgroundColor:C.navy,yAxisID:"y1",tension:.3,order:1,pointRadius:3}]};

  return html`<div>
    <div class="grid g-4">
      <${Stat} lbl="کل شاخص‌ها" val=${fa(ov.total)} sub=${`${fa(ov.measured)} شاخص دارای داده`} tone="navy" ic="📊"/>
      <${Stat} lbl="میانگین تحقق اهداف" val=${pct(ov.avg_achievement)} sub=${`تحقق وزنی: ${pct(ov.weighted_achievement)}`} tone=${ov.avg_achievement>=85?"green":ov.avg_achievement>=60?"yellow":"red"} ic="🎯"/>
      <${Stat} lbl="شاخص‌های مطلوب" val=${fa(cc.green)} sub=${pct(ov.green_pct)+" از کل"} tone="green" ic="✅"/>
      <${Stat} lbl="شاخص‌های بحرانی" val=${fa(cc.red)} sub=${fa(cc.yellow)+" شاخص نیازمند توجه"} tone="red" ic="⚠️"/>
    </div>

    <div class="grid g-3" style="margin-top:16px">
      <${Card} title="توزیع وضعیت شاخص‌ها">
        <${ChartBox} type="doughnut" data=${donut} options=${{cutout:"62%",plugins:{legend:{position:"bottom",labels:{padding:14,font:{size:12}}}}}}/>
      <//>
      <${Card} title="روند ۱۲ ماهه تحقق سازمان" cls="">
        ${trendData&&html`<${ChartBox} type="line" data=${trendData} options=${{scales:{y:{suggestedMax:100,ticks:{callback:v=>fa(v)}}},plugins:{legend:{display:false}}}}/>`}
      <//>
      <${Card} title="شاخص‌های استراتژیک">
        <div class="tbl-wrap" style="max-height:290px;overflow-y:auto">
        <table class="tbl"><tbody>
        ${strat.map(s=>html`<tr key=${s.code}>
          <td><div style="font-weight:700;font-size:12.5px">${s.name}</div><div style="color:var(--muted);font-size:11px">${s.process}</div></td>
          <td style="text-align:center">${s.achievement!==null?pct(s.achievement):"—"}</td>
          <td><${StatusBadge} s=${s.status}/></td></tr>`)}
        </tbody></table></div>
      <//>
    </div>

    <div class="grid g-2" style="margin-top:16px">
      <${Card} title="وضعیت شاخص‌ها به تفکیک فرایند">
        <${ChartBox} type="bar" data=${procBar} options=${{indexAxis:"y",scales:{x:{stacked:true,ticks:{callback:v=>fa(v)}},y:{stacked:true,ticks:{font:{size:10}}}},plugins:{legend:{position:"bottom"}}}}/>
      <//>
      <${Card} title="نمودار پارتو — تمرکز شاخص‌های بحرانی">
        <${ChartBox} type="bar" data=${paretoData} options=${{scales:{y:{ticks:{callback:v=>fa(v)}},y1:{position:"left",max:100,grid:{drawOnChartArea:false},ticks:{callback:v=>fa(v)+"٪"}},x:{ticks:{font:{size:10}}}},plugins:{legend:{position:"bottom"}}}}/>
      <//>
    </div>

    <div class="section-title">🏆 رتبه‌بندی عملکرد فرایندها</div>
    <${Card}>
      <div class="tbl-wrap"><table class="tbl">
        <thead><tr><th>رتبه</th><th>فرایند</th><th>تعداد شاخص</th><th>میانگین تحقق</th><th>توزیع وضعیت</th><th></th></tr></thead>
        <tbody>${procs.map((p,i)=>html`<tr key=${p.code}>
          <td><b>${fa(i+1)}</b></td>
          <td><b>${p.name}</b> <span class="mono" style="color:var(--muted)">${p.code}</span></td>
          <td>${fa(p.total)}</td>
          <td style="min-width:150px"><div style="display:flex;align-items:center;gap:8px"><${Progress} v=${p.avg_achievement}/><b>${pct(p.avg_achievement)}</b></div></td>
          <td><span class="badge green">${fa(p.counts.green)}</span> <span class="badge yellow">${fa(p.counts.yellow)}</span> <span class="badge red">${fa(p.counts.red)}</span></td>
          <td><a onClick=${()=>location.hash="#/kpis?process="+p.process_id}>مشاهده شاخص‌ها ›</a></td>
        </tr>`)}</tbody>
      </table></div>
    <//>

    <div class="grid g-2" style="margin-top:16px">
      <${Card} title="🏆 برترین شاخص‌ها (تحقق بدون سقف)" extra=${html`<span class="chip">${fa(rank?rank.top.length:0)} مورد</span>`}>
        ${!rank?html`<${Spinner}/>`:rank.top.length===0?html`<div class="empty">داده‌ای برای رتبه‌بندی نیست</div>`:html`
        <div class="tbl-wrap" style="max-height:280px;overflow-y:auto"><table class="tbl"><tbody>
          ${rank.top.map((r,i)=>html`<tr key=${r.code}>
            <td style="width:34px"><b>${fa(i+1)}</b></td>
            <td><div style="font-weight:700;font-size:12.5px">${r.name}</div>
                <div style="color:var(--muted);font-size:11px">${r.code} · واقعی ${fmt(r.actual)} / هدف ${fmt(r.target)}</div></td>
            <td style="text-align:center;color:var(--green);font-weight:700">${pct(r.value)}</td></tr>`)}
        </tbody></table></div>`}
      <//>
      <${Card} title="⚠️ ضعیف‌ترین شاخص‌ها" extra=${html`<span class="chip">نیازمند اقدام</span>`}>
        ${!rank?html`<${Spinner}/>`:rank.bottom.length===0?html`<div class="empty">داده‌ای نیست</div>`:html`
        <div class="tbl-wrap" style="max-height:280px;overflow-y:auto"><table class="tbl"><tbody>
          ${rank.bottom.map((r,i)=>html`<tr key=${r.code}>
            <td style="width:34px"><b>${fa(i+1)}</b></td>
            <td><div style="font-weight:700;font-size:12.5px">${r.name}</div>
                <div style="color:var(--muted);font-size:11px">${r.code} · واقعی ${fmt(r.actual)} / هدف ${fmt(r.target)}</div></td>
            <td style="text-align:center;color:var(--red);font-weight:700">${pct(r.value)}</td></tr>`)}
        </tbody></table></div>`}
      <//>
    </div>

    ${radar&&radar.items.length>1&&html`<div class="grid g-2" style="margin-top:16px">
      <${Card} title="🕸 نمودار راداری معاونت‌ها">
        <${ChartBox} type="radar" data=${{labels:radar.items.map(r=>r.name.replace("معاونت ","")),
          datasets:[{label:"میانگین تحقق (٪)",data:radar.items.map(r=>r.value),
            borderColor:C.blue,backgroundColor:"rgba(37,99,235,.18)",pointBackgroundColor:C.blue,borderWidth:2}]}}
          options=${{scales:{r:{suggestedMin:40,suggestedMax:100,ticks:{callback:v=>fa(v),stepSize:15,backdropColor:"transparent"},pointLabels:{font:{size:11}}}}}}/>
      <//>
      <${Card} title="📌 خلاصه معاونت‌ها">
        <div class="tbl-wrap" style="max-height:300px;overflow-y:auto"><table class="tbl">
          <thead><tr><th>معاونت</th><th>تعداد شاخص</th><th>میانگین تحقق</th><th></th></tr></thead>
          <tbody>${radar.items.map(r=>html`<tr key=${r.name}>
            <td><b>${r.name}</b></td><td>${fa(r.n)}</td>
            <td style="min-width:140px"><div style="display:flex;align-items:center;gap:8px"><${Progress} v=${r.value}/><b>${pct(r.value)}</b></div></td>
            <td>${html`<${StatusBadge} s=${r.value>=85?"green":r.value>=60?"yellow":"red"}/>`}</td>
          </tr>`)}</tbody></table></div>
      <//>
    </div>`}

    ${crit.length>0&&html`<div class="section-title">⚠️ شاخص‌های بحرانی سازمان (${fa(crit.length)} مورد)</div>
    <${Card}><div class="tbl-wrap"><table class="tbl">
      <thead><tr><th>کد</th><th>شاخص</th><th>فرایند</th><th>هدف</th><th>واقعی</th><th>تحقق</th><th>اهمیت</th></tr></thead>
      <tbody>${crit.slice(0,12).map(c=>html`<tr key=${c.code}>
        <td class="mono">${c.code}</td><td>${c.name}</td><td>${c.process}</td>
        <td>${fmt(c.target)}</td><td style="color:var(--red);font-weight:700">${fmt(c.actual)}</td>
        <td>${c.achievement!==null?pct(c.achievement):"—"}</td>
        <td>${c.importance==="key"?html`<span class="chip key">کلیدی</span>`:html`<span class="chip">عملیاتی</span>`}</td>
      </tr>`)}</tbody></table></div><//>`}
  </div>`;
}

/* ================= PROCESSES ================= */
function Processes(){
  const {year}=useApp(); const [procs,setProcs]=useState([]);
  useEffect(()=>{api.get(`/dashboard/by-process?year=${year}`).then(setProcs).catch(e=>toast(e.message,"err"))},[year]);
  return html`<div class="grid g-3">
    ${procs.map(p=>html`<${Card} key=${p.code} title=${p.name} extra=${html`<span class="mono chip">${p.code}</span>`}>
      <div class="gauge"><div class="big" style=${{color:p.avg_achievement>=85?C.green:p.avg_achievement>=60?C.yellow:C.red}}>${pct(p.avg_achievement)}</div>
        <div style="color:var(--muted);font-size:12px">میانگین تحقق (${fa(p.total)} شاخص)</div></div>
      <div style="margin:12px 0"><${Progress} v=${p.avg_achievement}/></div>
      <div style="display:flex;justify-content:space-around;text-align:center;font-size:12px">
        <div><div style="font-size:20px;font-weight:800;color:var(--green)">${fa(p.counts.green)}</div>مطلوب</div>
        <div><div style="font-size:20px;font-weight:800;color:var(--yellow)">${fa(p.counts.yellow)}</div>توجه</div>
        <div><div style="font-size:20px;font-weight:800;color:var(--red)">${fa(p.counts.red)}</div>بحرانی</div>
      </div>
      <button class="btn btn-ghost btn-block btn-sm" style="margin-top:14px" onClick=${()=>location.hash="#/kpis?process="+p.process_id}>مشاهده شاخص‌ها</button>
    <//>`)}
  </div>`;
}

/* ================= KPI LIST ================= */
function KpiList({params}){
  const {meta,user,company}=useApp();
  const [kpis,setKpis]=useState(null),[q,setQ]=useState(""),[proc,setProc]=useState(params.process||""),
        [imp,setImp]=useState(""),[detail,setDetail]=useState(null),[procs,setProcs]=useState([]);
  const load=useCallback(()=>{
    let u=`/kpis?`; if(proc)u+=`process_id=${proc}&`; if(imp)u+=`importance=${imp}&`; if(q)u+=`q=${encodeURIComponent(q)}&`;
    if(company)u+=`company=${company}&`;
    api.get(u).then(setKpis).catch(e=>toast(e.message,"err"));
  },[proc,imp,q,company]);
  useEffect(()=>{load()},[load]);
  useEffect(()=>{api.get("/org/processes").then(setProcs)},[]);
  return html`<div>
    <div class="toolbar">
      <div class="searchbox"><span class="si">🔍</span><input type="text" placeholder="جستجوی شاخص یا کد…" value=${q} onInput=${e=>setQ(e.target.value)}/></div>
      ${user.role_code!=="process_owner"&&html`<select value=${proc} onChange=${e=>setProc(e.target.value)}>
        <option value="">همه فرایندها</option>${procs.map(p=>html`<option key=${p.id} value=${p.id}>${p.name}</option>`)}</select>`}
      <select value=${imp} onChange=${e=>setImp(e.target.value)}><option value="">همه سطوح اهمیت</option>
        <option value="key">کلیدی</option><option value="operational">عملیاتی</option></select>
      <div class="spacer"></div>
      <span class="chip">${kpis?fa(kpis.length):"…"} شاخص</span>
    </div>
    ${!kpis?html`<${Spinner}/>`:html`<${Card}><div class="tbl-wrap"><table class="tbl">
      <thead><tr><th>کد</th><th>نام شاخص</th><th>فرایند</th><th>جهت</th><th>هدف</th><th>حد هشدار</th><th>تناوب</th><th>اهمیت</th><th></th></tr></thead>
      <tbody>${kpis.map(k=>html`<tr key=${k.id}>
        <td class="mono">${k.code}</td>
        <td><b>${k.name}</b> ${k.is_strategic&&html`<span class="chip strat">استراتژیک</span>`}</td>
        <td>${k.process_name}</td>
        <td class="tag-dir" title=${k.direction==="up"?"بیشتر بهتر":"کمتر بهتر"}>${k.direction==="up"?"🔺":"🔻"}</td>
        <td>${fmt(k.target)}${k.uom==="percent"?"٪":""}</td>
        <td>${fmt(k.warning)}${k.uom==="percent"?"٪":""}</td>
        <td>${meta.frequencies[k.frequency]||k.frequency}</td>
        <td>${k.importance==="key"?html`<span class="chip key">کلیدی</span>`:html`<span class="chip">عملیاتی</span>`}</td>
        <td><a onClick=${()=>setDetail(k)}>روند و جزئیات ›</a></td>
      </tr>`)}</tbody></table></div><//>`}
    ${detail&&html`<${KpiDetail} kpi=${detail} onClose=${()=>setDetail(null)}/>`}
  </div>`;
}

/* تحلیل آماری چندساله (offline analysisRange): معناداری تفاوت سال‌ها و روند */
function AnalysisPanel({kpi}){
  const {meta}=useApp();
  const cy = meta.current_year, cm = meta.current_month;
  const [fy,setFy]=useState(cy-2),[fm,setFm]=useState(1),[ty,setTy]=useState(cy),[tm,setTm]=useState(cm);
  const [alpha,setAlpha]=useState("0.05"),[method,setMethod]=useState("paired"),
        [res,setRes]=useState(null),[busy,setBusy]=useState(false),[err,setErr]=useState("");
  const years=meta.years&&meta.years.length?meta.years:[cy-2,cy-1,cy];
  const run=async()=>{setBusy(true);setErr("");
    try{const d=await api.get(`/kpis/${kpi.id}/analysis?fy=${fy}&fm=${fm}&ty=${ty}&tm=${tm}&alpha=${alpha}&method=${method}`);
      if(d.error){setErr(d.error);setRes(null)}else setRes(d);}
    catch(ex){setErr(ex.message)}finally{setBusy(false)}};
  useEffect(()=>{run()},[kpi.id]);
  const chart=res&&{labels:res.labels,datasets:[
    {label:"عملکرد واقعی",data:res.points.map(p=>p.actual),borderColor:C.blue,
     backgroundColor:"rgba(37,99,235,.10)",fill:true,tension:.3,pointRadius:2.5,borderWidth:2},
    {label:"هدف",data:res.labels.map(()=>kpi.target),borderColor:C.green,borderDash:[6,4],
     pointRadius:0,borderWidth:1.6}]};
  return html`<div>
    <div class="toolbar" style="flex-wrap:wrap;gap:8px">
      <span class="chip">از</span>
      <select value=${fy} onChange=${e=>setFy(+e.target.value)}>${years.map(y=>html`<option key=${y} value=${y}>${fa(y)}</option>`)}</select>
      <select value=${fm} onChange=${e=>setFm(+e.target.value)}>${meta.months.map(m=>html`<option key=${m.num} value=${m.num}>${m.name}</option>`)}</select>
      <span class="chip">تا</span>
      <select value=${ty} onChange=${e=>setTy(+e.target.value)}>${years.map(y=>html`<option key=${y} value=${y}>${fa(y)}</option>`)}</select>
      <select value=${tm} onChange=${e=>setTm(+e.target.value)}>${meta.months.map(m=>html`<option key=${m.num} value=${m.num}>${m.name}</option>`)}</select>
      <select value=${alpha} onChange=${e=>setAlpha(e.target.value)} title="سطح معناداری">
        <option value="0.05">α = ۰٫۰۵</option><option value="0.01">α = ۰٫۰۱</option><option value="0.1">α = ۰٫۱۰</option></select>
      <select value=${method} onChange=${e=>setMethod(e.target.value)} title="روش مقایسه">
        <option value="paired">مقایسه زوجی (ماه‌های مشترک)</option>
        <option value="welch">ولش (مستقل)</option></select>
      <button class="btn btn-primary btn-sm" disabled=${busy} onClick=${run}>${busy?"در حال تحلیل…":"تحلیل"}</button>
      <div class="spacer"></div>
      ${res&&html`<span class="chip">${fa(res.points.length)} نقطه داده</span>`}
    </div>
    ${err&&html`<div class="err" style="margin-bottom:10px">${err}</div>`}
    ${!res&&!err&&html`<${Spinner}/>`}
    ${res&&html`<div>
      ${chart&&html`<${ChartBox} type="line" data=${chart} options=${{scales:{y:{ticks:{callback:v=>fa(v)}}},plugins:{legend:{position:"bottom"}}}}/>`}
      <div class="grid g-3" style="margin-top:14px">
        ${res.summary.map(x=>html`<div class="card" key=${x.year} style="padding:12px 14px">
          <div style="display:flex;align-items:center;gap:8px"><b>سال ${fa(x.year)}</b><div class="spacer"></div>
            <span class="chip">${fa(x.n)} دوره</span></div>
          <div class="kv"><span>میانگین</span><b>${fmt(x.mean)}</b></div>
          <div class="kv"><span>انحراف معیار</span><b>${fmt(x.std)}</b></div>
          <div class="kv"><span>میانگین تحقق هدف</span><b>${per(x.mean_ach)}</b></div>
          <div class="kv"><span>ماه‌های دارای داده</span><b style="font-size:11.5px">${x.months&&x.months.length?x.months.join("، "):"—"}</b></div>
        </div>`)}
      </div>
      <div class="section-title" style="margin-top:16px">مقایسه زوجی سال‌ها (اصلاح هولم)</div>
      ${res.pairs.length===0?html`<div class="empty">برای مقایسه، حداقل دو سال با داده لازم است</div>`:html`
      <${Card}><div class="tbl-wrap"><table class="tbl">
        <thead><tr><th>مقایسه</th><th>تعداد</th><th>میانگین الف</th><th>میانگین ب</th><th>اختلاف</th><th>t</th><th>p</th><th>p اصلاح‌شده</th><th>تصمیم</th></tr></thead>
        <tbody>${res.pairs.map(p=>html`<tr key=${p.yearA+"-"+p.yearB}>
          <td><b>${fa(p.yearA)}</b> ↔ <b>${fa(p.yearB)}</b></td>
          <td>${fa(p.nA)} / ${fa(p.nB)}</td><td>${fmt(p.meanA)}</td><td>${fmt(p.meanB)}</td>
          <td style="color:${(p.delta||0)>=0?"var(--green)":"var(--red)"}">${fmt(p.delta)}</td>
          <td class="mono">${p.state==="ok"?fmt(p.t):"—"}</td><td class="mono">${p.state==="ok"?fmt(p.p):"—"}</td>
          <td class="mono"><b>${p.state==="ok"?fmt(p.adjusted):"—"}</b></td>
          <td style="font-size:12px">${p.state==="ok"?p.decision:(p.state==="insufficient"?"داده کافی برای آزمون نیست":"پراکندگی نامعتبر")}</td></tr>`)}
        </tbody></table></div><//>`}
      ${res.trend&&html`<div class="hint-box" style="margin-top:14px;border-right:4px solid ${
          res.trend.state==="derived"?"var(--yellow)":
          res.trend.title==="بازنگری پیشنهاد می‌شود"?"var(--red)":res.trend.state==="ok"?"var(--green)":"var(--yellow)"}">
        <b>بازنگری روند:</b> ${res.trend.title}${res.trend.reason?" — "+res.trend.reason:""}
        ${res.trend.state==="ok"&&html`<span style="color:var(--muted)"> (شیب: ${fmt(res.trend.slope)}، t=${fmt(res.trend.t)}، p=${fmt(res.trend.p)}، سطح اطمینان ${fa(res.confidence)}٪)</span>`}
      </div>`}
      ${res.mgt_warning&&html`<div class="hint-box" style="margin-top:10px;border-right:4px solid var(--yellow)">${res.mgt_warning}</div>`}
    </div>`}
  </div>`;
}

function KpiDetail({kpi,onClose}){
  const {meta}=useApp(); const [tr,setTr]=useState(null),[entries,setEntries]=useState([]);
  useEffect(()=>{
    api.get(`/dashboard/trend?kpi_id=${kpi.id}&months=24`).then(setTr);
    api.get(`/entries?kpi_id=${kpi.id}`).then(setEntries);
  },[kpi.id]);
  const uomLbl=meta.uoms[kpi.uom]||kpi.uom;
  const data=tr&&{labels:tr.labels,datasets:[
    {label:"عملکرد واقعی",data:tr.actual,borderColor:C.blue,backgroundColor:"rgba(37,99,235,.1)",tension:.3,fill:true,pointRadius:3,borderWidth:2.5},
    {label:"هدف",data:tr.target,borderColor:C.green,borderDash:[6,4],pointRadius:0,borderWidth:2}]};
  return html`<${Modal} wide title=${kpi.name} onClose=${onClose} footer=${html`<button class="btn btn-ghost" onClick=${onClose}>بستن</button>`}>
    <div class="grid g-2" style="margin-bottom:16px">
      <div>
        <div class="kv"><span>کد شاخص</span><b class="mono">${kpi.code}</b></div>
        <div class="kv"><span>فرایند</span><b>${kpi.process_name}</b></div>
        <div class="kv"><span>واحد اندازه‌گیری</span><b>${uomLbl}</b></div>
        <div class="kv"><span>جهت مطلوب</span><b>${kpi.direction==="up"?"🔺 بیشتر بهتر":"🔻 کمتر بهتر"}</b></div>
        <div class="kv"><span>تناوب پایش</span><b>${meta.frequencies[kpi.frequency]}</b></div>
      </div>
      <div>
        <div class="kv"><span>مقدار هدف</span><b>${fmt(kpi.target)}</b></div>
        <div class="kv"><span>حد هشدار</span><b style="color:var(--yellow)">${fmt(kpi.warning)}</b></div>
        <div class="kv"><span>حد بحرانی</span><b style="color:var(--red)">${fmt(kpi.critical)}</b></div>
        <div class="kv"><span>وزن / اهمیت</span><b>${fa(kpi.weight)} · ${kpi.importance==="key"?"کلیدی":"عملیاتی"}</b></div>
        <div class="kv"><span>معیار پذیرش (اصل)</span><b>${kpi.acceptance_text||"—"}</b></div>
      </div>
    </div>
    ${kpi.definition&&html`<div style="background:var(--gray-bg);padding:11px 14px;border-radius:10px;font-size:12.5px;margin-bottom:8px"><b>تعریف:</b> ${kpi.definition}</div>`}
    ${kpi.formula&&html`<div style="background:var(--gray-bg);padding:11px 14px;border-radius:10px;font-size:12.5px;margin-bottom:16px"><b>روش محاسبه:</b> ${kpi.formula}</div>`}
    <div class="section-title" style="margin-top:6px">📈 روند عملکرد در برابر هدف</div>
    ${data?html`<${ChartBox} type="line" data=${data} options=${{scales:{y:{ticks:{callback:v=>fa(v)}}},plugins:{legend:{position:"bottom"}}}}/>`:html`<${Spinner}/>`}
    <div class="section-title" style="margin-top:18px">🧮 تحلیل آماری چندساله</div>
    <${AnalysisPanel} kpi=${kpi}/>
  <//>`;
}

/* ================= DATA ENTRY ================= */
function DataEntry(){
  const {meta,user,year,company}=useApp();
  const [kpis,setKpis]=useState([]),[sel,setSel]=useState(null),[month,setMonth]=useState(meta.current_month),
        [entries,setEntries]=useState([]),[edit,setEdit]=useState(null);
  const load=()=>{
    api.get("/kpis"+(company?`?company=${company}`:"")).then(setKpis);
    api.get(`/entries?year=${year}`).then(setEntries);
  };
  useEffect(load,[year,company]);
  const emap={}; entries.forEach(e=>emap[e.kpi_id+"_"+e.month]=e);
  return html`<div>
    <div class="toolbar">
      <b>دوره ثبت:</b>
      <select value=${month} onChange=${e=>setMonth(+e.target.value)}>${meta.months.map(m=>html`<option key=${m.num} value=${m.num}>${m.name}</option>`)}</select>
      <span class="chip">${fa(year)}</span>
      <div class="spacer"></div>
      <span class="chip">${fa(kpis.filter(k=>isDue(k.frequency,month)).length)} شاخص در سررسید این دوره</span>
      <span style="font-size:12px;color:var(--muted)">فرایند شما: <b>${user.process_name||"—"}</b></span>
    </div>
    <div class="hint-box" style="margin-bottom:12px">
      فقط دوره‌های منطبق با تناوب پایش هر شاخص باید ثبت شوند (ماهانه: هر ماه · سه‌ماهه: ماه ۳،۶،۹،۱۲ ·
      شش‌ماهه: ماه ۶ و ۱۲ · سالانه: ماه ۱۲). ثبت دوره خارج از سررسید به‌عنوان داده معتبر در تحلیل‌ها لحاظ نمی‌شود.
    </div>
    <${Card}><div class="tbl-wrap"><table class="tbl">
      <thead><tr><th>کد</th><th>شاخص</th><th>هدف</th><th>عملکرد (${meta.months[month-1].name})</th><th>تحقق</th><th>وضعیت</th><th>گردش کار</th><th></th></tr></thead>
      <tbody>${kpis.map(k=>{const e=emap[k.id+"_"+month];const due=isDue(k.frequency,month);return html`<tr key=${k.id} style=${due?"":"opacity:.62"}>
        <td class="mono">${k.code}</td>
        <td>${k.name}${due?"":html` <span class="chip" title="این ماه در تناوب پایش شاخص نیست">بدون سررسید</span>`}</td>
        <td>${fmt(k.target)}${k.uom==="percent"?"٪":""}</td>
        <td>${e&&e.actual!==null?html`<b>${fmt(e.actual)}</b>`:html`<span style="color:var(--muted)">ثبت نشده</span>`}</td>
        <td>${e&&e.achievement!==null?pct(Math.round(e.achievement*100)):"—"}</td>
        <td>${e?html`<${StatusBadge} s=${e.status}/>`:"—"}</td>
        <td><span class="chip">${e?STATE_FA[e.workflow_state]:"—"}</span></td>
        <td><button class="btn btn-sm btn-primary" onClick=${()=>setEdit({kpi:k,entry:e})}>${e?"ویرایش":"ثبت"}</button></td>
      </tr>`})}</tbody>
    </table></div><//>
    ${edit&&html`<${EntryForm} kpi=${edit.kpi} entry=${edit.entry} year=${year} month=${month} meta=${meta} user=${user}
        onClose=${()=>setEdit(null)} onSaved=${()=>{setEdit(null);load()}}/>`}
  </div>`;
}

function EntryForm({kpi,entry,year,month,meta,user,onClose,onSaved}){
  const [f,setF]=useState({actual:entry?.actual??"",comment:entry?.comment||"",deviation_cause:entry?.deviation_cause||"",corrective_action:entry?.corrective_action||""});
  const [busy,setBusy]=useState(false);
  const set=(k,v)=>setF(s=>({...s,[k]:v}));
  const save=async(submit)=>{setBusy(true);try{
    const e=await api.post("/entries",{kpi_id:kpi.id,year,month,actual:f.actual===""?null:+f.actual,
      comment:f.comment,deviation_cause:f.deviation_cause,corrective_action:f.corrective_action});
    if(submit){await api.post("/entries/workflow",{entry_id:e.id,action:"submit"});toast("ثبت و برای بررسی ارسال شد");}
    else toast("ذخیره شد");
    onSaved();
  }catch(ex){toast(ex.message,"err")}finally{setBusy(false)}};
  const canWf=entry&&user.role_code!=="executive";
  const wf=async(action,reason)=>{setBusy(true);try{
    await api.post("/entries/workflow",{entry_id:entry.id,action,reason:reason||""});toast("انجام شد");onSaved();
  }catch(ex){toast(ex.message,"err")}finally{setBusy(false)}};
  return html`<${Modal} title=${`ثبت عملکرد — ${kpi.name}`} onClose=${onClose}
    footer=${html`<${React.Fragment}>
      <button class="btn btn-ghost" disabled=${busy} onClick=${()=>save(false)}>ذخیره پیش‌نویس</button>
      ${(user.role_code==="process_owner"||user.role_code==="admin")&&html`<button class="btn btn-primary" disabled=${busy} onClick=${()=>save(true)}>ذخیره و ارسال برای تأیید</button>`}
    <//>`}>
    <div style="background:var(--gray-bg);padding:10px 14px;border-radius:10px;margin-bottom:14px;font-size:12.5px">
      دوره: <b>${meta.months[month-1].name} ${fa(year)}</b> · هدف: <b>${fmt(kpi.target)}</b> · جهت: <b>${kpi.direction==="up"?"🔺 بیشتر بهتر":"🔻 کمتر بهتر"}</b>
      · تناوب: <b>${meta.frequencies[kpi.frequency]||kpi.frequency}</b>
      ${entry&&html` · وضعیت گردش‌کار: <span class="chip">${STATE_FA[entry.workflow_state]}</span>`}
      ${!isDue(kpi.frequency,month)&&html`<div style="color:var(--amber,#b45309);margin-top:6px">
        ⚠ این ماه در تناوب پایش این شاخص نیست؛ ثبت داده در دوره خارج از سررسید در تحلیل‌ها معتبر شمرده نمی‌شود.</div>`}
      ${kpi.is_mgt&&html`<div style="color:var(--muted);margin-top:6px">
        ℹ شاخص تجمعی (MGT): مقدار موثر از جمع داده‌های شاخص‌های پایه محاسبه می‌شود.</div>`}
    </div>
    <div class="form-grid">
      <div class="field full"><label>مقدار واقعی عملکرد (${meta.uoms[kpi.uom]})</label><input type="number" step="any" value=${f.actual} onInput=${e=>set("actual",e.target.value)}/></div>
      <div class="field full"><label>توضیحات عملکرد</label><textarea rows="2" value=${f.comment} onInput=${e=>set("comment",e.target.value)}></textarea></div>
      <div class="field full"><label>علت انحراف (در صورت وجود)</label><textarea rows="2" value=${f.deviation_cause} onInput=${e=>set("deviation_cause",e.target.value)}></textarea></div>
      <div class="field full"><label>اقدام اصلاحی</label><textarea rows="2" value=${f.corrective_action} onInput=${e=>set("corrective_action",e.target.value)}></textarea></div>
    </div>
    ${canWf&&(user.role_code==="quality"||user.role_code==="admin")&&["submitted","qc_reviewed"].includes(entry.workflow_state)&&html`
      <div style="border-top:1px solid var(--line);margin-top:12px;padding-top:12px;display:flex;gap:8px">
        <button class="btn btn-sm btn-green" onClick=${()=>wf("approve")}>تأیید نهایی</button>
        <button class="btn btn-sm btn-amber" onClick=${()=>wf("review")}>ثبت بررسی کیفیت</button>
        <button class="btn btn-sm btn-red" onClick=${()=>{const r=prompt("دلیل رد:");if(r)wf("reject",r)}}>رد</button>
      </div>`}
  <//>`;
}

/* ================= APPROVALS (inbox) ================= */
function Approvals(){
  const {user}=useApp(); const [items,setItems]=useState(null),[edit,setEdit]=useState(null);
  const load=()=>api.get("/entries/inbox").then(setItems).catch(e=>toast(e.message,"err"));
  useEffect(load,[]);
  const act=async(e,action,reason)=>{try{await api.post("/entries/workflow",{entry_id:e.id,action,reason:reason||""});toast("انجام شد");load()}catch(ex){toast(ex.message,"err")}};
  if(!items) return html`<${Spinner}/>`;
  return html`<div>
    <${Card} title=${`کارتابل تأیید — ${fa(items.length)} مورد در انتظار`}>
    ${items.length===0?html`<div class="empty">🎉 موردی در انتظار اقدام شما نیست.</div>`:html`<div class="tbl-wrap"><table class="tbl">
      <thead><tr><th>کد</th><th>شاخص</th><th>دوره</th><th>واقعی</th><th>تحقق</th><th>وضعیت</th><th>گردش‌کار</th><th>اقدام</th></tr></thead>
      <tbody>${items.map(e=>html`<tr key=${e.id}>
        <td class="mono">${e.kpi_code}</td><td>${e.kpi_name}</td><td>${e.period}</td>
        <td><b>${fmt(e.actual)}</b></td><td>${e.achievement!==null?pct(Math.round(e.achievement*100)):"—"}</td>
        <td><${StatusBadge} s=${e.status}/></td>
        <td><span class="chip">${STATE_FA[e.workflow_state]}</span></td>
        <td style="display:flex;gap:6px;flex-wrap:wrap">
          ${(user.role_code==="quality"||user.role_code==="admin")&&html`<${React.Fragment}>
            <button class="btn btn-sm btn-green" onClick=${()=>act(e,"approve")}>تأیید</button>
            <button class="btn btn-sm btn-red" onClick=${()=>{const r=prompt("دلیل رد:");if(r)act(e,"reject",r)}}>رد</button>
          <//>`}
          ${user.role_code==="process_owner"&&html`<button class="btn btn-sm btn-primary" onClick=${()=>setEdit(e)}>ویرایش و ارسال</button>`}
        </td>
      </tr>`)}</tbody>
    </table></div>`}
    <//>
  </div>`;
}

/* ================= KPI MASTER (admin) ================= */
function KpiMaster(){
  const {meta}=useApp(); const [kpis,setKpis]=useState(null),[procs,setProcs]=useState([]),[edit,setEdit]=useState(null),[q,setQ]=useState("");
  const load=()=>api.get("/kpis"+(q?`?q=${encodeURIComponent(q)}`:"")).then(setKpis);
  useEffect(load,[q]); useEffect(()=>{api.get("/org/processes").then(setProcs)},[]);
  const del=async(k)=>{const r=prompt(`حذف شاخص «${k.name}».\nدلیل حذف را وارد کنید:`);if(!r)return;
    try{await api.del(`/kpis/${k.id}?reason=${encodeURIComponent(r)}`);toast("حذف شد");load()}catch(ex){toast(ex.message,"err")}};
  if(!kpis) return html`<${Spinner}/>`;
  return html`<div>
    <div class="toolbar">
      <div class="searchbox"><span class="si">🔍</span><input type="text" placeholder="جستجو…" value=${q} onInput=${e=>setQ(e.target.value)}/></div>
      <div class="spacer"></div>
      <button class="btn btn-primary" onClick=${()=>setEdit({})}>+ شاخص جدید</button>
    </div>
    <${Card}><div class="tbl-wrap"><table class="tbl">
      <thead><tr><th>کد</th><th>نام</th><th>فرایند</th><th>هدف</th><th>هشدار</th><th>بحرانی</th><th>وزن</th><th>حالت محاسبه</th><th>عملیات</th></tr></thead>
      <tbody>${kpis.map(k=>html`<tr key=${k.id}>
        <td class="mono">${k.code}</td><td>${k.name}</td><td>${k.process_name}</td>
        <td>${fmt(k.target)}</td><td>${fmt(k.warning)}</td><td>${fmt(k.critical)}</td><td>${fa(k.weight)}</td>
        <td><span class="chip">${k.calc_mode==="achievement"?"درصد تحقق":"بازه‌ای"}</span></td>
        <td style="display:flex;gap:6px"><button class="btn btn-sm btn-ghost" onClick=${()=>setEdit(k)}>ویرایش</button>
          <button class="btn btn-sm btn-red" onClick=${()=>del(k)}>حذف</button></td>
      </tr>`)}</tbody>
    </table></div><//>
    ${edit&&html`<${KpiForm} kpi=${edit} procs=${procs} meta=${meta} onClose=${()=>setEdit(null)} onSaved=${()=>{setEdit(null);load()}}/>`}
  </div>`;
}

function KpiForm({kpi,procs,meta,onClose,onSaved}){
  const isNew=!kpi.id;
  const [f,setF]=useState({name:kpi.name||"",process_id:kpi.process_id||(procs[0]&&procs[0].id),uom:kpi.uom||"percent",
    direction:kpi.direction||"up",frequency:kpi.frequency||"monthly",target:kpi.target??"",warning:kpi.warning??"",critical:kpi.critical??"",
    weight:kpi.weight??1,importance:kpi.importance||"operational",is_strategic:kpi.is_strategic||false,
    definition:kpi.definition||"",formula:kpi.formula||"",acceptance_text:kpi.acceptance_text||"",calc_mode:kpi.calc_mode||"achievement",
    th_green:kpi.th_green??"",th_yellow:kpi.th_yellow??"",reason:""});
  const [busy,setBusy]=useState(false); const set=(k,v)=>setF(s=>({...s,[k]:v}));
  const save=async()=>{
    if(!isNew&&!f.reason){toast("ثبت دلیل تغییر الزامی است","err");return}
    setBusy(true);try{
      const body={...f,target:+f.target,warning:+f.warning,critical:+f.critical,weight:+f.weight,
        th_green:f.th_green===""?null:+f.th_green,th_yellow:f.th_yellow===""?null:+f.th_yellow};
      if(isNew)await api.post("/kpis",body); else await api.put(`/kpis/${kpi.id}`,body);
      toast("ذخیره شد");onSaved();
    }catch(ex){toast(ex.message,"err")}finally{setBusy(false)}};
  return html`<${Modal} wide title=${isNew?"تعریف شاخص جدید":"ویرایش شاخص "+kpi.code} onClose=${onClose}
    footer=${html`<button class="btn btn-primary" disabled=${busy} onClick=${save}>${busy?"…":"ذخیره"}</button><button class="btn btn-ghost" onClick=${onClose}>انصراف</button>`}>
    <div class="form-grid">
      <div class="field full"><label>نام شاخص *</label><input value=${f.name} onInput=${e=>set("name",e.target.value)}/></div>
      <div class="field"><label>فرایند</label><select value=${f.process_id} onChange=${e=>set("process_id",+e.target.value)}>${procs.map(p=>html`<option key=${p.id} value=${p.id}>${p.name}</option>`)}</select></div>
      <div class="field"><label>واحد اندازه‌گیری</label><select value=${f.uom} onChange=${e=>set("uom",e.target.value)}>${Object.entries(meta.uoms).map(([k,v])=>html`<option key=${k} value=${k}>${v}</option>`)}</select></div>
      <div class="field"><label>جهت مطلوب</label><select value=${f.direction} onChange=${e=>set("direction",e.target.value)}><option value="up">🔺 بیشتر بهتر</option><option value="down">🔻 کمتر بهتر</option></select></div>
      <div class="field"><label>تناوب پایش</label><select value=${f.frequency} onChange=${e=>set("frequency",e.target.value)}>${Object.entries(meta.frequencies).map(([k,v])=>html`<option key=${k} value=${k}>${v}</option>`)}</select></div>
      <div class="field"><label>مقدار هدف *</label><input type="number" step="any" value=${f.target} onInput=${e=>set("target",e.target.value)}/></div>
      <div class="field"><label>حد هشدار</label><input type="number" step="any" value=${f.warning} onInput=${e=>set("warning",e.target.value)}/></div>
      <div class="field"><label>حد بحرانی</label><input type="number" step="any" value=${f.critical} onInput=${e=>set("critical",e.target.value)}/></div>
      <div class="field"><label>وزن</label><input type="number" step="any" value=${f.weight} onInput=${e=>set("weight",e.target.value)}/></div>
      <div class="field"><label>سطح اهمیت</label><select value=${f.importance} onChange=${e=>set("importance",e.target.value)}><option value="key">کلیدی</option><option value="operational">عملیاتی</option></select></div>
      <div class="field"><label>حالت محاسبه وضعیت</label><select value=${f.calc_mode} onChange=${e=>set("calc_mode",e.target.value)}><option value="achievement">درصد تحقق (آستانه‌ای)</option><option value="band">بازه‌ای (هدف/هشدار/بحرانی)</option></select></div>
      <div class="field"><label>استراتژیک؟</label><select value=${f.is_strategic?"1":"0"} onChange=${e=>set("is_strategic",e.target.value==="1")}><option value="0">خیر</option><option value="1">بله</option></select></div>
      <div class="field full"><label>روش محاسبه (فرمول)</label><input value=${f.formula} onInput=${e=>set("formula",e.target.value)}/></div>
      <div class="field full"><label>تعریف شاخص</label><textarea rows="2" value=${f.definition} onInput=${e=>set("definition",e.target.value)}></textarea></div>
      ${!isNew&&html`<div class="field full"><label style="color:var(--red)">دلیل تغییر * (در لاگ ثبت می‌شود)</label><input value=${f.reason} onInput=${e=>set("reason",e.target.value)} placeholder="مثال: بازنگری هدف مطابق مصوبه کمیته"/></div>`}
    </div>
  <//>`;
}

/* ================= ORG STRUCTURE ================= */
function TreeNode({node}){
  return html`<div><div class="node lvl-${node.level}">
    <span>${node.level==="company"?"🏢":node.level==="division"?"🗂️":"⚙️"}</span>
    <b>${node.name}</b> <span class="mono" style="opacity:.7;font-size:11px">${node.code}</span>
    <span class="spacer" style="flex:1"></span>
    ${node.total_kpis>0&&html`<span class="chip">${fa(node.total_kpis)} شاخص</span>`}
  </div>${node.children&&node.children.length>0&&html`<div class="children">${node.children.map(c=>html`<${TreeNode} key=${c.id} node=${c}/>`)}</div>`}</div>`;
}
function Org(){
  const [tree,setTree]=useState(null);
  useEffect(()=>{api.get("/org/tree").then(setTree).catch(e=>toast(e.message,"err"))},[]);
  if(!tree) return html`<${Spinner}/>`;
  return html`<${Card} title="ساختار سازمانی: شرکت ← معاونت ← فرایند ← شاخص">
    <div class="tree">${tree.map(n=>html`<${TreeNode} key=${n.id} node=${n}/>`)}</div>
  <//>`;
}

/* ================= USERS (admin) ================= */
function Users(){
  const [users,setUsers]=useState(null),[roles,setRoles]=useState([]),[procs,setProcs]=useState([]),[edit,setEdit]=useState(null),
        [views,setViews]=useState([]),[roleDefaults,setRoleDefaults]=useState({});
  const load=()=>api.get("/users").then(setUsers);
  useEffect(()=>{load();api.get("/users/roles").then(setRoles);api.get("/org/processes").then(setProcs);
    api.get("/users/views").then(r=>{setViews(r.views);setRoleDefaults(r.role_defaults||{})}).catch(()=>{})},[]);
  const del=async(u)=>{if(!confirm(`حذف کاربر ${u.username}؟`))return;try{await api.del(`/users/${u.id}`);toast("حذف شد");load()}catch(ex){toast(ex.message,"err")}};
  if(!users) return html`<${Spinner}/>`;
  return html`<div>
    <div class="toolbar"><div class="spacer"></div><button class="btn btn-primary" onClick=${()=>setEdit({})}>+ کاربر جدید</button></div>
    <${Card}><div class="tbl-wrap"><table class="tbl">
      <thead><tr><th>نام کاربری</th><th>نام کامل</th><th>نقش</th><th>دسترسی‌ها</th><th>فرایند</th><th>وضعیت</th><th>عملیات</th></tr></thead>
      <tbody>${users.map(u=>html`<tr key=${u.id}>
        <td class="mono">${u.username}</td><td>${u.full_name}</td><td><span class="chip key">${u.role_name}</span></td>
        <td style="font-size:11px;max-width:260px">${(u.permissions||[]).map(k=>html`<span key=${k} class="chip" style="margin:1px">${VIEWLBL[k]||k}</span>`)}
          ${u.must_change?html`<span class="badge yellow">تغییر رمز در ورود بعدی</span>`:""}</td>
        <td>${u.process_name||"—"}</td><td>${u.is_active?html`<span class="badge green">فعال</span>`:html`<span class="badge gray">غیرفعال</span>`}</td>
        <td style="display:flex;gap:6px"><button class="btn btn-sm btn-ghost" onClick=${()=>setEdit(u)}>ویرایش</button>
        ${u.username!=="admin"&&html`<button class="btn btn-sm btn-red" onClick=${()=>del(u)}>حذف</button>`}</td>
      </tr>`)}</tbody>
    </table></div><//>
    ${edit&&html`<${UserForm} u=${edit} roles=${roles} procs=${procs} views=${views} roleDefaults=${roleDefaults}
       onClose=${()=>setEdit(null)} onSaved=${()=>{setEdit(null);load()}}/>`}
    <div class="section-title">🔑 نقش‌ها و سطوح دسترسی</div>
    <div class="grid g-2">${roles.map(r=>html`<${Card} key=${r.code} title=${r.name_fa} extra=${html`<span class="mono chip">${r.code}</span>`}>
      <div style="font-size:12.5px;color:var(--muted)">${r.description}</div><//>`)}</div>
  </div>`;
}
function UserForm({u,roles,procs,views,roleDefaults,onClose,onSaved}){
  const isNew=!u.id;
  const [f,setF]=useState({username:u.username||"",full_name:u.full_name||"",email:u.email||"",password:"",
    role_code:u.role_code||"process_owner",process_id:u.process_id||null,is_active:u.is_active!==false,
    must_change:!!u.must_change,
    permissions:(u.permissions&&u.permissions.length)?u.permissions:((roleDefaults||{})[u.role_code||"process_owner"]||[])});
  const [custom,setCustom]=useState(!!(u.permissions&&u.permissions.length));
  const [busy,setBusy]=useState(false);const set=(k,v)=>setF(s=>({...s,[k]:v}));
  const toggle=(k)=>{setCustom(true);setF(s=>{const p=new Set(s.permissions||[]);
    p.has(k)?p.delete(k):p.add(k);return {...s,permissions:[...p]}})};
  const applyRole=(code)=>{const d=(roleDefaults||{})[code]||[];
    setF(s=>({...s,role_code:code, ...(custom?{}:{permissions:d})}));
    if(!custom)setF(s=>({...s,permissions:d}))};
  const save=async()=>{setBusy(true);try{
    const body={...f,permissions:f.permissions||[]};
    if(isNew)await api.post("/users",body);else await api.put(`/users/${u.id}`,body);
    toast("ذخیره شد");onSaved();
  }catch(ex){toast(ex.message,"err")}finally{setBusy(false)}};
  return html`<${Modal} title=${isNew?"کاربر جدید":"ویرایش کاربر"} onClose=${onClose}
    footer=${html`<button class="btn btn-primary" disabled=${busy} onClick=${save}>ذخیره</button><button class="btn btn-ghost" onClick=${onClose}>انصراف</button>`}>
    <div class="form-grid">
      <div class="field"><label>نام کاربری</label><input value=${f.username} disabled=${!isNew} onInput=${e=>set("username",e.target.value)}/></div>
      <div class="field"><label>نام کامل</label><input value=${f.full_name} onInput=${e=>set("full_name",e.target.value)}/></div>
      <div class="field"><label>ایمیل</label><input value=${f.email} onInput=${e=>set("email",e.target.value)}/></div>
      <div class="field"><label>رمز عبور ${!isNew?"(خالی=بدون تغییر)":""}</label><input type="password" value=${f.password} onInput=${e=>set("password",e.target.value)}/></div>
      <div class="field"><label>نقش</label><select value=${f.role_code} onChange=${e=>applyRole(e.target.value)}>${roles.map(r=>html`<option key=${r.code} value=${r.code}>${r.name_fa}</option>`)}</select></div>
      <div class="field"><label>فرایند (برای مالک فرایند)</label><select value=${f.process_id||""} onChange=${e=>set("process_id",e.target.value?+e.target.value:null)}><option value="">—</option>${procs.map(p=>html`<option key=${p.id} value=${p.id}>${p.name}</option>`)}</select></div>
      <div class="field"><label>وضعیت</label><select value=${f.is_active?"1":"0"} onChange=${e=>set("is_active",e.target.value==="1")}><option value="1">فعال</option><option value="0">غیرفعال</option></select></div>
      <div class="field"><label>تغییر رمز در ورود بعدی</label>
        <select value=${f.must_change?"1":"0"} onChange=${e=>set("must_change",e.target.value==="1")}>
          <option value="0">خیر</option><option value="1">بله (اجباری)</option></select></div>
    </div>
    <div class="section-title" style="margin-top:14px">دسترسی به صفحات</div>
    <div style="display:flex;flex-wrap:wrap;gap:8px">
      ${(views||[]).map(v=>html`<label key=${v.key} style="display:flex;align-items:center;gap:5px;font-size:12px;
          border:1px solid var(--line);padding:5px 9px;border-radius:8px;cursor:pointer;
          background:${(f.permissions||[]).includes(v.key)?"var(--blue-50,#eff6ff)":"transparent"}">
        <input type="checkbox" checked=${(f.permissions||[]).includes(v.key)} onChange=${()=>toggle(v.key)}/>
        ${v.label}</label>`)}
    </div>
    <div style="font-size:11.5px;color:var(--muted);margin-top:8px">
      ${custom?"دسترسی‌ها به‌صورت اختصاصی برای این کاربر ذخیره می‌شود.":"در حال استفاده از دسترسی پیش‌فرض نقش؛ با تغییر هر گزینه، حالت اختصاصی فعال می‌شود."}
    </div>
  <//>`;
}

/* ================= AUDIT LOG ================= */
function Audit(){
  const [rows,setRows]=useState(null),[t,setT]=useState("");
  useEffect(()=>{api.get("/audit?limit=300"+(t?`&entity_type=${t}`:"")).then(setRows).catch(e=>toast(e.message,"err"))},[t]);
  const A={create:"ایجاد",update:"ویرایش",delete:"حذف",submit:"ارسال",review:"بررسی",approve:"تأیید",reject:"رد",
    reopen:"بازگشایی",seed:"بارگذاری داده نمونه",restore:"بازیابی از پشتیبان"};
  const E={kpi:"شاخص",entry:"داده",user:"کاربر",org:"سازمان",setting:"تنظیمات",system:"سیستم",strategy:"استراتژی"};
  return html`<div>
    <div class="pill-row">${[["","همه"],["kpi","شاخص‌ها"],["entry","داده‌ها"],["strategy","استراتژی"],["user","کاربران"],["setting","تنظیمات"],["system","سیستم"]].map(([v,l])=>
      html`<span key=${v} class="pill ${t===v?'active':''}" onClick=${()=>setT(v)}>${l}</span>`)}</div>
    ${!rows?html`<${Spinner}/>`:html`<${Card}><div class="tbl-wrap"><table class="tbl">
      <thead><tr><th>زمان</th><th>کاربر</th><th>موجودیت</th><th>عملیات</th><th>فیلد</th><th>مقدار قبل</th><th>مقدار بعد</th><th>دلیل</th></tr></thead>
      <tbody>${rows.map(r=>html`<tr key=${r.id}>
        <td class="mono" style="font-size:11px">${fa(r.created_at)}</td><td>${r.username}</td>
        <td><span class="chip">${E[r.entity_type]||r.entity_type}</span> <span class="mono" style="font-size:11px">${r.entity_id}</span></td>
        <td>${A[r.action]||r.action}</td><td style="font-size:11.5px">${r.field||"—"}</td>
        <td style="color:var(--red);font-size:11.5px">${r.old_value||"—"}</td>
        <td style="color:var(--green);font-size:11.5px">${r.new_value||"—"}</td>
        <td style="font-size:11.5px">${r.reason||"—"}</td>
      </tr>`)}</tbody></table></div><//>`}
  </div>`;
}

/* ================= REPORTS (offline parity) ================= */
const STATUS_FA = {green:"مطلوب", yellow:"نیازمند توجه", red:"بحرانی", null:"بدون داده"};

function Reports(){
  const {year,meta,company}=useApp();
  const [from,setFrom]=useState(`${meta.current_year}/01/01`);
  const [to,setTo]=useState(`${meta.current_year}/12/29`);
  const [basis,setBasis]=useState("avg");
  const [onlyApproved,setOnlyApproved]=useState(false);
  const [range,setRange]=useState(null),[busy,setBusy]=useState(false),[err,setErr]=useState("");
  const [nd,setNd]=useState(null),[ndKind,setNdKind]=useState(""),[ndBusy,setNdBusy]=useState(false);
  const [scope,setScope]=useState("active");
  const co=company?`&company=${company}`:"";

  const run=async()=>{setBusy(true);setErr("");
    try{setRange(await api.get(`/reports/range?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&basis=${basis}&approved_only=${onlyApproved}${co}`));}
    catch(ex){setErr(ex.message);setRange(null)}finally{setBusy(false)}};
  const runNd=async()=>{setNdBusy(true);
    try{setNd(await api.get(`/reports/no-data?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&approved_only=${onlyApproved}&kind=${ndKind}${co}`));}
    catch(ex){toast(ex.message,"err")}finally{setNdBusy(false)}};
  const dl=(path,name)=>api.download(path,name).then(()=>toast("فایل دانلود شد")).catch(e=>toast(e.message,"err"));
  const qs=`from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`;

  return html`<div>
    <${Card} title="📆 گزارش دوره‌ای (بازه زمانی دلخواه)" extra=${html`<span class="chip">مبنای ارزیابی: ${basis==="avg"?"میانگین دوره":"آخرین مقدار"}</span>`}>
      <div class="toolbar" style="flex-wrap:wrap;gap:10px">
        <div class="field" style="margin:0"><label>از تاریخ</label>
          <input value=${from} onInput=${e=>setFrom(e.target.value)} placeholder="1405/01/01" style="width:120px"/></div>
        <div class="field" style="margin:0"><label>تا تاریخ</label>
          <input value=${to} onInput=${e=>setTo(e.target.value)} placeholder="1405/12/29" style="width:120px"/></div>
        <div class="field" style="margin:0"><label>مبنا</label>
          <select value=${basis} onChange=${e=>setBasis(e.target.value)}>
            <option value="avg">میانگین دوره</option><option value="last">آخرین مقدار</option></select></div>
        <label style="display:flex;align-items:center;gap:6px;font-size:12.5px;margin-top:14px">
          <input type="checkbox" checked=${onlyApproved} onChange=${e=>setOnlyApproved(e.target.checked)}/>
          فقط داده‌های تأییدشده</label>
        <div class="spacer"></div>
        <button class="btn btn-primary" disabled=${busy} onClick=${run} style="margin-top:14px">${busy?"در حال محاسبه…":"محاسبه گزارش"}</button>
      </div>
      <div style="font-size:11.5px;color:var(--muted);margin-top:4px">
        قالب تاریخ: سال/ماه/روز شمسی (مثال ${fa("1405/01/01")}). دامنه حداکثر ۲۰ سال و فقط داخل سال‌های دارای داده پذیرفته می‌شود.
      </div>
      ${err&&html`<div class="err" style="margin-top:10px">${err}</div>`}
      ${range&&html`<div style="margin-top:14px">
        <div class="grid g-4">
          <${Stat} lbl="شاخص‌های در دامنه" val=${fa(range.agg.total)} sub=${`${fa(range.agg.all_with_data)} شاخص دارای داده`} tone="navy" ic="📊"/>
          <${Stat} lbl="میانگین تحقق" val=${pct(range.agg.avg*100)} sub=${`وزنی: ${pct(range.agg.weighted*100)}`} tone=${range.agg.avg>=0.85?"green":range.agg.avg>=0.6?"yellow":"red"} ic="🎯"/>
          <${Stat} lbl="توزیع وضعیت" val=${`${fa(range.agg.counts.green)} / ${fa(range.agg.counts.yellow)} / ${fa(range.agg.counts.red)}`} sub="سبز / زرد / قرمز" tone="yellow" ic="🎨"/>
          <${Stat} lbl="دوره گزارش" val=${`${range.from}`} sub=${`تا ${range.to}`} tone="blue" ic="📅"/>
        </div>
        <div class="toolbar" style="margin:12px 0">
          <span class="chip">${fa(range.rows.length)} ردیف</span>
          <div class="spacer"></div>
          <button class="btn btn-sm btn-green" onClick=${()=>dl(`/reports/range.xlsx?${qs}&basis=${basis}&approved_only=${onlyApproved}${co}`,`Range_${year}.xlsx`)}>⬇ Excel</button>
          <button class="btn btn-sm btn-ghost" onClick=${()=>dl(`/reports/range.csv?${qs}&basis=${basis}&approved_only=${onlyApproved}${co}`,`Range_${year}.csv`)}>⬇ CSV</button>
          <button class="btn btn-sm btn-red" onClick=${()=>dl(`/reports/range.pdf?${qs}&basis=${basis}&approved_only=${onlyApproved}${co}`,`Range_${year}.pdf`)}>⬇ PDF</button>
        </div>
        <div class="tbl-wrap" style="max-height:420px;overflow:auto"><table class="tbl">
          <thead><tr><th>کد</th><th>شاخص</th><th>فرایند</th><th>هدف</th><th>واقعی</th><th>تحقق</th><th>تعداد دوره</th><th>وضعیت</th></tr></thead>
          <tbody>${range.rows.map(r=>html`<tr key=${r.kpi_id}>
            <td class="mono">${r.code}</td><td>${r.name}${r.mgt?html` <span class="chip">تجمعی</span>`:""}</td>
            <td style="font-size:12px">${r.process}</td>
            <td>${fmt(r.target)}</td><td><b>${fmt(range.basis==="last"?r.last:r.avg_actual)}</b></td>
            <td>${r.avg_ach===null?"—":pct(r.avg_ach*100)}</td>
            <td>${fa(r.count)}</td>
            <td>${html`<${StatusBadge} s=${r.status}/>`}</td></tr>`)}</tbody></table></div>
      </div>`}
    <//>

    <div class="section-title">📭 گزارش داده‌های ناقص / بدون داده</div>
    <${Card}>
      <div class="toolbar" style="flex-wrap:wrap;gap:10px">
        <div class="field" style="margin:0"><label>نوع</label>
          <select value=${ndKind} onChange=${e=>setNdKind(e.target.value)}>
            <option value="">همه (بدون داده و ناقص)</option>
            <option value="none">کاملاً بدون داده</option>
            <option value="partial">ناقص (بخشی از دوره‌ها)</option></select></div>
        <label style="display:flex;align-items:center;gap:6px;font-size:12.5px;margin-top:14px">
          <input type="checkbox" checked=${onlyApproved} onChange=${e=>setOnlyApproved(e.target.checked)}/>
          فقط داده‌های تأییدشده</label>
        <div class="spacer"></div>
        <button class="btn btn-primary" disabled=${ndBusy} onClick=${runNd} style="margin-top:14px">${ndBusy?"…":"محاسبه"}</button>
        <button class="btn btn-sm btn-green" style="margin-top:14px" onClick=${()=>dl(`/reports/no-data.xlsx?${qs}&kind=${ndKind}&approved_only=${onlyApproved}${co}`,`NoData_${year}.xlsx`)}>⬇ Excel</button>
        <button class="btn btn-sm btn-red" style="margin-top:14px" onClick=${()=>dl(`/reports/no-data.pdf?${qs}&kind=${ndKind}&approved_only=${onlyApproved}${co}`,`NoData_${year}.pdf`)}>⬇ PDF</button>
      </div>
      ${nd&&html`<div style="margin-top:12px">
        <div class="pill-row">
          <span class="chip">دوره‌های سررسیدشده: ${fa(nd.considered)}</span>
          <span class="badge red">کاملاً بدون داده: ${fa(nd.none)}</span>
          <span class="badge yellow">ناقص: ${fa(nd.partial)}</span>
        </div>
        <div class="tbl-wrap" style="max-height:340px;overflow:auto"><table class="tbl">
          <thead><tr><th>کد</th><th>شاخص</th><th>فرایند</th><th>تناوب</th><th>نوع</th><th>انتظار / ثبت</th><th>دوره‌های ناقص</th></tr></thead>
          <tbody>${nd.rows.map(r=>html`<tr key=${r.kpi_id}>
            <td class="mono">${r.code}</td><td>${r.name}</td><td style="font-size:12px">${r.process}</td>
            <td style="font-size:11.5px">${meta.frequencies[r.frequency]||r.frequency}</td>
            <td>${r.kind==="none"?html`<span class="badge red">بدون داده</span>`:html`<span class="badge yellow">ناقص</span>`}</td>
            <td>${r.expected===null?"—":`${fa(r.got)} از ${fa(r.expected)}`}</td>
            <td style="font-size:11px;color:var(--muted)">${(r.missing||[]).join("، ")||"—"}</td></tr>`)}</tbody></table></div>
      </div>`}
    <//>

    <div class="section-title">📤 خروجی‌های آماده</div>
    <div class="grid g-2">
      <${Card} title="گزارش جامع سالانه (Excel)">
        <p style="color:var(--muted);font-size:12.5px">تمام شاخص‌ها با آخرین عملکرد، درصد تحقق، وضعیت رنگی و اطلاعات پایه — مخصوص سال ${fa(year)}.</p>
        <button class="btn btn-green" onClick=${()=>dl(`/export/excel?year=${year}`,`KPI_Report_${year}.xlsx`)}>⬇ Excel سال ${fa(year)}</button>
      <//>
      <${Card} title="گزارش مدیریتی (PDF)">
        <p style="color:var(--muted);font-size:12.5px">نمای کلی، رتبه‌بندی فرایندها و شاخص‌های بحرانی برای ارائه به مدیریت ارشد.</p>
        <button class="btn btn-red" onClick=${()=>dl(`/export/pdf?year=${year}`,`Mgmt_Report_${year}.pdf`)}>⬇ PDF سال ${fa(year)}</button>
      <//>
      <${Card} title="فهرست شاخص‌ها (CSV / Excel)">
        <div class="toolbar" style="margin-bottom:8px">
          <select value=${scope} onChange=${e=>setScope(e.target.value)}>
            <option value="all">همه شاخص‌ها</option><option value="active">فقط فعال</option>
            <option value="inactive">فقط غیرفعال</option></select>
        </div>
        <button class="btn btn-sm btn-ghost" onClick=${()=>dl(`/reports/list?scope=${scope}&format=csv`, `KPI_List_${scope}.csv`)}>⬇ CSV</button>
        <button class="btn btn-sm btn-green" onClick=${()=>dl(`/reports/list?scope=${scope}&format=xlsx`, `KPI_List_${scope}.xlsx`)}>⬇ Excel</button>
      <//>
      <${Card} title="داده خام (CSV)">
        <p style="color:var(--muted);font-size:12.5px">تمام ثبت‌های عملکرد سال ${fa(year)} برای تحلیل در ابزارهای دیگر.</p>
        <button class="btn btn-sm btn-ghost" onClick=${()=>dl(`/export/csv?year=${year}`,`KPI_Data_${year}.csv`)}>⬇ CSV داده خام</button>
      <//>
    </div>

    <BackupCard />

    <div class="grid g-1" style="margin-top:16px">
      <${Card} title="🔌 API یکپارچه‌سازی">
        <p style="color:var(--muted);font-size:13px">تمام قابلیت‌ها از طریق REST API در دسترس‌اند.</p>
        <a class="btn btn-ghost" href="/docs" target="_blank">مشاهده Swagger UI ↗</a>
        <div class="hint-box" style="margin-top:12px">
          <span class="mono" style="direction:ltr;display:block">
            GET /api/reports/range?from=1405/01/01&amp;to=1405/12/29&amp;basis=avg<br/>
            GET /api/kpis/1/analysis?fy=1403&amp;fm=1&amp;ty=1405&amp;tm=12<br/>
            GET /api/strategy/goals · GET /api/holding/overview
          </span>
        </div>
      <//>
    </div>
  </div>`;
}

function BackupCard(){
  const [busy,setBusy]=useState(false);
  const [restoreErr,setRestoreErr]=useState("");
  const {reload}=useApp();
  const backup=()=>api.download("/reports/backup", `KPI_Backup_${new Date().toISOString().slice(0,10)}.json`)
    .then(()=>toast("پشتیبان دانلود شد")).catch(e=>toast(e.message,"err"));
  const pick=async(e)=>{const f=e.target.files[0]; if(!f)return;
    if(!confirm("بازیابی، همه داده‌های فعلی (شاخص‌ها، ثبت‌ها، سازمان، کاربران، اهداف) را با فایل پشتیبان جایگزین می‌کند. ادامه می‌دهید؟"))return;
    setBusy(true);setRestoreErr("");
    try{const txt=await f.text();const data=JSON.parse(txt);
      const r=await api.post("/reports/restore",data);
      toast(`بازیابی انجام شد (${fa(r.tables.length)} جدول)`);await reload();}
    catch(ex){setRestoreErr(ex.message)}finally{setBusy(false);e.target.value=""}};
  return html`<${Card} title="💾 پشتیبان‌گیری و بازیابی" cls="" >
    <div style="display:flex;gap:10px;flex-wrap:wrap">
      <button class="btn btn-primary" onClick=${backup}>⬇ دریافت فایل پشتیبان (JSON)</button>
      <label class="btn btn-ghost" style="cursor:pointer">
        ⬆ بازیابی از فایل<input type="file" accept=".json,application/json" style="display:none" onChange=${pick} disabled=${busy}/>
      </label>
      ${busy&&html`<span class="chip">در حال بازیابی…</span>`}
    </div>
    ${restoreErr&&html`<div class="err" style="margin-top:10px">${restoreErr}</div>`}
    <div class="hint-box" style="margin-top:12px">
      فایل پشتیبان شامل شاخص‌ها، ثبت‌های عملکرد، ساختار سازمانی، کاربران، اهداف استراتژی و لاگ تغییرات است.
      بازیابی فقط برای مدیر سیستم مجاز است و پیش از جایگزینی، فایل معتبر بودن آن بررسی می‌شود.
    </div>
  <//>`;
}

/* ================= SETTINGS ================= */
function Settings(){
  const {reload}=useApp();
  const [s,setS]=useState(null),[busy,setBusy]=useState(false),[dmBusy,setDmBusy]=useState(false);
  useEffect(()=>{api.get("/settings").then(setS)},[]);
  if(!s) return html`<${Spinner}/>`;
  const set=(k,v)=>setS(x=>({...x,[k]:v}));
  const save=async()=>{setBusy(true);try{await api.put("/settings",{...s,th_green:+s.th_green,th_yellow:+s.th_yellow});
    toast("ذخیره شد");await reload()}catch(ex){toast(ex.message,"err")}finally{setBusy(false)}};
  const loadSample=async()=>{if(!confirm("داده‌های عملکرد سال جاری بازتولید می‌شود (داده فعلی همان سال حذف می‌شود). ادامه می‌دهید؟"))return;
    setDmBusy(true);try{const r=await api.post("/settings/load-sample",{});
      toast(`${fa(r.created)} رکورد نمونه برای سال ${fa(r.year)} ساخته شد`);await reload();}
    catch(ex){toast(ex.message,"err")}finally{setDmBusy(false)}};
  const clearData=async()=>{if(!confirm("همه ثبت‌های عملکرد حذف می‌شود (تعریف شاخص‌ها حفظ می‌شود). این عملیات قابل بازگشت نیست؛ ابتدا پشتیبان بگیرید. ادامه می‌دهید؟"))return;
    setDmBusy(true);try{const r=await api.post("/settings/clear-data",{});
      toast(`${fa(r.deleted)} رکورد حذف شد`);await reload();}
    catch(ex){toast(ex.message,"err")}finally{setDmBusy(false)}};
  return html`<div>
    <${Card} title="تنظیمات عمومی سامانه">
      <div class="form-grid">
        <div class="field full"><label>نام سازمان</label><input value=${s.org_name} onInput=${e=>set("org_name",e.target.value)}/></div>
        <div class="field"><label>سال جاری (شمسی)</label><input value=${s.current_year} onInput=${e=>set("current_year",e.target.value)}/></div>
        <div class="field"></div>
        <div class="field"><label>آستانه سبز (تحقق ≥)</label><input type="number" step="0.01" value=${s.th_green} onInput=${e=>set("th_green",e.target.value)}/>
          <small style="color:var(--muted)">مثال: ۰.۸۵ یعنی ۸۵٪</small></div>
        <div class="field"><label>آستانه زرد (تحقق ≥)</label><input type="number" step="0.01" value=${s.th_yellow} onInput=${e=>set("th_yellow",e.target.value)}/>
          <small style="color:var(--muted)">کمتر از این = قرمز (بحرانی)</small></div>
        <div class="field"><label>بازیابی رمز مدیر (RESET)</label>
          <select value=${s.recovery_enabled==="0"?"0":"1"} onChange=${e=>set("recovery_enabled",e.target.value)}>
            <option value="1">فعال (مانند نسخه آفلاین)</option><option value="0">غیرفعال (سخت‌گیرانه)</option></select>
          <small style="color:var(--muted)">در حالت غیرفعال، امکان بازنشانی رمز از صفحه ورود وجود ندارد.</small></div>
      </div>
      <button class="btn btn-primary" disabled=${busy} onClick=${save} style="margin-top:14px">ذخیره تنظیمات</button>
      <div class="hint-box" style="margin-top:18px">
        <b>منطق موتور محاسبات:</b> درصد تحقق طبق فرمول صعودی/نزولی (پشتیبانی از هدف صفر و اعداد منفی) محاسبه و سقف ۱۰۰٪ اعمال می‌شود؛
        سپس وضعیت با دو آستانه بالا تعیین می‌گردد. این آستانه‌ها سراسری‌اند و در هر شاخص قابل بازنویسی هستند.
      </div>
    <//>

    <div class="section-title">🗂 مدیریت داده‌ها</div>
    <${Card}>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <button class="btn btn-green" disabled=${dmBusy} onClick=${loadSample}>🎲 بازتولید داده نمونه سال جاری</button>
        <button class="btn btn-red" disabled=${dmBusy} onClick=${clearData}>🗑 پاک کردن همه داده‌های عملکرد</button>
      </div>
      <div class="hint-box" style="margin-top:12px">
        «بازتولید داده نمونه» برای نمایش و آموزش است و ثبت‌های سال جاری را با مقادیر تصادفی
        (متناسب با جهت شاخص) جایگزین می‌کند؛ شاخص‌های تجمعی MGT دست‌نخورده می‌مانند.
        «پاک کردن داده‌های عملکرد» فقط ثبت‌ها را حذف می‌کند و تعریف شاخص‌ها، کاربران و ساختار سازمانی باقی می‌ماند.
      </div>
    <//>

    <div class="section-title">💾 پشتیبان‌گیری</div>
    <${BackupCard} />
  </div>`;
}

/* ================= HOLDING (داشبورد هلدینگ) ================= */
function Holding(){
  const {meta,company,setCompany}=useApp();
  const [ov,setOv]=useState(null),[radar,setRadar]=useState(null),[year,setYear]=useState(meta.current_year);
  useEffect(()=>{(async()=>{
    setOv(await api.get(`/holding/overview?year=${year}`));
    setRadar(await api.get(`/dashboard/radar?year=${year}`));
  })().catch(e=>toast(e.message,"err"))},[year]);
  if(!ov) return html`<${Spinner}/>`;
  const radarData = radar&&radar.items.length>1&&{labels:radar.items.map(r=>r.name.replace("معاونت ","")),
    datasets:[{label:"میانگین تحقق (٪)",data:radar.items.map(r=>r.value),borderColor:C.blue,
      backgroundColor:"rgba(37,99,235,.18)",pointBackgroundColor:C.blue,borderWidth:2}]};
  return html`<div>
    <div class="toolbar">
      <div class="period-filter"><span style="font-size:12px;color:var(--muted)">سال مالی:</span>
        <select value=${year} onChange=${e=>setYear(+e.target.value)}>${((meta.years&&meta.years.length)?meta.years:[meta.current_year]).map(y=>html`<option key=${y} value=${y}>${fa(y)}</option>`)}</select></div>
      <div class="spacer"></div>
      ${company?html`<span class="chip">فیلتر جاری: شرکت انتخاب‌شده</span>
        <button class="btn btn-sm btn-ghost" onClick=${()=>setCompany(null)}>نمایش همه شرکت‌ها</button>`:html`<span class="chip">نمای کل هلدینگ</span>`}
    </div>
    <div class="grid g-4">
      <${Stat} lbl="تعداد شرکت‌ها" val=${fa(ov.total_companies)} sub=${`${fa(ov.total_kpis)} شاخص در سطح هلدینگ`} tone="navy" ic="🏢"/>
      <${Stat} lbl="میانگین تحقق هلدینگ" val=${pct(ov.holding_avg)} sub="میانگین وزنی شرکت‌ها" tone=${ov.holding_avg>=85?"green":ov.holding_avg>=60?"yellow":"red"} ic="🎯"/>
      <${Stat} lbl="شاخص‌های مطلوب" val=${fa(ov.counts.green)} sub=${`${fa(ov.counts.red)} شاخص بحرانی`} tone="green" ic="✅"/>
      <${Stat} lbl="بدون داده" val=${fa(ov.counts.nodata)} sub=${ov.top_company?`برترین شرکت: ${ov.top_company}`:"—"} tone="yellow" ic="📭"/>
    </div>

    <div class="section-title">🏭 مقایسه شرکت‌های هلدینگ</div>
    <${Card}>
      <div class="tbl-wrap"><table class="tbl">
        <thead><tr><th>شرکت</th><th>کد</th><th>شاخص</th><th>دارای داده</th><th>میانگین تحقق</th><th>توزیع وضعیت</th><th></th></tr></thead>
        <tbody>${ov.companies.map((c,i)=>html`<tr key=${c.id}>
          <td><b>${c.name}</b> ${i===0&&c.measured>0?html`<span class="chip strat">برترین</span>`:""}</td>
          <td class="mono">${c.code}</td>
          <td>${fa(c.total)}</td>
          <td>${fa(c.measured)}</td>
          <td style="min-width:160px"><div style="display:flex;align-items:center;gap:8px">
            <${Progress} v=${c.avg_achievement}/><b>${pct(c.avg_achievement)}</b></div></td>
          <td><span class="badge green">${fa(c.counts.green)}</span>
              <span class="badge yellow">${fa(c.counts.yellow)}</span>
              <span class="badge red">${fa(c.counts.red)}</span>
              <span class="badge gray">${fa(c.counts.nodata)}</span></td>
          <td><a onClick=${()=>{setCompany(c.id);location.hash="#/dashboard"}}>داشبورد شرکت ›</a></td>
        </tr>`)}</tbody></table></div>
    <//>

    ${radarData&&html`<div class="grid g-2" style="margin-top:16px">
      <${Card} title="🕸 رادار معاونت‌ها (سطح هلدینگ)">
        <${ChartBox} type="radar" data=${radarData} options=${{scales:{r:{suggestedMin:40,suggestedMax:100,ticks:{callback:v=>fa(v),stepSize:15,backdropColor:"transparent"},pointLabels:{font:{size:11}}}}}}/>
      <//>
      <${Card} title="نکات مدیریتی">
        <div class="hint-box" style="line-height:2">
          <b>راهنما:</b> میانگین تحقق هر شرکت به‌صورت وزنی بر پایه آخرین داده معتبر هر شاخص محاسبه می‌شود
          (شاخص‌های تجمعی MGT از مقدار موثر استفاده می‌کنند و در میانگین شرکت لحاظ می‌شوند).
          <br/>برای مشاهده جزئیات هر شرکت، از کلید «داشبورد شرکت» استفاده کنید؛
          سپس در نوار بالای صفحه، فیلتر شرکت فعال می‌ماند.
        </div>
      <//>
    </div>`}
  </div>`;
}

/* ================= COMPANIES (مدیریت شرکت‌ها) ================= */
function Companies(){
  const {reload}=useApp();
  const [rows,setRows]=useState(null),[edit,setEdit]=useState(null);
  const load=()=>api.get("/companies").then(setRows).catch(e=>toast(e.message,"err"));
  useEffect(()=>{load()},[]);
  const del=async(c)=>{if(!confirm(`حذف شرکت «${c.name}»؟`))return;
    try{await api.del(`/companies/${c.id}`);toast("حذف شد");load();await reload()}catch(ex){toast(ex.message,"err")}};
  if(!rows) return html`<${Spinner}/>`;
  return html`<div>
    <div class="toolbar"><div class="spacer"></div>
      <button class="btn btn-primary" onClick=${()=>setEdit({})}>+ شرکت جدید</button></div>
    <${Card}><div class="tbl-wrap"><table class="tbl">
      <thead><tr><th>ترتیب</th><th>نام شرکت</th><th>کد</th><th>تعداد شاخص</th><th>عملیات</th></tr></thead>
      <tbody>${rows.map(c=>html`<tr key=${c.id}>
        <td>${fa(c.order||0)}</td><td><b>${c.name}</b></td><td class="mono">${c.code||"—"}</td>
        <td>${fa(c.kpi_count)}</td>
        <td style="display:flex;gap:6px">
          <button class="btn btn-sm btn-ghost" onClick=${()=>setEdit(c)}>ویرایش</button>
          <button class="btn btn-sm btn-red" onClick=${()=>del(c)}>حذف</button></td>
      </tr>`)}</tbody></table></div><//>
    <div class="hint-box" style="margin-top:14px">
      شرکت‌ها سطح بالای ساختار سازمانی هستند؛ هر شرکت شامل معاونت‌ها، فرایندها و شاخص‌های خود است.
      حذف شرکتی که شاخص دارد ممکن نیست (ابتدا شاخص‌ها را منتقل یا حذف کنید).
    </div>
    ${edit&&html`<${CompanyForm} c=${edit} onClose=${()=>setEdit(null)} onSaved=${()=>{setEdit(null);load()}}/>`}
  </div>`;
}
function CompanyForm({c,onClose,onSaved}){
  const isNew=!c.id;
  const [f,setF]=useState({name:c.name||"",code:c.code||"",order:c.order||0});
  const [busy,setBusy]=useState(false);const set=(k,v)=>setF(s=>({...s,[k]:v}));
  const save=async()=>{setBusy(true);try{
    if(isNew)await api.post("/companies",f);else await api.put(`/companies/${c.id}`,f);
    toast("ذخیره شد");onSaved();}catch(ex){toast(ex.message,"err")}finally{setBusy(false)}};
  return html`<${Modal} title=${isNew?"شرکت جدید":"ویرایش شرکت"} onClose=${onClose}
    footer=${html`<button class="btn btn-primary" disabled=${busy} onClick=${save}>ذخیره</button>
      <button class="btn btn-ghost" onClick=${onClose}>انصراف</button>`}>
    <div class="form-grid">
      <div class="field"><label>نام شرکت</label><input value=${f.name} onInput=${e=>set("name",e.target.value)}/></div>
      <div class="field"><label>کد</label><input value=${f.code} onInput=${e=>set("code",e.target.value)}/></div>
      <div class="field"><label>ترتیب نمایش</label><input type="number" value=${f.order} onInput=${e=>set("order",+e.target.value)}/></div>
    </div>
  <//>`;
}

/* ================= STRATEGY (اهداف و برنامه‌های اقدام) ================= */
function Strategy(){
  const {meta,company,user}=useApp();
  const [data,setData]=useState(null),[kpis,setKpis]=useState([]),[procs,setProcs]=useState([]);
  const [editGoal,setEditGoal]=useState(null),[linkFor,setLinkFor]=useState(null),
        [actFor,setActFor]=useState(null),[reportFor,setReportFor]=useState(null),
        [open,setOpen]=useState({}),[busy,setBusy]=useState(false);
  const cy=meta.current_year, cm=meta.current_month;
  const [ay,setAy]=useState(cy),[am,setAm]=useState(cm);
  const asof=ay*12+(am-1);
  const load=useCallback(()=>{
    const q=`/strategy/goals?asof=${asof}`+(company?`&company_id=${company}`:"");
    api.get(q).then(setData).catch(e=>toast(e.message,"err"));
  },[asof,company]);
  useEffect(()=>{load()},[load]);
  useEffect(()=>{api.get("/kpis"+(company?`?company=${company}`:"")).then(setKpis).catch(()=>{});
    api.get("/org/processes").then(setProcs).catch(()=>{})},[company]);
  const kmap={}; kpis.forEach(k=>kmap[k.id]=k);

  const installSamples=async()=>{setBusy(true);try{
    const r=await api.post("/strategy/samples",{year:cy,company_id:company||undefined});
    toast(`${fa(r.created)} هدف نمونه با ${fa(r.linked)} اتصال ایجاد شد`);load();}
    catch(ex){toast(ex.message,"err")}finally{setBusy(false)}};
  const startChecked=async(a,g)=>{setBusy(true);try{
    await api.post(`/strategy/actions/${a.id}/start-checked`,{asof});toast("اقدام آغاز شد");load();}
    catch(ex){toast(ex.message,"err")}finally{setBusy(false)}};
  const archive=async(g)=>{if(!confirm(`بایگانی هدف «${g.title}»؟`))return;
    try{await api.post(`/strategy/goals/${g.id}/archive`);toast("بایگانی شد");load()}catch(ex){toast(ex.message,"err")}};

  if(!data) return html`<${Spinner}/>`;
  const goals=data.goals.filter(g=>!g.archived);
  const archived=data.goals.filter(g=>g.archived);
  const card=(g)=>{
    const ev=g.evaluation||{};
    return html`<div class="card" key=${g.id} style="margin-bottom:14px">
      <div class="hd" style="align-items:flex-start">
        <div>
          <h3 style="margin-bottom:4px">${g.title}</h3>
          <div style="font-size:11.5px;color:var(--muted)">${g.description||""}</div>
          <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap">
            <span class="chip">${periodLbl(g.start)} تا ${periodLbl(g.end)}</span>
            ${g.owner_process_code?html`<span class="chip">مسئول: ${g.owner_process_code}</span>`:""}
            <span class="chip" style="background:transparent">پوشش: ${fa(Math.round((ev.coverage||0)*100))}٪</span>
          </div>
        </div>
        <div class="spacer"></div>
        <div style="text-align:left">
          <span class="badge ${gcls(ev.status)}">${ev.status||"—"}</span>
          <div style="font-size:11.5px;margin-top:6px;color:var(--muted)">پیشرفت ${fa(Math.round((ev.progress||0)*100))}٪ از ${fa(Math.round((ev.expected||0)*100))}٪ انتظار</div>
          <div style="margin:6px 0"><${Progress} v=${Math.round((ev.progress||0)*100)}/></div>
        </div>
      </div>
      <div class="bd">
        <div class="section-title" style="margin-top:0">🔗 اتصال به شاخص‌ها</div>
        <div class="tbl-wrap"><table class="tbl">
          <thead><tr><th>شاخص</th><th>دوره</th><th>واقعی</th><th>هدف اتصال</th><th>پیشرفت</th><th>وضعیت</th><th>توضیح</th></tr></thead>
          <tbody>${g.links.map(r=>{const k=kmap[r.kpi_id];
            return html`<tr key=${r.link.id}>
            <td><b>${k?k.name:`#${r.kpi_id}`}</b><div class="mono" style="font-size:10.5px;color:var(--muted)">${k?k.code:""} · ${LINK_MODE[r.link.mode]||r.link.mode}</div></td>
            <td class="mono" style="font-size:11px">${r.period_text||"—"}</td>
            <td>${fmt(r.actual)}</td>
            <td>${fmt(r.target)}${r.weight!==1?html` <span class="chip" style="font-size:10px">وزن ${fa(r.weight)}</span>`:""}</td>
            <td>${r.progress===null?"—":pct(Math.round(r.progress*100))}</td>
            <td><span class="badge ${r.status==="ok"?"green":r.status==="stale"?"yellow":r.status==="invalid"?"red":"gray"}">${
              {ok:"معتبر", stale:"داده قدیمی", invalid:"تعریف تغییر کرده", missing:"بدون داده", future:"سررسید نشده", out:"خارج از دامنه"}[r.status]||r.status}</span></td>
            <td style="font-size:11.5px;color:var(--muted)">${r.reason||r.note||"—"}</td></tr>`})}
            ${g.links.length===0&&html`<tr><td colspan="7" class="empty">اتصالی ثبت نشده است</td></tr>`}
          </tbody></table></div>
        <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap">
          <button class="btn btn-sm btn-ghost" onClick=${()=>setLinkFor(g)}>+ اتصال شاخص</button>
          <button class="btn btn-sm btn-ghost" onClick=${()=>setActFor({goal:g})}>+ برنامه اقدام</button>
          <button class="btn btn-sm btn-ghost" onClick=${()=>setEditGoal(g)}>ویرایش هدف</button>
          <button class="btn btn-sm btn-ghost" onClick=${()=>archive(g)}>بایگانی</button>
          <div class="spacer"></div>
          <button class="btn btn-sm btn-ghost" onClick=${()=>setOpen(o=>({...o,[g.id]:!o[g.id]}))}>
            ${open[g.id]?"بستن رویدادها":"رویدادها و تاریخچه"}</button>
        </div>

        <div class="section-title">✅ برنامه‌های اقدام</div>
        <div class="tbl-wrap"><table class="tbl">
          <thead><tr><th>اقدام</th><th>مسئول</th><th>سررسید</th><th>شرط شروع</th><th>وضعیت فعلی</th><th>پیشرفت</th><th>عملیات</th></tr></thead>
          <tbody>${g.actions.map(a=>html`<tr key=${a.id}>
            <td><b>${a.title}</b>${a.rule!=="always"&&a.trigger&&a.trigger.active?html` <span class="badge red">شرط محقق شد</span>`:""}</td>
            <td style="font-size:12px">${a.owner_name||"—"}</td>
            <td class="mono" style="font-size:11.5px">${periodLbl(a.due)}</td>
            <td style="font-size:11.5px">${RULE_LBL[a.rule]||a.rule}${a.threshold!==null?` (${fmt(a.threshold)})`:""}
              <div style="color:var(--muted);font-size:10.5px">${a.trigger?a.trigger.reason:""}</div></td>
            <td><span class="badge ${a.state==="done"?"green":a.state==="in_progress"?"yellow":a.state==="canceled"?"gray":"blue"}">${ACTION_STATE[a.state]||a.state}</span></td>
            <td style="min-width:110px"><${Progress} v=${a.progress}/><div style="font-size:11px">${pct(a.progress)}</div></td>
            <td style="display:flex;gap:5px;flex-wrap:wrap">
              ${a.state==="planned"&&html`<button class="btn btn-sm btn-ghost" disabled=${busy} onClick=${()=>startChecked(a,g)}>بررسی شرط و شروع</button>`}
              <button class="btn btn-sm btn-ghost" onClick=${()=>setReportFor({goal:g,action:a})}>ثبت گزارش</button>
            </td></tr>`)}
            ${g.actions.length===0&&html`<tr><td colspan="7" class="empty">برنامه اقدامی ثبت نشده است</td></tr>`}
          </tbody></table></div>

        ${open[g.id]&&html`<div style="margin-top:12px">
          <div class="section-title" style="margin-top:0">📜 تاریخچه رویدادها</div>
          <div style="max-height:220px;overflow:auto;font-size:12px">
            ${g.events.length===0?html`<div class="empty">رویدادی ثبت نشده است</div>`:
              g.events.map(e=>html`<div key=${e.id} style="display:flex;gap:8px;padding:5px 0;border-bottom:1px dashed var(--line)">
                <span class="mono" style="color:var(--muted);font-size:10.5px;min-width:105px">${e.at_fa||e.at}</span>
                <b>${e.type}</b>
                <span style="color:var(--muted)">${JSON.stringify(e.details).slice(0,120)}</span></div>`)}
          </div>
        </div>`}
      </div>
    </div>`;
  };

  return html`<div>
    <div class="toolbar" style="flex-wrap:wrap;gap:8px">
      <span class="chip">ارزیابی در پایان دوره</span>
      <select value=${ay} onChange=${e=>setAy(+e.target.value)}>${((meta.years&&meta.years.length)?meta.years:[cy]).map(y=>html`<option key=${y} value=${y}>${fa(y)}</option>`)}</select>
      <select value=${am} onChange=${e=>setAm(+e.target.value)}>${meta.months.map(m=>html`<option key=${m.num} value=${m.num}>${m.name}</option>`)}</select>
      <span class="chip">${periodLbl(data.asof)}</span>
      <div class="spacer"></div>
      <button class="btn btn-primary btn-sm" onClick=${()=>setEditGoal({isNew:true})}>+ هدف جدید</button>
      ${goals.length===0&&html`<button class="btn btn-green btn-sm" disabled=${busy} onClick=${installSamples}>نصب اهداف نمونه</button>`}
    </div>

    <div class="hint-box" style="margin-bottom:14px;line-height:1.95">
      ارزیابی اهداف بر پایه <b>آخرین داده معتبر</b> هر شاخص در دوره‌های سررسید گذشته انجام می‌شود؛
      داده مفقود صفر محسوب نمی‌شود و «تازگی داده» (داده قدیمی) به‌صورت هشدار نمایش داده می‌شود.
      برنامه اقدام تنها زمانی قابل شروع است که شرط تعریف‌شده در دوره ارزیابی محقق شود.
    </div>

    ${goals.length===0?html`<${Card}><div class="empty">هنوز هدفی ثبت نشده است. با «هدف جدید» شروع کنید یا اهداف نمونه را نصب کنید.<//>`:
      goals.map(card)}

    ${archived.length>0&&html`<div class="section-title">🗄 اهداف بایگانی‌شده (${fa(archived.length)})</div>
      <${Card}>${archived.map(g=>html`<div key=${g.id} style="display:flex;gap:8px;align-items:center;padding:5px 0">
        <span style="color:var(--muted)">${g.title}</span><div class="spacer"></div>
        <span class="chip">${periodLbl(g.start)} تا ${periodLbl(g.end)}</span></div>`)}<//>`}

    ${editGoal&&html`<${GoalForm} g=${editGoal.isNew?{}:editGoal} procs=${procs} company=${company}
       onClose=${()=>setEditGoal(null)} onSaved=${()=>{setEditGoal(null);load()}}/>`}
    ${linkFor&&html`<${LinkForm} goal=${linkFor} kpis=${kpis}
       onClose=${()=>setLinkFor(null)} onSaved=${()=>{setLinkFor(null);load()}}/>`}
    ${actFor&&html`<${ActionForm} goal=${actFor.goal} procs=${procs}
       onClose=${()=>setActFor(null)} onSaved=${()=>{setActFor(null);load()}}/>`}
    ${reportFor&&html`<${ActionReport} goal=${reportFor.goal} action=${reportFor.action}
       onClose=${()=>setReportFor(null)} onSaved=${()=>{setReportFor(null);load()}}/>`}
  </div>`;
}

function PeriodPick({label,value,onChange,meta}){
  const y = value?Math.floor(value/12):meta.current_year;
  const m = value?value%12+1:1;
  const yrs=(meta.years&&meta.years.length?meta.years:[meta.current_year]);
  return html`<div class="field"><label>${label}</label>
    <div style="display:flex;gap:6px">
      <select value=${y} onChange=${e=>onChange(+e.target.value*12+(m-1))}>
        ${yrs.map(x=>html`<option key=${x} value=${x}>${fa(x)}</option>`)}</select>
      <select value=${m} onChange=${e=>onChange(y*12+(+e.target.value-1))}>
        ${meta.months.map(x=>html`<option key=${x.num} value=${x.num}>${x.name}</option>`)}</select>
    </div></div>`;
}

function GoalForm({g,procs,company,onClose,onSaved}){
  const {meta}=useApp(); const isNew=!g.id;
  const [f,setF]=useState({title:g.title||"",description:g.description||"",
    owner_process_code:g.owner_process_code||(procs[0]&&procs[0].code)||"",
    start_period:g.start||(meta.current_year*12),
    end_period:g.end||(meta.current_year*12+11)});
  const [busy,setBusy]=useState(false);const set=(k,v)=>setF(s=>({...s,[k]:v}));
  const save=async()=>{setBusy(true);try{
    const body={...f,company_id:company||undefined};
    if(isNew)await api.post("/strategy/goals",body);else await api.put(`/strategy/goals/${g.id}`,body);
    toast("ذخیره شد");onSaved();}catch(ex){toast(ex.message,"err")}finally{setBusy(false)}};
  return html`<${Modal} title=${isNew?"هدف استراتژیک جدید":"ویرایش هدف"} onClose=${onClose}
    footer=${html`<button class="btn btn-primary" disabled=${busy} onClick=${save}>ذخیره</button>
      <button class="btn btn-ghost" onClick=${onClose}>انصراف</button>`}>
    <div class="form-grid">
      <div class="field full"><label>عنوان هدف</label><input value=${f.title} onInput=${e=>set("title",e.target.value)}/></div>
      <div class="field full"><label>توضیح</label><textarea rows="2" value=${f.description} onInput=${e=>set("description",e.target.value)}></textarea></div>
      <div class="field"><label>فرایند مسئول</label><select value=${f.owner_process_code} onChange=${e=>set("owner_process_code",e.target.value)}>
        ${procs.map(p=>html`<option key=${p.code} value=${p.code}>${p.name}</option>`)}</select></div>
      <div class="field"></div>
      <${PeriodPick} label="دوره شروع" value=${f.start_period} meta=${meta} onChange=${v=>set("start_period",v)}/>
      <${PeriodPick} label="دوره پایان" value=${f.end_period} meta=${meta} onChange=${v=>set("end_period",v)}/>
    </div>
  <//>`;
}

function LinkForm({goal,kpis,onClose,onSaved}){
  const [f,setF]=useState({kpi_id:kpis[0]?kpis[0].id:"",mode:"maintain",baseline:"",target:"",weight:1,note:""});
  const [busy,setBusy]=useState(false);const set=(k,v)=>setF(s=>({...s,[k]:v}));
  const k=kpis.find(x=>x.id===+f.kpi_id);
  const save=async()=>{setBusy(true);try{
    const body={kpi_id:+f.kpi_id,mode:f.mode,weight:+f.weight,note:f.note,
      baseline:f.baseline===""?null:+f.baseline,
      target:f.target===""?(k?k.target:null):+f.target};
    await api.post(`/strategy/goals/${goal.id}/links`,body);toast("اتصال ذخیره شد");onSaved();}
    catch(ex){toast(ex.message,"err")}finally{setBusy(false)}};
  return html`<${Modal} title="اتصال شاخص به هدف" onClose=${onClose}
    footer=${html`<button class="btn btn-primary" disabled=${busy} onClick=${save}>ذخیره</button>
      <button class="btn btn-ghost" onClick=${onClose}>انصراف</button>`}>
    <div class="form-grid">
      <div class="field full"><label>شاخص</label><select value=${f.kpi_id} onChange=${e=>{set("kpi_id",e.target.value);
          const kk=kpis.find(x=>x.id===+e.target.value); if(kk)set("target",kk.target)}}>
        ${kpis.filter(x=>!x.is_mgt).map(x=>html`<option key=${x.id} value=${x.id}>${x.code} — ${x.name}</option>`)}</select>
        <small style="color:var(--muted)">شاخص‌های تجمعی (MGT) در ارزیابی اهداف استفاده نمی‌شوند.</small></div>
      <div class="field"><label>روش ارزیابی</label><select value=${f.mode} onChange=${e=>set("mode",e.target.value)}>
        ${Object.entries(LINK_MODE).map(([v,l])=>html`<option key=${v} value=${v}>${l}</option>`)}</select></div>
      <div class="field"><label>وزن در هدف</label><input type="number" step="0.5" value=${f.weight} onInput=${e=>set("weight",e.target.value)}/></div>
      <div class="field"><label>خط مبنا (برای حالت بهبود)</label><input value=${f.baseline} onInput=${e=>set("baseline",e.target.value)}/></div>
      <div class="field"><label>مقدار هدف</label><input value=${f.target} onInput=${e=>set("target",e.target.value)}/>
        <small style="color:var(--muted)">پیش‌فرض: هدف فعلی شاخص (${k?fmt(k.target):"—"})</small></div>
      <div class="field full"><label>یادداشت</label><input value=${f.note} onInput=${e=>set("note",e.target.value)}/></div>
    </div>
  <//>`;
}

function ActionForm({goal,procs,onClose,onSaved}){
  const {meta,user}=useApp();
  const [f,setF]=useState({title:"",description:"",due:goal.end,rule:"always",threshold:"",link_id:"",owner_id:""});
  const [busy,setBusy]=useState(false);const set=(k,v)=>setF(s=>({...s,[k]:v}));
  const save=async()=>{setBusy(true);try{
    await api.post(`/strategy/goals/${goal.id}/actions`,{...f,
      threshold:f.threshold===""?null:+f.threshold,
      link_id:f.link_id||null,owner_id:f.owner_id||null});
    toast("برنامه اقدام ثبت شد");onSaved();}catch(ex){toast(ex.message,"err")}finally{setBusy(false)}};
  const needsLink=f.rule==="below"||f.rule==="above";
  return html`<${Modal} title="برنامه اقدام جدید" onClose=${onClose}
    footer=${html`<button class="btn btn-primary" disabled=${busy} onClick=${save}>ذخیره</button>
      <button class="btn btn-ghost" onClick=${onClose}>انصراف</button>`}>
    <div class="form-grid">
      <div class="field full"><label>عنوان اقدام</label><input value=${f.title} onInput=${e=>set("title",e.target.value)}/></div>
      <div class="field full"><label>توضیح</label><textarea rows="2" value=${f.description} onInput=${e=>set("description",e.target.value)}></textarea></div>
      <div class="field"><label>شرط شروع</label><select value=${f.rule} onChange=${e=>set("rule",e.target.value)}>
        ${Object.entries(RULE_LBL).map(([v,l])=>html`<option key=${v} value=${v}>${l}</option>`)}</select></div>
      <div class="field"><label>آستانه شرط</label><input value=${f.threshold} onInput=${e=>set("threshold",e.target.value)} disabled=${!needsLink}/>
        <small style="color:var(--muted)">فقط برای «کمتر از حد» و «بیشتر از حد»</small></div>
      <div class="field"><label>اتصال شاخص (اختیاری)</label><select value=${f.link_id} onChange=${e=>set("link_id",e.target.value)}>
        <option value="">— بدون اتصال —</option>
        ${(goal.links||[]).map(r=>html`<option key=${r.link.id} value=${r.link.id}>#${r.kpi_id} · ${r.link.mode}</option>`)}</select></div>
      <${PeriodPick} label="دوره سررسید" value=${f.due} meta=${meta} onChange=${v=>set("due",v)}/>
    </div>
  <//>`;
}

function ActionReport({goal,action,onClose,onSaved}){
  const [f,setF]=useState({state:action.state==="planned"?"in_progress":action.state,
    progress:action.progress||0,evidence:action.evidence||""});
  const [busy,setBusy]=useState(false);const set=(k,v)=>setF(s=>({...s,[k]:v}));
  const save=async()=>{setBusy(true);try{
    await api.post(`/strategy/actions/${action.id}/report`,{...f,progress:+f.progress});
    toast("گزارش ثبت شد");onSaved();}catch(ex){toast(ex.message,"err")}finally{setBusy(false)}};
  return html`<${Modal} title=${`ثبت گزارش: ${action.title}`} onClose=${onClose}
    footer=${html`<button class="btn btn-primary" disabled=${busy} onClick=${save}>ثبت</button>
      <button class="btn btn-ghost" onClick=${onClose}>انصراف</button>`}>
    <div class="form-grid">
      <div class="field"><label>وضعیت</label><select value=${f.state} onChange=${e=>{set("state",e.target.value);
          if(e.target.value==="done")set("progress",100)}}>
        ${Object.entries(ACTION_STATE).map(([v,l])=>html`<option key=${v} value=${v}>${l}</option>`)}</select></div>
      <div class="field"><label>پیشرفت (٪)</label><input type="number" min="0" max="100" value=${f.progress}
        onInput=${e=>set("progress",e.target.value)} disabled=${f.state==="done"}/></div>
      <div class="field full"><label>گزارش اجرا / دلیل تغییر وضعیت <span style="color:var(--red)">*</span></label>
        <textarea rows="3" value=${f.evidence} onInput=${e=>set("evidence",e.target.value)}></textarea>
        <small style="color:var(--muted)">برای ثبت وضعیت، گزارش اجرا یا دلیل الزامی است.</small></div>
    </div>
  <//>`;
}

/* ================= APP SHELL ================= */
const NAV=[
  {g:"پایش و تحلیل",items:[
    {k:"dashboard",t:"داشبورد مدیریتی",ic:"📊",p:"dashboard"},
    {k:"holding",t:"داشبورد هلدینگ",ic:"🏢",p:"holding"},
    {k:"processes",t:"فرایندها",ic:"🗂️",p:"processes"},
    {k:"kpis",t:"شاخص‌ها و روندها",ic:"📈",p:"kpis"},
    {k:"strategy",t:"اهداف و برنامه‌ها",ic:"🎯",p:"strategy"},
  ]},
  {g:"ثبت و گردش کار",items:[
    {k:"entry",t:"ورود اطلاعات",ic:"✍️",p:"entry"},
    {k:"approvals",t:"کارتابل تأیید",ic:"✅",p:"approvals",badge:"inbox"},
  ]},
  {g:"مدیریت سیستم",items:[
    {k:"master",t:"مدیریت شاخص‌ها",ic:"🎚️",p:"master"},
    {k:"org",t:"ساختار سازمانی",ic:"🏗️",p:"org"},
    {k:"companies",t:"شرکت‌های هلدینگ",ic:"🏭",p:"companies"},
    {k:"reports",t:"گزارش‌ها و خروجی",ic:"📑",p:"reports"},
    {k:"users",t:"کاربران و نقش‌ها",ic:"👥",p:"users"},
    {k:"audit",t:"لاگ تغییرات",ic:"📜",p:"audit"},
    {k:"settings",t:"تنظیمات",ic:"⚙️",p:"settings"},
  ]},
];
const PAGES={dashboard:Dashboard,holding:Holding,processes:Processes,kpis:KpiList,strategy:Strategy,
  reports:Reports,entry:DataEntry,approvals:Approvals,master:KpiMaster,org:Org,companies:Companies,
  users:Users,audit:Audit,settings:Settings};
const TITLES={dashboard:"داشبورد مدیریتی",holding:"داشبورد هلدینگ",processes:"فرایندها",
  kpis:"شاخص‌ها و روندها",strategy:"اهداف استراتژیک و برنامه‌های اقدام",reports:"گزارش‌ها و خروجی",
  entry:"ورود اطلاعات عملکرد",approvals:"کارتابل تأیید",master:"مدیریت شاخص‌ها (KPI Master)",
  org:"ساختار سازمانی",companies:"شرکت‌های هلدینگ",users:"کاربران و نقش‌ها",audit:"لاگ تغییرات",
  settings:"تنظیمات سامانه"};
const VIEWLBL = {dashboard:"داشبورد",holding:"هلدینگ",processes:"فرایندها",kpis:"شاخص‌ها",
  strategy:"اهداف",entry:"ورود داده",approvals:"تأیید",master:"مدیریت شاخص",org:"سازمان",
  companies:"شرکت‌ها",reports:"گزارش‌ها",settings:"تنظیمات",users:"کاربران",audit:"لاگ"};

function NoAccess(){
  return html`<div class="card"><div class="bd" style="text-align:center;padding:40px 20px">
    <div style="font-size:34px">🔒</div>
    <h3 style="margin:10px 0">دسترسی به این صفحه برای شما فعال نیست</h3>
    <div style="color:var(--muted);font-size:13px">برای دریافت دسترسی با مدیر سیستم تماس بگیرید.</div>
  </div></div>`;
}

function parseHash(){
  const h=(location.hash||"#/dashboard").replace(/^#\//,"");
  const [path,qs]=h.split("?"); const params={};
  if(qs)qs.split("&").forEach(p=>{const[k,v]=p.split("=");params[k]=decodeURIComponent(v||"")});
  return {page:path||"dashboard",params};
}

function Shell({children}){
  const {user,logout,year,setYear,meta,inboxCount,company,setCompany}=useApp();
  const [route,setRoute]=useState(parseHash());
  useEffect(()=>{const on=()=>setRoute(parseHash());window.addEventListener("hashchange",on);return()=>window.removeEventListener("hashchange",on)},[]);
  let Page=PAGES[route.page]||Dashboard;
  const allowedNav=NAV.map(g=>({...g,items:g.items.filter(i=>canDo(user,i.p))})).filter(g=>g.items.length);
  const curNav=NAV.flatMap(g=>g.items).find(i=>i.k===route.page);
  if(curNav && !canDo(user,curNav.p)) Page=NoAccess;
  return html`<div class="app">
    <aside class="sidebar">
      <div class="brand"><div class="logo">K</div><div><b>سامانه پایش KPI</b><span>${meta.org_name||"مدیریت عملکرد سازمانی"}</span></div></div>
      <nav class="nav">${allowedNav.map(g=>html`<div key=${g.g}><div class="nav-group">${g.g}</div>
        ${g.items.map(i=>html`<a key=${i.k} class=${route.page===i.k?"active":""} onClick=${()=>location.hash="#/"+i.k}>
          <span class="ic">${i.ic}</span><span>${i.t}</span>
          ${i.badge==="inbox"&&inboxCount>0&&html`<span class="badge-n">${fa(inboxCount)}</span>`}
        </a>`)}</div>`)}</nav>
      <div class="foot">نسخه ۱.۱ · برابری کامل با نسخه آفلاین<br/>KPI-MS © ${fa(meta.current_year)}</div>
    </aside>
    <main class="main">
      <header class="topbar">
        <div><h2>${TITLES[route.page]||""}</h2><div class="crumb">${meta.org_name}</div></div>
        <div class="spacer"></div>
        ${meta.companies&&meta.companies.length>1&&html`<div class="period-filter"><span style="font-size:12px;color:var(--muted)">شرکت:</span>
          <select value=${company||""} onChange=${e=>setCompany(e.target.value?+e.target.value:null)}>
            <option value="">همه شرکت‌ها</option>
            ${meta.companies.map(c=>html`<option key=${c.id} value=${c.id}>${c.name}</option>`)}</select></div>`}
        <div class="period-filter"><span style="font-size:12px;color:var(--muted)">سال مالی:</span>
          <select value=${year} onChange=${e=>setYear(+e.target.value)}>${meta.years.map(y=>html`<option key=${y} value=${y}>${fa(y)}</option>`)}</select></div>
        <div class="userchip" onClick=${logout} title="خروج از سامانه">
          <div class="av">${(user.full_name||"?").trim()[0]}</div>
          <div><div class="nm">${user.full_name}</div><div class="rl">${user.role_name} · خروج ⏻</div></div>
        </div>
      </header>
      <div class="content"><${Page} params=${route.params}/></div>
    </main>
  </div>`;
}

/* ================= ROOT ================= */
function App(){
  const [user,setUser]=useState(null),[meta,setMeta]=useState(null),[loading,setLoading]=useState(true),
        [year,setYear]=useState(null),[toastMsg,setToastMsg]=useState(null),[inboxCount,setInboxCount]=useState(0),
        [authed,setAuthed]=useState(!!api.token),
        [company,setCompanyState]=useState(localStorage.getItem("kpi_company")?+localStorage.getItem("kpi_company"):null);
  const setCompany=(v)=>{setCompanyState(v);v?localStorage.setItem("kpi_company",String(v)):localStorage.removeItem("kpi_company");};
  _setToast=setToastMsg;
  useEffect(()=>{if(toastMsg){const t=setTimeout(()=>setToastMsg(null),2600);return()=>clearTimeout(t)}},[toastMsg]);

  const reload=useCallback(async()=>{
    if(!api.token){setUser(null);setLoading(false);return}
    try{
      const u=await api.get("/auth/me"); setUser(u);
      const m=await api.get("/meta"); setMeta(m);
      setYear(y=>y||m.current_year);
      try{const ib=await api.get("/entries/inbox");setInboxCount(ib.length)}catch{}
    }catch(e){setUser(null)}
    setLoading(false);
  },[]);
  useEffect(()=>{reload()},[]);
  useEffect(()=>{const on=()=>setAuthed(!!api.token);window.addEventListener("hashchange",on);return()=>window.removeEventListener("hashchange",on)},[]);

  const logout=()=>{api.token=null;localStorage.removeItem("kpi_token");setUser(null);location.hash="#/login"};

  const toastEl=toastMsg&&html`<div class="toast ${toastMsg.type}" key=${toastMsg.id}>${toastMsg.msg}</div>`;

  if(loading) return html`<${Spinner}/>`;
  const ctx={user,meta,year,setYear,reload,logout,inboxCount,company,setCompany};
  if(!user||location.hash==="#/login"&&!user) return html`<${Ctx.Provider} value=${ctx}><${Login}/>${toastEl}<//>`;
  if(!user) return html`<${Ctx.Provider} value=${ctx}><${Login}/>${toastEl}<//>`;
  if(!meta||!year) return html`<${Spinner}/>`;
  if(user.must_change) return html`<${Ctx.Provider} value=${ctx}><${ForceChange}/>${toastEl}<//>`;
  return html`<${Ctx.Provider} value=${ctx}><${Shell}/>${toastEl}<//>`;
}

/* PWA: نصب روی دسکتاپ/موبایل و کارکرد پس از قطع شبکه (پوسته رابط) */
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(()=>{}));
}

ReactDOM.createRoot(document.getElementById("root")).render(html`<${App}/>`);
