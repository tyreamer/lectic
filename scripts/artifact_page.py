"""One self-contained HTML page describing what a collection knows, for people without Lectic.

`lectic share` opens a live MCP tunnel; this is the opposite. It writes a single file with
no scripts, no network requests and no dependencies, so it opens from a folder, an email
attachment or a static host. Only material Lectic already treats as shareable travels:
knowledge units and their cited excerpts, the sources they came from, and reusable methods.
Private briefs, the user's own work and generated results stay behind.
"""
from datetime import datetime, timezone
import html
from pathlib import Path
from urllib.parse import urlsplit

from ec import Invalid, fingerprint, read, require, safe_child, text_write, validate_ir, validate_sources
from collection_store import Library
from release_version import VERSION as RELEASE_VERSION

SAFE_SCHEMES = {'http', 'https'}
MAX_QUOTE = 400


def safe_url(value):
    """A link is rendered as a link only when it cannot become script or a local path."""
    if not value or not isinstance(value, str): return None
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return None
    return value.strip() if parts.scheme in SAFE_SCHEMES and parts.netloc else None


def clip(text, limit=MAX_QUOTE):
    text = ' '.join(str(text or '').split())
    return text if len(text) <= limit else text[:limit].rstrip() + '...'


def resolve_target(library, selector):
    """A saved collection by name or id, or one build id inside a saved collection."""
    if selector and str(selector).startswith('build-'):
        for entry in library.index['collections']:
            folder, data = library.resolve(entry['collection_id'])
            if selector in data['builds']:
                return folder, data, selector
        raise Invalid('No saved build with that id: ' + str(selector))
    resolved = library.resolve(selector)
    require(resolved is not None, 'Name a saved collection (or a build id) to share')
    return resolved[0], resolved[1], None


def method_records(folder, data, ir, only_build=None):
    """Reusable methods that are still bound to the current knowledge. Never the result or brief."""
    from goal_workflow import validate_build
    ir_hash = fingerprint(ir) if ir else None
    known = {u['unit_id'] for u in ir['units']} if ir else set()
    records, seen = [], set()
    for build_id in reversed(data['builds']):
        if only_build and build_id != only_build: continue
        try:
            build = safe_child(folder / 'builds', build_id)
            validate_build(build)
            manifest = read(build / 'manifest.json')
            cap = read(build / 'method.json')['capability']
        except (Invalid, OSError, ValueError, KeyError):
            continue
        if manifest['ir_hash'] != ir_hash or cap['capability_id'] in seen: continue
        if not set(cap['unit_ids']) <= known: continue
        seen.add(cap['capability_id'])
        records.append({'build_id': build_id, 'title': cap['title'], 'description': cap['description'],
                        'inputs': cap['inputs'], 'output_contract': cap['output_contract'],
                        'steps': [s['instruction'] for s in cap['steps']], 'boundaries': cap['boundaries'],
                        'conflict_policy': cap['conflict_policy'],
                        'examples': [{'input': e['input'], 'output': e['output'], 'status': e['status']} for e in cap['examples']]})
    return records


