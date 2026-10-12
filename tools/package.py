"""Create a standalone preview and source ZIP without touching user demo files."""
from pathlib import Path
import shutil,sys,tempfile,zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT.parent
OUT.mkdir(parents=True,exist_ok=True)
from create_demo import create
html=(ROOT/'site/index.html').read_text(encoding='utf-8')
html=html.replace('<link rel="stylesheet" href="styles.css">','<style>'+(ROOT/'site/styles.css').read_text(encoding='utf-8')+'</style>')
html=html.replace('<script defer src="catalogue.js"></script><script defer src="app.js"></script>','')
html=html.replace('</body>','<script>'+(ROOT/'site/catalogue.js').read_text(encoding='utf-8')+'</script><script>'+(ROOT/'site/app.js').read_text(encoding='utf-8')+'</script></body>')
preview=OUT/'Retro-Renew-Preview.html';preview.write_text(html,encoding='utf-8')
archive=OUT/'Retro-Renew-Project.zip'
with tempfile.TemporaryDirectory(prefix='rr-package-') as folder:
    demo=Path(folder)/'demo';create(demo)
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(ROOT.rglob('*')):
            rel=p.relative_to(ROOT)
            if p.is_file() and not any(x in ('demo','__pycache__','.git','build-output') for x in rel.parts) and p.suffix not in ('.pyc','.spec') and p.name not in ('Retro-Renew-Preview.html','Retro-Renew-Project.zip'):
                z.write(p,Path('retro-renew')/rel)
        z.write(preview,'retro-renew/Retro-Renew-Preview.html')
        for p in sorted(demo.rglob('*')):
            if p.is_file():z.write(p,Path('retro-renew/demo')/p.relative_to(demo))
print(f'Preview: {preview}\nProject: {archive}\nSize: {archive.stat().st_size} bytes')
