"""Production-like saved-position recovery and actual GUI control regression."""
import ctypes
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import traceback
from unittest.mock import patch

def run_check(target):
    report={'passed':False,'frozen':bool(getattr(sys,'frozen',False)),'checks':[]}
    app=root=None
    try:
        with tempfile.TemporaryDirectory(dir=target.parent,prefix='repair-') as directory:
            os.environ['AION2_OVERLAY_DATA_DIR']=directory
            Path(directory,'ping_settings.json').write_text(json.dumps({'ping_layer':True,
                'ping_layer_position':{'x':-160,'y':1009},'width':449,'height':801,
                'auto_size_default_v1':True}),encoding='utf-8')
            Path(directory,'dialog_positions.json').write_text(json.dumps({'ping_settings':{'x':883,'y':-1709}}),encoding='utf-8')
            from window_group import system_dpi_awareness,hwnd
            system_dpi_awareness()
            import tkinter as tk
            import AION2_Event_Overlay as overlay
            from ping_feature import PingFeatureMixin
            from window_placement import work_area
            def descendants(w):
                for ch in w.winfo_children():
                    yield ch; yield from descendants(ch)
            def inside(w):
                left,top,right,bottom=work_area(w.winfo_x(),w.winfo_y())
                assert left<=w.winfo_x() and top<=w.winfo_y()
                assert w.winfo_x()+w.winfo_width()<=right and w.winfo_y()+w.winfo_height()<=bottom,(w.geometry(),(left,top,right,bottom))
            def click(w):
                w.event_generate('<Enter>',x=5,y=5);w.event_generate('<ButtonPress-1>',x=5,y=5)
                w.event_generate('<ButtonRelease-1>',x=5,y=5);root.update()
            original=PingFeatureMixin.init_ping
            def offline(self,path):original(self,path);self._background_disabled=True
            errors=[]
            with patch.object(PingFeatureMixin,'init_ping',offline),patch('webbrowser.open',return_value=True) as browser:
                root=tk.Tk();root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
                app=overlay.App(root);root.update()
                assert root.winfo_ismapped() and not app._ping_layer
                inside(root)
                u=ctypes.windll.user32
                get=u.GetWindowLongPtrW;get.argtypes=[ctypes.c_void_p,ctypes.c_int];get.restype=ctypes.c_ssize_t
                assert get(hwnd(root),-20)&0x40000
                assert app.ping_layer_button.cget('image') and not app.ping_layer_button.cget('text')
                click(app.ping_gear)
                dialog=app._dialog_windows['ping'];assert dialog.winfo_ismapped();inside(dialog)
                assert get(hwnd(dialog),-8)==hwnd(root)
                app.ping_gear.invoke();root.update();assert app._dialog_windows['ping'] is dialog
                assert len([w for w in descendants(root) if isinstance(w,tk.Toplevel) and w.title()=='Ping表示・オーバーレイ設定'])==1
                app._ping_selection_state['save'].invoke();root.update();assert not dialog.winfo_exists()
                report['checks'].append('real gear click recovers saved y=-1709, shows owned dialog inside current work area; repeated click reuses it; Save works')
                root.geometry('449x801+-1800+60');root.update()
                click(app.settings_button);settings=app._dialog_windows['settings'];assert settings.winfo_ismapped();inside(settings)
                app._safe_dialog_close(settings);root.update()
                click(app.ping_layer_button)
                assert app._ping_layer and not app.ping_layer_grip.winfo_ismapped()
                assert float(app.drag_surface.attributes('-alpha'))==0
                # Blank pixels must not target either overlay HWND on Windows.
                from ctypes import wintypes
                u.WindowFromPoint.argtypes=[wintypes.POINT];u.WindowFromPoint.restype=ctypes.c_void_p
                point=wintypes.POINT(root.winfo_x()+root.winfo_width()-25,root.winfo_y()+root.winfo_height()-3)
                blank=u.WindowFromPoint(point)
                assert blank not in (hwnd(root),hwnd(app.drag_surface)),blank
                label=app.ping_layer_rows[0][1]
                label.event_generate('<Button-3>',x=4,y=4,rootx=label.winfo_rootx()+4,rooty=label.winfo_rooty()+4);root.update()
                menu=app._layer_popup;assert menu.winfo_ismapped();inside(menu)
                cb=next(w for w in descendants(menu) if isinstance(w,tk.Checkbutton) and w.cget('text')=='サーバー名を表示')
                cb.invoke();root.update();assert app.ping_cfg['ping_layer_show_names']
                grip=next(w for w in descendants(menu) if isinstance(w,tk.Checkbutton) and w.cget('text')=='サイズ変更マークを表示')
                grip.invoke();root.update();assert app.ping_layer_grip.winfo_ismapped()
                grip.invoke();root.update();assert not app.ping_layer_grip.winfo_ismapped()
                settings_button=next(w for w in descendants(menu) if isinstance(w,tk.Button) and w.cget('text')=='表示するサーバーを選択')
                settings_button.invoke();root.update();dialog=app._dialog_windows['ping'];assert dialog.winfo_ismapped();inside(dialog)
                app._ping_selection_state['save'].invoke();root.update()
                label=app.ping_layer_rows[0][1]
                app.open_ping_layer_menu(type('Click',(),dict(widget=label,x_root=root.winfo_x()+10,y_root=root.winfo_y()+10))());root.update()
                menu=app._layer_popup
                next(w for w in descendants(menu) if isinstance(w,tk.Button) and w.cget('text')=='通常表示に戻す').invoke();root.update()
                assert not app._ping_layer and app.ping_layer_button.winfo_ismapped()
                report['checks'].append('antenna pictogram click switches same HWND; no default white grip; native blank-pixel hit test passes through; context names/grip/settings/normal actions work')
                for key,button in app.tab_buttons.items():
                    click(button);assert app.active_tab==key
                from server_data import validate_snapshot
                rows=[dict(name=name,serverId=n,region='AS',faction=faction,load=.4,isRunning=True,
                    inMaintenance=False,creationBlocked=False,spark=[]) for n,name,faction in
                    [(2501,'Israphel','Asmodian'),(2502,'Siel','Elyos')]]
                app.db_snapshot=validate_snapshot({'generatedAt':'2026-10-13T00:00:00Z','regions':[{'code':'AS','servers':rows}]})
                app.fetched_at=time.monotonic();app.show_tab('status');root.update()
                app.table_var.set(True);app.render_db();root.update()
                for field in ('players','capacity','queue','name','load'):app.sort_status(field);root.update()
                app.show_tab('balance');root.update()
                report['checks'].append('current load-only public JSON renders cards, table, every sort and balance with unknown population; no fabricated counts')
                app.show_tab('events');root.update()
                assert len(app.field_boss_widgets)==7
                for item,canvas,*_ in app.field_boss_widgets:
                    for button in canvas.winfo_children():
                        if isinstance(button,tk.Button) and 'MAP' in button.cget('text'):button.invoke()
                assert browser.call_count==14,browser.call_count
                before=app.cfg['events'][1].copy()
                report['checks'].append('all eight tab clicks work; fourteen boss faction MAP buttons call browser exactly once each; no browser on startup')
                assert not errors,errors
                app.on_close();root=app=None
                # Saved compact mode is respected after the one-time recovery.
                saved=json.loads(Path(directory,'ping_settings.json').read_text(encoding='utf-8'))
                saved.update(ping_layer=True,ping_layer_position={'x':-160,'y':1009})
                Path(directory,'ping_settings.json').write_text(json.dumps(saved),encoding='utf-8')
                root=tk.Tk();root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
                app=overlay.App(root);root.update();assert app._ping_layer;inside(root)
                app.open_ping_settings();root.update();inside(app._dialog_windows['ping'])
                app.on_close();root=app=None
                assert not errors,errors
                report['checks'].append('restart retains names/mode; bottom-edge saved compact position clamps above taskbar; negative-monitor dialogs remain visible')
                report['passed']=True
    except Exception:report['error']=traceback.format_exc()
    finally:
        if app is not None:
            try:app.on_close()
            except Exception:pass
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

