import copy, hashlib, json, os, sys, tempfile, unittest, zipfile
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'launcher'));sys.path.insert(0,str(ROOT/'tools'))
from core import SafetyError, digest, install, load_recipe, preflight, restore, stage_archive, validate
from create_demo import create

class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.game,self.archive,self.rp=create(self.base)
        self.recipe=load_recipe(self.rp);self.original=(self.game/'settings.ini').read_bytes()
    def go(self,**kwargs):return install(self.recipe,self.game,[self.archive],**kwargs)
    def test_install_and_restore_roundtrip(self):
        saves=self.game/'saves';saves.mkdir();(saves/'slot1').write_text('keep me')
        self.go();self.assertEqual((self.game/'settings.ini').read_text(),'renewed settings\n')
        self.assertTrue((self.game/'mods/renew.txt').exists())
        restore(self.recipe,self.game)
        self.assertEqual((self.game/'settings.ini').read_bytes(),self.original)
        self.assertFalse((self.game/'mods').exists());self.assertEqual((saves/'slot1').read_text(),'keep me')
    def test_unknown_game_rejected_without_changes(self):
        (self.game/'TrainingGame.exe').write_text('different edition')
        with self.assertRaises(SafetyError):self.go()
        self.assertEqual((self.game/'settings.ini').read_bytes(),self.original)
        self.assertFalse((self.game/'.retro-renew').exists())
    def test_modified_original_rejected(self):
        (self.game/'settings.ini').write_text('already modded')
        with self.assertRaises(SafetyError):self.go()
        self.assertEqual((self.game/'settings.ini').read_text(),'already modded')
    def test_existing_added_file_rejected(self):
        (self.game/'mods').mkdir();(self.game/'mods/renew.txt').write_text('mine')
        with self.assertRaises(SafetyError):self.go()
    def test_bad_archive_leaves_game_untouched(self):
        self.archive.write_bytes(b'invalid')
        with self.assertRaises(SafetyError):self.go()
        self.assertEqual((self.game/'settings.ini').read_bytes(),self.original)
        self.assertFalse((self.game/'.retro-renew/journal.json').exists())
    def test_interrupt_after_first_change_recovers(self):
        count=0
        def interrupt(e):
            nonlocal count
            count+=1
            if count==2:raise RuntimeError('simulated interruption')
        with self.assertRaises(RuntimeError):self.go(fault=interrupt)
        self.assertEqual((self.game/'settings.ini').read_text(),'renewed settings\n')
        with self.assertRaises(SafetyError):self.go()
        restore(self.recipe,self.game)
        self.assertEqual((self.game/'settings.ini').read_bytes(),self.original)
        self.assertFalse((self.game/'mods').exists())
    def test_subsequent_user_changes_block_entire_restore(self):
        self.go();(self.game/'mods/renew.txt').write_text('my own edit')
        with self.assertRaises(SafetyError):restore(self.recipe,self.game)
        self.assertEqual((self.game/'settings.ini').read_text(),'renewed settings\n')
    def test_damaged_backup_blocks_restore(self):
        self.go();state=self.game/'.retro-renew';j=json.loads((state/'journal.json').read_text())
        (state/j['transaction']/'backup/0.bak').write_text('bad backup')
        with self.assertRaises(SafetyError):restore(self.recipe,self.game)
        self.assertEqual((self.game/'settings.ini').read_text(),'renewed settings\n')
    def test_unrelated_files_preserved(self):
        self.go();(self.game/'mods/other.txt').write_text('keep')
        restore(self.recipe,self.game);self.assertEqual((self.game/'mods/other.txt').read_text(),'keep')
    def test_reinstall_after_restore(self):
        self.go();restore(self.recipe,self.game);self.go()
        self.assertTrue((self.game/'mods/renew.txt').exists())
    def test_unsafe_destination_rejected(self):
        for name in ['../outside','/absolute','C:/escape','mods/CON.txt','mods/trailing.','mods/a:stream','.retro-renew/journal.json','mods\\bad']:
            with self.subTest(name=name):
                r=copy.deepcopy(self.recipe);r['artifacts'][0]['files'][1]['destination']=name
                with self.assertRaises(SafetyError):validate(r)
    def test_case_collisions_rejected(self):
        r=copy.deepcopy(self.recipe);r['artifacts'][0]['files'][1]['destination']='SETTINGS.INI'
        with self.assertRaises(SafetyError):validate(r)
    def test_game_executable_replacement_rejected(self):
        r=copy.deepcopy(self.recipe);r['artifacts'][0]['files'][1]['destination']='TrainingGame.exe'
        with self.assertRaises(SafetyError):validate(r)
    def test_unreviewed_permissions_rejected(self):
        r=copy.deepcopy(self.recipe);r['artifacts'][0]['permission']['reviewed']=False
        with self.assertRaises(SafetyError):validate(r)
    def test_protected_save_path_rejected(self):
        r=copy.deepcopy(self.recipe);r['artifacts'][0]['files'][1]['destination']='saves/slot1'
        with self.assertRaises(SafetyError):validate(r)
    def test_archive_path_traversal_rejected(self):
        with zipfile.ZipFile(self.archive,'a') as z:z.writestr('../escape.txt','bad')
        a=copy.deepcopy(self.recipe['artifacts'][0]);a['sha256']=digest(self.archive)
        stage=self.base/'stage';stage.mkdir()
        with self.assertRaises(SafetyError):stage_archive(a,self.archive,stage)
        self.assertFalse((self.base/'escape.txt').exists())
    def test_expansion_limit_rejected(self):
        a=copy.deepcopy(self.recipe['artifacts'][0]);a['expanded_bytes']=1
        stage=self.base/'stage';stage.mkdir()
        with self.assertRaises(SafetyError):stage_archive(a,self.archive,stage)
    def test_archive_symlink_rejected(self):
        with zipfile.ZipFile(self.archive,'a') as z:
            info=zipfile.ZipInfo('link');info.create_system=3;info.external_attr=0o120777 << 16;z.writestr(info,'/tmp')
        a=copy.deepcopy(self.recipe['artifacts'][0]);a['sha256']=digest(self.archive)
        stage=self.base/'stage';stage.mkdir()
        with self.assertRaises(SafetyError):stage_archive(a,self.archive,stage)
    @unittest.skipIf(os.name=='nt','Symlink creation may require elevated Windows privileges')
    def test_linked_destination_rejected(self):
        outside=self.base/'outside';outside.mkdir();(self.game/'mods').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(SafetyError):self.go()
        self.assertEqual(list(outside.iterdir()),[])
    def test_tampered_recovery_record_rejected(self):
        self.go();p=self.game/'.retro-renew/journal.json';j=json.loads(p.read_text());j['entries'][0]['path']='other.txt';p.write_text(json.dumps(j))
        with self.assertRaises(SafetyError):restore(self.recipe,self.game)
    def test_direct_download_host_must_be_approved(self):
        r=copy.deepcopy(self.recipe);a=r['artifacts'][0];a['permission']['method']='direct';a['url']='https://example.com/file.zip';a['allowed_hosts']=['other.example']
        with self.assertRaises(SafetyError):validate(r)
    def test_second_install_blocked(self):
        self.go()
        with self.assertRaises(SafetyError):self.go()
    def test_demo_archive_is_reproducible(self):
        _,other,rp=create(self.base/'another fixture')
        self.assertEqual(digest(other),digest(self.archive))
        self.assertEqual(load_recipe(rp),self.recipe)
    def test_demo_generation_does_not_overwrite_installed_files(self):
        self.go()
        with self.assertRaises(FileExistsError):create(self.base)
        self.assertEqual((self.game/'settings.ini').read_text(),'renewed settings\n')
        restore(self.recipe,self.game)
        self.assertEqual((self.game/'settings.ini').read_bytes(),self.original)
    def test_parent_file_conflict_stops_before_installation(self):
        (self.game/'mods').write_text('unrelated file')
        with self.assertRaisesRegex(SafetyError,'occupied by a file'):self.go()
        self.assertEqual((self.game/'mods').read_text(),'unrelated file')
        self.assertFalse((self.game/'.retro-renew').exists())
    def test_protected_path_ancestor_rejected(self):
        r=copy.deepcopy(self.recipe);r['protected']=['mods/user-data']
        r['artifacts'][0]['files'][1]['destination']='mods'
        with self.assertRaises(SafetyError):validate(r)
    def test_missing_archive_payload_is_explained(self):
        with zipfile.ZipFile(self.archive,'w') as z:z.writestr('other.txt','unrelated')
        a=copy.deepcopy(self.recipe['artifacts'][0]);a['sha256']=digest(self.archive)
        stage=self.base/'stage';stage.mkdir()
        with self.assertRaisesRegex(SafetyError,'approved files'):stage_archive(a,self.archive,stage)
    def test_interrupted_restore_can_resume(self):
        self.go()
        # Recovery removes the added file first, then attempts the original
        # settings. Simulate failure at that copy and retry from the journal.
        with patch('core.atomic_copy',side_effect=OSError('simulated disk failure')):
            with self.assertRaises(OSError):restore(self.recipe,self.game)
        self.assertFalse((self.game/'mods/renew.txt').exists())
        self.assertEqual((self.game/'settings.ini').read_text(),'renewed settings\n')
        restore(self.recipe,self.game)
        self.assertEqual((self.game/'settings.ini').read_bytes(),self.original)
        self.assertFalse((self.game/'mods').exists())

if __name__=='__main__':unittest.main()
