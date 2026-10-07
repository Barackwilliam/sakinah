const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const lock=on=>document.body.classList.toggle('lock',on);

// mobile menu drawer
const burger=$('#burger'),links=$('#navlinks'),scrim=$('#scrim');
function menu(open){if(!links)return;links.classList.toggle('open',open);burger.classList.toggle('x',open);burger.setAttribute('aria-expanded',open);scrim.hidden=!open;lock(open)}
if(burger){burger.addEventListener('click',()=>menu(!links.classList.contains('open')));scrim.addEventListener('click',()=>menu(false))}

// header shadow once the page scrolls
const nav=$('#nav');const onScroll=()=>nav&&nav.classList.toggle('scrolled',scrollY>8);addEventListener('scroll',onScroll,{passive:true});onScroll();

// featured matches carousel arrows
const g=$('#mgrid');$$('.arr').forEach(a=>a.addEventListener('click',()=>g&&g.scrollBy({left:a.dataset.dir*g.clientWidth*.8,behavior:'smooth'})));

// show / hide password
document.addEventListener('click',e=>{const b=e.target.closest('[data-eye]');if(!b)return;const i=b.parentElement.querySelector('input');
  const show=i.type==='password';i.type=show?'text':'password';b.classList.toggle('on',show);b.setAttribute('aria-label',show?'Hide password':'Show password')});

// sign-in modal for visitors
const md=$('#amodal');
if(md){
  const open=nx=>{$$('.am-next',md).forEach(i=>i.value=nx);md.hidden=false;lock(true);const f=$('form:not([hidden]) input:not([type=hidden])',md);if(f)f.focus({preventScroll:true})};
  const close=()=>{md.hidden=true;lock(false)};
  document.addEventListener('click',e=>{const a=e.target.closest('[data-auth]');if(a){e.preventDefault();open(a.dataset.auth)}});
  md.addEventListener('click',e=>{if(e.target===md||e.target.closest('[data-close]'))close()});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!md.hidden)close()});
  $$('[data-tab]',md).forEach(t=>t.addEventListener('click',()=>{
    $$('[data-tab]',md).forEach(x=>x.classList.toggle('on',x===t));
    $('#am-su').hidden=t.dataset.tab!=='su';$('#am-li').hidden=t.dataset.tab!=='li'}));
}

// profile photo gallery
$$('.gallery').forEach(gal=>gal.addEventListener('click',e=>{
  const t=e.target.closest('button[data-src]');if(!t)return;const id=gal.dataset.for,img=$('#pc-main-'+id),n=$('#pc-n-'+id);
  if(img)img.src=t.dataset.src;if(n)n.textContent=t.dataset.n;$$('button',gal).forEach(b=>b.classList.toggle('on',b===t))}));

// gentle reveal on scroll
if('IntersectionObserver' in window&&!matchMedia('(prefers-reduced-motion: reduce)').matches){
  document.documentElement.classList.add('js');
  const io=new IntersectionObserver(es=>es.forEach(en=>{if(en.isIntersecting){en.target.classList.add('in');io.unobserve(en.target)}}),{threshold:.05,rootMargin:'0px 0px -40px 0px'});
  $$('.reveal').forEach(el=>io.observe(el));
}

// share buttons: native share sheet on phones, copy link elsewhere
document.addEventListener('click',async e=>{const b=e.target.closest('[data-share]');if(!b)return;
  const data={title:b.dataset.share,url:location.href.split('#')[0]};
  try{if(navigator.share)await navigator.share(data);else{await navigator.clipboard.writeText(data.url);b.classList.add('done');b.title='Link copied';setTimeout(()=>b.classList.remove('done'),1600)}}catch(_){}});

// dialogs (inquiry, report)
const openDlg=(d)=>{if(d&&d.showModal){d.showModal();lock(true)}};
document.addEventListener('click',e=>{
  const o=e.target.closest('[data-open-dlg]');if(o){const m=o.closest('details');if(m)m.open=false;openDlg($('#'+o.dataset.openDlg))}
  const q=e.target.closest('[data-inq]');if(q){const d=$('#inq');$('[name=kind]',d).value=q.dataset.inq;
    $('#inq-title').textContent=q.dataset.inq==='availability'?'Check availability':'Send an inquiry';openDlg(d)}
  if(e.target.closest('[data-close-dlg]')){const d=e.target.closest('dialog');d.close()}
  if(e.target.tagName==='DIALOG')e.target.close();
});
$$('dialog').forEach(d=>d.addEventListener('close',()=>lock(false)));

// advert gallery
const adT=$('#ad-thumbs');if(adT)adT.addEventListener('click',e=>{const t=e.target.closest('button[data-src]');if(!t)return;
  $('#ad-img').src=t.dataset.src;$('#ad-n').textContent=t.dataset.n;$$('button',adT).forEach(b=>b.classList.toggle('on',b===t))});

// in-page tabs: highlight the clicked tab
$$('.tabs').forEach(tb=>tb.addEventListener('click',e=>{const a=e.target.closest('a');if(!a)return;$$('a',tb).forEach(x=>x.classList.toggle('on',x===a))}));

// login page: member / admin tabs only change where you land after login
$$('[data-lg]').forEach(t=>t.addEventListener('click',()=>{$$('[data-lg]').forEach(x=>x.classList.toggle('on',x===t));
  $('#lg-next').value=t.dataset.next;$('#lg-title').textContent=t.dataset.lg==='admin'?'Admin Login':'Welcome Back'}));
