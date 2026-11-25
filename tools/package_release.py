"""Immutable public ZIP: source, local assets and verified update manifest; no user data."""
from pathlib import Path
import argparse,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
ROOT_FILES=['VERSION','README.md','CHANGES.md','ARCHITECTURE.md','LICENSE','requirements.txt','requirements-build.txt','app.manifest','build_exe.bat','run_overlay.bat','通常表示で起動.bat','AION2_Event_Overlay_Ping.pyw','MAP_SOURCES.md']
def public_sources():
    for name in ROOT_FILES:
        if (ROOT/name).is_file():yield ROOT/name
    for folder in ('AION2-Event-Overlay','assets','tools','tests','.github'):
        for file in sorted((ROOT/folder).rglob('*')):
            if not file.is_file() or any(x in file.parts for x in ('__pycache__','data','.git')):continue
            if folder=='AION2-Event-Overlay' and file.suffix not in ('.py','.json','.ico') and file.name not in ('LICENSE','README_UPSTREAM.md'):continue
            if folder=='tests' and file.suffix not in ('.py','.json','.mp3'):continue
            yield file
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--exe',type=Path,default=ROOT/'.build/dist/AION2_Event_Overlay_Ping.exe');parser.add_argument('--output',type=Path,default=ROOT/'release');args=parser.parse_args()
    version=(ROOT/'VERSION').read_text().strip();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    name=f'AION2_Event_Overlay_Ping_{version}.zip';target=output/name
    if target.exists():raise SystemExit('Refusing to overwrite existing versioned ZIP: '+str(target))
    files={p.relative_to(ROOT).as_posix():p for p in public_sources()};files['AION2_Event_Overlay_Ping.exe']=args.exe
    manifest=dict(schema=1,repository='cotodama/AION2_Event_Overlay_Ping',version=version,files=[])
    with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for relative,file in sorted(files.items()):
            data=file.read_bytes();manifest['files'].append(dict(path=relative,size=len(data),sha256=hashlib.sha256(data).hexdigest()));z.writestr(relative,data)
        z.writestr('release_manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    digest=hashlib.sha256(target.read_bytes()).hexdigest();(output/'SHA256SUMS.txt').write_text(digest+'  '+name+'\n',encoding='utf-8')
    print(target);print('SHA256 '+digest)
if __name__=='__main__':main()
