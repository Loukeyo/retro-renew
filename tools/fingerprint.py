"""Print a SHA-256 checksum without modifying the source file."""
import argparse,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('file');a=p.parse_args()
h=hashlib.sha256()
with Path(a.file).open('rb') as f:
    for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
print(h.hexdigest())
