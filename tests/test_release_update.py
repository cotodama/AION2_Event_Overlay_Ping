import hashlib,io,json,os,sys,tempfile,threading,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'AION2-Event-Overlay'))
import update_core as u
import update_install as install

def package(root):
    root.mkdir(parents=True,exist_ok=True);files={u.EXE:b'new executable','VERSION':b'1.4.0','module.py':b'new source'}
    rows=[]
    for n,data in files.items():(root/n).write_bytes(data);rows.append(dict(path=n,size=len(data),sha256=hashlib.sha256(data).hexdigest()))
    manifest=dict(schema=1,version='1.4.0',repository=u.REPO,files=rows)
    (root/u.MANIFEST).write_text(json.dumps(manifest));return manifest

class UpdateTests(unittest.TestCase):
    def test_numeric_version_and_unsupported_url(self):
        self.assertGreater(u.version('v1.4.0'),u.version('1.3.10-gartua-cycle'))
        for url in ('http://github.com/x','https://example.com/x','https://github.com@evil.com/x','https://github.com:8443/x'):
            with self.assertRaises(u.UpdateError):u.secure_url(url)

    def test_paths_reject_escape_device_data_and_windows_aliases(self):
        for path in ('../app.exe','/app.exe','C:/app.exe','foo\\bar','data/settings.json','.updates/a','CON.txt','a/../b','a//b','a./b','a /b'):
            with self.subTest(path=path),self.assertRaises(u.UpdateError):u.relative_path(path)

    def test_release_checksum_and_repository_binding(self):
        name='AION2_Event_Overlay_Ping_1.4.0.zip';url=f'https://github.com/{u.REPO}/releases/download/v1.4.0/{name}'
        release=dict(tag_name='v1.4.0',assets=[dict(name=name,browser_download_url=url,size=100,digest='sha256:'+'a'*64)])
        opener=lambda url:io.BytesIO(json.dumps(release).encode())
        self.assertEqual(u.check_release('1.3.10',opener)['sha256'],'a'*64)
        self.assertIsNone(u.check_release('1.4.0',opener))
        release['assets'][0]['browser_download_url']=url.replace('cotodama/','attacker/')
        with self.assertRaises(u.UpdateError):u.check_release('1.3.10',opener)

    def test_corrupt_and_cancelled_download_never_extract(self):
        with tempfile.TemporaryDirectory() as d:
            job=Path(d)/'job';release=dict(url='unused',version='1.4.0',size=3,sha256='0'*64)
            with self.assertRaises(u.UpdateError):u.stage_release(release,job,opener=lambda _:io.BytesIO(b'zip'))
            self.assertFalse((job/'payload').exists())
            event=threading.Event();event.set()
            with self.assertRaises(u.Cancelled):u.stage_release(release,Path(d)/'cancel',cancel=event,opener=lambda _:io.BytesIO(b'zip'))

    def test_valid_stage_and_file_hash_rejects_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);package(root/'source');archive=io.BytesIO()
            with zipfile.ZipFile(archive,'w') as z:
                for p in (root/'source').iterdir():z.writestr(p.name,p.read_bytes())
            data=archive.getvalue();release=dict(url='unused',version='1.4.0',size=len(data),sha256=hashlib.sha256(data).hexdigest())
            payload=u.stage_release(release,root/'job',opener=lambda _:io.BytesIO(data));self.assertTrue((payload/u.EXE).is_file())
            (payload/'module.py').write_bytes(b'tampered')
            with self.assertRaises(u.UpdateError):u.verify_payload(payload,'1.4.0')

    def test_traversal_archive_with_correct_checksum_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            archive=io.BytesIO()
            with zipfile.ZipFile(archive,'w') as z:z.writestr('../escaped.txt','bad')
            data=archive.getvalue();release=dict(url='unused',version='1.4.0',size=len(data),sha256=hashlib.sha256(data).hexdigest())
            with self.assertRaises(u.UpdateError):u.stage_release(release,Path(d)/'job',opener=lambda _:io.BytesIO(data))
            self.assertFalse((Path(d)/'escaped.txt').exists())

    def test_partial_replace_rolls_back_and_keeps_personal_files(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);payload=root/'payload';manifest=package(payload);target=root/'app';target.mkdir();(target/u.EXE).write_bytes(b'old')
            (target/'data').mkdir();(target/'data/settings.json').write_text('private');(target/'custom.txt').write_text('keep')
            count=0
            def fail_second(a,b):
                nonlocal count
                count+=1
                if count==2:raise OSError('simulated disk failure')
                os.replace(a,b)
            with self.assertRaises(OSError):install.replace_files(payload,target,root/'backup',manifest,fail_second)
            self.assertEqual((target/u.EXE).read_bytes(),b'old');self.assertEqual((target/'custom.txt').read_text(),'keep');self.assertEqual((target/'data/settings.json').read_text(),'private')

    def test_health_failure_restores_old_program_and_settings(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'app';target.mkdir();(target/u.EXE).write_bytes(b'old');data=target/'data';data.mkdir();(data/'settings.json').write_text('old settings')
            job=target/'.updates/test';package(job/'payload');plan=dict(target=str(target),data=str(data),version='1.4.0',parent_pid=123)
            (job/'plan.json').write_text(json.dumps(plan));launches=[]
            def launch(plan,health=None):
                launches.append(health)
                if health:(data/'settings.json').write_text('changed');(data/'new.json').write_text('new')
                return type('Process',(),{'poll':lambda s:0})()
            with patch.dict(os.environ,{'AION2_OVERLAY_DATA_DIR':str(data)}):
                self.assertFalse(install.run_plan(job/'plan.json',launcher=launch,waiter=lambda pid:None,health_wait=lambda *a:False))
            self.assertEqual((target/u.EXE).read_bytes(),b'old');self.assertEqual((data/'settings.json').read_text(),'old settings');self.assertFalse((data/'new.json').exists());self.assertEqual(len(launches),2)
            self.assertTrue(json.loads((job/'status.json').read_text())['rolled_back'])

if __name__=='__main__':unittest.main()
