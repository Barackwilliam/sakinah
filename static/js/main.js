const b=document.getElementById('burger'),n=document.getElementById('navlinks');
if(b)b.addEventListener('click',()=>{n.classList.toggle('open');document.body.classList.toggle('lock')});
const g=document.getElementById('mgrid');
document.querySelectorAll('.arr').forEach(a=>a.addEventListener('click',()=>{if(g)g.scrollBy({left:a.dataset.dir*g.clientWidth/2,behavior:'smooth'})}));
