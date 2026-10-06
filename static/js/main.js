const b=document.getElementById('burger'),n=document.getElementById('navlinks');
if(b)b.addEventListener('click',()=>{n.classList.toggle('open');document.body.classList.toggle('lock')});
