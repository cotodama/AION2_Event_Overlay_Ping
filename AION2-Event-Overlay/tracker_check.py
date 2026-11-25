"""Offline source/frozen integration regression for the new HUD and ownership."""
import ctypes
import datetime as dt
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import traceback

def run_check(target):
    report={'passed':False,'frozen':bool(getattr(sys,'frozen',False)),'checks':[],
            'physical_multi_monitor':'未検証','virtual_desktop_shell_move':'未検証','physical_dpi_change':'未検証'}
    root=None; app=None
    try:
        with tempfile.TemporaryDirectory(dir=target.parent,prefix='tracker-check-') as directory:
            os.environ['AION2_OVERLAY_DATA_DIR']=directory
            from window_group import system_dpi_awareness,hwnd
            system_dpi_awareness()
            import tkinter as tk
            import AION2_Event_Overlay as overlay
            from ping_feature import PingFeatureMixin
            from tracker_model import UTC
            original=PingFeatureMixin.init_ping
            def offline(self,path): original(self,path); self._background_disabled=True
            PingFeatureMixin.init_ping=offline
            root=tk.Tk(); app=overlay.App(root); root.update()
            ready=tk.BooleanVar(value=False); root.after(500,lambda:ready.set(True)); root.wait_variable(ready)
            errors=[]; root.report_callback_exception=lambda *args:errors.append(str(args))
            assert len(app.tab_buttons)==8
            for key,count in [('il',7),('daily',7),('weekly',6),('bosses',7)]:
                app.show_tab(key); root.update()
                assert app.extra_section.winfo_ismapped()
                assert len(app.tracker_widgets)==count
                assert app.summary_area.canvas.winfo_ismapped()
                app.list_area.canvas.yview_moveto(1); root.update()
                assert app.list_area.canvas.yview()[0]>0
                app.list_area.canvas.yview_moveto(0)
            report['checks'].append('eight tabs, unchanged Ping header, four new vertical scroll panels')
            item=app.tracker.catalog['daily'][0]; app.set_tracker_check(item['id'],True)
            app.tracker.state['bells'][item['id']]=True; app.set_tracker_lead(item['id'],'10')
            app.save_tracker()
            data=json.loads(app.state_path.read_text(encoding='utf-8'))
            assert data['checks'][item['id']] and data['bells'][item['id']] and data['leads'][item['id']]==10
            app.init_tracker(directory); assert app.tracker.done(item['id']) and app.tracker.bell(item['id'])
            report['checks'].append('checks, individual bells, lead times persist and reload without overwriting legacy settings')
            app.show_tab('daily'); root.update(); app.edit_tracker_catalog(); root.update()
            win=app._dialog_windows['tracker']
            assert win.winfo_ismapped(); app.window_group.sync(); root.update()
            if os.name=='nt':
                u=ctypes.windll.user32; u.GetWindow.argtypes=[ctypes.c_void_p,ctypes.c_uint]; u.GetWindow.restype=ctypes.c_void_p
                assert int(u.GetWindow(hwnd(root),4) or 0)==hwnd(app.drag_surface)
                assert int(u.GetWindow(hwnd(win),4) or 0)==hwnd(root)
            offset=(win.winfo_x()-root.winfo_x(),win.winfo_y()-root.winfo_y())
            for x,y in [(-1920,80),(80,-1080),(-1920,-1080),(1920,100),(80,80)]:
                root.geometry(f'+{x}+{y}'); root.update(); app.window_group.sync(); app.sync_drag_surface(); root.update()
                assert (root.winfo_x(),root.winfo_y())==(x,y)
                assert (app.drag_surface.winfo_x(),app.drag_surface.winfo_y())==(x,y)
                assert (win.winfo_x()-x,win.winfo_y()-y)==offset
            report['checks'].append('native owner chain and dialog/backdrop follow positive and negative desktop coordinates')
            app._safe_dialog_close(win)
            for scale in (1.0,1.25,1.5,2.0):
                root.tk.call('tk','scaling',scale); app.show_tab('daily'); root.update()
                button=app.tab_buttons['bosses']
                # Native Configure/Map events can arrive after update() returns.
                # Wait for the visible tab layout before checking its hit region.
                until=time.monotonic()+1.5
                while time.monotonic()<until:
                    x=button.winfo_rootx()+button.winfo_width()//2
                    y=button.winfo_rooty()+button.winfo_height()//2
                    if button.winfo_ismapped() and root.winfo_y()<=y<root.winfo_y()+root.winfo_height():break
                    ready=tk.BooleanVar(root,value=False);root.after(40,lambda:ready.set(True));root.wait_variable(ready);root.update()
                x,y=button.winfo_rootx()+button.winfo_width()//2,button.winfo_rooty()+button.winfo_height()//2
                assert app._interactive_widget_at_screen(x,y),(scale,x,y,root.geometry(),str(root.winfo_containing(x,y)),button.winfo_ismapped(),app.drag_surface.geometry())
                button.event_generate('<Enter>',x=5,y=5)
                button.event_generate('<ButtonPress-1>',x=5,y=5); root.update()
                button.event_generate('<ButtonRelease-1>',x=5,y=5); root.update()
                assert app.active_tab=='bosses'
                app.window_group.display_changed(); root.update()
            report['checks'].append('Tk scaling 100/125/150/200%, actual tab click routing, display-change reconciliation')
            app.minimize_window(); root.update(); assert not app.drag_surface.winfo_ismapped()
            root.deiconify(); root.update(); app.sync_drag_surface(); app.window_group.sync(); root.update()
            assert app.drag_surface.winfo_ismapped()
            report['checks'].append('minimize/restore reunites backdrop and ownership after Tk wrapper recreation')
            assert not errors,errors
            app.on_close(); root=None; report['passed']=True
    except Exception:
        report['error']=traceback.format_exc()
        if app:
            try: app.restore_selective_hit_test(); app.stop_workers.set()
            except Exception: pass
        if root:
            try: root.destroy()
            except Exception: pass
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
