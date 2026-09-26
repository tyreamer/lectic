(() => {
  const root = document.getElementById('demo-content');
  if (!root) return;
  const byId = id => document.getElementById(id);
  const element = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const tabs = [...root.querySelectorAll('[data-stage]')];
  function showStage(stage, focus = false) {
    tabs.forEach(tab => {
      const active = tab.dataset.stage === stage;
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      byId(`demo-${tab.dataset.stage}`).hidden = !active;
      if (active && focus) tab.focus();
    });
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => showStage(tab.dataset.stage));
    tab.addEventListener('keydown', event => {
      const offset = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
      let target = offset ? (index + offset + tabs.length) % tabs.length : null;
      if (event.key === 'Home') target = 0;
      if (event.key === 'End') target = tabs.length - 1;
      if (target !== null) {
        event.preventDefault();
        showStage(tabs[target].dataset.stage, true);
      }
    });
  });
  root.querySelectorAll('[data-next]').forEach(button => {
    button.addEventListener('click', () => showStage(button.dataset.next, true));
  });

  async function loadJSON(path) {
    const response = await fetch(path);
    if (!response.ok) throw new Error('Example data is unavailable.');
    return response.json();
  }
  async function load() {
    try {
      const [data, pack] = await Promise.all([loadJSON('demo/customer-discovery.json'), loadJSON('demo/pack-info.json')]);
      if (data.sources.length !== pack.sources || data.sources.reduce((n, source) => n + source.paragraphs.length, 0) !== pack.units) {
        throw new Error('The source list and example pack do not match.');
      }
      const sources = new Map(data.sources.map(source => [source.id, source]));
      const sourceButtons = [];
      function showSource(source) {
        sourceButtons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.source === source.id)));
        byId('demo-source-format').textContent = `${source.format} · ${source.ready}`;
        byId('demo-source-title').textContent = source.title;
        byId('demo-source-passages').replaceChildren(...source.paragraphs.map(p => element('blockquote', p)));
        byId('demo-source-route').textContent = source.route;
      }
      for (const source of data.sources) {
        const button = element('button', '', 'demo-source-card');
        button.type = 'button';
        button.dataset.source = source.id;
        button.setAttribute('aria-pressed', 'false');
        button.setAttribute('aria-label', `Inspect ${source.format}: ${source.title}`);
        const mark = element('span', source.mark, 'demo-source-mark');
        mark.setAttribute('aria-hidden', 'true');
        const body = element('span', '', 'demo-source-body');
        body.append(element('strong', source.format), element('span', source.title), element('small', source.ready));
        button.append(mark, body);
        button.addEventListener('click', () => showSource(source));
        byId('demo-source-list').append(button);
        sourceButtons.push(button);
      }
      byId('demo-request-text').textContent = data.prompt;
      showSource(data.sources[0]);

      const methodButtons = [];
      function showMethod(step) {
        methodButtons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.method === step.id)));
        byId('demo-method-title').textContent = step.title;
        byId('demo-method-instruction').textContent = step.instruction;
        byId('demo-method-example').textContent = step.example;
        byId('demo-evidence').replaceChildren(...step.source_ids.map(id => {
          const source = sources.get(id);
          const card = element('div', '', 'demo-evidence-card');
          card.append(element('strong', source.format), element('span', source.title), element('blockquote', source.paragraphs[0]));
          return card;
        }));
      }
      data.playbook.forEach((step, index) => {
        const button = element('button', '', 'demo-method-card');
        button.type = 'button';
        button.dataset.method = step.id;
        button.setAttribute('aria-pressed', 'false');
        button.append(element('span', `0${index + 1}`, 'demo-method-number'), element('strong', step.title),
          element('small', step.source_ids.map(id => sources.get(id).format).join(' + ')));
        button.addEventListener('click', () => showMethod(step));
        byId('demo-method-list').append(button);
        methodButtons.push(button);
      });
      showMethod(data.playbook[0]);
      byId('demo-pack-size').textContent = `${(pack.bytes / 1024).toFixed(1)} KB · v${pack.version} · real, installable example`;
      byId('demo-pack-hash').textContent = `SHA-256: ${pack.sha256}`;
      byId('demo-verify').addEventListener('click', async () => {
        const status = byId('demo-verify-status');
        status.textContent = 'Checking the downloaded bytes…';
        try {
          const response = await fetch('packs/customer-discovery.lectic');
          if (!response.ok) throw new Error('The download is unavailable.');
          const bytes = await response.arrayBuffer();
          const digest = await crypto.subtle.digest('SHA-256', bytes);
          const hex = [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join('');
          if (hex !== pack.sha256 || bytes.byteLength !== pack.bytes) throw new Error('The download differs from the published example.');
          status.textContent = `Verified: ${bytes.byteLength.toLocaleString()} bytes match the example checksum.`;
        } catch (error) {
          status.textContent = `Could not verify: ${error.message}`;
        }
      });
      byId('demo-load-status').hidden = true;
      root.hidden = false;
    } catch {
      byId('demo-load-status').textContent = 'The walkthrough could not load. Reload to try again, or use the example pack and source links below.';
    }
  }
  load();
})();
