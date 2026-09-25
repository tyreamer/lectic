"""Check the configured transport with a real MCP handshake and home lookup."""
import json
import os
import subprocess
import urllib.request


def check_connection(spec, cwd=None):
    requests = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
         'params': {'protocolVersion': '2025-06-18', 'capabilities': {},
                    'clientInfo': {'name': 'lectic-setup', 'version': '1'}}},
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
         'params': {'name': 'lectic_home', 'arguments': {}}},
    ]
    try:
        if spec.get('url'):
            responses = []
            headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
            headers.update(spec.get('http_headers', {}))
            if spec.get('bearer_token_env_var'):
                headers['Authorization'] = 'Bearer ' + os.environ[spec['bearer_token_env_var']]
            for request in (requests[0], requests[2]):
                req = urllib.request.Request(spec['url'], data=json.dumps(request).encode(), headers=headers, method='POST')
                with urllib.request.urlopen(req, timeout=8) as response:
                    raw = response.read(2 * 1024 * 1024 + 1)
                    if len(raw) > 2 * 1024 * 1024: return False, None
                    responses.append(json.loads(raw))
        else:
            command = [spec['command']] + list(spec.get('args', []))
            environment = {**os.environ, **spec.get('env', {})}
            result = subprocess.run(command, input=''.join(json.dumps(r) + '\n' for r in requests),
                                    capture_output=True, text=True, encoding='utf-8', errors='replace',
                                    timeout=15, cwd=cwd, env=environment)
            if result.returncode != 0: return False, None
            responses = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        by_id = {r.get('id'): r for r in responses}
        init, call = by_id[1]['result'], by_id[2]['result']
        if 'serverInfo' not in init or call.get('isError'): return False, None
        home = json.loads(call['content'][0]['text'])
        return isinstance(home.get('home'), str), home
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
        # URLs may contain bearer tokens. Never return raw transport exceptions.
        return False, None
