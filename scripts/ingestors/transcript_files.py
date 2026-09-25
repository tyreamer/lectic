"""Stable V1 input adapter. Reading has no network or filesystem write effects."""
from pathlib import Path
from . import TranscriptInput

EXTENSIONS = {'.txt', '.md', '.vtt', '.srt'}


class TranscriptFiles:
    def __init__(self, folder):
        self.folder = Path(folder).resolve()

    def collect(self, metadata=None):
        from ec import read, require
        require(self.folder.is_dir(), f'Transcript folder does not exist: {self.folder}')
        meta = read(metadata) if metadata else {}
        require(type(meta) is dict, 'Metadata must map relative filenames to objects')
        paths = sorted(p for p in self.folder.rglob('*') if p.is_file() and p.suffix.lower() in EXTENSIONS)
        require(paths, 'No .txt/.md/.vtt/.srt transcripts found')
        names = {p.relative_to(self.folder).as_posix() for p in paths}
        require(set(meta) <= names, f'Metadata names absent from inputs: {set(meta)-names}')
        result = []
        for path in paths:
            require(path.resolve().is_relative_to(self.folder), 'Input symlink escapes folder')
            from privacy import require_shareable
            from home import storage_root
            require_shareable(path, storage_root())
            name = path.relative_to(self.folder).as_posix()
            m = meta.get(name, {})
            require(type(m) is dict and not set(m)-{'title', 'creator', 'url', 'caption_type'}, f'Invalid metadata for {name}')
            result.append(TranscriptInput(name, path.read_bytes(), m))
        return result
