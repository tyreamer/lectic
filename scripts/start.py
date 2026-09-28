"""First run for someone who has never used Lectic: save real material, or show the offline example.

Nothing here invents knowledge. Saving sources is deterministic and local; deriving
reusable knowledge from them is the assistant's job, so `start` reports the exact
next thing to say rather than pretending a model already ran.
"""
from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile
from urllib.parse import urlsplit

from ec import require
from collection_store import Library
from goal_workflow import work
from ingestors.transcript_files import EXTENSIONS
from store import home_transaction


def existing_collection(library, name):
    if not name: return None
    return next((e for e in library.index['collections'] if e['name'].casefold() == name.casefold()), None)


def suggested_name(project, source):
    """Give local material a useful name before a single file is staged."""
    if str(source).lower().startswith(('http://', 'https://')):
        host = (urlsplit(str(source)).hostname or 'web').removeprefix('www.')
        label = 'YouTube' if host in {'youtube.com', 'youtu.be'} else host.split('.')[0].title()
        return label + ' Sources'
    candidate = (Path(project) / source).expanduser()
    if candidate.is_file():
        stem = candidate.stem
    elif candidate.is_dir():
        stem = candidate.name
    else:
        return None
    return stem.replace('-', ' ').replace('_', ' ').title() + ' Sources'


@contextmanager
def readable_input(project, source):
    """Adapters read folders and links. A beginner points at one file, so stage it into a folder."""
    candidate = (Path(project) / source).expanduser()
    if candidate.is_file():
        require(candidate.suffix.lower() in EXTENSIONS,
                'Lectic reads .txt, .md, .vtt and .srt files, folders of them, or a YouTube link: ' + source)
        with tempfile.TemporaryDirectory(prefix='lectic-start-') as staging:
            shutil.copy2(candidate, Path(staging) / candidate.name)
            yield staging
        return
    yield source


@home_transaction
def start(project='.', sources=(), name=None, goal=None):
    """Save the given files/folders/links into one collection, or run the offline sample."""
    project = Path(project).resolve()
    sources = [str(s) for s in sources if str(s).strip()]
    if not sources:
        from starter import try_starter
        sample = try_starter(project)
        return {'phase': 'started', 'mode': 'sample', 'collection': sample['collection'],
                'created': 'a sample collection with a reviewed result and a reusable checklist',
                'learned': sample['example_type'],
                'first_result': sample['first_result'], 'second_result': sample['second_result'],
                'reused_units': len(sample['reuse']['reused_units']),
                'next_prompt': sample['next_prompt'],
                'share_command': 'lectic share-artifact "' + sample['collection'] + '"'}
    library = Library(project)
    name = name or suggested_name(project, sources[0])
    target = existing_collection(library, name)
    collection = target['collection_id'] if target else None
    for source in sources:
        action = 'add' if collection else 'save'
        with readable_input(project, source) as material:
            result = work(project=project, input=material, collection=collection,
                          name=None if collection else name, action=action)
        require(result['phase'] == 'archived', 'Lectic could not save that material: ' + str(result))
        collection = result['collection_id']
    library.reload()
    summary = library.inspect(collection)
    folder, _ = library.resolve(collection)
    titles = [s['title'] or s['filename'] for s in summary['sources']]
    desired_use = str(goal or '').strip()
    next_prompt = (f"Prepare my {summary['name']} collection and use it to {desired_use}. "
                   'Tell me what you learned, what the sources support, and what I can reuse next time.'
                   if desired_use else
                   f"Prepare my {summary['name']} collection, then tell me what it can help with.")
    return {'phase': 'started', 'mode': 'saved', 'collection': summary['name'],
            'collection_id': collection, 'location': str(folder),
            'created': f"a collection named {summary['name']}",
            'sources': titles, 'source_count': summary['source_count'],
            'knowledge_units': summary['knowledge_units'],
            'learned': (f"{summary['knowledge_units']} reusable knowledge units are saved" if summary['knowledge_units']
                        else 'No reusable knowledge yet: the sources are saved and indexed; your assistant prepares it next.'),
            'source_revision': summary['active_revision'], 'desired_use': desired_use or None,
            'next_prompt': next_prompt,
            'share_command': 'lectic share-artifact "' + summary['name'] + '"',
            'refresh_command': 'lectic refresh "' + summary['name'] + '" --from "' + sources[-1] + '"'}
