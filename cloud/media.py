import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
from PIL import Image, ImageOps
from .config import VERSION
from .retrieval import NeedsContent

VISION_SCHEMA = {"type": "object", "properties": {"text": {"type": "string"}, "interpretation": {"type": "string"}},
                 "required": ["text", "interpretation"], "additionalProperties": False}


def image_data(raw):
    Image.MAX_IMAGE_PIXELS = 25_000_000
    with Image.open(io.BytesIO(raw)) as image:
        if image.width*image.height > 25_000_000:
            raise NeedsContent("This image is too large to process. Resize it below 25 megapixels.")
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((1600,1600))
        out = io.BytesIO(); image.save(out, "JPEG", quality=85)
    return base64.b64encode(out.getvalue()).decode()


def clock(seconds):
    millis = round(seconds*1000)
    return f"{millis//3600000:02}:{millis//60000%60:02}:{millis//1000%60:02}.{millis%1000:03}"


def process(raw, filename, model, settings, scratch):
    """Normalized source documents plus optional, nonbreaking derivation records."""
    scratch.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix.lower()
    original_hash = hashlib.sha256(raw).hexdigest()
    documents, derivations = [], []
    def add(text, label, kind, reference=None, caption="automatic"):
        if not text.strip(): return
        if reference and "page" in reference: label += " · page " + str(reference["page"])
        if reference and "timestamp" in reference: label += " · frame at " + str(reference["timestamp"]) + "s"
        ident = f"{original_hash[:12]}-{len(documents)+1}"
        name = ident + (".vtt" if kind == "transcript" else ".txt")
        documents.append({"filename": name, "text": text, "metadata": {"title": label+" — "+filename,
            "creator": "Automatic processing" if caption == "automatic" else "Supplied source", "caption_type": caption}})
        derivations.append({"filename": name, "kind": kind, "original_sha256": original_hash, "reference": reference,
                            "model": "whisper-1" if kind == "transcript" else getattr(model, "last_model", model.settings.model) if kind in {"ocr", "visual_interpretation"} else None,
                            "processing_version": VERSION, "label": label})
    def vision(image, reference):
        result = model.json("Transcribe visible text exactly into text; unreadable regions stay [unreadable]. Describe useful visual information in interpretation, clearly as an interpretation. Do not infer unseen pages or frames.",
                            {"reference": reference}, VISION_SCHEMA, images=[image_data(image)])
        add(result["text"], "Automatic OCR", "ocr", reference)
        add(result["interpretation"], "Visual interpretation (not a quotation)", "visual_interpretation", reference)
    if suffix in {".txt", ".md", ".vtt", ".srt"}:
        try: text = raw.decode("utf-8-sig")
        except UnicodeDecodeError: raise NeedsContent("Save text as UTF-8, or upload a PDF.")
        if len(text) > 200000: raise NeedsContent("This document exceeds the pilot text limit. Split it into smaller sources.")
        documents.append({"filename": original_hash[:12]+suffix, "text": text,
                          "metadata": {"title": filename, "creator": "Supplied source", "caption_type": "unknown"}})
        derivations.append({"filename": documents[-1]["filename"], "kind": "supplied_text", "original_sha256": original_hash,
                            "reference": None, "model": None, "processing_version": VERSION})
    elif raw.startswith(b"%PDF-"):
        from pypdf import PdfReader
        import pypdfium2
        pdf = PdfReader(io.BytesIO(raw))
        if pdf.is_encrypted: raise NeedsContent("Upload an unlocked PDF.")
        if len(pdf.pages) > 40: raise NeedsContent("This PDF exceeds the pilot limit of 40 pages.")
        renderer = None
        try:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                if text.strip(): add(text, "Extracted PDF text", "pdf_text", {"page": i+1}, "unknown")
                # Inspect every page: text extraction alone can omit diagrams and scanned regions.
                if renderer is None: renderer = pypdfium2.PdfDocument(raw)
                page_view = renderer[i]
                width, height = page_view.get_size()
                # Bound rasterization before allocating a bitmap, including oversized page boxes.
                scale = min(1.5, 1600/max(width, height))
                bitmap = page_view.render(scale=scale)
                rendered = bitmap.to_pil()
                out = io.BytesIO(); rendered.save(out, "PNG")
                vision(out.getvalue(), {"page": i+1})
                rendered.close(); bitmap.close(); page_view.close()
        finally:
            if renderer: renderer.close()
    elif suffix in {".png", ".jpg", ".jpeg", ".webp", ".heic", ".gif"}:
        if suffix in {".heic", ".gif"}: raise NeedsContent("Export this image as JPEG or PNG so no frames are lost.")
        vision(raw, {"image": 1})
    elif suffix in {".mp3", ".wav", ".m4a", ".mp4", ".mov", ".webm", ".ogg", ".flac", ".mkv"}:
        input_path = scratch / ("input"+suffix); input_path.write_bytes(raw)
        ffprobe, ffmpeg = os.getenv("LECTIC_FFPROBE", "ffprobe"), os.getenv("LECTIC_FFMPEG", "ffmpeg")
        def run(args, timeout=120):
            options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
            result = subprocess.run(args, capture_output=True, timeout=timeout, **options)
            if result.returncode: raise NeedsContent("This media could not be read. Try MP4, MP3 or a screenshot.")
            return result.stdout
        info = json.loads(run([ffprobe, "-v", "error", "-protocol_whitelist", "file,pipe", "-show_format", "-show_streams", "-of", "json", str(input_path)], 20))
        duration = float(info.get("format", {}).get("duration", 0))
        if duration <= 0 or duration > settings.max_seconds: raise NeedsContent("Upload media no longer than 15 minutes.")
        has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
        has_video = any(s["codec_type"] == "video" for s in info["streams"])
        if has_audio:
            audio = scratch / "audio.mp3"
            run([ffmpeg, "-v", "error", "-nostdin", "-y", "-protocol_whitelist", "file,pipe", "-i", str(input_path),
                 "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", "-t", str(settings.max_seconds), str(audio)])
            transcript = model.transcribe(audio, duration)
            segments = [s for s in transcript.get("segments", []) if s.get("no_speech_prob", 0) < 0.6 and s.get("text", "").strip()]
            if segments:
                vtt = "WEBVTT\n\n" + "\n\n".join(f"{clock(s['start'])} --> {clock(s['end'])}\n{s['text'].strip()}" for s in segments)
                add(vtt, "Automatic transcript", "transcript", {"start": 0, "end": duration})
        if has_video:
            # Bounded sampled frames are explicitly labeled; this never claims full visual coverage.
            samples = min(12, max(2, int(duration/30)+1))
            for i in range(samples):
                at = min(duration-0.05, duration*i/samples)
                frame = scratch / f"frame-{i}.jpg"
                run([ffmpeg, "-v", "error", "-nostdin", "-y", "-protocol_whitelist", "file,pipe", "-ss", str(at),
                     "-i", str(input_path), "-frames:v", "1", "-vf", "scale=1280:-2", str(frame)], 30)
                vision(frame.read_bytes(), {"timestamp": round(at, 2), "sampled": True, "duration": duration})
        if not documents: raise NeedsContent("No speech or readable visual content was found. Add notes or screenshots.")
    else: raise NeedsContent("This file type is not supported yet. Add text, PDF, JPEG, PNG, audio or video.")
    if not documents: raise NeedsContent("No readable content was found. Add text or another image.")
    return {"documents": documents, "derivations": derivations, "original_sha256": original_hash,
            "limitations": ["Video frames are sampled; unsampled on-screen information may be missing."] if any(d["reference"] and d["reference"].get("sampled") for d in derivations) else []}
