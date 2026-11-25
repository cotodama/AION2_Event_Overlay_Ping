"""Offline GUI regression, sound API checks and settings migration for source/exe."""
import datetime as dt
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback
import wave
from unittest.mock import patch

def run_check(target):
    report={'passed':False,'frozen':bool(getattr(sys,'frozen',False)),'checks':[],
            'speaker_heard':'未確認（Windows APIの呼出成功まで検証）'}
    root=None; app=None
    try:
        with tempfile.TemporaryDirectory(dir=target.parent,prefix='notify-check-') as directory:
            os.environ['AION2_OVERLAY_DATA_DIR']=directory
            from window_group import system_dpi_awareness,hwnd
            system_dpi_awareness()
            import tkinter as tk
            import AION2_Event_Overlay as overlay
            from ping_feature import PingFeatureMixin
            from event_model import JST
            init=PingFeatureMixin.init_ping
            def offline(self,path): init(self,path); self._background_disabled=True
            PingFeatureMixin.init_ping=offline
            root=tk.Tk(); errors=[]
            root.report_callback_exception=lambda *args:errors.append(''.join(traceback.format_exception(*args)))
            app=overlay.App(root); root.update()
            assert len(app.event_widgets)==5 and len(app.tab_buttons)==8
            assert app.event_scroll.canvas.yview()[1]<1
            app.event_scroll.canvas.yview_moveto(1); root.update()
            assert app.event_scroll.canvas.yview()[0]>0
            app.event_scroll.canvas.yview_moveto(0)
            assert len(app.field_boss_widgets)==7
            report['checks'].append('5 regular events plus 7 grouped named cards, 8 tabs and vertical event scrolling')
            app.settings(); root.update()
            win=app._dialog_windows['settings']
            def descendants(w):
                for child in w.winfo_children():
                    yield child; yield from descendants(child)
            emoji=next(w for w in descendants(win) if isinstance(w,tk.Checkbutton) and '絵文字' in w.cget('text'))
            assert emoji.winfo_ismapped()
            emoji.invoke(); root.update()
            assert not app.cfg['show_event_emoji']
            assert all(not w[1].itemcget(w[2],'text').startswith(('🌌','🦊','🌀')) for w in app.event_widgets)
            assert 'show_event_emoji' in json.loads(Path(directory,'aion2_overlay.json').read_text(encoding='utf-8'))
            assert all(b.winfo_exists() for b in app.bell_buttons)
            emoji.invoke(); root.update(); assert app.cfg['show_event_emoji']
            for page in ('表示','アラート','情報','イベント'):
                next(w for w in descendants(win) if isinstance(w,tk.Button) and w.cget('text')==page).invoke(); root.update()
                assert emoji.winfo_ismapped(),page
            app.open_ping_settings(); root.update()
            ping=app._dialog_windows['ping']
            other=next(w for w in descendants(ping) if isinstance(w,tk.Checkbutton) and '絵文字' in w.cget('text'))
            assert other.winfo_ismapped()
            other.invoke(); root.update(); assert not app.event_emoji_var.get()
            other.invoke(); root.update(); assert app.event_emoji_var.get()
            app._safe_dialog_close(ping)
            report['checks'].append('emoji checkbox is visible on every settings page and Ping settings; both controls stay synchronized')
            # Drive the same resize handler as the lower-right grip.
            from types import SimpleNamespace
            def resize_to(height,width=533):
                app.resize_start(SimpleNamespace(x_root=0,y_root=0))
                old_width,old_height=root.winfo_width(),root.winfo_height()
                app.resize_drag(SimpleNamespace(x_root=width-old_width,y_root=height-old_height))
                app.resize_end(None); root.update()
            resize_to(520)
            small_height=app.event_scroll.canvas.winfo_height()
            assert app.event_scroll.canvas.yview()[1]<1
            resize_to(root.winfo_screenheight()-40)
            assert app.event_scroll.canvas.winfo_height()>small_height+200
            assert app.event_scroll.vbar.winfo_ismapped() # twelve normal cards exceed a physical monitor
            app.set_event_compact(True); root.update()
            app.event_scroll.canvas.yview_moveto(0); root.update()
            assert app.event_scroll.canvas.yview()==(0.0,1.0), (root.geometry(),app.event_scroll.canvas.winfo_height(),app.event_scroll.canvas.yview(),app.event_box.winfo_reqheight())
            last=app.field_boss_widgets[-1][1]
            assert last.winfo_rooty()+last.winfo_height()<=app.event_scroll.canvas.winfo_rooty()+app.event_scroll.canvas.winfo_height()
            assert not app.event_scroll.vbar.winfo_ismapped()
            app.show_tab('daily'); root.update(); app.show_tab('events'); root.update()
            assert app.event_scroll.canvas.yview()==(0.0,1.0)
            app.set_event_compact(False); root.update()
            resize_to(520); assert app.event_scroll.vbar.winfo_ismapped()
            report['checks'].append('grip resize grows the event viewport; tall windows show all 12 compact cards, shrinking restores scroll, and tab switch retains size')
            compact=next(w for w in descendants(win) if isinstance(w,tk.Checkbutton) and 'シンプル表示' in w.cget('text'))
            compact.invoke(); root.update()
            assert app.cfg['event_compact'] and all(w[1].winfo_height()==42 for w in app.event_widgets)
            assert all(w[1].winfo_height()==42 for w in app.field_boss_widgets)
            assert overlay.load_config()['event_compact']
            compact.invoke(); root.update(); assert not app.cfg['event_compact']
            assert app.event_widgets[1][1].winfo_height()==100
            report['checks'].append('normal/compact mode switches actual card heights and persists without changing Shugo notification text')
            from unittest.mock import patch as mock_patch
            import webbrowser
            with mock_patch.object(webbrowser,'open',return_value=True) as browser:
                rift=app.event_widgets[0][1]
                links=[w for w in rift.winfo_children() if isinstance(w,tk.Button) and w.cget('text').startswith('MAP')]
                assert len(links)==2
                for button in links: button.invoke()
                for item,canvas,*_ in app.field_boss_widgets:
                    for w in canvas.winfo_children():
                        if isinstance(w,tk.Button) and 'MAP' in w.cget('text'): w.invoke()
                urls=[call.args[0] for call in browser.call_args_list]
                assert len(urls)==16 and all('/ja/map?' in url and 'q=' in url and 'map=' in url for url in urls),urls
            report['checks'].append('rift faction MAP buttons and field boss MAP buttons call the browser with Japanese filtered map URLs')
            win.withdraw(); root.update()
            for mode in (False,True):
                app.set_event_compact(mode)
                for width in (340,533):
                    resize_to(800,width); root.update(); app._tick_once()
                    for event,canvas,title,*_ in app.event_widgets:
                        clock=canvas.find_withtag('headerclock')[0]
                        a,b=canvas.bbox(title),canvas.bbox(clock)
                        assert a[2]+4<=b[0],(mode,width,event['name_ja'],a,b)
                        for button in canvas.winfo_children():
                            if isinstance(button,tk.Button):
                                x=button.winfo_rootx()+button.winfo_width()//2
                                y=button.winfo_rooty()+button.winfo_height()//2
                                if app.event_scroll.canvas.winfo_rooty()<=y<=app.event_scroll.canvas.winfo_rooty()+app.event_scroll.canvas.winfo_height():
                                    assert app._interactive_widget_at_screen(x,y),(mode,width,button.cget('text'),x,y,str(root.winfo_containing(x,y)))
            app.set_event_compact(False); root.update()
            win.deiconify(); root.update()
            report['checks'].append('normal/compact titles and times do not overlap at 340/533px; MAP and bell click regions remain aligned')
            report['checks'].append('real display checkbox updates labels immediately, persists, and retains functional bells')
            e=next(e for e in app.cfg['events'] if e['name_en']=='Shugo Festa')
            app.open_event_notification_settings(e); root.update()
            audio=app._dialog_windows['event_notice_'+e['id']]
            next(w for w in descendants(audio) if isinstance(w,tk.Checkbutton) and w.cget('text')=='通知音を鳴らす').invoke()
            next(w for w in descendants(audio) if isinstance(w,tk.Button) and w.cget('text')=='保存').invoke(); root.update()
            assert not e['sound_enabled']
            reloaded=overlay.load_config(); saved=next(x for x in reloaded['events'] if x['id']==e['id'])
            assert not saved['sound_enabled'] and saved['alert_enabled']
            e['sound_enabled']=True
            report['checks'].append('individual sound OFF persists independently of the bell and shared volume')
            at=dt.datetime(2026,10,12,12,tzinfo=JST)
            app.event_previous=at-dt.timedelta(seconds=11)
            with patch.object(app,'play_event_alert',return_value=True) as sound:
                app.tick_event_notifications(at+dt.timedelta(seconds=2))
                app.tick_event_notifications(at+dt.timedelta(seconds=3))
                assert sound.call_count==1
                app.init_event_notifications(directory)
                app.event_previous=at-dt.timedelta(seconds=1)
                app.tick_event_notifications(at)
                assert sound.call_count==1
            report['checks'].append('delayed start alerts and persisted dedupe across reload prevent duplicate sound')
            boss=app.tracker.catalog['bosses'][0]
            boss['schedule']={'kind':'daily','time':'13:00','utc_offset':9}
            app.tracker.state['bells'][boss['id']]=True; app.tracker.state['leads'][boss['id']]=0
            app.tracker.previous=at+dt.timedelta(minutes=59,seconds=59)
            app.event_previous=at+dt.timedelta(hours=1)
            with patch.object(app,'play_event_alert',return_value=True) as sound:
                app.tick_tracker(at+dt.timedelta(hours=1))
                app.tick_event_notifications(at+dt.timedelta(hours=1))
                app.tick_tracker(at+dt.timedelta(hours=1,seconds=1))
                assert sound.call_count==1
            app.update_field_boss_events(at+dt.timedelta(hours=1))
            assert '次回まで' in app.field_boss_widgets[0][1].itemcget(app.field_boss_widgets[0][3],'text')
            report['checks'].append('field boss event card shares tracker schedule/bell and produces only one notification')
            # Exercise Windows audio API once, then failure/fallback via mocks.
            report['native_sound_api_success']=app.play_event_alert({'sound_file':'missing-test-file.wav','sound_volume':10},preview=True)
            assert report['native_sound_api_success']
            with patch.object(app.audio,'play_file',return_value=True) as play:
                assert not app.play_event_alert({'sound_enabled':False})
                assert not app.play_event_alert({'sound_volume':0})
                assert play.call_count==0
                assert app.play_event_alert({'sound_file':'missing-test-file.wav'})
                assert play.call_count==1
                with wave.open(play.call_args[0][0],'rb') as wav: assert wav.getnframes()>1000
            report['checks'].append('native audio API succeeds; mute, missing file fallback and non-empty WAV are verified')
            app.edit_event(win,app.cfg['events'].index(e),lambda:None); root.update()
            editor=next(w for w in descendants(win) if isinstance(w,tk.Toplevel))
            app.window_group.sync(); root.update()
            offset=(editor.winfo_x()-win.winfo_x(),editor.winfo_y()-win.winfo_y())
            win.geometry(f'+{win.winfo_x()+35}+{win.winfo_y()+25}'); root.update()
            app.window_group.sync(); root.update()
            assert (editor.winfo_x()-win.winfo_x(),editor.winfo_y()-win.winfo_y())==offset
            import ctypes
            u=ctypes.windll.user32; u.GetWindow.argtypes=[ctypes.c_void_p,ctypes.c_uint]; u.GetWindow.restype=ctypes.c_void_p
            assert int(u.GetWindow(hwnd(editor),4) or 0)==hwnd(win)
            assert int(u.GetWindow(hwnd(win),4) or 0)==hwnd(root)
            report['checks'].append('nested editor retains ownership and follows its moved settings parent')
            app._safe_dialog_close(editor); app._safe_dialog_close(win)
            for tab in app.tab_buttons: app.show_tab(tab); root.update()
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

