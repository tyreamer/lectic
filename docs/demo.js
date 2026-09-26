(() => {
  const root = document.getElementById('demo-content');
  if (!root) return;
  const byId = id => document.getElementById(id);
  const canvas = byId('demo-canvas');
  const pack = byId('demo-pack-node');
  const people = byId('demo-people');
  const action = byId('demo-action');
  const result = byId('demo-result');
  const outputs = [...root.querySelectorAll('[data-output]')];
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const examples = {
    plan: {title: 'An interview plan', lines: 'Ask. Listen. Find the next question.', request: 'create an interview plan for [my research question]'},
    checklist: {title: 'A research checklist', lines: 'Prepare → Interview → Compare → Test', request: 'create a research checklist for [my project]'},
    lesson: {title: 'A lesson for your team', lines: 'A concept. An example. A practice exercise.', request: 'create a lesson on customer interviews for [my team]'},
    review: {title: 'A review of your approach', lines: 'What works. What is missing. What to change.', request: 'review this interview approach: [paste it here]'},
    proposal: {title: 'A proposal for the next test', lines: 'One assumption. One experiment. A clear next step.', request: 'draft a discovery experiment proposal for [my project]'},
    idea: {title: 'What will you make?', lines: '', request: ''}
  };
  let selected = null;
  let frame;
  function announce(text) { byId('demo-status').textContent = text; }
  function point(node, side) {
    const a = node.getBoundingClientRect(), b = canvas.getBoundingClientRect();
    return {x: a.left - b.left + (side === 'left' ? 0 : side === 'right' ? a.width : a.width / 2),
      y: a.top - b.top + (side === 'top' ? 0 : side === 'bottom' ? a.height : a.height / 2)};
  }
  function drawWires() {
    const svg = byId('demo-wires');
    svg.setAttribute('viewBox', `0 0 ${canvas.clientWidth} ${canvas.clientHeight}`);
    svg.replaceChildren();
    const narrow = matchMedia('(max-width: 900px)').matches;
    function wire(from, to, kind, vertical = false) {
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      const mid = vertical ? (from.y + to.y) / 2 : (from.x + to.x) / 2;
      path.setAttribute('d', vertical ? `M${from.x} ${from.y} C${from.x} ${mid},${to.x} ${mid},${to.x} ${to.y}` : `M${from.x} ${from.y} C${mid} ${from.y},${mid} ${to.y},${to.x} ${to.y}`);
      path.dataset.wire = kind;
      svg.append(path);
    }
    root.querySelectorAll('[data-source]').forEach(node => wire(point(node, narrow ? 'bottom' : 'right'), point(pack, narrow ? 'top' : 'left'), 'source', narrow));
    wire(point(pack, 'right'), point(people, 'left'), 'share');
    outputs.forEach(node => wire(point(people, narrow ? 'bottom' : 'right'), point(node, narrow ? 'top' : 'left'), 'output', narrow));
  }
  function scheduleWires() { cancelAnimationFrame(frame); frame = requestAnimationFrame(drawWires); }
  new ResizeObserver(scheduleWires).observe(canvas);
  window.addEventListener('resize', scheduleWires);
  pack.addEventListener('animationend', scheduleWires);
  function fly(from, to, icon, color, delay = 0) {
    if (reducedMotion.matches) return;
    const start = point(from), end = point(to);
    const particle = document.createElement('span');
    particle.className = 'demo-flight';
    particle.style.cssText = `left:${start.x - 14}px;top:${start.y - 14}px;color:${color}`;
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    use.setAttribute('href', `demo-icons.svg#${icon}`);
    svg.append(use); particle.append(svg); canvas.append(particle);
    const animation = particle.animate([{transform:'translate(0,0) scale(1)',opacity:0}, {offset:.12,opacity:1},
      {transform:`translate(${end.x-start.x}px,${end.y-start.y}px) scale(.4)`,opacity:0}],
      {duration:600,delay,easing:'cubic-bezier(.4,0,.2,1)',fill:'both'});
    animation.finished.then(() => particle.remove(), () => particle.remove());
  }
  function showOutput(key, focusIdea = false) {
    selected = key;
    outputs.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.output === key)));
    const sample = examples[key];
    byId('demo-result-title').textContent = sample.title;
    byId('demo-result-lines').textContent = sample.lines;
    byId('demo-result-icon').setAttribute('href', `demo-icons.svg#${key}`);
    byId('demo-idea-label').hidden = key !== 'idea';
    byId('demo-copy-prompt').textContent = 'Copy prompt ↗';
    result.hidden = false;
    if (focusIdea) byId('demo-idea').focus();
  }
  function reset() {
    root.dataset.stage = 'sources';
    byId('demo-pack-name').textContent = 'Your collection';
    action.textContent = 'Create pack →';
    outputs.forEach(button => { button.disabled = true; button.setAttribute('aria-pressed', 'false'); });
    canvas.querySelectorAll('.demo-flight').forEach(node => node.remove());
    result.hidden = true;
    selected = null;
    announce('Ready to create another example pack.');
    scheduleWires();
  }
  action.addEventListener('click', () => {
    if (root.dataset.stage === 'sources') {
      root.dataset.stage = 'packed';
      byId('demo-pack-name').textContent = 'Customer Discovery';
      action.textContent = 'Share pack →';
      root.querySelectorAll('[data-source]').forEach((node, i) => fly(node, pack, node.dataset.source, node.style.getPropertyValue('--source-color'), i * 55));
      announce('The example sources are combined into one Customer Discovery pack. Share it next.');
    } else if (root.dataset.stage === 'packed') {
      root.dataset.stage = 'shared';
      people.querySelectorAll('.demo-person').forEach((node, i) => fly(pack, node, 'pack', '#7dd3fc', i * 80));
      outputs.forEach(button => { button.disabled = false; });
      action.textContent = 'Replay ↻';
      showOutput('plan');
      announce('The same pack is shared in this example. Choose a plan, checklist, lesson, review, proposal, or your own idea.');
    } else reset();
    scheduleWires();
  });
  outputs.forEach(button => button.addEventListener('click', () => showOutput(button.dataset.output, button.dataset.output === 'idea')));
  byId('demo-copy-prompt').addEventListener('click', async () => {
    const idea = byId('demo-idea').value.trim();
    if (selected === 'idea' && !idea) { byId('demo-idea').focus(); announce('Enter what you would like to create.'); return; }
    const request = selected === 'idea' ? `create ${idea}` : examples[selected].request;
    try {
      await navigator.clipboard.writeText(`Use my Customer Discovery collection to ${request}. Keep the source passages attached.`);
      byId('demo-copy-prompt').textContent = 'Copied ✓';
      announce('Prompt copied. Use it after installing the example pack in a connected assistant.');
    } catch { byId('demo-copy-prompt').textContent = 'Copy unavailable'; announce('Clipboard access is unavailable in this browser.'); }
  });
  byId('demo-verify').addEventListener('click', async () => {
    const status = byId('demo-verify-status');
    status.textContent = 'Checking…';
    try {
      const [metaResponse, packResponse] = await Promise.all([fetch('demo/pack-info.json'), fetch('packs/customer-discovery.lectic')]);
      if (!metaResponse.ok || !packResponse.ok) throw new Error('Download unavailable.');
      const metadata = await metaResponse.json(), bytes = await packResponse.arrayBuffer();
      const digest = await crypto.subtle.digest('SHA-256', bytes);
      const hex = [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2,'0')).join('');
      if (hex !== metadata.sha256 || bytes.byteLength !== metadata.bytes) throw new Error('Download does not match.');
      status.textContent = 'Verified: the downloaded example matches its checksum.';
    } catch (error) { status.textContent = `Could not verify: ${error.message}`; }
  });
  scheduleWires();
})();
