/* Appearance is browser-local presentation only, separate from account and permissions. */
(function(){
 const key='orvyth-appearance-v1',themes=['mist','sand','ink'];let current='mist';
 try{const saved=localStorage.getItem(key);if(themes.includes(saved))current=saved;}catch{}
 function apply(name){document.documentElement.dataset.appearance=name;current=name;document.querySelectorAll('[data-theme-choice]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.themeChoice===name)));}
 apply(current);
 try{if(sessionStorage.getItem("orvyth-welcome-arrival")==="1"){sessionStorage.removeItem("orvyth-welcome-arrival");document.documentElement.classList.add("welcome-arrival");setTimeout(()=>document.documentElement.classList.remove("welcome-arrival"),1000);}}catch{}
 document.addEventListener('DOMContentLoaded',()=>{apply(current);document.querySelectorAll('[data-theme-choice]').forEach(button=>button.addEventListener('click',()=>{
  apply(button.dataset.themeChoice);let message='已切换，外观保存在当前浏览器。';try{localStorage.setItem(key,current);}catch{message='已切换；浏览器禁止保存，刷新后将恢复默认。';}document.querySelector('#appearance-status').textContent=message;
 }));});
})();
