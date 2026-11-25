"""Public GitHub releases and verified staging. Never modifies installed files."""
import hashlib,json,os,re,stat,threading,urllib.request,urllib.parse,zipfile
from pathlib import Path,PurePosixPath

REPO='cotodama/AION2_Event_Overlay_Ping'
RELEASES_URL=f'https://github.com/{REPO}/releases'
API_URL=f'https://api.github.com/repos/{REPO}/releases/latest'
EXE='AION2_Event_Overlay_Ping.exe'
MANIFEST='release_manifest.json'
MAX_ZIP=250*1024*1024
MAX_EXPANDED=600*1024*1024
ALLOWED_HOSTS={'api.github.com','github.com','release-assets.githubusercontent.com','objects.githubusercontent.com','github-releases.githubusercontent.com'}

class UpdateError(Exception):pass
class Cancelled(UpdateError):pass

def version(value):
    match=re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:-[A-Za-z0-9.-]+)?',str(value))
    if not match:raise UpdateError('Invalid release version')
    return tuple(map(int,match.groups()))

def secure_url(url):
    u=urllib.parse.urlsplit(url)
    if u.scheme!='https' or u.hostname not in ALLOWED_HOSTS or u.username or u.password or u.port not in (None,443):
        raise UpdateError('Unexpected download destination')
    return url

class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        secure_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def open_url(url):
    secure_url(url)
    request=urllib.request.Request(url,headers={'User-Agent':'AION2-Event-Overlay-Ping-Updater','Accept':'application/vnd.github+json' if url==API_URL else 'application/octet-stream'})
    return urllib.request.build_opener(Redirects()).open(request,timeout=20)

def small_response(url,limit=2*1024*1024,opener=open_url):
    with opener(url) as response:
        data=response.read(limit+1)
        if len(data)>limit:raise UpdateError('Response too large')
        return data

def asset_url(asset,tag,name):
    url=asset.get('browser_download_url','')
    expected=f'https://github.com/{REPO}/releases/download/{tag}/{name}'
    if url!=expected:raise UpdateError('Release asset belongs to an unexpected repository/path')
    return secure_url(url)

def check_release(current,opener=open_url):
    release=json.loads(small_response(API_URL,opener=opener))
    tag=release.get('tag_name','');target=version(tag)
    if release.get('draft') or release.get('prerelease') or target<=version(current):return None
    plain='.'.join(map(str,target));name=f'AION2_Event_Overlay_Ping_{plain}.zip'
    assets=release.get('assets',[])
    matches=[a for a in assets if a.get('name')==name]
    if len(matches)!=1:raise UpdateError('This release has no supported update ZIP')
    asset=matches[0];size=int(asset.get('size',0))
    if not 0<size<=MAX_ZIP:raise UpdateError('Invalid release ZIP size')
    digest=asset.get('digest') or ''
    if digest and not re.fullmatch(r'sha256:[0-9a-fA-F]{64}',digest):raise UpdateError('Unsupported asset checksum')
    sums=[a for a in assets if a.get('name')=='SHA256SUMS.txt']
    checksum=None
    if len(sums)==1:
        text=small_response(asset_url(sums[0],tag,'SHA256SUMS.txt'),32768,opener).decode('utf-8')
        found=[m.group(1).lower() for line in text.splitlines() if (m:=re.fullmatch(r'([0-9a-fA-F]{64})\s+\*?'+re.escape(name),line.strip()))]
        if len(found)!=1:raise UpdateError('Missing ZIP checksum')
        checksum=found[0]
    if digest:
        if checksum and checksum!=digest[7:].lower():raise UpdateError('Conflicting release checksums')
        checksum=digest[7:].lower()
    if not checksum:raise UpdateError('Release checksum is required')
    return dict(version=plain,name=name,url=asset_url(asset,tag,name),size=size,sha256=checksum)

