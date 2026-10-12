"""Fixed-recipe installer. No arbitrary scripts, registry changes or auto updates."""
from __future__ import annotations
import contextlib, csv, hashlib, json, os, re, shutil, stat, subprocess, tempfile, uuid, zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

STATE = '.retro-renew'
HEX = re.compile(r'^[0-9a-f]{64}$')
RESERVED = {'CON','PRN','AUX','NUL', *(f'COM{i}' for i in range(1,10)), *(f'LPT{i}' for i in range(1,10))}

class SafetyError(Exception):
    pass

def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def relative(value):
    if not isinstance(value,str) or not value or '\\' in value or any(c in value for c in ':<>"|?*\x00'):
        raise SafetyError('Unsafe file path in recipe or archive.')
    p = PurePosixPath(value)
    if p.is_absolute() or any(x in ('','.','..') for x in value.split('/')):
        raise SafetyError('Paths must stay inside the game folder.')
    for x in p.parts:
        if x.endswith((' ','.')) or x.split('.')[0].upper() in RESERVED or any(ord(c)<32 for c in x):
            raise SafetyError('Unsupported Windows file name.')
    if p.parts[0].lower() == STATE:
        raise SafetyError('A mod cannot replace installer recovery data.')
    return p

def no_links(path):
    """Reject symlinks and Windows junctions, including parents of the game."""
    p = Path(os.path.abspath(path))
    for item in [*reversed(p.parents), p]:
        if item.exists() or item.is_symlink():
            s = item.lstat()
            if stat.S_ISLNK(s.st_mode) or getattr(s,'st_file_attributes',0) & 0x400:
                raise SafetyError('Linked folders/junctions are unsupported. Select a normal local folder.')
    return p

def target(root, value):
    p = no_links(Path(root).joinpath(*relative(value).parts))
    if not p.is_relative_to(Path(root)):
        raise SafetyError('File escapes the game folder.')
    return p

def sha(value):
    if not isinstance(value,str) or not HEX.fullmatch(value):
        raise SafetyError('Every supported file needs a real SHA-256 checksum.')

def https(value):
    p = urlparse(value)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None,443):
        raise SafetyError('Only HTTPS source links are accepted.')

def validate(recipe):
    if recipe.get('schema') != 1 or recipe.get('status') not in ('released','demo'):
        raise SafetyError('This recipe has not been approved for installation.')
    if not re.fullmatch(r'[a-z0-9-]{1,80}',recipe.get('id','')):
        raise SafetyError('Invalid setup identifier.')
    if not recipe.get('title') or not recipe.get('version') or not recipe.get('edition'):
        raise SafetyError('Missing setup information.')
    relative(recipe['executable'])
    markers = recipe.get('markers',[])
    if not markers or recipe['executable'] not in [m['path'] for m in markers]:
        raise SafetyError('The game executable must be fingerprinted.')
    for m in markers:
        relative(m['path']); sha(m['sha256'])
    destinations = set()
    ids = set()
    protected = [relative(x).as_posix().casefold() for x in recipe.get('protected',[])]
    for a in recipe.get('artifacts',[]):
        if not re.fullmatch(r'[a-z0-9-]{1,80}',a.get('id','')) or a['id'] in ids:
            raise SafetyError('Invalid or duplicate component ID.')
        ids.add(a['id'])
        if not a.get('author') or not a.get('name'):
            raise SafetyError('Components must include author credits.')
        https(a['page']); sha(a['sha256'])
        if a.get('permission',{}).get('reviewed') is not True or not a['permission'].get('evidence'):
            raise SafetyError('Author permissions have not been reviewed.')
        if a['permission'].get('method') not in ('manual','direct'):
            raise SafetyError('Unsupported permission method.')
        if not isinstance(a.get('max_bytes'),int) or not 0 < a['max_bytes'] <= 2*1024**3:
            raise SafetyError('Archive size limit is required (maximum 2 GB).')
        if not isinstance(a.get('expanded_bytes'),int) or not 0 < a['expanded_bytes'] <= 4*1024**3:
            raise SafetyError('Expanded size limit is required (maximum 4 GB).')
        if a['permission']['method'] == 'direct':
            https(a['url'])
            hosts = a.get('allowed_hosts',[])
            if not hosts or urlparse(a['url']).hostname not in hosts:
                raise SafetyError('Direct downloads require explicit allowed hosts.')
        if not a.get('files'):
            raise SafetyError('An explicit installation file list is required.')
        for f in a['files']:
            relative(f['source']); d = relative(f['destination']).as_posix().casefold()
            sha(f['sha256'])
            if f.get('original_sha256') is not None: sha(f['original_sha256'])
            if d in destinations or any(d == q or d.startswith(q+'/') or q.startswith(d+'/') for q in protected):
                raise SafetyError('Overlapping files or protected save/configuration paths.')
            if any(d.startswith(q+'/') or q.startswith(d+'/') for q in destinations):
                raise SafetyError('Conflicting file and directory destinations.')
            destinations.add(d)
    if not destinations:
        raise SafetyError('Recipe has no installation files.')
    marker_paths = {m['path'].casefold() for m in markers}
    if destinations & marker_paths:
        raise SafetyError('This engine does not replace game executables or identity markers.')
    return recipe

