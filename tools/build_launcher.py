"""Build a Windows EXE with one immutable recipe and publishable checksums."""
import argparse
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'launcher'))
from core import load_recipe


def repository_recipe(value):
    """Workflow inputs are data, confined to a JSON file in this checkout."""
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    if path.is_symlink():
        raise ValueError('Recipe symlinks are not supported.')
    path = path.resolve(strict=True)
    if not path.is_relative_to(ROOT) or path.suffix.lower() != '.json' or not path.is_file():
        raise ValueError('Recipe must be a JSON file inside this repository.')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipe', required=True)
    args = parser.parse_args()
    recipe_path = repository_recipe(args.recipe)
    recipe = load_recipe(recipe_path)
    if sys.platform != 'win32':
        parser.error('Build on Windows, or run the Build Windows launcher GitHub workflow.')
    # Fail before invoking the packager if Tk is unavailable on the build host.
    import tkinter
    output = ROOT / 'build-output'
    output.mkdir(exist_ok=True)
    name = 'RetroRenew-' + recipe['id']
    executable = output / (name + '.exe')
    with tempfile.TemporaryDirectory() as temp:
        embedded = Path(temp) / 'recipe.json'
        shutil.copy2(recipe_path, embedded)
        subprocess.run([
            sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
            '--onefile', '--windowed', '--name', name,
            '--paths', str(ROOT / 'launcher'), '--add-data', str(embedded) + ';.',
            '--distpath', str(output), '--workpath', str(Path(temp) / 'work'),
            '--specpath', temp, str(ROOT / 'launcher' / 'app.py'),
        ], check=True, cwd=ROOT)
    if not executable.is_file() or executable.stat().st_size == 0:
        raise RuntimeError('Packager did not produce the expected executable.')
    checksum = hashlib.sha256(executable.read_bytes()).hexdigest()
    (output / 'SHA256SUMS.txt').write_text(checksum + '  ' + executable.name + '\n', encoding='utf-8')
    info = {
        'recipe': recipe['id'], 'version': recipe['version'], 'status': recipe['status'],
        'recipe_sha256': hashlib.sha256(recipe_path.read_bytes()).hexdigest(),
        'executable': executable.name, 'sha256': checksum,
        'python': sys.version.split()[0],
        'pyinstaller': importlib.metadata.version('PyInstaller'),
        'signed': False, 'windows_runtime_verified': False,
    }
    (output / 'build-info.json').write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
    print('Built ' + executable.name + '; Windows runtime testing is still required.')


if __name__ == '__main__':
    main()
