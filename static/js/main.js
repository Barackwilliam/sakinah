const b=document.getElementById('burger'),n=document.getElementById('navlinks');
if(b)b.addEventListener('click',()=>{n.classList.toggle('open');document.body.classList.toggle('lock')});
const g=document.getElementById('mgrid');
document.querySelectorAll('.arr').forEach(a=>a.addEventListener('click',()=>{if(g)g.scrollBy({left:a.dataset.dir*g.clientWidth/2,behavior:'smooth'})}));
const md=document.getElementById('amodal');
if(md){
  const open=nx=>{md.querySelectorAll('.am-next').forEach(i=>i.value=nx);md.hidden=false;document.body.classList.add('lock');const f=md.querySelector('form:not([hidden]) input:not([type=hidden])');if(f)f.focus()};
  const close=()=>{md.hidden=true;document.body.classList.remove('lock')};
  document.addEventListener('click',e=>{const a=e.target.closest('[data-auth]');if(a){e.preventDefault();open(a.dataset.auth)}});
  md.addEventListener('click',e=>{if(e.target===md||e.target.closest('[data-close]'))close()});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!md.hidden)close()});
  md.querySelectorAll('[data-tab]').forEach(t=>t.addEventListener('click',()=>{
    md.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('on',x===t));
    document.getElementById('am-su').hidden=t.dataset.tab!=='su';document.getElementById('am-li').hidden=t.dataset.tab!=='li'}));
}
document.querySelectorAll('.gallery').forEach(g=>g.addEventListener('click',e=>{
  const t=e.target.closest('button[data-src]');if(!t)return;const id=g.dataset.for,img=document.getElementById('pc-main-'+id),n=document.getElementById('pc-n-'+id);
  if(img)img.src=t.dataset.src;if(n)n.textContent=t.dataset.n;g.querySelectorAll('button').forEach(b=>b.classList.toggle('on',b===t))}));
