const $=s=>document.querySelector(s);
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
let me=null,users=[],all=[],f={q:"",loc:"",sort:"recommended",cat:"All"};

const IMG={tomato:"photo-1546094096-0df4bcaaa337",banana:"photo-1571771894821-ce9b6c11b08e",cucumber:"photo-1604977042946-1eecc30f269e",carrot:"photo-1445282768818-728615cc910a",papaya:"photo-1517282009859-f000ec3b26fe",pepper:"photo-1563565375-f3fdfdbefa83",onion:"photo-1508747703725-719777637510"};
const img=p=>{const k=Object.keys(IMG).find(k=>p.toLowerCase().includes(k));return `https://images.unsplash.com/${IMG[k]||"photo-1542838132-92c53300491e"}?auto=format&fit=crop&w=700&q=80`};
const cat=p=>/spinach|gotukola|kale|lettuce|leaf|mukunuwenna/i.test(p)?"Leafy greens":/banana|papaya|mango|pineapple|lime|orange|fruit/i.test(p)?"Fruits":"Vegetables";
const hours=l=>l.available_until?(new Date(l.available_until)-Date.now())/36e5:null;
const urgent=l=>{const h=hours(l);return h!==null&&h<=48};
const when=l=>{const h=hours(l);return h===null?"No deadline":h<0?"Deadline passed":h<=48?`Sell within ${Math.ceil(h)} hours`:"Until "+new Date(l.available_until).toLocaleDateString()};

async function api(path,method="GET",body){
  const r=await fetch("/api"+path,{method,headers:{"Content-Type":"application/json","X-User-Id":me?.id??""},body:body?JSON.stringify(body):undefined});
  const d=await r.json().catch(()=>({}));
  if(!r.ok) throw new Error(typeof d.detail==="string"?d.detail:"Check the form and try again.");
  return d;
}
let tt;const toast=t=>{const e=$("#toast");e.textContent=t;e.classList.add("show");clearTimeout(tt);tt=setTimeout(()=>e.classList.remove("show"),3200);};
const run=async fn=>{try{await fn();}catch(e){toast(e.message);}};
const openModal=h=>{$("#modalContent").innerHTML=h;$("#modalBackdrop").hidden=false;};
const closeModal=()=>$("#modalBackdrop").hidden=true;
$("#modalClose").onclick=closeModal;$("#modalBackdrop").onclick=e=>{if(e.target.id==="modalBackdrop")closeModal();};
document.onkeydown=e=>{if(e.key==="Escape")closeModal();};

async function init(){
  users=await api("/users");
  $("#who").innerHTML=users.map(u=>`<option value="${u.id}">${esc(u.name)}</option>`).join("");
  $("#who").onchange=e=>login(e.target.value);
  login(users[0].id);
}
function login(id){
  me=users.find(u=>u.id==id);$("#who").value=id;
  const farmer=me.role==="farmer";
  $("#sellButton").hidden=!farmer;$("#navMine").hidden=!farmer;$("#my-listings").hidden=!farmer;
  $("#ordersHint").textContent=farmer?"Orders from buyers for your produce.":"Orders you have placed with farmers.";
  refresh();
}
const refresh=()=>run(async()=>{all=await api("/listings");drawFilters();drawGrid();await Promise.all([drawOrders(),me.role==="farmer"?drawMine():0]);});

function drawFilters(){
  const cur=$("#locationFilter").value;
  $("#locationFilter").innerHTML='<option value="">All locations</option>'+[...new Set(all.map(l=>l.district))].sort().map(d=>`<option ${d===cur?"selected":""}>${esc(d)}</option>`).join("");
}
function drawGrid(){
  let ls=all.filter(l=>(f.cat==="All"||(f.cat==="Surplus"?urgent(l):cat(l.produce)===f.cat))
    &&(!f.loc||l.district===f.loc)
    &&(!f.q||(l.produce+l.farmer_name+l.district).toLowerCase().includes(f.q)));
  const by={"price-low":(a,b)=>a.price_per_kg-b.price_per_kg,"price-high":(a,b)=>b.price_per_kg-a.price_per_kg,
    urgent:(a,b)=>(hours(a)??1e9)-(hours(b)??1e9)}[f.sort];
  if(by) ls=[...ls].sort(by);
  $("#resultsCount").textContent=`${ls.length} listing${ls.length===1?"":"s"}`;
  $("#emptyState").hidden=ls.length>0;
  $("#productGrid").innerHTML=ls.map(l=>`<article class="product-card" data-id="${l.id}" tabindex="0">
    <div class="product-image"><img src="${img(l.produce)}" alt="${esc(l.produce)}" loading="lazy">${urgent(l)?'<span class="tag urgent">NEEDS QUICK SALE</span>':""}</div>
    <div class="product-info"><div class="farm-location"><span>${esc(l.farmer_name)}</span><span>${esc(l.district)}</span></div>
    <h3>${esc(l.produce)}</h3>
    <div class="product-bottom"><div class="price">LKR ${l.price_per_kg}<small>/kg</small></div><button class="add-btn">View details</button></div>
    <div class="product-meta"><span>${l.quantity_kg} kg available</span><span>${when(l)}</span></div></div></article>`).join("");
}
$("#productGrid").onclick=e=>{const c=e.target.closest(".product-card");if(c)detail(+c.dataset.id);};
$("#productGrid").onkeydown=e=>{if(e.key==="Enter"){const c=e.target.closest(".product-card");if(c)detail(+c.dataset.id);}};
$("#searchInput").oninput=e=>{f.q=e.target.value.toLowerCase();drawGrid();};
$("#locationFilter").onchange=e=>{f.loc=e.target.value;drawGrid();};
$("#sortFilter").onchange=e=>{f.sort=e.target.value;drawGrid();};
$("#categoryRow").onclick=e=>{const b=e.target.closest(".category");if(!b)return;
  document.querySelectorAll(".category").forEach(x=>x.classList.toggle("active",x===b));f.cat=b.dataset.category;drawGrid();};

