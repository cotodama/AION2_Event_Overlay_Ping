"""Tk updater controls; network/disk work stays off the UI thread."""
import json,os,queue,shutil,subprocess,sys,threading,time,uuid
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from update_core import check_release,stage_release,Cancelled,RELEASES_URL

class UpdateFeatureMixin:
    def init_updater(self):
        self.cfg.setdefault('auto_update_enabled',False)
        self._update_queue=queue.Queue();self._update_cancel=threading.Event();self._update_busy=False
        self._update_labels=[];self._update_status='';self._update_auto_vars=[];self._update_after=None;self._update_started=False

    def updater_controls(self,parent):
        self.label(parent,self.tr('アプリの更新','Application updates'),font=self.ui(10,'bold')).pack(anchor='w',padx=10,pady=(10,4))
        value=tk.BooleanVar(parent,value=self.cfg.get('auto_update_enabled',False));self._update_auto_vars.append(value)
        def changed():
            from AION2_Event_Overlay import save_config
            self.cfg['auto_update_enabled']=value.get();save_config(self.cfg)
            for v in self._update_auto_vars:
                try:v.set(value.get())
                except tk.TclError:pass
        tk.Checkbutton(parent,text=self.tr('起動時に自動更新','Automatically update at startup'),variable=value,command=changed,
            bg=parent.cget('bg'),fg='white',selectcolor='#26303a',font=self.ui(10)).pack(anchor='w',padx=8)
        self.button(parent,self.tr('今すぐ更新','Check and install updates'),lambda:self.check_updates(manual=True),padx=12,pady=5).pack(anchor='w',padx=10,pady=4)
        label=self.label(parent,self._update_status or self.tr('設定・チェック・通知履歴を保持して更新します。','Updates keep your settings and task history.'),wraplength=360,justify='left')
        label.pack(fill='x',padx=10,pady=(2,10));self._update_labels.append(label)

    def start_update_checks(self):
        if self._update_started:return
        self._update_started=True
        if '--update-health' in sys.argv:
            from AION2_Event_Overlay import APP_VERSION
            from update_install import write_status
            path=Path(sys.argv[sys.argv.index('--update-health')+1]);write_status(path,version=APP_VERSION,pid=os.getpid(),ready=True)
        if getattr(self,'_background_disabled',False):return
        self._update_after=self.root.after(150,self.poll_updates)
        if self.cfg.get('auto_update_enabled') and '--update-health' not in sys.argv:self.root.after(800,self.check_updates)

    def update_status(self,text):
        self._update_status=text
        self._update_labels=[w for w in self._update_labels if w.winfo_exists()]
        for w in self._update_labels:w.configure(text=text)
        progress=getattr(self,'_update_dialog_state',None)
        if progress and progress['win'].winfo_exists():progress['label'].configure(text=text)

    def check_updates(self,manual=False):
        if self._update_busy:return
        from AION2_Event_Overlay import APP_VERSION
        self._update_busy=True;self._update_cancel.clear()
        self.update_status(self.tr('更新を確認中…','Checking for updates…'))
        def work():
            try:self._update_queue.put(('release',check_release(APP_VERSION),manual))
            except Exception as exc:self._update_queue.put(('error',str(exc),manual))
        threading.Thread(target=work,daemon=True).start()
        if getattr(self,'_background_disabled',False):self.root.after(40,self.poll_updates)

    def open_update_progress(self,version):
        win=self._new_dialog(self.tr('アプリを更新','Update application'));win.configure(bg='#202020')
        label=self.label(win,f'v{version}',wraplength=370,justify='left');label.pack(fill='x',padx=15,pady=12)
        bar=ttk.Progressbar(win,orient='horizontal',maximum=100,length=350);bar.pack(fill='x',padx=15,pady=8)
        self.button(win,self.tr('キャンセル','Cancel'),self._update_cancel.set,padx=14,pady=5).pack(pady=10)
        win.protocol('WM_DELETE_WINDOW',self._update_cancel.set)
        self._update_dialog_state=dict(win=win,label=label,bar=bar)
        self._place_compact_dialog(win,420,180);self.reveal_dialog(win)

    def download_update(self,release):
        from AION2_Event_Overlay import PORTABLE_DIR
        self.open_update_progress(release['version'])
        self.update_status(self.tr('ダウンロード中…','Downloading…'))
        job=Path(PORTABLE_DIR)/'.updates'/uuid.uuid4().hex
        def work():
            try:
                payload=stage_release(release,job,lambda done,total:self._update_queue.put(('progress',done,total)),self._update_cancel)
                self._update_queue.put(('staged',job,release))
            except Exception as exc:self._update_queue.put(('error',str(exc),True))
        threading.Thread(target=work,daemon=True).start()

    def launch_update_helper(self,job,release):
        from AION2_Event_Overlay import PORTABLE_DIR,USER_DATA_DIR
        job=Path(job).resolve();target=Path(PORTABLE_DIR).resolve()
        plan=dict(target=str(target),data=str(Path(USER_DATA_DIR).resolve()),version=release['version'],parent_pid=os.getpid(),source=not getattr(sys,'frozen',False),python=sys.executable)
        if getattr(sys,'frozen',False):plan['bootloader_pid']=os.getppid()
        path=job/'plan.json';path.write_text(json.dumps(plan,indent=2),encoding='utf-8')
        if getattr(sys,'frozen',False):
            helper=job/'updater.exe';shutil.copy2(sys.executable,helper);command=[str(helper),'--apply-update',str(path)]
        else:
            source=Path(__file__).parent
            for name in ('update_install.py','update_core.py'):shutil.copy2(source/name,job/name)
            command=[sys.executable,str(job/'update_install.py'),'--plan',str(path)]
        subprocess.Popen(command,cwd=job,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.update_status(self.tr('検証完了。更新して再起動します…','Verified. Installing and restarting…'))
        self.on_close()

    def poll_updates(self):
        if not self.root.winfo_exists():return
        try:
            while True:
                kind,*args=self._update_queue.get_nowait()
                if kind=='release':
                    release,manual=args
                    if release:self.download_update(release)
                    else:self._update_busy=False;self.update_status(self.tr('最新バージョンです。','You are up to date.'))
                elif kind=='progress':
                    done,total=args
                    if getattr(self,'_update_dialog_state',None):self._update_dialog_state['bar']['value']=done/total*100
                elif kind=='staged':
                    if self._update_cancel.is_set():raise Cancelled('Update cancelled')
                    self.launch_update_helper(*args);return
                elif kind=='error':raise RuntimeError(args[0])
        except queue.Empty:pass
        except Exception as exc:
            self._update_busy=False;self.update_status(self.tr('更新できませんでした: ','Update unavailable: ')+str(exc))
            dialog=getattr(self,'_update_dialog_state',None)
            if dialog and dialog['win'].winfo_exists():self._safe_dialog_close(dialog['win'])
        self._update_after=self.root.after(150,self.poll_updates)

    def close_updater(self):
        self._update_cancel.set()
        if self._update_after:
            try:self.root.after_cancel(self._update_after)
            except tk.TclError:pass
