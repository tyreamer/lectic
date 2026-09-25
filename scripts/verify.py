"""Evidence linkage verification for Lectic collections and packs.

Checks that every knowledge unit in a compiled IR has its claimed evidence
anchored in the actual source material — verifying both that evidence excerpts
exist and that each excerpt's source content hash matches what's stored.

Exit codes (for CLI use):
    0  — all units fully evidence-backed (or partial with --allow-partial)
    1  — one or more units have broken evidence linkage

Usage:
    from verify import verify_collection, verify_pack, format_report
"""
from __future__ import annotations

import json
from pathlib import Path

from collection_store import Library
from ec import Invalid, digest, fingerprint, read, require, validate_ir, validate_sources
from home import storage_root
from store import LocalStore


# ---------------------------------------------------------------- core check

def check_unit_evidence(unit: dict, docs: dict, segments: dict) -> dict:
    """Verify the evidence citations on one knowledge unit.

    Returns a result dict:
      unit_id       — the unit's ID
      status        — 'verified' | 'partial' | 'broken'
      evidence_ok   — list of (source_id, segment_id) pairs that verified
      evidence_fail — list of dicts describing failures
    """
    ok, fail = [], []
    for ev in unit.get('evidence', []):
        sid = ev.get('source_id')
        seg_id = ev.get('segment_id')
        quote = ev.get('quote', '')
        doc = docs.get(sid)
        if not doc:
            fail.append({'source_id': sid, 'segment_id': seg_id,
                         'reason': 'source not in corpus'})
            continue
        key = (sid, seg_id)
        seg = segments.get(key)
        if not seg:
            fail.append({'source_id': sid, 'segment_id': seg_id,
                         'reason': 'segment not found in source'})
            continue
        # Quote should appear in the segment text (case-sensitive substring match)
        seg_text = seg.get('text', '') if isinstance(seg, dict) else ''
        if quote and quote not in seg_text:
            fail.append({'source_id': sid, 'segment_id': seg_id,
                         'reason': f'quote not found in segment: {quote[:80]!r}…'})
            continue
        ok.append({'source_id': sid, 'segment_id': seg_id})

    total = len(unit.get('evidence', []))
    if total == 0:
        status = 'no_evidence'
    elif not fail:
        status = 'verified'
    elif not ok:
        status = 'broken'
    else:
        status = 'partial'

    return {
        'unit_id': unit['unit_id'],
        'type': unit.get('type', '?'),
        'title': unit.get('title', ''),
        'status': status,
        'evidence_ok': len(ok),
        'evidence_total': total,
        'failures': fail,
    }


def check_source_hashes(docs: dict, home: Path) -> dict:
    """Verify that stored raw source bytes still hash to their recorded content_hash.

    Returns:
      verified   — list of source_id strings where bytes match
      mismatched — list of dicts with source_id, filename, reason
      missing    — list of source_id strings where raw file not found
    """
    store = LocalStore(home)
    verified, mismatched, missing = [], [], []
    for sid, doc in docs.items():
        raw_path = doc.get('raw_path')
        content_hash = doc.get('content_hash')
        if not raw_path or not content_hash:
            mismatched.append({'source_id': sid, 'filename': doc.get('filename', '?'),
                               'reason': 'missing raw_path or content_hash in document'})
            continue
        # Try to find the raw file via the blob store
        blob_hash = content_hash  # content_hash is SHA-256 of raw bytes
        blob_path = store.blob_path(blob_hash)
        if blob_path and blob_path.is_file():
            actual = digest(blob_path.read_bytes())
            if actual == content_hash:
                verified.append(sid)
            else:
                mismatched.append({'source_id': sid, 'filename': doc.get('filename', '?'),
                                   'reason': f'blob hash mismatch: expected {content_hash[:16]}… got {actual[:16]}…'})
        else:
            missing.append(sid)
    return {'verified': verified, 'mismatched': mismatched, 'missing': missing}


# ---------------------------------------------------------------- collection verify