function detail(id){
  const l=all.find(x=>x.id===id);
  const buy=me.role==="buyer"?`<form id="buyForm"><div class="field"><label for="q">Quantity (kg)</label><input id="q" type="number" min="1" max="${l.quantity_kg}" value="${l.quantity_kg}" required></div><button class="btn btn-green">Place order</button></form>`
    :`<p>Switch to a buyer account to order this produce.</p>`;
  openModal(`<h2>${esc(l.produce)}</h2><img class="listing-detail-image" src="${img(l.produce)}" alt="">
    <div class="detail-price">LKR ${l.price_per_kg}<small> /kg</small></div>
    <div class="detail-grid"><div class="detail-cell"><small>Farmer</small><strong>${esc(l.farmer_name)}</strong></div>
    <div class="detail-cell"><small>Location</small><strong>${esc(l.district)}</strong></div>
    <div class="detail-cell"><small>Available</small><strong>${l.quantity_kg} kg</strong></div>
    <div class="detail-cell"><small>Timing</small><strong>${when(l)}</strong></div></div>${buy}`);
  const form=$("#buyForm");
  if(form) form.onsubmit=e=>{e.preventDefault();run(async()=>{
    await api("/orders","POST",{listing_id:id,quantity_kg:+$("#q").value});
    closeModal();toast("Order placed. The farmer will confirm it.");await refresh();location.hash="#orders";});};
}

const ACTS={
  farmer:{pending:[["accept","Accept","btn-green"],["decline","Decline","btn-danger"]]},
  buyer:{pending:[["cancel","Cancel order","btn-danger"]],
    confirmed:[["complete","Mark received","btn-green"],["reject_delivery","Reject delivery","btn-danger"],["cancel","Cancel order","btn-danger"]]}};
async function drawOrders(){
  const os=await api("/orders");
  $("#orderList").innerHTML=os.length?os.map(o=>`<div class="row"><div><b>${esc(o.produce)}</b> · ${o.quantity_kg} kg at LKR ${o.price_per_kg}/kg
    <small>${me.role==="farmer"?"Buyer: "+esc(o.buyer_name):"Farmer: "+esc(o.farmer_name)} · <span class="status ${o.status}">${o.status.toUpperCase()}</span></small></div>
    <div class="acts">${(ACTS[me.role][o.status]||[]).map(([a,l,c])=>`<button class="btn small ${c}" data-o="${o.id}" data-a="${a}">${l}</button>`).join("")}</div></div>`).join("")
    :`<p class="empty">No orders yet.${me.role==="buyer"?" Browse the market to place one.":""}</p>`;
}
$("#orderList").onclick=e=>{const b=e.target.closest("[data-a]");if(!b)return;
  run(async()=>{await api(`/orders/${b.dataset.o}/${b.dataset.a}`,"POST");toast("Order updated.");await refresh();});};

async function drawMine(){
  const ls=await api("/listings?farmer_id="+me.id+"&include_closed=true");
  $("#mineList").innerHTML=ls.length?ls.map(l=>`<div class="row"><div><b>${esc(l.produce)}</b> · ${l.quantity_kg} kg at LKR ${l.price_per_kg}/kg
    <small>${esc(l.district)} · ${when(l)} · <span class="status ${l.status}">${l.status.toUpperCase()}</span></small></div>
    <div class="acts">${l.status==="open"?`<button class="btn small btn-danger" data-c="${l.id}">Close listing</button>`:""}</div></div>`).join("")
    :'<p class="empty">You have no listings yet. Use “Sell produce” to add one.</p>';
}
$("#mineList").onclick=e=>{const b=e.target.closest("[data-c]");if(!b)return;
  run(async()=>{await api("/listings/"+b.dataset.c,"DELETE");toast("Listing closed.");await refresh();});};

$("#sellButton").onclick=()=>{
  openModal(`<h2>Sell produce</h2><p>List what you have so buyers can find it.</p>
  <form id="sellForm"><div class="field"><label for="p">Produce</label><input id="p" required placeholder="e.g. Tomatoes"></div>
  <div class="field-row"><div class="field"><label for="k">Quantity (kg)</label><input id="k" type="number" min="1" required></div>
  <div class="field"><label for="r">Price (LKR per kg)</label><input id="r" type="number" min="1" required></div></div>
  <div class="field"><label for="d">District</label><input id="d" required value="${esc(me.district)}"></div>
  <div class="field"><label for="u">Sell by (optional)</label><input id="u" type="datetime-local"></div>
  <button class="btn btn-green">Publish listing</button></form>`);
  $("#sellForm").onsubmit=e=>{e.preventDefault();run(async()=>{
    const b={produce:$("#p").value,quantity_kg:+$("#k").value,price_per_kg:+$("#r").value,district:$("#d").value};
    if($("#u").value)b.available_until=$("#u").value;
    await api("/listings","POST",b);closeModal();toast("Listing published.");await refresh();});};
};
init();
