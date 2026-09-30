"""Refresh a saved collection from material the user names again, and report honestly what changed.

WayKit never guesses where a collection's sources came from on disk, so `--from` is required.
Refreshing adds a new immutable source revision; every earlier revision, its knowledge and
every saved build stay exactly where they were. Comparison is file-level and deterministic:
WayKit reports which sources appeared, vanished or changed bytes, and which extracted units
could no longer be carried forward. It does not claim to know what the change means.
"""
from pathlib import Path

from ec import read, require, status
from collection_store import Library
from goal_workflow import work
from store import home_transaction


def compare_revisions(library, collection_id, before, after):
    if before == after:
        return {'before': before, 'after': after, 'added_sources': [], 'removed_sources': [], 'changed_sources': []}
    changes = library.compare(collection_id, before=before, after=after)
    return {k: changes[k] for k in ('before', 'after', 'added_sources', 'removed_sources', 'changed_sources')}


@home_transaction
def refresh(project='.', collection=None, source=None):
    """Replace same-named sources from `source` and add new ones; keep everything already saved."""
    require(source, 'Name the file, folder or link to refresh from: waykit refresh NAME --from PATH')
    project = Path(project).resolve()
    library = Library(project)
    resolved = library.resolve(collection)
    require(resolved is not None, 'Name a saved collection to refresh')
    folder, data = resolved
    before = data['active_revision']
    builds_before = len(data['builds'])
    source_path = (project / str(source)).expanduser()
    prune_missing = source_path.is_dir()
    from start import readable_input
    with readable_input(project, str(source)) as material:
        result = work(project=project, collection=data['collection_id'], input=material, action='replace',
                      prune_missing=prune_missing)
    require(result['phase'] == 'archived', 'WayKit could not read that material: ' + str(result))
    library.reload()
    folder, data = library.resolve(data['collection_id'])
    after = data['active_revision']
    run = library.run(folder, data)
    changes = compare_revisions(library, data['collection_id'], before, after)
    carried = {}
    change_record = run / 'source-change.json'
    if change_record.is_file():
        try:
            record = read(change_record)
            carried = {'retained_units': len(record['retained_unit_ids']),
                       'invalidated_units': len(record['invalidated_unit_ids']),
                       'carry_report_available': True}
        except (OSError, ValueError, KeyError):
            carried = {}
    state = status(run)
    unchanged = before == after
    report = {'phase': 'refreshed', 'collection': data['name'], 'collection_id': data['collection_id'],
              'source': str(source), 'unchanged': unchanged,
              'previous_revision': before, 'active_revision': after,
              'source_revisions': len(data['revisions']), 'builds_preserved': builds_before,
              'pruned_missing_sources': prune_missing,
              'sources': state['sources'], 'pending_sources': state['pending_source_ids'],
              'next_step': state['next'], 'rebuild_needed': state['next'] != 'discover',
              'carry_report_available': False, **changes, **carried}
    report['message'] = message_for(report)
    return report


def message_for(report):
    if report['unchanged']:
        return ('Nothing changed: the material at that location is byte-for-byte what this collection already holds. '
                'The saved knowledge and every earlier revision are untouched.')
    counts = []
    for label, key in (('added', 'added_sources'), ('changed', 'changed_sources'), ('removed', 'removed_sources')):
        if report[key]: counts.append(f"{len(report[key])} {label}")
    summary = ', '.join(counts) or 'no source-level differences'
    detail = (f"{report['invalidated_units']} saved knowledge unit(s) no longer match their sources and were set aside; "
              f"{report['retained_units']} were carried forward"
              if report['carry_report_available'] else
              'The carry-forward report was unavailable, so no knowledge-change count is claimed')
    if report['rebuild_needed']:
        next_step = ('WayKit did not re-derive knowledge; that needs your assistant. Open it and say: '
                     f"Prepare my {report['collection']} collection.")
    else:
        next_step = 'The current knowledge already covers every active source; no rebuild is needed.'
    return (f"Saved a new source revision ({summary}). Earlier revisions, their knowledge and "
            f"{report['builds_preserved']} saved build(s) were kept for the previous revision until you rebuild. "
            f"{detail}. {next_step}")


def diff(project='.', collection=None, before=None, after=None):
    """Read-only comparison of two saved source revisions and their knowledge."""
    library = Library(project)
    require(library.resolve(collection) is not None, 'Name a saved collection to compare')
    return {'phase': 'compared', 'changes': library.compare(collection, before=before, after=after)}
