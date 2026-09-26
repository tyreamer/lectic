import io
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import pytest
from PIL import Image
from lectic.cloud.config import Settings
from lectic.cloud.media import process, image_data
from lectic.cloud.retrieval import NeedsContent, validate_url, retrieve


class Vision:
    settings=SimpleNamespace(model="fixture-vision")
    def json(self,purpose,payload,schema,images=None):
        return {"text":"Measure whether a person reaches the intended result without coaching.","interpretation":"A teaching card containing one instruction."}


def test_image_interpretation_is_not_quoted_as_original(tmp_path):
    stream=io.BytesIO();Image.new('RGB',(100,100),'white').save(stream,'PNG')
    result=process(stream.getvalue(),'page.png',Vision(),Settings(dev=True),tmp_path)
    assert [d['kind'] for d in result['derivations']]==['ocr','visual_interpretation']
    assert all(d['metadata']['caption_type']=='automatic' for d in result['documents'])
    assert 'not a quotation' in result['documents'][1]['metadata']['title']


def test_scanned_pdf_has_page_bound_ocr(tmp_path):
    stream=io.BytesIO();Image.new('RGB',(100,100),'white').save(stream,'PDF')
    result=process(stream.getvalue(),'scan.pdf',Vision(),Settings(dev=True),tmp_path)
    assert all(d['reference']=={'page':1} for d in result['derivations'])
    assert all('page 1' in d['metadata']['title'] for d in result['documents'])


def test_large_image_rejected_before_decoding():
    stream=io.BytesIO();Image.new('1',(5100,5000),1).save(stream,'PNG')
    with pytest.warns(Image.DecompressionBombWarning), pytest.raises(NeedsContent,match='25 megapixels'):
        image_data(stream.getvalue())


def test_oversized_pdf_page_rasterization_is_bounded(tmp_path):
    from pypdf import PdfWriter
    writer=PdfWriter();writer.add_blank_page(width=100000,height=100000)
    stream=io.BytesIO();writer.write(stream)
    result=process(stream.getvalue(),'large-page.pdf',Vision(),Settings(dev=True),tmp_path)
    assert result['derivations'][0]['reference']=={'page':1}


def test_silent_video_inspects_frames_without_inventing_transcript(tmp_path,monkeypatch):
    import lectic.cloud.media as media
    image=io.BytesIO();Image.new('RGB',(100,100),'white').save(image,'JPEG')
    def fake_run(args,**kw):
        if 'ffprobe' in args[0]: return SimpleNamespace(returncode=0,stdout=b'{"format":{"duration":"60"},"streams":[{"codec_type":"video"}]}')
        Path(args[-1]).write_bytes(image.getvalue());return SimpleNamespace(returncode=0,stdout=b'')
    monkeypatch.setattr(media.subprocess,'run',fake_run)
    result=process(b'video-fixture','silent.mp4',Vision(),Settings(dev=True),tmp_path)
    assert not any(d['kind']=='transcript' for d in result['derivations'])
    assert all(d['reference']['sampled'] for d in result['derivations'])
    assert result['limitations']


def test_unknown_file_needs_content(tmp_path):
    with pytest.raises(NeedsContent):process(b'unknown','archive.zip',Vision(),Settings(dev=True),tmp_path)


def test_dns_private_address_is_blocked(monkeypatch):
    import lectic.cloud.retrieval as retrieval
    monkeypatch.setattr(retrieval.socket,'getaddrinfo',lambda *a,**kw:[(2,1,6,'',('127.0.0.1',443))])
    with pytest.raises(ValueError):validate_url('https://public.example.com')


def test_partial_carousel_is_not_ready(monkeypatch):
    import yt_dlp
    class Extractor:
        def __init__(self,*a,**kw):pass
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def extract_info(self,*a,**kw):return {'entries':[{'url':'https://example.com/one-video.mp4'}]}
    monkeypatch.setattr(yt_dlp,'YoutubeDL',Extractor)
    with pytest.raises(NeedsContent,match='may contain more'):
        retrieve('https://instagram.com/p/example/',Settings(dev=True))
