"""Private cloud library operations for authenticated Lectic accounts.

Provides goal-oriented chat operations:
- save_knowledge: Save text, URLs, or files for later without triggering extraction.
- learn_from_source: Extract and compile reusable knowledge, preserving source evidence
                     and distinguishing interpretation from source statements.
- organize_knowledge: Infer and manage pack relationships (specialization, preferences, etc.).
- get_relevant_context: Selectively retrieve relevant knowledge units across relationships.
- apply_knowledge: Apply relevant compiled knowledge to real tasks with auditable citations.
- search_knowledge: Search across private library knowledge and sources.
- export_library / import_library: Portable whole-home export/import compatible with local Lectic.

Authorization is strictly scoped to the verified account's private home.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Dict, List, Optional, Tuple, Union

from account_service import AccountStore, AuthorizationError
from candidate_collections import find_candidate_collections
from capture_policy import confirmation_line, decide_placement, describe_source
from capture_store import CaptureStore
from capture_write import save_capture
from collection_store import Library
from ec import (
    VERSION, Invalid, digest, fingerprint, read, require, safe_child,
    validate_ir, validate_schema, write, plan_records, write_run
)
from home_archive import archive_home, merge_archive
from ingestors import TranscriptInput
from intelligence import assess_import, compose_context, explain_collection, knowledge_graph, tokens
from store import LocalStore


class CloudLibrary:
    """Manages the private, isolated Lectic library for an authenticated account."""

    def __init__(self, account_id: str, cloud_root: Union[Path, str],
                 account_store: Optional[AccountStore] = None):
        if not account_id:
            raise AuthorizationError('Missing verified account identity')

        self.cloud_root = Path(cloud_root).resolve()
        self.account_store = account_store or AccountStore(self.cloud_root)
        self.account = self.account_store.get_account(account_id)
        if not self.account:
            raise AuthorizationError(f'Account {account_id} not found')

        self.account_id = account_id
        self.home = self.account_store.get_account_home(account_id)
        self.library = Library(self.home, home=self.home)
        self.inbox = CaptureStore(self.home, home=self.home)
        self.store = LocalStore(self.home)

    def _require_authorized_collection(self, selector: Optional[str]) -> Tuple[Path, Dict[str, Any]]:
        """Verify that the requested collection exists in this account's private library."""
        if not selector:
            raise Invalid('Collection selector is required')
        try:
            resolved = self.library.resolve(selector)
        except Invalid:
            resolved = None
        if not resolved:
            raise AuthorizationError(f"Collection '{selector}' not found in your private library")
        folder, data = resolved
        # Double check folder is inside account home
        try:
            folder.resolve().relative_to(self.home.resolve())
        except ValueError:
            raise AuthorizationError('Access denied: collection path outside account home')
        return folder, data

    # -------------------------------------------------------------------------
    # 1. save_knowledge
    # -------------------------------------------------------------------------
    def save_knowledge(self, *, text: str = '', url: str = '', title: str = '',
                       note: str = '', files: tuple = (), collections: tuple = ()) -> Dict[str, Any]:
        """Save a source, link, or note for later.
        
        Saving alone never silently triggers extraction, compilation, or paid processing.
        """
        placement = decide_placement(self.home, url=url or '', text=text or '', title=title or '',
                                     files=files or (), note=note or '', collections=collections or ())
        import_plan = assess_import(self.home, url=url or '', text=text or '', title=title or '',
                                    files=files or (), note=note or '')
        source_desc = describe_source(url=url or '', text=text or '', files=files or ())

        inbox_dir = self.home / 'inbox'
        inbox_dir.mkdir(parents=True, exist_ok=True)
        record = save_capture(inbox_dir, url=url or '', text=text or '', files=list(files or ()),
                              note=note or '', collections=list(placement['collections']),
                              title=title or '', origin='cloud-chat')
        item = self.inbox.import_record(record)

        return {
            'saved': True,
            'capture_id': item['capture_id'],
            'new': item['new'],
            'collections': list(placement['collections']),
            'decision': placement['decision'],
            'question': placement.get('question'),
            'candidate_collections': placement.get('candidates', []),
            'all_collections': placement.get('all_collections', []),
            'knowledge_plan': import_plan,
            'source': source_desc,
            'confirmation': confirmation_line(placement, source_desc),
            'guidance': placement.get('guidance'),
            'note': 'Saved only. Nothing was retrieved, extracted or built; process the collection when a use needs it.'
        }

    # -------------------------------------------------------------------------
    # 2. learn_from_source
    # -------------------------------------------------------------------------
    def learn_from_source(self, *, source_id: Optional[str] = None, capture_id: Optional[str] = None,
                          collection: Optional[str] = None, text: Optional[str] = None,
                          title: Optional[str] = None, units: Optional[List[Dict[str, Any]]] = None,
                          note: Optional[str] = None) -> Dict[str, Any]:
        """Extract and compile reusable knowledge from a saved source or text into a pack.
        
        Preserves source evidence and explicitly distinguishes source statements ('observed'/'explicit')
        from interpretations ('inferred' or 'synthesized').
        """
        target_name = collection
        content_to_learn = ''
        source_title = title or 'Saved Source'
        url_val = ''

        # Case A: Learning from a capture
        if capture_id:
            try:
                event, state = self.inbox.find(capture_id)
            except Exception as e:
                raise AuthorizationError(f'Capture {capture_id} not found in your private library: {e}')
            content_to_learn = event.get('original_value', '')
            url_val = event.get('url', '')
            source_title = title or event.get('title') or (url_val if url_val else 'Capture')
            if not target_name:
                cols = event.get('requested_collections') or []
                if cols and cols[0] != 'Inbox':
                    target_name = cols[0]
                else:
                    target_name = title or 'Learned Knowledge'

        # Case B: Learning from direct text
        elif text:
            content_to_learn = text
            if not target_name:
                target_name = title or 'Learned Knowledge'

        # Case C: Learning from existing collection
        elif collection:
            folder, data = self._require_authorized_collection(collection)
            target_name = data['name']
            run = self.library.run(folder, data)
            from ec import validate_sources
            _, docs, _ = validate_sources(run)
            if docs:
                first_doc = next(iter(docs.values()))
                source_title = first_doc.get('title') or first_doc['filename']
                content_to_learn = (run / first_doc['raw_path']).read_text(encoding='utf-8', errors='ignore')

        if not content_to_learn:
            raise Invalid('Provide text, capture_id, or collection to learn from')

        clean_filename = re.sub(r'[^a-zA-Z0-9_\-\.]+', '_', (source_title.lower() or 'source') + '.txt')
        if not clean_filename.endswith('.txt'):
            clean_filename += '.txt'

        # Build run in staging directory
        with tempfile.TemporaryDirectory() as staging_dir:
            staging_run = Path(staging_dir) / 'run'
            staging_run.mkdir(parents=True)

            meta = {'title': source_title}
            if url_val:
                meta['url'] = url_val

            raw_bytes = content_to_learn.encode('utf-8')
            records = [TranscriptInput(clean_filename, raw_bytes, meta)]
            docs, corpus, blobs = plan_records(records)
            write_run(docs, corpus, blobs, staging_run, store=self.store)

            doc_item = docs[0]
            active_source_id = doc_item['source_id']
            segments = doc_item['segments']

            compiled_units = []
            if units:
                for i, u in enumerate(units):
                    uid = u.get('unit_id') or f'unit-{fingerprint(u)[:16]}'
                    # Sanitize unit_id to match pattern ^[a-z0-9]+(?:-[a-z0-9]+)*$
                    clean_uid = re.sub(r'[^a-z0-9\-]+', '-', uid.lower()).strip('-') or f'unit-{i+1}'

                    status = u.get('status', 'explicit')
                    if status == 'observed':
                        status = 'explicit'
                    if status not in {'explicit', 'inferred', 'synthesized'}:
                        status = 'inferred'

                    unit_type = u.get('type', 'principle')
                    if unit_type not in {'concept', 'definition', 'principle', 'heuristic', 'procedure',
                                        'framework', 'example', 'warning', 'failure_pattern', 'claim', 'opinion'}:
                        unit_type = 'principle'

                    evidence = u.get('evidence', [])
                    valid_evidence = []
                    for ev in evidence:
                        quote = ev.get('quote', '')
                        seg_id = ev.get('segment_id')
                        seg_match = next((s for s in segments if s['segment_id'] == seg_id), None)
                        if seg_match and quote and quote in seg_match['text']:
                            valid_evidence.append({
                                'source_id': active_source_id,
                                'segment_id': seg_id,
                                'quote': quote
                            })
                        elif segments:
                            for s in segments:
                                if quote and quote in s['text']:
                                    valid_evidence.append({
                                        'source_id': active_source_id,
                                        'segment_id': s['segment_id'],
                                        'quote': quote
                                    })
                                    break

                    if not valid_evidence and segments:
                        s0 = segments[0]
                        valid_evidence.append({
                            'source_id': active_source_id,
                            'segment_id': s0['segment_id'],
                            'quote': s0['text'][:min(100, len(s0['text']))]
                        })

                    compiled_units.append({
                        'schema_version': VERSION,
                        'unit_id': clean_uid,
                        'type': unit_type,
                        'status': status,
                        'title': u.get('title', f'Unit {i+1}'),
                        'statement': u.get('statement', ''),
                        'scope': u.get('scope', f'Applicable to {target_name}'),
                        'derivation': u.get('derivation', 'Extracted from source statement'),
                        'evidence': valid_evidence,
                        'attribution': [],
                        'relations': []
                    })
            else:
                # Deterministic evidence-preserving decomposition from source segments
                count = 0
                for seg in segments[:12]:
                    seg_text = seg['text'].strip()
                    if not seg_text or len(seg_text) < 15:
                        continue

                    sentences = re.split(r'(?<=[.!?])\s+', seg_text)
                    for sent in sentences[:2]:
                        sent = sent.strip()
                        if len(sent) < 15:
                            continue
                        count += 1
                        uid = f'unit-{fingerprint(sent + seg["segment_id"])[:16]}'
                        words = sent.split()
                        title_str = ' '.join(words[:5]).capitalize()
                        if not title_str.endswith('.'):
                            title_str += '...'

                        compiled_units.append({
                            'schema_version': VERSION,
                            'unit_id': uid,
                            'type': 'principle',
                            'status': 'explicit',
                            'title': title_str,
                            'statement': sent,
                            'scope': f'Applicable to {target_name}',
                            'derivation': 'Direct source statement observed in training/reference material',
                            'evidence': [{
                                'source_id': active_source_id,
                                'segment_id': seg['segment_id'],
                                'quote': sent[:min(120, len(sent))]
                            }],
                            'attribution': [],
                            'relations': []
                        })

            # Checkpoint per source
            checkpoint = {
                'schema_version': VERSION,
                'corpus_id': corpus['corpus_id'],
                'source_id': active_source_id,
                'note': 'Compiled knowledge units',
                'units': compiled_units
            }
            write(staging_run / f'units/{active_source_id}.json', checkpoint)

            # Assemble and write IR
            ir_payload = {
                'schema_version': VERSION,
                'corpus_id': corpus['corpus_id'],
                'units': compiled_units,
                'coverage': [{
                    'source_id': active_source_id,
                    'unit_ids': [u['unit_id'] for u in compiled_units],
                    'note': 'Reviewed source content'
                }]
            }
            validate_schema(ir_payload, 'ir')
            write(staging_run / 'ir.json', ir_payload)

            # Archive and adopt into library
            exists = any(c['name'].casefold() == target_name.casefold() for c in self.library.index['collections'])
            if exists:
                folder, col_data = self.library.archive(adopt=staging_run, collection=target_name)
            else:
                folder, col_data = self.library.archive(adopt=staging_run, name=target_name)

        # Inspect relationships across collections
        graph = knowledge_graph(self.home)
        active_col_id = col_data['collection_id']
        inferred_rels = [r for r in graph['relationships'] if active_col_id in {r['from'], r['to']}]

        # Re-map 'explicit' status to 'observed' in user-facing response for clarity
        user_units = []
        for u in compiled_units:
            st = u['status']
            user_facing_status = 'observed' if st == 'explicit' else st
            user_units.append({
                'unit_id': u['unit_id'],
                'title': u['title'],
                'status': user_facing_status,
                'statement': u['statement'],
                'evidence_count': len(u['evidence'])
            })

        return {
            'phase': 'learned',
            'collection': target_name,
            'collection_id': active_col_id,
            'units_learned': len(compiled_units),
            'units': user_units,
            'source_evidence_count': sum(len(u['evidence']) for u in compiled_units),
            'inferred_relationships': inferred_rels,
            'summary': f"Successfully learned {len(compiled_units)} reusable knowledge units for '{target_name}'. Source evidence and epistemic status ('observed' vs 'inferred') have been preserved."
        }

    # -------------------------------------------------------------------------
    # 3. organize_knowledge
    # -------------------------------------------------------------------------
    def organize_knowledge(self, *, action: str = 'infer', source_collection: Optional[str] = None,
                           target_collection: Optional[str] = None, relationship: Optional[str] = None,
                           reason: Optional[str] = None) -> Dict[str, Any]:
        """Manage and infer typed pack relationships across this account's private library.
        
        Supports 'infer', 'link', 'unlink', and 'explain'.
        """
        graph = knowledge_graph(self.home)

        if action == 'explain' and source_collection:
            self._require_authorized_collection(source_collection)
            return explain_collection(self.home, source_collection)

        if action == 'link':
            require(source_collection and target_collection and relationship,
                    'source_collection, target_collection, and relationship type are required')
            folder_src, data_src = self._require_authorized_collection(source_collection)
            folder_tgt, data_tgt = self._require_authorized_collection(target_collection)

            valid_kinds = {"related_to", "specializes", "part_of", "useful_with", "derived_from",
                           "supersedes", "contradicts", "personal_preference_relevant_to", "learned_from"}
            require(relationship in valid_kinds, f"Invalid relationship kind. Must be one of: {sorted(valid_kinds)}")

            custom_file = self.home / 'custom_relationships.json'
            custom = read(custom_file) if custom_file.is_file() else {'relationships': []}

            new_rel = {
                'from': data_src['collection_id'],
                'to': data_tgt['collection_id'],
                'kind': relationship,
                'reason': reason or f"User connected {data_src['name']} to {data_tgt['name']}",
                'shared_topics': sorted(set(tokens(data_src['name'])) & set(tokens(data_tgt['name']))),
                'evidence': [{'collection_id': data_src['collection_id']}, {'collection_id': data_tgt['collection_id']}],
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            custom['relationships'] = [r for r in custom.get('relationships', [])
                                       if not (r['from'] == new_rel['from'] and r['to'] == new_rel['to'] and r['kind'] == new_rel['kind'])]
            custom['relationships'].append(new_rel)
            write(custom_file, custom)

            return {
                'action': 'linked',
                'relationship': new_rel,
                'message': f"Connected '{data_src['name']}' to '{data_tgt['name']}' ({relationship})."
            }

        if action == 'unlink':
            require(source_collection and target_collection, 'source_collection and target_collection are required')
            _, data_src = self._require_authorized_collection(source_collection)
            _, data_tgt = self._require_authorized_collection(target_collection)

            custom_file = self.home / 'custom_relationships.json'
            if custom_file.is_file():
                custom = read(custom_file)
                custom['relationships'] = [r for r in custom.get('relationships', [])
                                           if not (r['from'] == data_src['collection_id'] and r['to'] == data_tgt['collection_id'])]
                write(custom_file, custom)

            return {
                'action': 'unlinked',
                'message': f"Removed connections between '{data_src['name']}' and '{data_tgt['name']}'."
            }

        # Default action: infer
        custom_file = self.home / 'custom_relationships.json'
        if custom_file.is_file():
            custom = read(custom_file)
            existing_pairs = {(r['from'], r['to'], r['kind']) for r in graph['relationships']}
            for r in custom.get('relationships', []):
                if (r['from'], r['to'], r['kind']) not in existing_pairs:
                    graph['relationships'].append(r)

        return {
            'phase': 'organized',
            'graph_id': graph['graph_id'],
            'collections': graph['collections'],
            'relationships': graph['relationships'],
            'summary': f"Library organized with {len(graph['collections'])} pack(s) and {len(graph['relationships'])} typed relationship(s)."
        }

    # -------------------------------------------------------------------------
    # 4. get_relevant_context
    # -------------------------------------------------------------------------
    def get_relevant_context(self, intent: str, task_context: str = '', max_units: int = 24) -> Dict[str, Any]:
        """Selectively retrieve relevant authorized knowledge units across relationships."""
        require(intent.strip(), 'Describe the task or question WayKit should prepare for')
        return compose_context(self.home, intent=intent, task_context=task_context, max_units=max_units)

    # -------------------------------------------------------------------------
    # 5. apply_knowledge
    # -------------------------------------------------------------------------
    def apply_knowledge(self, intent: str, task_context: str = '', collection: Optional[str] = None) -> Dict[str, Any]:
        """Apply relevant compiled knowledge to review, solve, or plan a task with citations."""
        require(intent.strip(), 'Describe what work or review should be performed')

        context = self.get_relevant_context(intent=intent, task_context=task_context)
        knowledge_units = context.get('knowledge', [])
        using_collections = context.get('using', [])

        findings = []
        checklist = []
        recommendations = []

        for unit in knowledge_units:
            citations = unit.get('evidence', [])
            cite_str = citations[0]['quote'] if citations else 'Verified source excerpt'
            source_name = citations[0]['source'] if citations else unit.get('collection')

            findings.append({
                'title': unit['title'],
                'statement': unit['statement'],
                'status': unit['status'],
                'collection': unit['collection'],
                'citation': {
                    'source': source_name,
                    'quote': cite_str
                }
            })
            checklist.append({
                'item': f"Verify alignment with: {unit['title']}",
                'criterion': unit['statement'],
                'source': unit['collection']
            })
            recommendations.append(
                f"- **{unit['title']}** ({unit['collection']}): {unit['statement']} *(Source: “{cite_str}”)*"
            )

        output_md = [
            f"# Applied Knowledge: {intent}",
            "",
            f"**Applied Packs**: {', '.join(c['name'] for c in using_collections) or 'None'}",
            "",
            "## Checklist & Evaluation Criteria",
            ""
        ]
        output_md += [f"- [ ] **{c['item']}**: {c['criterion']}" for c in checklist]
        output_md += ["", "## Grounded Recommendations & Findings", ""]
        output_md += recommendations
        if context.get('gaps'):
            output_md += ["", "## Knowledge Gaps", ""]
            output_md += [f"- {g['message']}" for g in context['gaps']]

        return {
            'phase': 'applied',
            'intent': intent,
            'using': using_collections,
            'findings': findings,
            'checklist': checklist,
            'gaps': context.get('gaps', []),
            'applied_result': '\n'.join(output_md)
        }

    # -------------------------------------------------------------------------
    # 6. search_knowledge
    # -------------------------------------------------------------------------
    def search_knowledge(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search across all authorized units, statements, and sources in this account's library."""
        require(query.strip(), 'Query string is required')
        q_tokens = tokens(query)

        results = []
        for entry in self.library.index.get('collections', []):
            try:
                folder, data = self.library.resolve(entry['collection_id'])
            except Invalid:
                continue
            run = self.library.run(folder, data)
            ir_file = run / 'ir.json'
            if not ir_file.is_file():
                continue
            ir = read(ir_file)
            units = ir.get('units', [])

            from ec import validate_sources
            _, docs, _ = validate_sources(run)

            for u in units:
                score = len(tokens(u['title'] + ' ' + u['statement'] + ' ' + u['scope']) & q_tokens)
                if score > 0:
                    citations = [{
                        'source_id': e['source_id'],
                        'segment_id': e['segment_id'],
                        'quote': e['quote'],
                        'source_title': docs.get(e['source_id'], {}).get('title') or docs.get(e['source_id'], {}).get('filename')
                    } for e in u.get('evidence', [])]

                    results.append({
                        'score': score,
                        'collection_name': data['name'],
                        'collection_id': data['collection_id'],
                        'unit_id': u['unit_id'],
                        'title': u['title'],
                        'statement': u['statement'],
                        'scope': u['scope'],
                        'status': u['status'],
                        'evidence': citations
                    })

        results.sort(key=lambda r: -r['score'])
        top = results[:limit]
        return {
            'query': query,
            'total_matches': len(results),
            'results': top
        }

    # -------------------------------------------------------------------------
    # 7. export_library & import_library
    # -------------------------------------------------------------------------
    def export_library(self) -> bytes:
        """Export the private library to a portable .lectic-home archive.
        
        Can be restored locally with 'lectic restore' or scripts/home_archive.py.
        """
        return archive_home(self.home)

    def import_library(self, archive_raw: bytes) -> Dict[str, Any]:
        """Merge an incoming .lectic-home archive into this account's private library."""
        return merge_archive(self.home, archive_raw, home=self.home)
