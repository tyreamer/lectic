async function loadCatalog(){
  const status=document.getElementById('catalog-status');
  try{
    const response=await fetch('registry/index.json');if(!response.ok)throw new Error('Catalog could not be loaded.');
    const {packs}=await response.json();
    for(const pack of packs){
      const card=document.createElement('article');card.className='catalog-card';
      card.innerHTML='<p class="eyebrow">Lectic-authored teaching material · MIT</p><h2></h2><p class="description"></p><p class="fine count"></p><div class="actions"><a class="button primary" download>Download pack</a><button class="verify">Verify download</button></div><p class="fine verification" role="status"></p><details><summary>Use with your connected assistant</summary><div class="copy-box"><code></code><button>Copy</button></div><p class="fine">Unsigned teaching material. Integrity checks verify downloaded bytes, not effectiveness or publisher identity.</p><p class="hash"></p></details>';
      card.querySelector('h2').textContent=pack.title;card.querySelector('.description').textContent=pack.description;
      card.querySelector('.count').textContent=pack.units+' cited takeaways · version '+pack.version;
      const location='packs/'+encodeURIComponent(pack.name)+'.lectic';card.querySelector('a').href=location;
      card.querySelector('code').textContent='Install registry:'+pack.name;
      card.querySelector('.hash').textContent='SHA-256: '+pack.sha256;
      card.querySelector('.copy-box button').onclick=async()=>{try{await navigator.clipboard.writeText('Install registry:'+pack.name);card.querySelector('.verification').textContent='Install request copied.'}catch{card.querySelector('.verification').textContent='Select the install request and copy it.'}};
      card.querySelector('.verify').onclick=async()=>{
        const label=card.querySelector('.verification');label.textContent='Checking download…';
        try{const r=await fetch(location);if(!r.ok)throw new Error('Download unavailable');const bytes=await r.arrayBuffer();const digest=await crypto.subtle.digest('SHA-256',bytes);const hash=Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('');if(hash!==pack.sha256)throw new Error('Checksum differs from the catalog');label.textContent='Verified: download matches the catalog ('+bytes.byteLength+' bytes).'}catch(e){label.textContent='Verification failed: '+e.message}
      };
      document.getElementById('catalog-grid').append(card);
    }
    status.textContent=packs.length+' downloadable packs. These are teaching materials, not recordings of outside experts.';
  }catch(e){status.textContent=e.message;}
}
loadCatalog();
