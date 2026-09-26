"""Publishing knowledge packs to team hosts (GitHub Releases, S3/R2 presigned PUT, HTTP PUT)."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit, urlunsplit
import urllib.request
import urllib.error

from ec import VERSION, Invalid, digest, require
from collection_store import Library
from packs import build_pack, open_pack, slug


def publish_pack(project, target, to_url, token=None, webhook_url=None, download_url=None, include_sources=False):
    """Publish a compiled pack to a team host.

    target: a collection name or a path to an existing .lectic file.
    to_url: a GitHub Release URL / repo spec (e.g. 'owner/repo'), S3/R2 presigned PUT URL, or HTTP PUT URL.
    token: optional auth token (for GitHub or HTTP Bearer; falls back to GITHUB_TOKEN / GH_TOKEN env vars).
    webhook_url: optional Slack/Discord webhook URL to notify after publishing.
    """
    project = Path(project).resolve()
    target_path = Path(target)
    if not target_path.is_absolute():
        target_path = project / target

    if target_path.is_file():
        pack_path = target_path.resolve()
    else:
        # Treat as collection name
        library = Library(project)
        resolved = library.resolve(target)
        require(resolved is not None, f"Collection or pack file '{target}' not found")
        folder, data = resolved
        candidate = project / (slug(data['name']) + '.lectic')
        packed = build_pack(project, data['name'], destination=candidate, team=True, include_sources=include_sources)
        pack_path = Path(packed['pack'])

    require(pack_path.is_file(), f"Pack file not found: {pack_path}")
    raw_bytes = pack_path.read_bytes()
    manifest, _ = open_pack(raw_bytes)
    pack_name = manifest['name']
    version = manifest.get('version') or datetime.now(timezone.utc).strftime('%Y-%m-%d')
    install_name = manifest.get('distribution', {}).get('install_name') or slug(pack_name)

    to_url_str = str(to_url).strip()
    is_github = urlsplit(to_url_str).hostname in {'github.com', 'api.github.com'} or (re.fullmatch(r'[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+', to_url_str) and not to_url_str.startswith('http'))
    if not is_github:
        parsed = urlsplit(to_url_str)
        require(parsed.scheme == 'https' or (parsed.scheme == 'http' and parsed.hostname in {'localhost', '127.0.0.1'}),
                'Upload over HTTPS (HTTP is supported only on localhost)')
        presigned = any(key in parsed.query for key in ('X-Amz-', 'Signature=', 'AWSAccessKeyId='))
        require(not presigned or download_url, 'A presigned upload needs an explicit recipient download URL (--download-url). Its PUT signature cannot be converted to a GET link.')

    if is_github:
        auth_token = token or os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
        require(auth_token, "Publishing to GitHub Releases requires a token (--token or GITHUB_TOKEN environment variable)")

        # Parse owner, repo, tag
        if to_url_str.startswith('http'):
            parts = [p for p in urlsplit(to_url_str).path.strip('/').split('/') if p]
            if parts and parts[0] == 'repos':
                parts = parts[1:]
            require(len(parts) >= 2, f"Invalid GitHub URL: {to_url_str}")
            owner, repo = parts[0], parts[1]
            tag = None
            if len(parts) >= 5 and parts[2] == 'releases' and parts[3] == 'tag':
                tag = parts[4]
            elif len(parts) >= 4 and parts[2] == 'releases' and parts[3] == 'latest':
                tag = 'latest'
        else:
            owner, repo = to_url_str.split('/')
            tag = None

        if not tag:
            tag = f'v{version}'

        gh_headers = {
            'Authorization': f'Bearer {auth_token}',
            'Accept': 'application/vnd.github+json',
            'User-Agent': f'lectic/{VERSION}'
        }

        # Find or create release
        release = None
        if tag == 'latest':
            req = urllib.request.Request(f'https://api.github.com/repos/{owner}/{repo}/releases/latest', headers=gh_headers)
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    release = json.loads(resp.read().decode('utf-8'))
            except urllib.error.HTTPError as exc:
                raise Invalid(f"Failed to find latest release for {owner}/{repo}: {exc}")
        else:
            req = urllib.request.Request(f'https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}', headers=gh_headers)
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    release = json.loads(resp.read().decode('utf-8'))
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    # Create release
                    create_url = f'https://api.github.com/repos/{owner}/{repo}/releases'
                    body = json.dumps({
                        'tag_name': tag,
                        'name': f'{pack_name} {tag}',
                        'body': f'Lectic knowledge pack for {pack_name} (v{version}).\n\nInstall with:\n```bash\nlectic install https://github.com/{owner}/{repo}/releases/download/{tag}/{pack_path.name} --as {install_name}\n```'
                    }).encode('utf-8')
                    c_req = urllib.request.Request(create_url, data=body, headers={**gh_headers, 'Content-Type': 'application/json'}, method='POST')
                    try:
                        with urllib.request.urlopen(c_req, timeout=30) as resp:
                            release = json.loads(resp.read().decode('utf-8'))
                    except urllib.error.HTTPError as c_exc:
                        raise Invalid(f"Failed to create release {tag} on {owner}/{repo}: {c_exc}")
                else:
                    raise Invalid(f"GitHub API error ({exc.code}): {exc}")

        # Replacing an asset by delete-then-upload can destroy the working release.
        # Publish a new version or choose a new filename instead.
        for asset in release.get('assets', []):
            require(asset.get('name') != pack_path.name, 'That release asset already exists. Use a new version or filename; the existing asset was preserved.')

        upload_url_template = release.get('upload_url', '')
        upload_url = upload_url_template.split('{')[0] + f'?name={pack_path.name}'
        up_headers = {
            **gh_headers,
            'Content-Type': 'application/octet-stream',
            'Content-Length': str(len(raw_bytes))
        }
        up_req = urllib.request.Request(upload_url, data=raw_bytes, headers=up_headers, method='POST')
        try:
            with urllib.request.urlopen(up_req, timeout=60) as resp:
                asset_data = json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            raise Invalid(f"Failed to upload release asset: {exc}")

        actual_tag = release.get('tag_name') or tag
        download_url = asset_data.get('browser_download_url') or f"https://github.com/{owner}/{repo}/releases/download/{actual_tag}/{pack_path.name}"

    else:
        # Generic HTTP PUT / S3 / R2 presigned PUT
        require(to_url_str.startswith('http://') or to_url_str.startswith('https://'),
                "Destination URL must start with http:// or https://")
        put_headers = {
            'Content-Type': 'application/octet-stream',
            'Content-Length': str(len(raw_bytes)),
            'User-Agent': f'lectic/{VERSION}'
        }
        if token:
            put_headers['Authorization'] = f'Bearer {token}'

        put_req = urllib.request.Request(to_url_str, data=raw_bytes, headers=put_headers, method='PUT')
        try:
            with urllib.request.urlopen(put_req, timeout=60) as resp:
                pass
        except urllib.error.HTTPError as exc:
            raise Invalid(f"HTTP upload failed ({exc.code}): {exc}")

        download_url = download_url or to_url_str

    from packs import fetch
    try:
        require(digest(fetch(download_url)) == digest(raw_bytes), 'Recipient download differs from the uploaded pack')
    except (OSError, ValueError):
        return {'phase': 'uploaded_unverified', 'name': pack_name, 'version': version,
                'download_url': download_url, 'webhook_sent': False,
                'message': 'Upload completed, but the recipient download could not be verified. Check its access policy or supply a working GET link before sharing.'}

    # Optional webhook notification
    webhook_sent = False
    webhook_error = None
    if webhook_url:
        install_cmd = f"lectic install {download_url} --as {install_name}"
        text_msg = f"Published {pack_name} v{version}.\nTeam install: `{install_cmd}`"
        payload = {
            'text': text_msg,
            'content': text_msg,
            'pack': {
                'name': pack_name,
                'version': version,
                'install_name': install_name,
                'download_url': download_url,
                'install_command': install_cmd
            }
        }
        w_body = json.dumps(payload).encode('utf-8')
        w_req = urllib.request.Request(
            webhook_url,
            data=w_body,
            headers={'Content-Type': 'application/json', 'User-Agent': f'lectic/{VERSION}'},
            method='POST'
        )
        try:
            with urllib.request.urlopen(w_req, timeout=10) as resp:
                webhook_sent = True
        except Exception as exc:
            webhook_error = str(exc)

    install_cmd = f"lectic install {download_url} --as {install_name}"
    msg = f"Published {pack_name} v{version}. Team install: {install_cmd}"
    return {
        'phase': 'published',
        'name': pack_name,
        'version': version,
        'install_name': install_name,
        'download_url': download_url,
        'install_command': install_cmd,
        'webhook_sent': webhook_sent,
        'webhook_error': webhook_error,
        'message': msg
    }