def load_recipe(path):
    return validate(json.loads(Path(path).read_text(encoding='utf-8')))

def atomic_json(path, value):
    path = Path(path); no_links(path)
    tmp = path.with_name(path.name+'.new')
    no_links(tmp)
    with open(tmp,'w',encoding='utf-8') as f:
        json.dump(value,f,indent=2); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,path)

def atomic_copy(source, destination):
    no_links(source); no_links(destination)
    fd, name = tempfile.mkstemp(prefix='.rr-',dir=Path(destination).parent)
    try:
        with os.fdopen(fd,'wb') as f, open(source,'rb') as s:
            shutil.copyfileobj(s,f); f.flush(); os.fsync(f.fileno())
        os.replace(name,destination)
    finally:
        if os.path.exists(name): os.unlink(name)

@contextlib.contextmanager
def locked(root):
    state = no_links(Path(root)/STATE); state.mkdir(exist_ok=True)
    lock = no_links(state/'operation.lock')
    with open(lock,'a+b') as f:
        f.seek(0); f.write(b'0'); f.flush(); f.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            raise SafetyError('Another installer is using this game folder.')
        try: yield state
        finally:
            if os.name == 'nt':
                f.seek(0); msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
            else: fcntl.flock(f.fileno(),fcntl.LOCK_UN)

def not_running(recipe):
    if os.name != 'nt': return
    try:
        out = subprocess.run(['tasklist','/FO','CSV','/NH'],capture_output=True,text=True,
                             timeout=15,check=True,creationflags=0x08000000).stdout
    except (OSError,subprocess.SubprocessError):
        raise SafetyError('Cannot check running processes. Close the game and retry.')
    exe = PurePosixPath(recipe['executable']).name.casefold()
    if any(row and row[0].casefold()==exe for row in csv.reader(out.splitlines())):
        raise SafetyError('Close the game before installing or restoring.')

def preflight(recipe,root):
    validate(recipe); root = no_links(root)
    if os.name == 'nt' and str(root).startswith('\\\\'):
        raise SafetyError('Network game folders are unsupported. Select a local installation.')
    if not root.is_dir() or root == Path(root.anchor):
        raise SafetyError('Select the actual game folder.')
    not_running(recipe)
    for m in recipe['markers']:
        p = target(root,m['path'])
        if not p.is_file() or digest(p) != m['sha256']:
            raise SafetyError('Unsupported game edition/version: '+m['path']+'. No game files changed.')
    for x in recipe.get('conflicts',[]):
        if target(root,x).exists(): raise SafetyError('Existing mod conflict: '+x)
    state = no_links(root/STATE)
    jp = no_links(state/'journal.json')
    if jp.exists():
        j = json.loads(jp.read_text())
        if j.get('status') != 'restored':
            raise SafetyError('A setup or unfinished installation already exists. Use Restore / recover first.')
    total = 128*1024**2
    for a in recipe['artifacts']:
        total += a['max_bytes'] + a['expanded_bytes']
        for f in a['files']:
            p = target(root,f['destination'])
            for parent in p.parents:
                if parent == root: break
                if parent.exists() and not parent.is_dir():
                    raise SafetyError('An installation folder is occupied by a file: '+parent.relative_to(root).as_posix())
            if p.exists():
                if not p.is_file() or f.get('original_sha256') is None or digest(p)!=f['original_sha256']:
                    raise SafetyError('Unexpected existing file: '+f['destination']+'. Start from a supported clean installation.')
                total += p.stat().st_size
            elif f.get('original_sha256') is not None:
                raise SafetyError('Required original file is missing: '+f['destination'])
    if shutil.disk_usage(root).free < total:
        raise SafetyError('Not enough free space for staging and backups.')
    # Writability probe creates and removes one temporary file, never touches game files.
    try:
        fd,p = tempfile.mkstemp(prefix='.rr-write-check-',dir=root); os.close(fd); os.unlink(p)
    except OSError:
        raise SafetyError('This folder is not writable. Use a game installation outside protected Windows folders.')
    return root

