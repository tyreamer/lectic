"""Storage primitives with cloud-shaped semantics, implemented on the local filesystem.

Everything Lectic persists is one of two kinds:

- immutable objects: content-addressed blobs and validated snapshots (source runs,
  builds, maps, packages), written once and never edited in place;
- small mutable indexes: library.json, collection.json, capture state.

LocalStore keeps blobs under HOME/blobs/<sha256>, publishes snapshots atomically
from a sibling staging directory, and serializes index writers with an OS lock.
A remote store implements the same three operations with object storage and
compare-and-swap; nothing above this module may rely on hard links, directory
renames or process locks directly.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import tempfile

from ec import Invalid, digest, require


class LocalStore:
    def __init__(self, root):
        self.root = Path(root).resolve()

    # --- immutable blobs -------------------------------------------------

    def blob_path(self, blob_hash):
        require(isinstance(blob_hash, str) and len(blob_hash) == 64 and all(c in '0123456789abcdef' for c in blob_hash),
                'Malformed blob hash')
        current = self.root / 'blobs' / blob_hash
        if current.exists(): return current
        # Project-local installs kept capture blobs one level deeper.
        legacy = self.root / 'capture' / 'blobs' / blob_hash
        return legacy if legacy.exists() else current

    def has_blob(self, blob_hash):
        return self.blob_path(blob_hash).is_file()

    def put_blob(self, raw):
        blob_hash = digest(raw)
        path = self.blob_path(blob_hash)
        if path.exists():
            require(digest(path.read_bytes()) == blob_hash, 'Canonical blob was modified')
            return blob_hash
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
            f.write(raw); temp = Path(f.name)
        temp.replace(path)
        return blob_hash

    def get_blob(self, blob_hash):
        path = self.blob_path(blob_hash)
        require(path.is_file(), 'Missing canonical blob ' + blob_hash)
        raw = path.read_bytes()
        require(digest(raw) == blob_hash, 'Canonical blob was modified')
        return raw

    def materialize(self, blob_hash, destination):
        """Place a blob's bytes at a snapshot path. The blob store stays canonical.

        A hard link avoids a second copy where the filesystem allows it; otherwise the
        bytes are copied. Either way the snapshot is self-contained and hash-verified.
        """
        source = self.blob_path(blob_hash)
        require(source.is_file(), 'Missing canonical blob ' + blob_hash)
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(source, destination)
        except OSError:
            shutil.copyfile(source, destination)
        require(digest(destination.read_bytes()) == blob_hash, 'Materialized blob differs from canonical bytes')
        return destination

    # --- immutable snapshots ---------------------------------------------

    def stage(self, destination, prefix='.stage-'):
        return staged(destination, prefix)

    # --- mutable indexes -------------------------------------------------

    @contextmanager
    def transaction(self, name):
        """Serialize writers of a named index family. The OS releases the lock on interruption."""
        locks = self.root / '.locks'
        locks.mkdir(parents=True, exist_ok=True)
        with (locks / (name + '.lock')).open('a+b') as lock:
            if lock.tell() == 0: lock.write(b'0'); lock.flush()
            lock.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise Invalid('Another ' + name + ' operation is active; retry after it finishes') from exc
            try:
                yield
            finally:
                lock.seek(0)
                if os.name == 'nt': msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else: fcntl.flock(lock, fcntl.LOCK_UN)


@contextmanager
def staged(destination, prefix='.stage-'):
    """Assemble a snapshot beside its destination, then publish it in one step.

    Yields the staging path. On normal exit the snapshot is renamed into place,
    unless an identical snapshot was already published there (callers that can
    collide verify identity themselves); on error the staging area is discarded
    and nothing is published.
    """
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=prefix, dir=destination.parent))
    staging = temp / destination.name
    staging.mkdir()
    try:
        yield staging
        if not destination.exists():
            staging.rename(destination)
    finally:
        if temp.exists():
            shutil.rmtree(temp, ignore_errors=True)