def page_data(project='.', selector=None, build=None, include_quotes=True):
    """Everything the page shows, as plain data, so it can be inspected and tested."""
    library = Library(project)
    folder, data, build_id = resolve_target(library, build or selector)
    run = library.run(folder, data)
    _, docs, _ = validate_sources(run)
    ir = validate_ir(run) if (run / 'ir.json').is_file() else None
    kinds = {}
    for unit in (ir['units'] if ir else []):
        kinds[unit['type']] = kinds.get(unit['type'], 0) + 1
    source_title = lambda doc: doc['title'] or Path(doc['filename']).name
    units = [{'unit_id': u['unit_id'], 'type': u['type'], 'status': u['status'], 'title': u['title'],
              'statement': u['statement'], 'scope': u['scope'],
              'evidence': [{'source': source_title(docs[e['source_id']])
                            if e['source_id'] in docs else e['source_id'],
                            'url': safe_url(docs[e['source_id']]['url']) if e['source_id'] in docs else None,
                            'quote': clip(e['quote']) if include_quotes else None} for e in u['evidence']]}
             for u in (ir['units'] if ir else [])]
    sources = [{'title': source_title(d), 'creator': d['creator'], 'url': safe_url(d['url']),
                'kind': d['caption_type'] if d['caption_type'] not in {None, 'unknown'} else 'text'}
               for d in docs.values()]
    version = None
    origin = folder / 'pack-origin.json'
    if origin.is_file():
        try:
            version = read(origin)['manifest'].get('version')
        except (OSError, ValueError, KeyError):
            version = None
    record = folder / 'collection.json'
    return {'name': data['name'], 'collection_id': data['collection_id'], 'build_id': build_id,
            'purpose': (f"Reusable, source-backed knowledge compiled from {len(sources)} "
                        f"source{'s' if len(sources) != 1 else ''} with Lectic."),
            'units': units, 'unit_kinds': sorted(kinds.items(), key=lambda kv: (-kv[1], kv[0])),
            'unit_count': len(units), 'sources': sources, 'quotes_included': include_quotes,
            'methods': method_records(folder, data, ir, build_id),
            'provenance': {'source_revision': data['active_revision'],
                           'knowledge_revision': fingerprint(ir)[:16] if ir else None,
                           'source_revisions': len(data['revisions']),
                           'version': version,
                           'updated_at': datetime.fromtimestamp(record.stat().st_mtime, timezone.utc).isoformat(timespec='seconds') if record.is_file() else None,
                           'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                           'lectic_version': RELEASE_VERSION}}


# ------------------------------------------------------------------ render

STYLE = """
:root { color-scheme: light dark; }
body { margin: 0 auto; max-width: 52rem; padding: 2rem 1.25rem 4rem;
       font: 16px/1.6 system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }
h1 { margin-bottom: .25rem; } h2 { margin-top: 2.5rem; border-bottom: 1px solid #8884; padding-bottom: .3rem; }
h3 { margin-bottom: .2rem; } p { margin: .4rem 0; }
.lede { font-size: 1.05rem; opacity: .85; }
.tags { padding: 0; list-style: none; display: flex; flex-wrap: wrap; gap: .4rem; }
.tags li { border: 1px solid #8886; border-radius: 999px; padding: .1rem .7rem; font-size: .85rem; }
article { border: 1px solid #8884; border-radius: .6rem; padding: .9rem 1.1rem; margin: .9rem 0; }
blockquote { margin: .5rem 0; padding: .1rem 0 .1rem .9rem; border-left: 3px solid #8886; opacity: .9; }
cite { display: block; font-size: .85rem; opacity: .75; font-style: normal; }
dl { display: grid; grid-template-columns: max-content 1fr; gap: .25rem 1rem; margin: 0; }
dt { opacity: .7; } dd { margin: 0; }
code, pre { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .9em; }
pre { background: #8881; padding: .8rem 1rem; border-radius: .5rem; overflow-x: auto; }
footer { margin-top: 3rem; font-size: .85rem; opacity: .75; }
""".strip()


def e(value):
    return html.escape('' if value is None else str(value), quote=True)


def link(url, label):
    """Escaped anchor for a vetted URL; plain text for anything else."""
    return f'<a href="{e(url)}" rel="noopener noreferrer nofollow">{e(label)}</a>' if url else e(label)


def render_page(info):
    p = info['provenance']
    out = ['<!doctype html>', '<html lang="en">', '<head>', '<meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1">',
           f'<title>{e(info["name"])} | Lectic knowledge</title>', f'<style>{STYLE}</style>',
           '</head>', '<body>',
           f'<h1>{e(info["name"])}</h1>', f'<p class="lede">{e(info["purpose"])}</p>']
    if info['unit_kinds']:
        out.append('<ul class="tags">' + ''.join(
            f'<li>{e(count)} {e(kind)}{"s" if count != 1 else ""}</li>' for kind, count in info['unit_kinds']) + '</ul>')

    out.append('<h2>What it can help with</h2>')
    if info['methods']:
        for method in info['methods']:
            out += [f'<article><h3>{e(method["title"])}</h3>', f'<p>{e(method["description"])}</p>',
                    '<dl>', f'<dt>Give it</dt><dd>{e(method["inputs"])}</dd>',
                    f'<dt>You get</dt><dd>{e(method["output_contract"])}</dd>', '</dl>']
            if method['steps']:
                out.append('<p>Steps:</p><ol>' + ''.join(f'<li>{e(s)}</li>' for s in method['steps']) + '</ol>')
            if method['boundaries']:
                out.append('<p>Limits:</p><ul>' + ''.join(f'<li>{e(b)}</li>' for b in method['boundaries']) + '</ul>')
            if method['conflict_policy'].strip():
                out.append(f'<p>Where sources disagree: {e(method["conflict_policy"])}</p>')
            for example in method['examples']:
                out += ['<blockquote>', f'<p><strong>Example input.</strong> {e(clip(example["input"], 600))}</p>',
                        f'<p><strong>Example output.</strong> {e(clip(example["output"], 600))}</p>',
                        f'<cite>Illustrative {e(example["status"])} example written when the method was built, not a recorded result.</cite>',
                        '</blockquote>']
            out.append('</article>')
    else:
        out.append('<p>No reusable method has been built against the current knowledge yet. '
                   'The knowledge below is still what this collection can answer from.</p>')

    out.append('<h2>What it knows</h2>')
    if info['units'] and not info['quotes_included']:
        out.append('<p>Evidence sources are identified below; quoted excerpts were omitted from this shared page.</p>')
    if info['units']:
        for unit in info['units']:
            out += [f'<article><h3>{e(unit["title"])}</h3>',
                    f'<p>{e(unit["statement"])}</p>',
                    f'<p><small>{e(unit["type"])} / {e(unit["status"])} / applies where: {e(unit["scope"])}</small></p>']
            for item in unit['evidence']:
                if item['quote'] is None:
                    out.append(f'<p><small>Evidence: {link(item["url"], item["source"])}</small></p>')
                else:
                    out += ['<blockquote>', f'<p>{e(item["quote"])}</p>',
                            f'<cite>{link(item["url"], item["source"])}</cite>', '</blockquote>']
            out.append('</article>')
    else:
        out.append('<p>Sources are saved, but no knowledge has been derived from them yet.</p>')

    out.append('<h2>Sources</h2><ul>')
    for source in info['sources']:
        label = source['title'] + (' - ' + source['creator'] if source['creator'] else '')
        out.append(f'<li>{link(source["url"], label)} <small>({e(source["kind"])})</small></li>')
    out.append('</ul>')

    out += ['<h2>Use it yourself</h2>',
            '<p>This page is a read-only summary. To let your own assistant apply this knowledge, '
            'ask the person who sent it for the packaged collection, then:</p>',
            '<pre><code>pip install lectic\n'
            'lectic setup\n'
            f'lectic install &quot;{e(info["pack_file"])}&quot;</code></pre>',
            '<p>After installing, open any connected assistant and say: '
            f'<code>Use my {e(info["name"])} to review this.</code></p>']

    out += ['<h2>Provenance</h2>', '<dl>',
            f'<dt>Source revision</dt><dd><code>{e(p["source_revision"])}</code> '
            f'({e(p["source_revisions"])} saved revision{"s" if p["source_revisions"] != 1 else ""})</dd>']
    if p['knowledge_revision']:
        out.append(f'<dt>Knowledge revision</dt><dd><code>{e(p["knowledge_revision"])}...</code></dd>')
    if info['build_id']:
        out.append(f'<dt>Build</dt><dd><code>{e(info["build_id"])}</code></dd>')
    if p['version']:
        out.append(f'<dt>Version</dt><dd>{e(p["version"])}</dd>')
    if p['updated_at']:
        out.append(f'<dt>Last updated</dt><dd>{e(p["updated_at"])}</dd>')
    out += [f'<dt>Page generated</dt><dd>{e(p["generated_at"])}</dd>',
            f'<dt>Built with</dt><dd>Lectic {e(p["lectic_version"])}</dd>', '</dl>']

    quote_note = ('Quoted passages establish traceability, not agreement or truth. '
                  'Citing a source does not grant permission to redistribute it. ' if info['quotes_included'] else '')
    out += [f'<footer><p>{quote_note}This command does not read private briefs, submitted work or generated results. '
            'Review reusable methods and examples for sensitive details before publishing.</p></footer>',
            '</body>', '</html>', '']
    return '\n'.join(out)


def write_page(project='.', selector=None, destination=None, build=None, include_quotes=True):
    from packs import slug
    info = page_data(project, selector, build, include_quotes)
    info['pack_file'] = slug(info['name']) + '.lectic'
    path = Path(destination).expanduser() if destination else Path(project) / (slug(info['name']) + '.html')
    path = path.resolve()
    if path.is_dir(): path = path / (slug(info['name']) + '.html')
    if path.suffix.lower() not in {'.html', '.htm'}: path = path.with_name(path.name + '.html')
    text_write(path, render_page(info))
    return {'phase': 'artifact_written', 'file': str(path), 'name': info['name'],
            'collection_id': info['collection_id'], 'build_id': info['build_id'],
            'units': info['unit_count'], 'sources': len(info['sources']), 'methods': len(info['methods']),
            'bytes': path.stat().st_size,
            'contains': ('knowledge units, source links, reusable methods and provenance' +
                         (', plus cited source excerpts' if include_quotes else '')),
            'privacy': ('This command does not read private briefs, submitted work or generated results. '
                        'Review methods and examples for sensitive details before publishing.')}
