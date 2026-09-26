"""Bounded public retrieval. Social previews are never promoted to full sources."""
from contextlib import contextmanager
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import select
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit, urljoin
from bs4 import BeautifulSoup


class NeedsContent(ValueError): pass


def validate_url(url, resolve=True):
    u = urlsplit(url)
    if u.scheme not in {"https", "http"} or not u.hostname or u.username or u.password or u.port not in {None, 80, 443}:
        raise ValueError("Use a public http or https link.")
    host = u.hostname.rstrip(".").lower()
    if host in {"localhost", "metadata.google.internal"} or "." not in host:
        raise ValueError("Only public Internet addresses are allowed.")
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global: raise ValueError("Private addresses are not allowed.")
    except ValueError:
        if all(c in "0123456789abcdefABCDEF:." for c in host): raise ValueError("Private or invalid address.")
    addresses = []
    if resolve:
        for info in socket.getaddrinfo(host, u.port or (443 if u.scheme == "https" else 80), type=socket.SOCK_STREAM):
            address = info[4][0]
            if not ipaddress.ip_address(address).is_global: raise ValueError("Private addresses are not allowed.")
            addresses.append(address)
        if not addresses: raise ValueError("Address unavailable")
    return u, addresses


def fetch(url, maximum=8*1024**2, redirects=4):
    """Resolve, verify, then connect to that exact IP (including every redirect)."""
    started = time.monotonic()
    for _ in range(redirects+1):
        u, addresses = validate_url(url)
        port = u.port or (443 if u.scheme == "https" else 80)
        sock = socket.create_connection((addresses[0], port), timeout=15)
        if u.scheme == "https": sock = ssl.create_default_context().wrap_socket(sock, server_hostname=u.hostname)
        connection = http.client.HTTPConnection(u.hostname, port, timeout=15)
        connection.sock = sock
        try:
            connection.request("GET", (u.path or "/") + ("?"+u.query if u.query else ""), headers={
                "Host": u.netloc, "User-Agent": "LecticPilot/1.0", "Accept-Encoding": "identity"})
            response = connection.getresponse()
            if response.status in {301,302,303,307,308}:
                url = urljoin(url, response.getheader("Location", "")); continue
            if response.status != 200: raise NeedsContent("This link could not be retrieved. Add screenshots or video.")
            if response.getheader("Content-Encoding", "identity") != "identity": raise NeedsContent("Compressed response unavailable. Add the original file.")
            raw, count = [], 0
            while True:
                chunk = response.read(min(65536, maximum-count+1))
                if not chunk: break
                count += len(chunk)
                if count > maximum or time.monotonic()-started > 60: raise NeedsContent("Download exceeded the pilot's limit.")
                raw.append(chunk)
            return b"".join(raw), response.getheader("Content-Type", "").split(";")[0], url
        finally: connection.close()
    raise NeedsContent("Too many redirects. Add the original file.")


@contextmanager
def public_proxy(maximum):
    """yt-dlp egress: pinned public CONNECT destinations, aggregate bytes and wall time.

    No cookies, inherited proxy, external downloader or extractor plugins are used.
    """
    total, lock, started = [0], threading.Lock(), time.monotonic()
    class Proxy(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_CONNECT(self):
            remote = None
            try:
                u, addresses = validate_url("https://" + self.path)
                if u.port != 443: raise ValueError()
                remote = socket.create_connection((addresses[0], 443), timeout=10)
                self.send_response(200); self.end_headers()
                while time.monotonic()-started < 75:
                    ready, _, _ = select.select([self.connection, remote], [], [], 2)
                    for source in ready:
                        chunk = source.recv(65536)
                        if not chunk: return
                        with lock:
                            total[0] += len(chunk)
                            if total[0] > maximum: return
                        (remote if source is self.connection else self.connection).sendall(chunk)
            except (ValueError, OSError):
                pass
            finally:
                if remote: remote.close()
                self.close_connection = True
        def do_GET(self): self.send_error(403)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try: yield "http://127.0.0.1:" + str(server.server_port)
    finally: server.shutdown(); server.server_close()


def platform(url):
    u, _ = validate_url(url, resolve=False)
    host = u.hostname.lower().removeprefix("www.").removeprefix("m.")
    if host in {"instagram.com", "x.com", "twitter.com"}:
        if host == "instagram.com" and not u.path.startswith(("/p/", "/reel/")):
            raise NeedsContent("Share a public post or Reel. Profiles, Stories and messages are not imported.")
        if host in {"x.com", "twitter.com"} and "/status/" not in u.path:
            raise NeedsContent("Share one public post. Profiles and full threads are not imported.")
        return "instagram" if host == "instagram.com" else "x"
    if host in {"youtube.com", "youtu.be"}: return "youtube"
    return "article"


def retrieve(url, settings):
    kind = platform(url)
    if kind == "article":
        raw, mime, final = fetch(url)
        if mime == "application/pdf" or raw.startswith(b"%PDF-"): return [{"raw": raw, "filename": "article.pdf", "url": final}]
        if mime not in {"text/html", "text/plain"}: raise NeedsContent("Add the original file for this type of link.")
        if mime == "text/plain": text = raw.decode("utf-8", errors="replace")
        else:
            soup = BeautifulSoup(raw, "html.parser")
            for tag in soup.select("script,style,nav,footer,header,aside,form,noscript"): tag.decompose()
            article = soup.find("article") or soup.find("main")
            if not article: raise NeedsContent("A complete article could not be identified. Add its text or PDF.")
            text = article.get_text("\n", strip=True)
        if len(text.strip()) < 200: raise NeedsContent("This page has too little readable content. Add screenshots or text.")
        return [{"raw": text.encode(), "filename": "article.txt", "url": final}]
    import yt_dlp
    class Quiet:
        def debug(self, *a): pass
        def warning(self, *a): pass
        def error(self, *a): pass
    try:
        with public_proxy(12*1024**2) as proxy, yt_dlp.YoutubeDL({
            "proxy": proxy, "socket_timeout": 10, "retries": 0, "extractor_retries": 0,
            "noplaylist": True, "playlistend": 21, "skip_download": True, "quiet": True,
            "no_warnings": True, "logger": Quiet(), "cachedir": False, "cookiefile": None,
            "cookiesfrombrowser": None, "remote_components": [], "js_runtimes": {},
        }) as ydl:
            info = ydl.extract_info(url, download=False)
        entries = info.get("entries")
        # Extractors often omit carousel photographs. A playlist is not proof of completeness.
        if entries is not None: raise NeedsContent("This post may contain more than the retrieved media. Add all screenshots or the video.")
        if not info.get("duration") or info["duration"] > settings.max_seconds:
            raise NeedsContent("Media length is unknown or exceeds 15 minutes. Add a shorter original.")
        formats = [f for f in info.get("formats", []) if f.get("protocol") == "https" and
                   f.get("vcodec", "none") != "none" and f.get("acodec", "none") != "none" and f.get("url")]
        if not formats: raise NeedsContent("A complete public video is unavailable. Add screenshots or video.")
        chosen = min(formats, key=lambda f: (f.get("height") or 10000, f.get("filesize") or 0))
        raw, _, _ = fetch(chosen["url"], settings.max_upload)
        return [{"raw": raw, "filename": "public-video.mp4", "url": url, "platform": kind,
                 "retrieval": "public video; comments and surrounding threads excluded"}]
    except NeedsContent: raise
    except Exception:
        raise NeedsContent("The public post could not be retrieved completely. Add screenshots or video.") from None