def verify_collection(project, collection_name: str | None = None) -> dict:
    """Full evidence verification for an installed collection.

    Checks:
    1. Every knowledge unit has its cited evidence anchored in the source corpus
    2. Source content hashes still match the stored raw bytes

    Returns a report dict suitable for both human formatting and JSON output.
    """
    project = Path(project).resolve()
    home = storage_root(project)
    library = Library(project)
    resolved = library.resolve(collection_name)
    require(resolved is not None, 'No collection found — pass a collection name or set an active one')
    folder, data = resolved
    run = library.run(folder, data)
    require((run / 'ir.json').is_file(), 'Collection has not been compiled yet — run lectic prepare first')
    ir = validate_ir(run)
    corpus, docs, segments = validate_sources(run)

    unit_results = [check_unit_evidence(unit, docs, segments) for unit in ir['units']]
    source_check = check_source_hashes(docs, home)

    # Aggregate
    by_status = {}
    for r in unit_results:
        by_status.setdefault(r['status'], []).append(r)

    verified_count = len(by_status.get('verified', []))
    partial_count = len(by_status.get('partial', []))
    broken_count = len(by_status.get('broken', []))
    no_evidence_count = len(by_status.get('no_evidence', []))
    total = len(unit_results)

    overall = 'verified' if (verified_count == total and not source_check['mismatched']) else (
        'partial' if (broken_count == 0 and not source_check['mismatched']) else 'issues_found'
    )

    return {
        'collection': data['name'],
        'collection_id': data['collection_id'],
        'overall': overall,
        'units': {
            'total': total,
            'verified': verified_count,
            'partial': partial_count,
            'broken': broken_count,
            'no_evidence': no_evidence_count,
        },
        'sources': {
            'total': len(docs),
            'verified': len(source_check['verified']),
            'mismatched': len(source_check['mismatched']),
            'missing': len(source_check['missing']),
        },
        'unit_results': unit_results,
        'source_issues': source_check['mismatched'],
        'sources_missing_raw': source_check['missing'],
    }


# ---------------------------------------------------------------- pack verify (without installing)

def verify_pack_manifest(manifest: dict, members: dict) -> dict:
    """Verify internal consistency of a pack's evidence excerpts vs. its IR.

    Checks that each knowledge unit's evidence citations have corresponding
    excerpts in sources/excerpts.json, and that the file hashes in the manifest
    match the actual zip member bytes.

    Returns a report dict.
    """
    # File hash check (already done by open_pack, but we re-report it here)
    from ec import digest as ec_digest
    hash_issues = []
    for path, expected in manifest.get('files', {}).items():
        if path in members:
            actual = ec_digest(members[path])
            if actual != expected:
                hash_issues.append({'path': path, 'reason': 'file hash mismatch'})

    # Load IR and excerpts
    ir_raw = members.get('knowledge/ir.json')
    excerpts_raw = members.get('sources/excerpts.json')
    if not ir_raw or not excerpts_raw:
        return {'overall': 'incomplete', 'reason': 'Missing knowledge/ir.json or sources/excerpts.json',
                'hash_issues': hash_issues}

    ir = json.loads(ir_raw.decode('utf-8'))
    excerpts_list = json.loads(excerpts_raw.decode('utf-8'))

    # Build excerpt lookup: (source_id, segment_id) → quote text
    excerpt_index: dict[tuple, str] = {}
    for src in excerpts_list:
        for ex in src.get('excerpts', []):
            excerpt_index[(src['source_id'], ex['segment_id'])] = ex.get('quote', '')

    broken, partial, verified, no_ev = [], [], [], []
    for unit in ir.get('units', []):
        ev_list = unit.get('evidence', [])
        if not ev_list:
            no_ev.append(unit['unit_id'])
            continue
        ok_ev, fail_ev = [], []
        for ev in ev_list:
            key = (ev.get('source_id'), ev.get('segment_id'))
            quote = ev.get('quote', '')
            if key not in excerpt_index:
                fail_ev.append({'source_id': ev.get('source_id'), 'segment_id': ev.get('segment_id'),
                                'reason': 'no matching excerpt in pack'})
            elif quote and quote not in excerpt_index[key]:
                fail_ev.append({'source_id': ev.get('source_id'), 'segment_id': ev.get('segment_id'),
                                'reason': 'quote not in excerpt'})
            else:
                ok_ev.append(key)
        if not fail_ev:
            verified.append(unit['unit_id'])
        elif not ok_ev:
            broken.append({'unit_id': unit['unit_id'], 'failures': fail_ev})
        else:
            partial.append({'unit_id': unit['unit_id'], 'failures': fail_ev})

    total = len(ir.get('units', []))
    overall = ('verified' if not broken and not partial and not hash_issues and not no_ev
               else 'partial' if not broken and not hash_issues
               else 'issues_found')

    return {
        'overall': overall,
        'units': {
            'total': total,
            'verified': len(verified),
            'partial': len(partial),
            'broken': len(broken),
            'no_evidence': len(no_ev),
        },
        'broken_units': broken,
        'partial_units': partial,
        'hash_issues': hash_issues,
    }