class RestrictedRedirect(HTTPRedirectHandler):
    def __init__(self, hosts): self.hosts = hosts
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        https(newurl)
        if urlparse(newurl).hostname not in self.hosts:
            raise SafetyError('Download redirected to an unapproved host.')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def obtain(a, archives, stage, log):
    for p in archives:
        p = no_links(p)
        if p.is_file() and p.stat().st_size<=a['max_bytes'] and digest(p)==a['sha256']:
            return p
    if a['permission']['method'] != 'direct':
        raise SafetyError('Download '+a['name']+' from its author page, then add its ZIP archive.')
    log('Downloading '+a['name'])
    dest = stage/(a['id']+'.zip')
    opener = build_opener(RestrictedRedirect(a['allowed_hosts']))
    with opener.open(Request(a['url'],headers={'User-Agent':'RetroRenew/0.1'}),timeout=30) as r, open(dest,'xb') as f:
        https(r.url)
        if urlparse(r.url).hostname not in a['allowed_hosts']: raise SafetyError('Unapproved final download host.')
        count=0
        while True:
            b = r.read(1024*1024)
            if not b: break
            count+=len(b)
            if count>a['max_bytes']: raise SafetyError('Download exceeded its approved size.')
            f.write(b)
    if digest(dest)!=a['sha256']: raise SafetyError('Download checksum does not match the tested version.')
    return dest

def stage_archive(a, archive, folder):
    try:
        return _stage_archive(a,archive,folder)
    except (zipfile.BadZipFile,KeyError,RuntimeError,NotImplementedError) as e:
        raise SafetyError('The archive is invalid or does not contain the approved files: '+a['name']) from e

def _stage_archive(a, archive, folder):
    if digest(archive)!=a['sha256']: raise SafetyError('Archive changed during preparation.')
    with zipfile.ZipFile(archive) as z:
        infos=z.infolist()
        if len(infos)>10000 or sum(x.file_size for x in infos)>a['expanded_bytes']:
            raise SafetyError('Archive exceeds its expansion limit.')
        names=set()
        for i in infos:
            relative(i.filename.rstrip('/'))
            if i.filename.casefold() in names: raise SafetyError('Duplicate archive paths.')
            names.add(i.filename.casefold())
            if i.flag_bits & 1 or stat.S_ISLNK(i.external_attr >> 16):
                raise SafetyError('Encrypted archives and archive symlinks are unsupported.')
        result=[]
        for n,f in enumerate(a['files']):
            info=z.getinfo(f['source'])
            if info.is_dir(): raise SafetyError('Expected file, found directory.')
            out=folder/(a['id']+'-'+str(n)+'.payload')
            with z.open(info) as s, open(out,'xb') as d: shutil.copyfileobj(s,d)
            if digest(out)!=f['sha256']: raise SafetyError('Extracted file checksum failed: '+f['source'])
            result.append((f,out))
        return result

