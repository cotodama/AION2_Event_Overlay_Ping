"""Regression for resizable settings, named groups, editable emoji and Ping layer."""
import datetime as dt
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
        with tempfile.TemporaryDirectory(dir=target.parent,prefix='feature-check-') as directory:
            os.environ['AION2_OVERLAY_DATA_DIR']=directory
            from window_group import system_dpi_awareness,hwnd
            system_dpi_awareness()
            import tkinter as tk
            import AION2_Event_Overlay as overlay
            from ping_feature import PingFeatureMixin
            from event_model import JST,event_name,notification_text
            from boss_groups import boss_display_items,members,next_boss_occurrence
            original=PingFeatureMixin.init_ping
            def offline(self,path): original(self,path); self._background_disabled=True
            def descendants(w):
                for ch in w.winfo_children():
                    yield ch; yield from descendants(ch)
            errors=[]
            with patch.object(PingFeatureMixin,'init_ping',offline):
                root=tk.Tk(); root.report_callback_exception=lambda *args:errors.append(''.join(traceback.format_exception(*args)))
                app=overlay.App(root); root.update()
                grouped=boss_display_items(app.tracker.catalog['bosses'])
                assert [r['name'] for r in grouped]==['NM ガルトゥア','軍団長ラグタ','執行者アグロ','精霊王アグロⅡ','執行者カイラ','監視者カイラ','守護神将ナフマ']
                assert [len(members(r)) for r in grouped]==[2,2,1,1,1,1,1]
                assert grouped[1]['equipment_il']=='46' and grouped[2]['equipment_il']=='70'
                moment=dt.datetime(2026,10,12,21,29,tzinfo=JST)
                assert next_boss_occurrence(grouped[2],moment)[0].astimezone(JST).strftime('%a %H:%M')=='Mon 21:30'
                nxt=next_boss_occurrence(grouped[2],moment+dt.timedelta(minutes=1))[0].astimezone(JST)
                assert (nxt.weekday(),nxt.hour,nxt.minute)==(3,21,30)
                app.show_tab('bosses'); root.update(); assert len(app.tracker_widgets)==7
                app.show_tab('events'); root.update()
                report['checks'].append('single Gartua and Ragta cards retain both faction IDs/maps; IL46/70 are truthful; multi-weekday countdown works')
                app.settings(); root.update(); settings=app._dialog_windows['settings']; area=settings._event_settings_area
                settings.geometry('390x350'); root.update(); area.canvas.yview_moveto(0); root.update()
                assert area.vbar.winfo_ismapped()
                small_height=area.canvas.winfo_height()
                settings.geometry('850x800'); root.update(); area.canvas.yview_moveto(0); root.update()
                assert area.canvas.winfo_height()>small_height+200
                assert not area.vbar.winfo_ismapped(),area.canvas.yview()
                names=[w for w in descendants(area.body) if isinstance(w,tk.Label) and w.cget('text')=='NM ガルトゥア']
                assert len(names)==1
                assert names[0].winfo_ismapped()
                frame=names[0].master.master
                assert int(frame.grid_info()['column']) in (0,1)
                normal=app.root.geometry()
                check=next(w for w in descendants(settings) if isinstance(w,tk.Checkbutton) and 'シンプルPingレイヤー' in w.cget('text'))
                check.invoke(); root.update()
                assert app._ping_layer and root.winfo_width()==160 and not app.event_section.winfo_ismapped()
                assert app.ping_layer_frame.winfo_ismapped() and app.ping_layer_rows
                app.results[app.ping_layer_rows[0][0]]=(23.4,0); app.paint_ping(); root.update()
                row=app.ping_layer_rows[0][2]; children=row.winfo_children()
                assert isinstance(children[0],tk.Canvas) and children[1].cget('text')=='23.4 ms'
                assert children[1].winfo_x()>=children[0].winfo_x()+children[0].winfo_width()
                # The real drag handler uses screen coordinates; crossing x=0
                # must remain an absolute negative coordinate, never right-relative.
                app.surface_drag_start(SimpleNamespace(widget=children[1],x_root=200,y_root=200))
                oldx,oldy=root.winfo_x(),root.winfo_y()
                app.surface_drag_motion(SimpleNamespace(x_root=200-oldx-120,y_root=245)); root.update()
                app.surface_drag_end(None); root.update(); app.window_group.sync(); app.sync_drag_surface(); root.update()
                assert (root.winfo_x(),root.winfo_y())==(-120,oldy+45)
                assert app.drag_surface.geometry()==root.geometry(),(root.geometry(),app.drag_surface.geometry())
                app.save_window_position()
                assert json.loads(app.ping_path.read_text(encoding='utf-8'))['ping_layer_position']['x']==-120
                import ctypes
                u=ctypes.windll.user32
                get_owner=u.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p)==8 else u.GetWindowLongW
                get_owner.argtypes=[ctypes.c_void_p,ctypes.c_int]; get_owner.restype=ctypes.c_ssize_t
                assert get_owner(hwnd(root),-8)==hwnd(app.drag_surface)
                from ctypes import wintypes
                monitors=[]
                callback_type=ctypes.WINFUNCTYPE(ctypes.c_int,ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(wintypes.RECT),ctypes.c_ssize_t)
                def monitor_callback(handle,dc,rect,data):
                    r=rect.contents; monitors.append((r.left,r.top,r.right,r.bottom)); return 1
                callback=callback_type(monitor_callback)
                u.EnumDisplayMonitors(None,None,callback,0)
                report['monitor_rectangles']=monitors
                for left,top,right,bottom in monitors:
                    targetx,targety=left+40,top+60
                    x0,y0=root.winfo_x(),root.winfo_y()
                    app.surface_drag_start(SimpleNamespace(widget=children[1],x_root=x0+30,y_root=y0+20))
                    for step in range(1,6):
                        x1=round(x0+(targetx-x0)*step/5); y1=round(y0+(targety-y0)*step/5)
                        app.surface_drag_motion(SimpleNamespace(x_root=x1+30,y_root=y1+20))
                        root.update(); app.window_group.display_changed(); root.update()
                        assert (root.winfo_x(),root.winfo_y())==(x1,y1)
                        assert app.drag_surface.geometry()==root.geometry()
                        assert get_owner(hwnd(root),-8)==hwnd(app.drag_surface)
                    app.surface_drag_end(None)
                report['checks'].append(f'compact overlay dragged through {len(monitors)} connected monitor rectangles; absolute position, backdrop and owner stay aligned')
                for button in app.ping_layer_frame.winfo_children()[0].winfo_children():
                    if isinstance(button,tk.Button):
                        x=button.winfo_rootx()+button.winfo_width()//2; y=button.winfo_rooty()+button.winfo_height()//2
                        assert app._interactive_widget_at_screen(x,y)
                check.invoke(); root.update(); assert not app._ping_layer and root.geometry()==normal
                assert app.event_section.winfo_ismapped()
                report['checks'].append('Ping layer checkbox, antenna-adjacent ms, real drag to negative coordinates, owner/backdrop/hit regions, saved position and normal-GUI restore')
                e=next(r for r in app.cfg['events'] if r['name_en']=='Shugo Festa')
                assert e['name_ja'].startswith('🦊')
                expected=notification_text(e,dt.datetime(2026,10,12,8,tzinfo=JST),0)
                assert expected=='🦊 シューゴフェスタ 08:00 JST 開始 / 入場締切 08:03 JST\n次回 09:00 JST\n🔔 開始予定時刻'
                app.edit_event(settings,app.cfg['events'].index(e),lambda:None); root.update()
                editor=next(w for w in descendants(settings) if isinstance(w,tk.Toplevel))
                entries=[w for w in descendants(editor) if isinstance(w,tk.Entry)]
                assert entries[0].get()==e['name_ja']
                typed='✨ テスト名 🦊'; entries[0].delete(0,'end'); entries[0].insert(0,typed)
                next(w for w in descendants(editor) if isinstance(w,tk.Button) and w.cget('text')=='保存').invoke(); root.update()
                saved=overlay.load_config()['events'][app.cfg['events'].index(e)] if e in app.cfg['events'] else next(r for r in overlay.load_config()['events'] if r['id']==e['id'])
                assert saved['name_ja']==typed and event_name(saved,emoji=False)=='テスト名'
                report['checks'].append('name editor contains emoji text, saves typed emoji, OFF hides glyphs without deleting name; default Shugo notification remains identical')
                gartua=names[0].master.master
                next(w for w in descendants(gartua) if isinstance(w,tk.Button) and w.cget('text')=='削除').invoke(); root.update()
                assert not any(r['id'].startswith('gartua-') for r in app.tracker.catalog['bosses'])
                app.init_tracker(directory); app.rebuild_event_widgets(); root.update()
                assert len(boss_display_items(app.tracker.catalog['bosses']))==6
                assert not any(r['id'].startswith('gartua-') for r in app.tracker.catalog['bosses'])
                assert app.tracker.catalog['named_catalog_version']==7
                report['checks'].append('settings shows named groups; delete removes both Gartua rows permanently and reload does not re-add them')
                assert not errors,errors
                app.set_ping_layer(True); root.update()
                root.geometry('+120+80'); root.update()
                app.on_close(); app=root=None
                root=tk.Tk(); app=overlay.App(root); root.update()
                assert app._ping_layer and root.winfo_width()==160
                assert (root.winfo_x(),root.winfo_y())==(120,80)
                assert app.drag_surface.geometry()==root.geometry()
                app.set_ping_layer(False); root.update(); assert root.geometry()==normal
                report['checks'].append('compact mode and separate position survive restart; GUI geometry restores across restart')
                app.on_close(); app=root=None
                report['passed']=True
    except Exception:
        report['error']=traceback.format_exc()
    finally:
        if app is not None:
            try: app.on_close()
            except Exception: pass
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
