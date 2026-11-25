"""Separate updater process: backup, replace, health-check and rollback."""
import ctypes,json,os,shutil,subprocess,sys,time
from pathlib import Path
from update_core import EXE,MANIFEST,UpdateError,checked_path,verify_payload

def write_status(path,**values):
    temp=Path(str(path)+'.tmp');temp.write_text(json.dumps(values,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(temp,path)

def wait_process(pid,timeout=60):
    if os.name!='nt':raise UpdateError('Automatic installation currently requires Windows')
    k=ctypes.windll.kernel32
    k.OpenProcess.argtypes=[ctypes.c_uint,ctypes.c_int,ctypes.c_uint];k.OpenProcess.restype=ctypes.c_void_p
    k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint];k.WaitForSingleObject.restype=ctypes.c_uint
    k.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=k.OpenProcess(0x100000,False,int(pid))
    if not handle:
        if k.GetLastError()==87:return
        raise UpdateError('Cannot wait for the previous program to exit')
    try:
        if k.WaitForSingleObject(handle,int(timeout*1000))!=0:raise UpdateError('Previous program did not exit; installed files were not changed')
    finally:k.CloseHandle(handle)

def snapshot_settings(data,backup):
    data=Path(data);backup.mkdir(parents=True,exist_ok=True);names=[]
    if data.exists():
        for file in data.glob('*.json'):
            if file.is_symlink():raise UpdateError('Settings directory contains a link')
            names.append(file.name);shutil.copy2(file,backup/file.name)
    return names

def restore_settings(data,backup,names):
    data=Path(data);data.mkdir(parents=True,exist_ok=True)
    for file in data.glob('*.json'):
        if file.name not in names and not file.is_symlink():file.unlink()
    for name in names:
        target=data/name
        if target.is_symlink():raise UpdateError('Settings destination changed to a link')
        shutil.copy2(backup/name,target)

def replace_files(payload,target,backup,manifest,replace=os.replace):
    """Only release-managed files are replaced. data/ and unknown files stay put."""
    records=[];backup.mkdir(parents=True,exist_ok=True)
    try:
        for row in manifest['files']+[{'path':MANIFEST}]:
            relative=row['path'];destination=checked_path(target,relative);source=checked_path(payload,relative)
            previous=checked_path(backup,relative);had=destination.exists()
            if had and not destination.is_file():raise UpdateError('A managed file path is a directory: '+relative)
            if had:previous.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(destination,previous)
            destination.parent.mkdir(parents=True,exist_ok=True)
            temp=destination.with_name(destination.name+'.update-tmp')
            if temp.exists():raise UpdateError('Update temporary file already exists')
            shutil.copy2(source,temp)
            try:replace(temp,destination)
            finally:
                if temp.exists():temp.unlink()
            records.append((relative,had))
        return records
    except Exception:
        rollback_files(target,backup,records)
        raise

def rollback_files(target,backup,records):
    for relative,had in reversed(records):
        destination=checked_path(target,relative)
        if had:
            temp=destination.with_name(destination.name+'.rollback-tmp')
            shutil.copy2(checked_path(backup,relative),temp);os.replace(temp,destination)
        elif destination.exists():destination.unlink()

def start_program(plan,health=None):
    target=Path(plan['target']);command=[str(target/EXE)]
    if plan.get('source'):
        command=[plan['python'],str(target/'AION2_Event_Overlay_Ping.pyw')]
    if health:command+=['--update-health',str(health)]
    env=os.environ.copy();env['AION2_OVERLAY_DATA_DIR']=plan['data']
    return subprocess.Popen(command,cwd=target,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

def await_health(process,path,expected,timeout=25):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if process.poll() is not None:return False
        try:
            health=json.loads(path.read_text(encoding='utf-8'))
            if health.get('version')==expected and health.get('pid') and health.get('ready'):return True
        except (OSError,ValueError):pass
        time.sleep(.1)
    return False

def run_plan(path,launcher=start_program,waiter=wait_process,health_wait=await_health):
    path=Path(path).resolve();job=path.parent;status=job/'status.json';records=[];process=None;installed=False;data_names=None;parent_exited=False;lock=None
    try:
        plan=json.loads(path.read_text(encoding='utf-8'));target=Path(plan['target']).resolve()
        if job.parent.name!='.updates' or job.parent.parent!=target or path.name!='plan.json':raise UpdateError('Invalid updater plan location')
        # A second running copy must never replace/rollback concurrently.
        if os.name=='nt':
            import msvcrt
            lock=(job.parent/'install.lock').open('a+b')
            if lock.tell()==0:lock.write(b'0');lock.flush()
            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        payload=job/'payload';expected=plan['version'];manifest=verify_payload(payload,expected)
        data=Path(plan['data']).resolve()
        configured=Path(os.environ.get('AION2_OVERLAY_DATA_DIR',target/'data')).resolve()
        if data!=configured:raise UpdateError('Settings location does not match the running application')
        if not (target/EXE).is_file() and not (target/'AION2_Event_Overlay_Ping.pyw').is_file():raise UpdateError('Not an overlay installation')
        waiter(plan['parent_pid'])
        parent_exited=True
        if plan.get('bootloader_pid'):waiter(plan['bootloader_pid'])
        backup=job/'backup';data_names=snapshot_settings(data,backup/'settings')
        write_status(status,state='installing',version=expected)
        records=replace_files(payload,target,backup/'files',manifest);installed=True
        health=job/'health.json';process=launcher(plan,health)
        if not health_wait(process,health,expected):raise UpdateError('New version did not finish starting')
        write_status(status,state='complete',version=expected,backup=str(backup));return True
    except Exception as exc:
        rollback_error=None
        try:
            if process is not None and process.poll() is None:
                if os.name=='nt':subprocess.run([str(Path(os.environ['SystemRoot'])/'System32/taskkill.exe'),'/PID',str(process.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
                else:process.terminate()
                process.wait(timeout=8)
            if installed:rollback_files(target,backup/'files',records)
            if data_names is not None:restore_settings(data,backup/'settings',data_names)
            # If files were changed, restore the previous running program too.
            if parent_exited:launcher(plan)
        except Exception as failure:rollback_error=str(failure)
        write_status(status,state='failed',error=str(exc),rollback_error=rollback_error,rolled_back=parent_exited and rollback_error is None)
        return False
    finally:
        if lock is not None:lock.close()

if __name__=='__main__':
    sys.exit(0 if run_plan(sys.argv[sys.argv.index('--plan')+1]) else 1)
