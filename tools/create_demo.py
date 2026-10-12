"""Generate a harmless game fixture and recipe owned entirely by this project."""
import hashlib,json,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def create(base):
    base=Path(base); game=base/'Training Game'
    archive=base/'retro-renew-demo.zip'; rp=base/'recipe.json'
    # Never reset a previous installation or overwrite unrelated local files.
    if any(p.exists() or p.is_symlink() for p in (game,archive,rp)):
        raise FileExistsError('Demo files already exist. Choose a new empty folder.')
    game.mkdir(parents=True)
    data=b'Retro Renew training fixture. This is not an executable.\n'
    (game/'TrainingGame.exe').write_bytes(data)
    old=b'original settings\n'; new=b'renewed settings\n'; added=b'Retro Renew demonstration content\n'
    (game/'settings.ini').write_bytes(old)
    with zipfile.ZipFile(archive,'w') as z:
        # Fixed metadata makes the archive checksum match on every system and
        # every build, including the recipe bundled with the Windows launcher.
        for name,payload in [('settings.ini',new),('mods/renew.txt',added)]:
            info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0))
            info.create_system=3; info.external_attr=0o100644 << 16
            z.writestr(info,payload)
    h=lambda b:hashlib.sha256(b).hexdigest()
    recipe={'schema':1,'id':'training-demo','status':'demo','title':'Retro Renew training demo','version':'0.1.0',
        'edition':'Generated training fixture only','executable':'TrainingGame.exe','steam_folders':[],
        'markers':[{'path':'TrainingGame.exe','sha256':h(data)}], 'conflicts':[], 'protected':['saves'],
        'artifacts':[{'id':'training-files','name':'Training files','author':'Retro Renew project',
        'page':'https://github.com/Loukeyo/retro-renew','sha256':h(archive.read_bytes()),'max_bytes':1024*1024,
        'expanded_bytes':1024*1024,'notice':'MIT-licensed original demonstration files. No third-party mods are included.',
        'permission':{'reviewed':True,'method':'manual','evidence':'Original demonstration files under this project MIT licence.'},
        'files':[{'source':'settings.ini','destination':'settings.ini','sha256':h(new),'original_sha256':h(old)},
                 {'source':'mods/renew.txt','destination':'mods/renew.txt','sha256':h(added),'original_sha256':None}]}]}
    rp.write_text(json.dumps(recipe,indent=2)+'\n',encoding='utf-8')
    return game,archive,rp
if __name__=='__main__':
    paths=create(sys.argv[1] if len(sys.argv)>1 else ROOT/'demo')
    print('\n'.join(map(str,paths)))