# ---------------------------------------------------------------- formatting

def format_report(report: dict) -> str:
    """Human-readable summary of a verify_collection report."""
    lines = []
    collection_name = report.get('collection', '?')
    overall = report.get('overall', '?')

    status_symbol = {'verified': 'OK', 'partial': '~', 'issues_found': '!'}.get(overall, '?')
    lines.append(f"[{status_symbol}] {collection_name}  [{overall}]")
    lines.append('')

    u = report.get('units', {})
    total = u.get('total', 0)
    lines.append(f"  Knowledge units : {total} total")
    lines.append(f"    {u.get('verified', 0)} verified  "
                 f"{u.get('partial', 0)} partial  "
                 f"{u.get('broken', 0)} broken  "
                 f"{u.get('no_evidence', 0)} without evidence")

    s = report.get('sources', {})
    lines.append(f"  Sources         : {s.get('total', 0)} total, "
                 f"{s.get('verified', 0)} content-verified")

    if report.get('source_issues'):
        lines.append('')
        lines.append('  Source hash issues:')
        for issue in report['source_issues']:
            lines.append(f"    [!] {issue.get('filename', issue.get('source_id', '?'))}: {issue['reason']}")

    broken_units = [r for r in report.get('unit_results', []) if r['status'] == 'broken']
    if broken_units:
        lines.append('')
        lines.append('  Broken evidence linkage:')
        for r in broken_units[:10]:  # cap at 10
            lines.append(f"    [!] [{r['type']}] {r['title'][:70]}")
            for f in r['failures'][:3]:
                lines.append(f"        {f['reason']}")
        if len(broken_units) > 10:
            lines.append(f"    ... and {len(broken_units) - 10} more")

    partial_units = [r for r in report.get('unit_results', []) if r['status'] == 'partial']
    if partial_units:
        lines.append('')
        lines.append(f"  Partial evidence ({len(partial_units)} units -- some evidence citations missing):")
        for r in partial_units[:5]:
            lines.append(f"    [~] [{r['type']}] {r['title'][:70]}")
        if len(partial_units) > 5:
            lines.append(f"    ... and {len(partial_units) - 5} more")

    lines.append('')
    if overall == 'verified':
        lines.append('  All evidence-backed. Your AI can cite its sources for every claim in this collection.')
    elif overall == 'partial':
        lines.append('  Some units have missing evidence links -- re-compile to regenerate.')
    else:
        lines.append('  Evidence linkage broken -- sources may have changed. Re-add and re-compile.')
    return '\n'.join(lines)


def format_pack_report(report: dict) -> str:
    """Human-readable summary of a verify_pack_manifest report."""
    lines = []
    overall = report.get('overall', '?')
    status_symbol = {'verified': 'OK', 'partial': '~', 'issues_found': '!'}.get(overall, '?')
    lines.append(f"[{status_symbol}] Pack evidence check  [{overall}]")
    lines.append('')
    u = report.get('units', {})
    lines.append(f"  {u.get('total', 0)} units: "
                 f"{u.get('verified', 0)} verified, "
                 f"{u.get('partial', 0)} partial, "
                 f"{u.get('broken', 0)} broken, "
                 f"{u.get('no_evidence', 0)} without evidence")
    if report.get('hash_issues'):
        lines.append('  File hash issues:')
        for issue in report['hash_issues']:
            lines.append(f"    [!] {issue['path']}: {issue['reason']}")
    if report.get('broken_units'):
        lines.append('  Broken evidence:')
        for r in report['broken_units'][:10]:
            lines.append(f"    [!] {r['unit_id']}")
            for f in r['failures'][:2]:
                lines.append(f"        {f['reason']}")
    return '\n'.join(lines)
