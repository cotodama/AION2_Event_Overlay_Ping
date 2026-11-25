"""Exercise the minimalist Ping UI, popup, sizing, persistence and ownership."""
import ctypes
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback
from types import SimpleNamespace
from unittest.mock import patch

def run_check(target):
    report={'passed':False,'frozen':bool(getattr(sys,'frozen',False)),'checks':[]}
    app=root=None
    try:
        with tempfile.TemporaryDirectory(dir=target.parent,prefix='minimal-ping-') as directory:
            os.environ['AION2_OVERLAY_DATA_DIR']=directory
            from window_group import system_dpi_awareness,hwnd
            system_dpi_awareness()
            import tkinter as tk
            import AION2_Event_Overlay as overlay
            from ping_feature import PingFeatureMixin
            init=PingFeatureMixin.init_ping
            def offline(self,path): init(self,path); self._background_disabled=True
            def descendants(widget):
                for child in widget.winfo_children():
                    yield child; yield from descendants(child)
            errors=[]
            with patch.object(PingFeatureMixin,'init_ping',offline):
                root=tk.Tk(); root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
                app=overlay.App(root); root.update()
                normal=root.geometry(); normal_size=(app.overlay_width,app.manual_height); native=hwnd(root)
                assert app.ping_layer_button.winfo_rootx()+app.ping_layer_button.winfo_width()<app.settings_button.winfo_rootx()
                japan=[s for r,s in app.all_endpoints() if r=='Japan']
                lumiel=next(s for s in japan if s['name']=='Lumiel')
                login=next(s for s in japan if s['name']=='LoginServer')
                selected=[lumiel['id'],login['id']]
                app.ping_cfg['selected']=selected; app.rebuild_summary()
                events=[]
                for name in ('<Map>','<Unmap>'):
                    root.bind(name,lambda e:events.append(str(e.type)) if e.widget is root else None,add='+')
                button=app.ping_layer_button
                button.event_generate('<Enter>',x=5,y=5); button.event_generate('<ButtonPress-1>',x=5,y=5)
                button.event_generate('<ButtonRelease-1>',x=5,y=5); root.update()
                assert app._ping_layer and hwnd(root)==native
                assert {sid for sid,*_ in app.ping_layer_rows}==set(selected)
                assert not [w for w in descendants(app.ping_layer_frame) if isinstance(w,(tk.Button,tk.Checkbutton))]
                for sid,label,row in app.ping_layer_rows:
                    app.results[sid]=(17.3 if sid==lumiel['id'] else 21.7,0)
                    assert len(row.winfo_children())==2
                app.paint_ping(); root.update()
                assert {v.cget('text') for _,v,_ in app.ping_layer_rows}=={'17.3 ms','21.7 ms'}
                assert not events,events
                import ping_feature
                app.active_tab='ping'; app._background_disabled=False
                app.fetch_busy=True; app.next_scan=0; app.scan_busy=False
                with patch.object(ping_feature.threading,'Thread') as worker:
                    app.poll_network()
                    scanned=worker.call_args.kwargs['args'][0]
                    assert {s['id'] for s in scanned}==set(selected)
                app.active_tab='events'; app._background_disabled=True
                app.fetch_busy=False; app.scan_busy=False
                report['checks'].append('top icon is immediately left of settings; real click switches same HWND; only selected Lumiel/LoginServer antenna and ms rows appear')
                assert not app.ping_layer_grip.winfo_ismapped()
                assert float(app.drag_surface.attributes('-alpha'))==0.0
                app.set_ping_layer_grip(True); app.set_ping_layer_clear_background(False); root.update()
                grip=app.ping_layer_grip
                x,y=grip.winfo_rootx()+6,grip.winfo_rooty()+6
                assert app._interactive_widget_at_screen(x,y),('resize corner must consume native clicks',x,y,str(root.winfo_containing(x,y)),grip.winfo_ismapped(),(grip.winfo_x(),grip.winfo_y()),root.geometry(),app._hud_control_rects)
                before=(root.winfo_x(),root.winfo_y(),root.winfo_width(),root.winfo_height())
                grip.event_generate('<ButtonPress-1>',x=6,y=6,rootx=x,rooty=y)
                grip.event_generate('<B1-Motion>',x=126,y=56,rootx=x+120,rooty=y+50)
                grip.event_generate('<ButtonRelease-1>',x=126,y=56,rootx=x+120,rooty=y+50); root.update()
                assert (root.winfo_x(),root.winfo_y())==before[:2]
                assert (root.winfo_width(),root.winfo_height())==(before[2]+120,before[3]+50)
                assert (app.overlay_width,app.manual_height)==normal_size
                assert app.drag_surface.geometry()==root.geometry()
                size=dict(app.ping_cfg['ping_layer_size'])
                report['checks'].append('native resize grip hit area and actual Tk drag resize independently without moving root or changing normal GUI size')
                root.geometry('+-1880+70'); root.update()
                label=app.ping_layer_rows[0][1]
                label.event_generate('<Button-3>',x=5,y=5,rootx=-1870,rooty=80); root.update()
                menu=app._layer_popup; assert menu is not None and menu.winfo_ismapped()
                assert -1920<=menu.winfo_x()<0
                u=ctypes.windll.user32
                get_owner=u.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p)==8 else u.GetWindowLongW
                get_owner.argtypes=[ctypes.c_void_p,ctypes.c_int]; get_owner.restype=ctypes.c_ssize_t
                assert get_owner(hwnd(menu),-8)==hwnd(root)
                scale=next(w for w in descendants(menu) if isinstance(w,tk.Scale))
                scale.set(65); root.update()
                assert app.ping_cfg['transparency']==65 and abs(app.cfg['background_opacity']-.35)<.001
                assert abs(float(app.drag_surface.attributes('-alpha'))-.35)<.001
                names=next(w for w in descendants(menu) if isinstance(w,tk.Checkbutton))
                names.invoke(); root.update()
                assert app.ping_cfg['ping_layer_show_names']
                labels=[row.winfo_children()[2].cget('text') for _,_,row in app.ping_layer_rows]
                assert set(labels)=={'Lumiel','LoginServer'}
                names.invoke(); root.update()
                assert all(len(row.winfo_children())==2 for _,_,row in app.ping_layer_rows)
                offset=(menu.winfo_x()-root.winfo_x(),menu.winfo_y()-root.winfo_y())
                root.geometry('+-1820+100'); root.update(); app.window_group.sync(); app.sync_drag_surface(); root.update()
                assert (menu.winfo_x()-root.winfo_x(),menu.winfo_y()-root.winfo_y())==offset
                assert app.drag_surface.geometry()==root.geometry()
                next(w for w in descendants(menu) if isinstance(w,tk.Button) and w.cget('text')=='通常表示に戻す').invoke(); root.update()
                assert not app._ping_layer and root.geometry()==normal and app._layer_popup is None,(app._ping_layer,root.geometry(),normal,app._normal_layer_geometry,app._layer_popup)
                assert not events,events
                report['checks'].append('right-click opens an owned popup on negative monitor; opacity slider and server-name ON/OFF work; popup follows root; menu restores normal GUI without remapping')
                app.ping_layer_button.invoke(); root.update()
                # Select only the login endpoint; the unselected world must disappear.
                app.ping_cfg['selected']=[login['id']]; app.rebuild_summary(); root.update()
                assert [sid for sid,*_ in app.ping_layer_rows]==[login['id']]
                root.geometry('+130+90'); root.update()
                app.on_close(); app=root=None
                root=tk.Tk(); app=overlay.App(root); root.update()
                assert app._ping_layer and (root.winfo_x(),root.winfo_y())==(130,90)
                assert app.ping_cfg['transparency']==65 and not app.ping_cfg['ping_layer_show_names']
                assert app.ping_cfg['ping_layer_size']==size
                assert (root.winfo_width(),root.winfo_height())==(size['width'],size['height'])
                assert [sid for sid,*_ in app.ping_layer_rows]==[login['id']]
                # 100% background transparency must retain right-click recovery.
                app.set_ping_layer_transparency(100); root.update()
                app.drag_surface.event_generate('<Button-3>',x=5,y=5,rootx=135,rooty=95); root.update()
                assert app._layer_popup is not None
                app.close_ping_layer_menu(); root.update()
                app.set_ping_layer_transparency(0); root.update(); assert float(app.drag_surface.attributes('-alpha'))==1
                app.ping_cfg['selected']=[]; app.rebuild_summary(); root.update()
                assert not app.ping_layer_rows
                assert not [w for w in descendants(app.ping_layer_frame) if isinstance(w,tk.Label)]
                app.set_ping_layer(False); root.update(); assert root.geometry()==normal
                assert not errors,errors
                report['checks'].append('selection removal, size/name/opacity/mode/position persistence, 100% right-click recovery, empty selection with no extra labels, and GUI restoration')
                app.on_close(); app=root=None; report['passed']=True
    except Exception:
        report['error']=traceback.format_exc()
    finally:
        if app is not None:
            try: app.on_close()
            except Exception: pass
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
