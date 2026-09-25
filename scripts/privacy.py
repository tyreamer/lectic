"""Keep Lectic's own credentials outside assistant reads and source exports."""
from pathlib import Path
import os
from ec import require


def require_shareable(path, home):
    candidate = Path(path).expanduser().resolve()
    cookie_path = os.environ.get('LECTIC_YTDLP_COOKIES')
    require(not cookie_path or candidate != Path(cookie_path).expanduser().resolve(),
            'Lectic credentials cannot be read, captured or exported as knowledge')
    root = Path(home).resolve()
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return candidate
    protected = {'identity.json', 'identity-legacy.json', 'server.json', 'share-link.json',
                 'cookies.txt', 'cookies.json', '.env'}
    require(not any(part.lower() in protected or part.lower().startswith(('identity-', '.env.', 'credentials'))
                    for part in relative.parts), 'Lectic credentials cannot be read, captured or exported as knowledge')
    return candidate