def relative_path(name):
    if not isinstance(name,str) or not name or any(ord(c)<32 for c in name) or '\\' in name or ':' in name or name.startswith('/'):
        raise UpdateError('Invalid archive path')
    path=PurePosixPath(name)
    if not path.parts or any(p in ('','..','.') for p in name.split('/')) or any(p.endswith(('.', ' ')) or re.match(r'(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)',p) for p in path.parts):
        raise UpdateError('Unsafe archive path')
    if path.parts[0].lower() in ('data','.git','.updates','.venv','.build-env'):
        raise UpdateError('An update cannot contain private data or updater state')
    return path.as_posix()

def checked_path(root,relative):
    relative=relative_path(relative);root=Path(root).resolve();target=root.joinpath(*PurePosixPath(relative).parts)
    for p in (target,*target.parents):
        if p==root:break
        if p.exists():
            attributes=getattr(p.stat(follow_symlinks=False),'st_file_attributes',0)
            if p.is_symlink() or attributes&0x400:raise UpdateError('Update destination contains a link/junction')
    if root not in target.resolve().parents:raise UpdateError('Destination outside installation')
    return target

def verify_payload(folder,expected_version):
    folder=Path(folder);manifest=json.loads((folder/MANIFEST).read_text(encoding='utf-8'))
    if manifest.get('schema')!=1 or manifest.get('version')!=expected_version or manifest.get('repository')!=REPO:
        raise UpdateError('Invalid update manifest')
    files=manifest.get('files');seen=set()
    if not isinstance(files,list) or not 1<=len(files)<=2000:raise UpdateError('Invalid update file list')
    for row in files:
        name=relative_path(row['path']);key=name.casefold()
        if key in seen or name==MANIFEST:raise UpdateError('Duplicate update path')
        seen.add(key);file=checked_path(folder,name)
        if not file.is_file() or file.stat().st_size!=int(row['size']) or hashlib.sha256(file.read_bytes()).hexdigest()!=row['sha256']:
            raise UpdateError('Update file verification failed: '+name)
    actual={p.relative_to(folder).as_posix().casefold() for p in folder.rglob('*') if p.is_file() and p!=folder/MANIFEST}
    if actual!=seen or EXE.casefold() not in seen:raise UpdateError('Incomplete update package')
    if (folder/'VERSION').read_text(encoding='utf-8').strip()!=expected_version:raise UpdateError('Version file does not match release')
    return manifest

def stage_release(release,job,progress=lambda *_:None,cancel=None,opener=open_url):
    cancel=cancel or threading.Event();job=Path(job);job.mkdir(parents=True,exist_ok=True)
    archive=job/'download.zip';digest=hashlib.sha256();total=0
    try:
        with opener(release['url']) as response,archive.open('wb') as output:
            while True:
                if cancel.is_set():raise Cancelled('Update cancelled')
                chunk=response.read(65536)
                if not chunk:break
                total+=len(chunk)
                if total>release['size'] or total>MAX_ZIP:raise UpdateError('Download exceeds expected size')
                digest.update(chunk);output.write(chunk);progress(total,release['size'])
        if total!=release['size'] or digest.hexdigest()!=release['sha256']:raise UpdateError('ZIP checksum/size verification failed')
        payload=job/'payload';payload.mkdir()
        with zipfile.ZipFile(archive) as z:
            entries=z.infolist()
            if len(entries)>2000 or sum(i.file_size for i in entries)>MAX_EXPANDED:raise UpdateError('Update archive too large')
            seen=set()
            for item in entries:
                if item.is_dir():continue
                if cancel.is_set():raise Cancelled('Update cancelled')
                name=relative_path(item.filename)
                if name.casefold() in seen or stat.S_ISLNK(item.external_attr>>16) or item.flag_bits&1:
                    raise UpdateError('Duplicate, linked, or encrypted ZIP entry')
                seen.add(name.casefold());target=checked_path(payload,name);target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(item) as source,target.open('wb') as output:
                    import shutil
                    shutil.copyfileobj(source,output,65536)
        verify_payload(payload,release['version']);return payload
    except Exception:
        # Keep diagnostics/staging isolated; installed program and data are untouched.
        raise
