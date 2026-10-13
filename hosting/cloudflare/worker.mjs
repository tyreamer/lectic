import { TOOLS, INSTRUCTIONS } from './tool-registry.mjs';

const CHUNK = 48 * 1024;
const HASH = /^[a-f0-9]{64}$/;
const AREAS = new Set(['blobs', 'collections', 'capture', 'capabilities', 'exports', 'evaluations', 'runs', 'use-guides', 'inbox']);
const encoder = new TextEncoder();
function check(ok, message, status = 400) { if (!ok) throw Object.assign(new Error(message), { status }); }
function reply(body, status = 200) {
  return Response.json(body, { status, headers: { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' } });
}
async function matches(value, secret) {
  if (!value || !secret) return false;
  const key = await crypto.subtle.importKey('raw', encoder.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign', 'verify']);
  const signature = await crypto.subtle.sign('HMAC', key, encoder.encode(secret));
  return crypto.subtle.verify('HMAC', key, signature, encoder.encode(value));
}
async function body(request, max = 1024 * 1024) {
  const reader = request.body?.getReader();
  if (!reader) return '';
  const decoder = new TextDecoder('utf-8', { fatal: true });
  let size = 0, text = '';
  while (true) {
    const part = await reader.read(); if (part.done) break;
    size += part.value.byteLength;
    if (size > max) { await reader.cancel(); check(false, 'Request is too large', 413); }
    text += decoder.decode(part.value, { stream: true });
  }
  return text + decoder.decode();
}
function stmt(env, sql, ...params) { const s = env.DB.prepare(sql); return params.length ? s.bind(...params) : s; }
function safePath(path) {
  return typeof path === 'string' && !path.includes('\\') && !path.includes(':') &&
    path.split('/').every(p => p && !p.startsWith('.')) &&
    (['library.json', 'custom_relationships.json', 'identity.json'].includes(path) || path.startsWith('sessions/') || AREAS.has(path.split('/')[0]));
}
async function manifest(env) {
  const row = await stmt(env, 'SELECT revision, manifest, library FROM home WHERE id=1').first();
  return { revision: row.revision, ...JSON.parse(row.manifest), library: JSON.parse(row.library) };
}
async function store(request, env, path) {
  if (path === '/store/manifest' && request.method === 'GET') return reply(await manifest(env));
  if (path === '/store/queue' && request.method === 'GET') {
    const rows = await stmt(env, 'SELECT id, captured_at, payload FROM phone_captures WHERE processed=0 ORDER BY captured_at,id LIMIT 50').all();
    return reply({ items: rows.results.map(r => ({ id: r.id, captured_at: r.captured_at, ...JSON.parse(r.payload) })) });
  }
  check(request.method === 'POST', 'Not found', 404);
  const value = JSON.parse(await body(request));
  if (path === '/store/lease') {
    check(typeof value.owner === 'string' && /^[a-f0-9]{32}$/.test(value.owner), 'Invalid lease owner');
    const now = Date.now();
    const result = await stmt(env, 'UPDATE home SET lease_owner=?,lease_until=? WHERE id=1 AND (lease_until<? OR lease_owner=?)',
      value.owner, now + 600000, now, value.owner).run();
    check(result.meta.changes === 1, 'Another WayKit operation is active; retry shortly', 409);
    return reply(await manifest(env));
  }
  if (path === '/store/release') {
    await stmt(env, 'UPDATE home SET lease_owner=\'\',lease_until=0 WHERE id=1 AND lease_owner=?', value.owner).run();
    return reply({ released: true });
  }
  if (path === '/store/get-objects') {
    check(Array.isArray(value.ids) && value.ids.length <= 16 && value.ids.every(h => HASH.test(h)), 'Invalid object selection');
    const objects = [];
    for (const id of value.ids) {
      const meta = await stmt(env, 'SELECT * FROM objects WHERE id=?', id).first();
      check(meta, 'Knowledge object is missing', 404);
      const parts = await stmt(env, 'SELECT part,body FROM object_parts WHERE id=? ORDER BY part', id).all();
      check(parts.results.length === meta.parts, 'Knowledge object is incomplete', 409);
      objects.push({ ...meta, data: parts.results.map(p => p.body) });
    }
    return reply({ objects });
  }
  if (path === '/store/objects') {
    check(Array.isArray(value.objects) && value.objects.length <= 16, 'Invalid object batch');
    const statements = [];
    for (const o of value.objects) {
      check(HASH.test(o.id) && HASH.test(o.raw_hash) && o.encoding === 'zlib', 'Invalid object identity');
      check(Number.isInteger(o.raw_size) && o.raw_size <= 64 * 1024 * 1024 && o.raw_size >= 0, 'Invalid object size');
      check(Number.isInteger(o.encoded_size) && o.encoded_size > 0 && o.parts === Math.ceil(o.encoded_size / CHUNK), 'Invalid chunk count');
      check(Array.isArray(o.data) && o.data.length <= 16, 'Invalid chunk batch');
      statements.push(stmt(env, 'INSERT OR IGNORE INTO objects(id,raw_hash,raw_size,encoded_size,parts,encoding) VALUES(?,?,?,?,?,?)',
        o.id, o.raw_hash, o.raw_size, o.encoded_size, o.parts, o.encoding));
      for (const p of o.data) {
        check(Number.isInteger(p.part) && p.part >= 0 && p.part < o.parts && typeof p.body === 'string' &&
          p.body.length <= CHUNK * 4 / 3 && /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(p.body), 'Invalid chunk');
        statements.push(stmt(env, 'INSERT OR IGNORE INTO object_parts(id,part,body) VALUES(?,?,?)', o.id, p.part, p.body));
      }
    }
    check(statements.length <= 48, 'Batch exceeds the free query limit');
    if (statements.length) await env.DB.batch(statements);
    return reply({ stored: true });
  }
  if (path === '/store/commit') {
    check(value.files && typeof value.files === 'object' && !Array.isArray(value.files), 'Missing knowledge inventory');
    const files = Object.entries(value.files);
    check(files.length <= 3000, 'This free deployment supports up to 3000 knowledge files');
    let bytes = 0;
    for (const [path, f] of files) {
      check(safePath(path) && HASH.test(f.hash) && HASH.test(f.object) && Number.isInteger(f.size) && f.size >= 0, 'Unsafe knowledge inventory');
      bytes += f.size;
    }
    check(bytes <= 256 * 1024 * 1024, 'The personal library exceeds this free deployment limit');
    const ids = [...new Set(files.map(([, f]) => f.object))];
    for (let at = 0; at < ids.length; at += 90) {
      const group = ids.slice(at, at + 90);
      const rows = await stmt(env, `SELECT o.id,o.parts,COUNT(p.part) AS present FROM objects o LEFT JOIN object_parts p ON p.id=o.id WHERE o.id IN (${group.map(() => '?').join(',')}) GROUP BY o.id`, ...group).all();
      check(rows.results.length === group.length && rows.results.every(r => r.parts === r.present), 'Knowledge objects are not completely stored', 409);
    }
    const encoded = JSON.stringify({ files: value.files });
    const library = JSON.stringify(value.library || { collections: [] });
    check(encoder.encode(encoded + library).byteLength < 1800000, 'Knowledge index exceeds the database row limit');
    check(Array.isArray(value.ack || []) && (value.ack || []).length <= 50, 'Invalid phone receipt list');
    const updates = [stmt(env, 'UPDATE home SET manifest=?,library=?,revision=revision+1 WHERE id=1 AND revision=? AND lease_owner=? AND lease_until>?',
      encoded, library, value.revision, value.owner, Date.now())];
    if (value.ack?.length) updates.push(stmt(env, `UPDATE phone_captures SET processed=1 WHERE id IN (${value.ack.map(() => '?').join(',')}) AND EXISTS(SELECT 1 FROM home WHERE id=1 AND revision=? AND lease_owner=?)`,
      ...value.ack, value.revision + 1, value.owner));
    const done = await env.DB.batch(updates);
    check(done[0].meta.changes === 1, 'The central library changed; retry without overwriting', 409);
    return reply({ committed: true, revision: value.revision + 1 });
  }
  check(false, 'Not found', 404);
}
async function capture(request, env, ctx) {
  const text = await body(request, 32768);
  const p = (request.headers.get('Content-Type') || '').split(';')[0] === 'application/json' ? JSON.parse(text) : { value: text };
  check(p && typeof p === 'object' && !Array.isArray(p), 'Share a link or text');
  const value = p.value || p.url || p.text;
  check(typeof value === 'string' && value.trim(), 'Nothing to save');
  const collections = p.collections ?? (p.collection ? [p.collection] : []);
  check(Array.isArray(collections) && collections.every(c => typeof c === 'string' && c.trim()), 'Invalid collection names');
  check((p.note == null || typeof p.note === 'string') && (p.title == null || typeof p.title === 'string'), 'Note and title must be text');
  const key = request.headers.get('Idempotency-Key');
  check(!key || /^[a-f0-9-]{32,36}$/i.test(key), 'Invalid save receipt key');
  const id = 'capture-' + (key || crypto.randomUUID()).replaceAll('-', '').toLowerCase();
  const payload = JSON.stringify({ value: value.trim(), note: p.note || '', title: p.title || '', collections });
  const result = await stmt(env, 'INSERT OR IGNORE INTO phone_captures(id,captured_at,payload) VALUES(?,?,?)', id, new Date().toISOString(), payload).run();
  if (!result.meta.changes) {
    const existing = await stmt(env, 'SELECT payload FROM phone_captures WHERE id=?', id).first();
    check(existing?.payload === payload, 'That save receipt already belongs to different content', 409);
  }
  if (env.BACKEND_URL) ctx.waitUntil(fetch(new URL('/health', env.BACKEND_URL), { signal: AbortSignal.timeout(20000) }).catch(() => {}));
  return reply({ saved: true, new: !!result.meta.changes, capture_id: id, collections: collections.length ? collections : ['Inbox'],
    confirmation: 'Saved to WayKit. Your share is safely stored; no computer is needed.',
    note: 'Stored only. A link does not include the post or video contents.' });
}
function wire(id, result) { return { jsonrpc: '2.0', id, result }; }
function tool(value) { return { content: [{ type: 'text', text: JSON.stringify(value) }], isError: false }; }
function phonePage(url) {
  const base = url.origin + url.pathname.replace(/\/phone$/, '');
  const capture = base + '/capture', connection = base + '/mcp';
  const nonce = crypto.randomUUID();
  const html = `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Save to WayKit</title>
  <style>body{margin:0;background:#f7f4eb;color:#243629;font:17px/1.55 system-ui,sans-serif}main{max-width:600px;margin:auto;padding:36px 24px}h1{font-size:38px;line-height:1.15;letter-spacing:-1px}h2{font-size:22px;margin-top:36px}strong{color:#244e35}label{display:block;font-weight:600}input{box-sizing:border-box;width:100%;padding:14px;border:1px solid #c6cdbf;border-radius:8px;background:white;font-size:14px;margin:10px 0}button{padding:13px 18px;background:#244e35;color:white;border:0;border-radius:8px;font:600 16px system-ui}li{margin:14px 0}.small{font-size:14px;color:#586252}.brand{letter-spacing:2px;font-size:13px;font-weight:700}.card{background:#fff;padding:20px;border-radius:14px;margin:24px 0}</style>
  <main><div class="brand">WAYKIT</div><h1>Save from Instagram.<br>Keep it in WayKit.</h1><p>Share a link on your iPhone and it is saved immediately. Your computer can be off.</p>
  <div class="card"><label for="capture">Your private save address</label><input id="capture" readonly><button id="copy-capture">Copy save address</button><p id="feedback" role="status" class="small"></p></div>
  <h2>Set it up once on your iPhone</h2><ol><li>Open <strong>Shortcuts</strong> and create <strong>Save to WayKit</strong>. In its details, enable <strong>Show in Share Sheet</strong> and receive <strong>URLs and Text</strong>.</li>
  <li>Add <strong>Get Text from Input</strong>, with <strong>Shortcut Input</strong>.</li><li>Add <strong>Get Contents of URL</strong> and paste your save address. Choose <strong>POST</strong>, set the request body to <strong>JSON</strong>, and add a Text field named <strong>value</strong>. Select the previous action's Text variable for its value.</li>
  <li>Add <strong>Get Dictionary Value</strong> for <strong>confirmation</strong>, then <strong>Show Notification</strong> with that result.</li></ol>
  <h2>Then just share</h2><p><strong>Instagram → Share → Save to WayKit.</strong> The notification confirms the save. Check your first share in a connected assistant.</p><p class="small">An Instagram save keeps the link and any supplied text. Reading the reel's video or audio is currently unavailable.</p>
  <h2>Connect an assistant</h2><p>Add WayKit to ChatGPT on the web using this private connection address. Current custom MCP apps are web-only; your iPhone Shortcut saves directly to WayKit.</p><input id="connection" readonly><button id="copy-connection">Copy connection address</button>
  <p class="small">A first assistant task after inactivity can take about a minute while the free Python service wakes. Phone saves remain safely stored.</p>
  <p class="small"><strong>Keep these addresses private.</strong> Anyone with them can read or change your library. This page is a setup recipe, not an automatically installed Shortcut.</p></main>
  <script nonce="${nonce}">const capture=${JSON.stringify(capture)},connection=${JSON.stringify(connection)};document.querySelector('#capture').value=capture;document.querySelector('#connection').value=connection;
  for(const name of ['capture','connection'])document.querySelector('#copy-'+name).onclick=async()=>{try{await navigator.clipboard.writeText(document.querySelector('#'+name).value);document.querySelector('#feedback').textContent='Copied. Paste it into your setup.';}catch{document.querySelector('#'+name).select();document.querySelector('#feedback').textContent='Select the address and use Copy.';}};</script></html>`;
  return new Response(html, { headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store',
    'Referrer-Policy': 'no-referrer', 'X-Content-Type-Options': 'nosniff',
    'Content-Security-Policy': `default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}'; base-uri 'none'; frame-ancestors 'none'` } });
}
async function mcp(message, env) {
  check(message && message.jsonrpc === '2.0', 'Invalid MCP request');
  const { method, id, params = {} } = message;
  if (method?.startsWith('notifications/')) return null;
  if (method === 'initialize') return wire(id, { protocolVersion: params.protocolVersion || '2025-06-18',
    capabilities: { tools: { listChanged: false } }, serverInfo: { name: 'waykit', version: '0.3.2' }, instructions: INSTRUCTIONS });
  if (method === 'ping') return wire(id, {});
  if (method === 'tools/list') return wire(id, { tools: TOOLS });
  if (method === 'tools/call' && /^(waykit|lectic)_home$/.test(params.name)) return wire(id, tool({
    home: '/tmp/waykit-cache', mode: 'remote', transport: 'http', reach: 'Your central knowledge is persisted in Cloudflare D1. Phone saves work while the computer is off.' }));
  if (method === 'tools/call' && /^(waykit|lectic)_library$/.test(params.name) &&
      !Object.entries(params.arguments || {}).some(([key, value]) => key !== 'project' && value)) {
    const row = await stmt(env, 'SELECT revision,library FROM home WHERE id=1').first();
    const library = JSON.parse(row.library);
    const pending = await stmt(env, 'SELECT COUNT(*) AS n FROM phone_captures WHERE processed=0').first();
    return wire(id, tool({ ...library, home: '/tmp/waykit-cache', storage_mode: 'remote', snapshot_revision: row.revision,
      pending_phone_saves: pending.n, pending_note: pending.n ? 'Phone shares are durably saved and will be imported when the free Python service next handles a task.' : '' }));
  }
  if (method === 'resources/templates/list') return wire(id, { resourceTemplates: [] });
  if (method === 'prompts/list') return wire(id, { prompts: [] });
  if (!env.BACKEND_URL) return wire(id, { content: [{ type: 'text', text: 'The free WayKit service is being connected. Phone saves are already stored safely.' }], isError: true });
  try {
    const response = await fetch(new URL('/mcp', env.BACKEND_URL), { method: 'POST', headers: {
      'Content-Type': 'application/json', Authorization: 'Bearer ' + env.USER_TOKEN }, body: JSON.stringify(message), signal: AbortSignal.timeout(25000) });
    check(response.ok, 'Free service is starting', 503);
    return response.json();
  } catch {
    return wire(id, { content: [{ type: 'text', text: 'WayKit’s free Python service is waking up. Saves are safe. Retry this tool in about a minute; do not report the task completed yet.' }], isError: true });
  }
}
export default {
  async fetch(request, env, ctx) {
    try {
      const url = new URL(request.url);
      let path = url.pathname;
      if (path === '/health') return reply({ ok: true, service: 'waykit-free', persistent_storage: 'D1' });
      const supplied = request.headers.get('Authorization')?.replace(/^Bearer\s+/i, '');
      if (path.startsWith('/store/')) {
        check(await matches(supplied, env.STORE_TOKEN), 'Unauthorized', 401);
        return await store(request, env, path);
      }
      const match = /^\/t\/([A-Za-z0-9_-]+)(\/.*)$/.exec(path);
      if (match) path = match[2];
      check(await matches(supplied || match?.[1], env.USER_TOKEN), 'Unauthorized', 401);
      if (path === '/phone' && request.method === 'GET') return phonePage(url);
      if (path === '/capture' && request.method === 'POST') return await capture(request, env, ctx);
      if (path === '/mcp' && request.method === 'GET') return reply({ error: 'POST MCP requests here' }, 405);
      if (path === '/mcp' && request.method === 'DELETE') return new Response(null, { status: 204 });
      if (path === '/mcp' && request.method === 'POST') {
        const input = JSON.parse(await body(request, 2 * 1024 * 1024));
        const messages = Array.isArray(input) ? input : [input];
        check(messages.length <= 16, 'Too many MCP messages');
        const responses = [];
        for (const message of messages) { const response = await mcp(message, env); if (response) responses.push(response); }
        return responses.length ? reply(Array.isArray(input) ? responses : responses[0]) : new Response(null, { status: 202 });
      }
      if (path === '/home' && env.BACKEND_URL) {
        const response = await fetch(new URL('/home', env.BACKEND_URL), { method: request.method, headers: {
          Authorization: 'Bearer ' + env.USER_TOKEN, 'Content-Type': request.headers.get('Content-Type') || 'application/zip' },
          body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body });
        return new Response(response.body, { status: response.status, headers: response.headers });
      }
      return reply({ error: 'Not found' }, 404);
    } catch (error) {
      const status = error.status || (error instanceof SyntaxError ? 400 : 503);
      console.error(JSON.stringify({ event: 'request_failed', status }));
      return reply({ saved: false, error: status === 503 ? 'Free storage is temporarily unavailable. Retry; no save was acknowledged.' : error.message }, status);
    }
  }
};
