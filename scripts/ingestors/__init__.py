"""Adapters produce original transcript bytes plus metadata; the IR is adapter-neutral."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TranscriptInput:
    filename: str
    raw: bytes
    metadata: dict


class Ingestor(Protocol):
    def collect(self, metadata=None) -> list[TranscriptInput]: ...


def adapter_for(location):
    from .youtube import YouTubeIngestor
    from .web import WebArticleIngestor
    from .transcript_files import TranscriptFiles
    if YouTubeIngestor.accepts(location):
        return YouTubeIngestor(location)
    if WebArticleIngestor.accepts(location):
        return WebArticleIngestor(location)
    return TranscriptFiles(location)
