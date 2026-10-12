"""Check catalogue structure and release links without browser dependencies."""
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'launcher'))
from core import load_recipe


def require(condition, message):
    # Do not use assert: these checks must also run under python -O.
    if not condition:
        raise ValueError(message)


def url(value):
    require(isinstance(value, str), 'External URL must be text.')
    parsed = urlparse(value)
    require(parsed.scheme == 'https' and parsed.hostname and not parsed.username
            and not parsed.password and parsed.port in (None, 443),
            'Invalid HTTPS external URL: ' + value)


def main():
    script = ('global.window={};require(' + json.dumps(str(ROOT / 'site/catalogue.js'))
              + ');process.stdout.write(JSON.stringify(window.RETRO_RENEW))')
    data = json.loads(subprocess.check_output(['node', '-e', script], text=True, timeout=30))
    require(isinstance(data, dict) and isinstance(data.get('games'), list), 'Missing games list.')
    url(data['channel'])
    ids = set()
    for game in data['games']:
        identifier = game.get('id', '')
        require(isinstance(identifier, str) and re.fullmatch(r'[a-z0-9-]{1,80}', identifier)
                and identifier not in ids, 'Duplicate or invalid page ID.')
        ids.add(identifier)
        require(game.get('status') in ('draft', 'example', 'released', 'reference'),
                identifier + ': invalid status.')
        require(game.get('title') and game.get('series') and isinstance(game.get('mods'), list),
                identifier + ': missing title, series or mods.')
        require(isinstance(game.get('color'), str) and re.fullmatch(r'#[0-9a-fA-F]{6}', game['color']),
                identifier + ': invalid colour.')
        for mod in game['mods']:
            require(mod.get('author') and mod.get('name') and mod.get('permission'),
                    identifier + ': missing component credit or permission note.')
            url(mod['page'])
        for key in ('videoUrl', 'installerUrl'):
            if game.get(key):
                url(game[key])
        if game['status'] == 'released':
            require(game.get('installerUrl') and game.get('testedDate'),
                    identifier + ': release needs a download and test date.')
            tested = game['testedDate']
            require(isinstance(tested, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', tested),
                    identifier + ': test date must be YYYY-MM-DD.')
            datetime.date.fromisoformat(tested)
            recipe = load_recipe(ROOT / 'recipes' / (identifier + '.json'))
            require(recipe['status'] == 'released' and recipe['id'] == identifier,
                    identifier + ': released page must match its released recipe.')
    for path in (ROOT / 'recipes').glob('*.json'):
        if path.name.endswith('.template.json'):
            continue
        recipe = load_recipe(path)
        require(path.stem == recipe['id'], 'Recipe filename must match its ID: ' + path.name)
    print(f'Catalogue checked: {len(ids)} pages. Released recipes validated.')


if __name__ == '__main__':
    main()
