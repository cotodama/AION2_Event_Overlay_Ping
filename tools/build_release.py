"""Build the windowed executable using VERSION as the only version input."""
from pathlib import Path
import os,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
def main():
    os.chdir(ROOT);version=(ROOT/'VERSION').read_text().strip();parts=tuple(map(int,version.split('.')))+(0,)
    build=ROOT/'.build';build.mkdir(exist_ok=True)
    info="VSVersionInfo(ffi=FixedFileInfo(filevers=%r,prodvers=%r,mask=0x3f,flags=0,OS=0x40004,fileType=1,subtype=0,date=(0,0)),kids=[StringFileInfo([StringTable('040904B0',[StringStruct('FileDescription','AION2 Event Overlay Ping'),StringStruct('FileVersion',%r),StringStruct('ProductVersion',%r),StringStruct('ProductName','AION2 Event Overlay Ping'),StringStruct('OriginalFilename','AION2_Event_Overlay_Ping.exe')])]),VarFileInfo([VarStruct('Translation',[1033,1200])])])"%(parts,parts,version,version)
    (build/'version_info.txt').write_text(info,encoding='utf-8')
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile','--windowed','--noupx','--hidden-import','_cffi_backend','--version-file',str(build/'version_info.txt'),'--manifest','app.manifest','--name','AION2_Event_Overlay_Ping','--paths','AION2-Event-Overlay','--icon','AION2-Event-Overlay/AION2_Event_Overlay.ico','--distpath',str(build/'dist'),'--workpath',str(build/'temp'),'--specpath',str(build)]
    for source,dest in [('VERSION','.'),('assets','assets'),('tests/fixtures/audio-test.mp3','audio-test'),('AION2-Event-Overlay/AION2_Event_Overlay.ico','.'),('AION2-Event-Overlay/aion2_overlay.json','.')]:command+=['--add-data',str(ROOT/source)+';'+dest]
    # PyInstaller resolves these paths relative to --specpath, not always cwd.
    for option in ('--manifest','--paths','--icon'):
        index=command.index(option)+1;command[index]=str(ROOT/command[index])
    command.append(str(ROOT/'AION2_Event_Overlay_Ping.pyw'));subprocess.run(command,check=True)
    print(build/'dist/AION2_Event_Overlay_Ping.exe')
if __name__=='__main__':main()