def install(recipe, root, archives, log=lambda _:None, fault=None):
    root=preflight(recipe,root)
    with locked(root) as state:
        # Repeat after acquiring the lock, before committing any modifications.
        preflight(recipe,root)
        txn=state/uuid.uuid4().hex; txn.mkdir()
        stage=txn/'stage'; stage.mkdir(); backup=txn/'backup'; backup.mkdir()
        entries=[]; created=[]
        j={'schema':1,'recipe':recipe['id'],'version':recipe['version'],'transaction':txn.name,
           'status':'preparing','entries':entries,'directories':created}
        jp=state/'journal.json'
        try:
            payloads=[]
            for a in recipe['artifacts']:
                log('Checking '+a['name'])
                archive=obtain(a,archives,stage,log)
                payloads.extend(stage_archive(a,archive,stage))
            # Preparation can take time: revalidate originals and game process now.
            preflight(recipe,root)
            for index,(f,out) in enumerate(payloads):
                dst=target(root,f['destination'])
                old=digest(dst) if dst.exists() else None
                b=backup/(str(index)+'.bak')
                if old:
                    shutil.copy2(dst,b)
                    if digest(b)!=old: raise SafetyError('Backup verification failed. No installation changes made.')
                entries.append({'path':f['destination'],'old':old,'new':f['sha256'],
                                'backup':b.name,'status':'pending'})
            j['status']='installing'; atomic_json(jp,j)
            for e,(_,out) in zip(entries,payloads):
                not_running(recipe)
                dst=target(root,e['path'])
                actual=digest(dst) if dst.is_file() else None
                if actual!=e['old']: raise SafetyError('A game file changed during installation.')
                missing=[]; parent=dst.parent
                while not parent.exists(): missing.append(parent); parent=parent.parent
                for p in reversed(missing):
                    created.append(p.relative_to(root).as_posix()); atomic_json(jp,j); p.mkdir()
                e['status']='writing'; atomic_json(jp,j)
                if fault: fault(e)
                atomic_copy(out,dst)
                if digest(dst)!=e['new']: raise SafetyError('Installed file verification failed.')
                e['status']='done'; atomic_json(jp,j); log('Installed '+e['path'])
            j['status']='installed'; atomic_json(jp,j)
            shutil.rmtree(stage)
            return j
        except BaseException:
            if jp.exists() and json.loads(jp.read_text()).get('transaction')==txn.name:
                log('Installation stopped. Recovery data is retained. Use Restore / recover.')
            else: shutil.rmtree(txn)
            raise

def restore(recipe, root, log=lambda _:None):
    root=no_links(root); validate(recipe); not_running(recipe)
    for m in recipe['markers']:
        p=target(root,m['path'])
        if not p.is_file() or digest(p)!=m['sha256']: raise SafetyError('Game identity changed; automatic restoration is blocked.')
    with locked(root) as state:
        jp=no_links(state/'journal.json')
        if not jp.is_file(): raise SafetyError('No installation backup found in this folder.')
        j=json.loads(jp.read_text())
        if j.get('schema')!=1 or j.get('recipe')!=recipe['id'] or j.get('version')!=recipe['version']:
            raise SafetyError('Recovery data belongs to a different setup.')
        if j.get('status')=='restored': raise SafetyError('The previous setup has already been restored.')
        if not re.fullmatch(r'[0-9a-f]{32}',j.get('transaction','')): raise SafetyError('Invalid recovery data.')
        expected={f['destination']:f for a in recipe['artifacts'] for f in a['files']}
        if len(j.get('entries',[]))!=len(expected): raise SafetyError('Incomplete recovery journal.')
        seen=set()
        for index,e in enumerate(j['entries']):
            if e.get('path') not in expected or e['path'] in seen: raise SafetyError('Invalid recovery file list.')
            seen.add(e['path']); f=expected[e['path']]
            if e.get('new')!=f['sha256'] or e.get('old')!=f.get('original_sha256') or e.get('backup')!=str(index)+'.bak':
                raise SafetyError('Recovery record does not match the approved recipe.')
            p=target(root,e['path'])
            if p.exists() and not p.is_file(): raise SafetyError('A recovery target is now a directory.')
            actual=digest(p) if p.exists() else None
            if actual not in (e['old'],e['new']):
                raise SafetyError('File changed since installation: '+e['path']+'. Keep it safe before recovering.')
            if e['old']:
                b=no_links(state/j['transaction']/'backup'/e['backup'])
                if not b.is_file() or digest(b)!=e['old']: raise SafetyError('Backup missing or damaged. Automatic recovery stopped.')
        allowed_dirs=set()
        for f in expected:
            allowed_dirs.update(p.as_posix() for p in PurePosixPath(f).parents if p.as_posix()!='.')
        if any(d not in allowed_dirs for d in j.get('directories',[])):
            raise SafetyError('Invalid recovery directory list.')
        j['status']='restoring'; atomic_json(jp,j)
        for e in reversed(j['entries']):
            not_running(recipe); p=target(root,e['path'])
            actual=digest(p) if p.is_file() else None
            if actual not in (e['old'],e['new']): raise SafetyError('File changed during recovery.')
            if actual != e['old']:
                if e['old']: atomic_copy(state/j['transaction']/'backup'/e['backup'],p)
                elif p.exists(): p.unlink()
            e['status']='restored'; atomic_json(jp,j); log('Restored '+e['path'])
        for d in reversed(j.get('directories',[])):
            p=target(root,d)
            if p.is_dir():
                try: p.rmdir()
                except OSError: pass  # Preserve directories containing unrelated user files.
        j['status']='restored'; atomic_json(jp,j)
        return j
