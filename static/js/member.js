const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const sb=$('#msb'),scrim=$('#sb-scrim'),ob=$('#sb-open');
if(ob&&sb){ob.addEventListener('click',()=>{const o=!sb.classList.contains('open');sb.classList.toggle('open',o);scrim.hidden=!o});scrim.addEventListener('click',()=>{sb.classList.remove('open');scrim.hidden=true})}
// confirm buttons
document.addEventListener('click',e=>{const b=e.target.closest('[data-confirm]');if(b&&!confirm(b.dataset.confirm))e.preventDefault()});
