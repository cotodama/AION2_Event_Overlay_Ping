"""Exercise the actual startup path with delayed, local network substitutes."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import traceback
from unittest.mock import patch


def run_check(target):
    report={'passed':False,'frozen':bool(getattr(sys,'frozen',False)),
            'checks':[],'presentations':[]}
    root=app=None
    release=threading.Event()
    try:
        with tempfile.TemporaryDirectory(dir=target.parent,prefix='startup-check-') as directory:
            os.environ['AION2_OVERLAY_DATA_DIR']=directory
            from window_group import system_dpi_awareness,hwnd
            system_dpi_awareness()
            import tkinter as tk
            import webbrowser
            import AION2_Event_Overlay as overlay
            import ping_feature
            errors=[]
            for x,topmost in ((180,True),(-80,False)):
                Path(directory,'window_position.json').write_text(json.dumps({'x':x,'y':80}),encoding='utf-8')
                Path(directory,'ping_settings.json').write_text(json.dumps({
                    'width':533,'height':700,'topmost':topmost,'transparency':12,
                    'auto_size_default_v1':True}),encoding='utf-8')
                release.clear(); entered=threading.Event(); finished=threading.Event()
                workers=[]; records=[]; background=[]; responsive=[]
                def delayed_json():
                    workers.append(threading.current_thread().ident)
                    entered.set()
                    assert release.wait(5),'test worker was not released'
                    finished.set()
                    raise OSError('local simulated response failure')
                def local_scan(targets,generation,q,stop):
                    q.put(('scan_done',))
                def observed(event):
                    if event.widget is root:
                        records.append((str(event.type),root.winfo_x(),root.winfo_y(),
                                        root.winfo_width(),root.winfo_height()))
                with patch.object(ping_feature,'fetch_snapshot',delayed_json), \
                     patch.object(ping_feature,'scan',local_scan), \
                     patch.object(webbrowser,'open',return_value=True) as browser:
                    root=tk.Tk()
                    root.report_callback_exception=lambda *args:errors.append(''.join(traceback.format_exception(*args)))
                    for name in ('<Map>','<Unmap>','<Configure>'): root.bind(name,observed,add='+')
                    app=overlay.App(root)
                    assert not app._background_disabled,'test must exercise normal online startup'
                    assert root.state()=='withdrawn' and not root.winfo_ismapped()
                    assert not app.drag_surface.winfo_ismapped()
                    assert not records,records
                    backdrop=app.drag_surface
                    def backdrop_mapped(event):
                        if event.widget is backdrop:
                            background.append((backdrop.winfo_x(),backdrop.winfo_y(),
                                               backdrop.winfo_width(),backdrop.winfo_height()))
                    backdrop.bind('<Map>',backdrop_mapped,add='+')
                    def probe():
                        responsive.append(bool(entered.is_set() and app.fetch_busy and not finished.is_set()))
                        app.refresh_taskbar_entry()  # compatibility call may not hide/show
                    root.after(300,probe)
                    root.after(1200,root.quit)
                    root.mainloop()
                    assert getattr(root,'_startup_error',None) is None
                    maps=[r for r in records if r[0]=='19']
                    unmaps=[r for r in records if r[0]=='18']
                    assert len(maps)==1 and not unmaps,records
                    from window_placement import work_area
                    left,top,right,bottom=work_area(x,80)
                    expected=(max(left+8,min(x,right-533-8)),80,533,700)
                    assert all(r[1:]==expected for r in maps),maps
                    assert all(r[1:]==expected for r in records if r[0]=='22' and records.index(r)>records.index(maps[0])),records
                    assert background==[expected],background
                    assert bool(root.attributes('-topmost'))==topmost
                    assert responsive==[True] and all(w!=threading.current_thread().ident for w in workers)
                    assert not browser.called,'startup must not launch a browser'
                    assert len(app.tab_buttons)==8 and len(app.event_widgets)==5 and len(app.field_boss_widgets)==7
                    assert app.header_canvas.itemcget(app.clock_item,'text')
                    import ctypes
                    u=ctypes.windll.user32
                    get_owner=u.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p)==8 else u.GetWindowLongW
                    get_owner.argtypes=[ctypes.c_void_p,ctypes.c_int]; get_owner.restype=ctypes.c_ssize_t
                    assert get_owner(hwnd(root),-8)==hwnd(backdrop)
                    canvas=app.field_boss_widgets[0][1]
                    next(w for w in canvas.winfo_children() if isinstance(w,tk.Button) and w.cget('text')=='天族MAP').invoke()
                    assert browser.call_count==1
                    report['presentations'].append({'saved_rect':expected,'hud_maps':len(maps),
                        'hud_unmaps':len(unmaps),'backdrop_maps':len(background),
                        'ready_seconds':round(app._startup_ready_seconds,3),'topmost':topmost})
                    release.set(); assert finished.wait(2)
                    # Consume the response; failure must not hide/rebuild the HUD.
                    root.update(); app.poll_network(); root.update()
                    assert not app.fetch_busy and 'local simulated' in app.fetch_error
                    assert browser.call_count==1
                    assert len([r for r in records if r[0]=='19'])==1
                    assert not [r for r in records if r[0]=='18']
                    app.on_close(); root=None; app=None
            assert not errors,errors
            report['checks'].extend([
                'construction remains hidden; first HUD/backdrop mapping uses saved size and coordinates',
                'one HUD map and zero unmaps over 1.2 seconds; no delayed position jump or taskbar re-show',
                'saved negative coordinates and topmost ON/OFF are retained with native HUD ownership',
                'GUI callback runs while JSON worker is waiting; worker is on a separate thread',
                'no browser call during startup; MAP click still opens the browser once',
                'network failure does not re-map the HUD; 8 tabs and 12 event cards remain'])
            # A broken preparation closes cleanly instead of leaving an invisible process.
            with patch.object(overlay.App,'restore_window_position',side_effect=RuntimeError('injected startup failure')):
                root=tk.Tk(); app=overlay.App(root)
                root.mainloop()
                assert isinstance(root._startup_error,RuntimeError)
                assert not root.tk.call('after','info')
                try:
                    assert not root.winfo_exists()
                except tk.TclError:
                    pass
                root=None; app=None
            report['checks'].append('initialization failure destroys hidden surfaces and is propagated to the entry point')
            report['passed']=True
    except Exception:
        report['error']=traceback.format_exc()
    finally:
        release.set()
        if app is not None:
            try: app.on_close()
            except Exception: pass
        elif root is not None:
            try: root.destroy()
            except Exception: pass
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
