'use strict';
const data=window.RETRO_RENEW;
const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeUrl=u=>{try{const p=new URL(u);return p.protocol==='https:'&&!p.username&&!p.password?p.href:null}catch{return null}};
const link=(url,text,cls='')=>safeUrl(url)?`<a class="${esc(cls)}" href="${esc(safeUrl(url))}" target="_blank" rel="noopener noreferrer">${text}</a>`:'';
let series='All games',onlyInstallers=false;
function setNav(){
  $('#home-link').classList.toggle('active',!onlyInstallers);
  $('#home-link').setAttribute('aria-pressed',String(!onlyInstallers));
  $('#setups-link').classList.toggle('active',onlyInstallers);
  $('#setups-link').setAttribute('aria-pressed',String(onlyInstallers));
}
function statusLabel(g){return ready(g)?'Installer ready':g.status==='example'?'Example':g.status==='reference'?'Reference list':'Draft'}
function filters(){
  $('#filters').innerHTML=['All games',...new Set(data.games.map(g=>g.series))].map(s=>`<button class="filter" data-series="${esc(s)}" aria-pressed="${s===series}">${esc(s)}</button>`).join('');
  $('#filters').querySelectorAll('button').forEach(b=>b.onclick=()=>{
    series=b.dataset.series;
    $('#filters').querySelectorAll('button').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.series===series)));
    render();
  });
}
function ready(g){return g.status==='released'&&safeUrl(g.installerUrl)}
function render(){
  const q=$('#search').value.toLowerCase().trim();
  const games=data.games.filter(g=>(series==='All games'||g.series===series)&&(!onlyInstallers||ready(g))&&[g.title,g.series,...g.mods.flatMap(m=>[m.name,m.author])].join(' ').toLowerCase().includes(q));
  $('#result-count').textContent=games.length+' game'+(games.length===1?'':'s');
  const released=data.games.filter(ready).length;
  $('#catalogue-status').textContent=released?released+' tested installer'+(released===1?'':'s')+' available. Other entries are reference lists, drafts, or examples.':'No game installers released. Drafts and examples are labelled below.';
  const groups=[...new Set(games.map(g=>g.series))];
  $('#games').innerHTML=groups.map(name=>`<section class="series-group"><h2>${esc(name)}</h2>${games.filter(g=>g.series===name).map(g=>`<article class="game-row"><div class="game-identity"><h3><a href="#${encodeURIComponent(g.id)}">${esc(g.title)}</a></h3><p>${esc(g.edition)}</p></div><span class="source-count">${g.mods.length} mod${g.mods.length===1?'':'s'}</span><span class="setup-status ${ready(g)?'released':''}">${statusLabel(g)}</span><a class="row-action" href="#${encodeURIComponent(g.id)}" aria-label="View ${esc(g.title)} mods">View mods <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M5 12h14m-5-5 5 5-5 5"/></svg></a></article>`).join('')}</section>`).join('');
  $('#empty').hidden=games.length!==0;
  $('#empty-title').textContent=onlyInstallers?'No installers match your filters.':'No games match your search.';
  $('#empty-description').textContent=onlyInstallers?(released?'Try another game series or clear your search.':'Game companion pages and original mod links are available while setups are being verified.'):'Try a game title, mod name, or author, or clear your filters.';
  $('#reset').textContent=onlyInstallers?'Browse all games':'Clear filters';
  setNav();
}
function modRows(g,q=''){
  const mods=g.mods.filter(m=>[m.name,m.author,m.category].join(' ').toLowerCase().includes(q.toLowerCase()));
  $('#mod-list').innerHTML=mods.length?mods.map(m=>`<article class="mod-row"><div><h3>${esc(m.name)}</h3><span class="author">By ${esc(m.author)}</span><p>${esc(m.description)}</p><p><span class="category">${esc(m.category)}</span><span class="version">${m.version?'Version '+esc(m.version):'Version unconfirmed'}</span></p>${m.permission?`<details class="permission-note"><summary>Usage and installer permissions</summary><p>${esc(m.permission)}</p></details>`:''}</div>${link(m.page,'Original project')||'<span class="source-unavailable">Source link unavailable</span>'}</article>`).join(''):'<div class="empty">No matching mods.</div>';
}
function route(moveFocus=false){
  let id;try{id=decodeURIComponent(location.hash.slice(1))}catch{id=''}
  if(id==='main')return;
  const g=data.games.find(g=>g.id===id);
  $('#shelf-view').hidden=!!g;$('#detail-view').hidden=!g;
  if(!g){
    document.title='Retro Renew / Games';
    $('#route-error').hidden=!id;
    if(id)$('#route-error').textContent='This companion link is unavailable. Choose a game below.';
    if(moveFocus)$('#shelf-heading').focus();
    return;
  }
  $('#route-error').hidden=true;
  document.title=g.title+' / Retro Renew';
  $('#detail-view').innerHTML=`<a class="detail-back" href="#">Back to games</a><div class="detail-heading"><h1 id="detail-title" tabindex="-1">${esc(g.title)}</h1><p>${esc(g.edition)}</p><div class="detail-actions">${link(g.videoUrl,'Watch video','button secondary')}${ready(g)?link(g.installerUrl,'Download installer','button'):'<span class="installer-unavailable">Installer not released</span>'}<button class="text-button" id="share-link">Copy page link</button></div></div><div class="status-box"><p>${g.status==='example'?'Example entry. No tested setup or video is claimed.':ready(g)?'Tested setup available.':g.status==='reference'?'Mod reference list.':'Draft list. Versions and compatibility need confirmation.'}</p><details><summary>Setup notes</summary><p>${esc(g.notes)}</p>${g.videoTitle?`<p>Video: ${esc(g.videoTitle)}${safeUrl(g.videoUrl)?'':' / link pending'}</p>`:''}${g.testedDate?`<p>Last tested: ${esc(g.testedDate)}</p>`:''}</details></div><div class="mod-heading"><h2>Mods & tools</h2><label class="search"><svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg><input id="mod-search" type="search" placeholder="Search this mod list" aria-label="Search this mod list"></label></div><div id="mod-list"></div><p class="detail-note">Check your game edition and follow each author’s instructions. Listed mods are not automatically included in an installer.</p>`;
  modRows(g);$('#mod-search').oninput=e=>modRows(g,e.target.value);$('#share-link').onclick=copyLink;
  window.scrollTo(0,0);
  if(moveFocus)$('#detail-title').focus();
}
async function copyLink(){try{await navigator.clipboard.writeText(location.href);toast('Companion link copied.')}catch{dialog('<h2>Your companion link</h2><p>Copy the address below.</p><input class="copy-address" aria-label="Companion page address" readonly value="'+esc(location.href)+'">')}}
function toast(msg){$('#toast').textContent=msg;$('#toast').classList.add('show');setTimeout(()=>$('#toast').classList.remove('show'),2500)}
function dialog(html){$('#dialog-content').innerHTML=html.replace('<h2>','<h2 id="dialog-title">');$('#info-dialog').showModal()}
function how(){dialog(`<h2>Installing a setup</h2><div class="dialog-step"><h3>01 / Find your game</h3><p>Select its installation folder. The helper checks the supported edition, file fingerprints, space, and known conflicts.</p></div><div class="dialog-step"><h3>02 / Get the right files</h3><p>Approved direct downloads are verified. Restricted downloads stay on the author’s page; add those ZIP archives to the helper.</p></div><div class="dialog-step"><h3>03 / Install the tested setup</h3><p>Files are prepared before changes begin. Only explicitly listed files are installed, with backups and a recovery journal.</p></div><div class="dialog-step"><h3>04 / Keep a way back</h3><p>Restore the files changed by the setup. Later user changes block automatic restoration so they aren’t silently lost.</p></div><p>Real-game installers are not available yet. The source project includes a harmless training demo for testing the installation and recovery flow.</p>`)}
function authors(){
  const mods=[...new Map(data.games.flatMap(g=>g.mods).map(m=>[m.page,m])).values()];
  dialog('<h2>Mod authors</h2><p>These projects are made by their own authors and contributors. Retro Renew provides companion lists and setup automation.</p><div class="author-grid">'+mods.map(m=>`<div class="author-entry"><strong>${esc(m.name)}</strong><p>${esc(m.author)}</p>${link(m.page,'Original project')}</div>`).join('')+'</div>');
}
$('#search').oninput=render;$('#reset').onclick=()=>{$('#search').value='';series='All games';onlyInstallers=false;filters();render();setNav();$('#search').focus()};
$('#setups-link').onclick=()=>{location.hash='';onlyInstallers=true;series='All games';$('#search').value='';filters();render();setNav()};
$('.brand').onclick=()=>$('#home-link').onclick();
$('#home-link').onclick=()=>{location.hash='';onlyInstallers=false;series='All games';$('#search').value='';filters();render();setNav()};
$('#how-link').onclick=how;$('#credits-link').onclick=authors;
$('.dialog-close').onclick=()=>$('#info-dialog').close();$('#info-dialog').onclick=e=>{if(e.target===$('#info-dialog'))$('#info-dialog').close()};
document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)&&!document.activeElement.isContentEditable&&!$('#info-dialog').open){e.preventDefault();($('#detail-view').hidden?$('#search'):$('#mod-search')).focus()}});
window.addEventListener('hashchange',()=>route(true));filters();render();route();
