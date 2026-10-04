"""Explicit offline integration check for source and frozen Windows builds."""
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import traceback

def run_check(result_path):
    report={'frozen':bool(getattr(sys,'frozen',False)),'passed':False,'checks':[]}
    root=None; app=None
    try:
        with tempfile.TemporaryDirectory(prefix='event-check-',dir=result_path.parent) as data_dir:
            os.environ['AION2_OVERLAY_DATA_DIR']=data_dir
            import tkinter as tk
            import AION2_Event_Overlay as overlay
            from ping_feature import PingFeatureMixin
            from ping_service import measure,latency_color
            from server_data import decode_response,balance_fraction,balance_groups,filtered_servers
            # No internet, no existing settings, no audio notifications during this check.
            original_init=PingFeatureMixin.init_ping
            def init(self,directory):
                original_init(self,directory); self._background_disabled=True
            PingFeatureMixin.init_ping=init
            root=tk.Tk(); app=overlay.App(root); root.update()
            assert app.event_section.winfo_ismapped() and len(app.event_widgets)==4
            assert app.daily_item and app.summary_area.canvas.winfo_ismapped()
            for region in ('Japan','NA West','NA East','Central Europe','South America','KR Server'):
                servers=app.ordered_faction_servers(region,'Asmodians')
                first=servers[0]; before=(first['id'],first['host'],first['port'])
                first['name']='Zikel'; app.repair_duplicate_names()
                assert first['name']=='Israphel' and (first['id'],first['host'],first['port'])==before
                assert [s['name'] for s in app.ordered_faction_servers(region,'Asmodians')][:5]==['Israphel','Zikel','Triniel','Lumiel','Marchutan']
            report['checks'].append('duplicate Zikel repair restores Israphel while retaining ID and endpoint')
            report['checks'].append('original events + daily reset + selected Ping')
            from types import SimpleNamespace
            origin=(root.winfo_x(),root.winfo_y())
            event=SimpleNamespace(widget=app.header_canvas,x_root=100,y_root=100)
            app.surface_drag_start(event)
            app.surface_drag_motion(SimpleNamespace(x_root=145,y_root=125)); root.update()
            assert (root.winfo_x(),root.winfo_y())==(origin[0]+45,origin[1]+25)
            app.surface_drag_end(event)
            app.surface_drag_start(SimpleNamespace(widget=app.close_button,x_root=100,y_root=100))
            assert not app._surface_dragging
            assert app.window_controls.winfo_y()<app.header_actions.winfo_y()
            assert bool(root.attributes('-topmost'))
            app.sync_drag_surface(); root.update(); app.sync_drag_surface(); root.update()
            ready=tk.BooleanVar(root,value=False)
            root.after(300,lambda:ready.set(True)); root.wait_variable(ready)
            root.update()
            app.sync_drag_surface(); root.update()
            assert app.drag_surface.winfo_ismapped()
            assert (app.drag_surface.winfo_x(),app.drag_surface.winfo_y())==(root.winfo_x(),root.winfo_y()), (app.drag_surface.geometry(),root.geometry(),app.drag_surface.winfo_x(),app.drag_surface.winfo_y(),root.winfo_x(),root.winfo_y())
            original_xy=(root.winfo_x(),root.winfo_y())
            for x,y in [(-1920,100),(-3840,100),(100,-1080),(-1920,-1080),(1920,120),(3840,120),(100,2160),(100,100)]:
                root.geometry(f'+{x}+{y}'); root.update()
                assert (root.winfo_x(),root.winfo_y())==(x,y), (x,y,root.winfo_x(),root.winfo_y())
                app.sync_drag_surface(); root.update()
                assert (app.drag_surface.winfo_x(),app.drag_surface.winfo_y())==(root.winfo_x(),root.winfo_y())
                before=root.geometry()
                app.toggle_window_maximize(); root.update()
                app.sync_drag_surface(); root.update()
                assert (app.drag_surface.winfo_x(),app.drag_surface.winfo_y())==(root.winfo_x(),root.winfo_y())
                app.toggle_window_maximize(); root.update()
                assert root.geometry()==before
                root.geometry('440x600'); root.update()
                app.sync_drag_surface(); root.update()
                assert (app.drag_surface.winfo_width(),app.drag_surface.winfo_height())==(root.winfo_width(),root.winfo_height())
            root.geometry('390x525')
            root.geometry(f'+{original_xy[0]}+{original_xy[1]}'); root.update()
            report['checks'].append('background follows absolute negative and positive multi-monitor coordinates')
            normal=root.geometry(); app.toggle_window_maximize(); root.update()
            assert app.window_maximized
            app.fit_window_to_content(); root.update()
            app.toggle_window_maximize(); root.update(); assert root.geometry()==normal
            if os.name=='nt':
                import ctypes
                app.minimize_window(); hwnd=app.get_native_toplevel_hwnd()
                assert ctypes.windll.user32.IsIconic(ctypes.c_void_p(hwnd))
                assert app.tray_icon
                ctypes.windll.user32.FindWindowW.restype=ctypes.c_void_p
                if ctypes.windll.user32.FindWindowW('Shell_TrayWnd',None): assert app.tray_icon.visible
                else: report['tray_visual_check']='Explorer taskbar unavailable in build session; callback restoration checked'
                app.tray_icon.callback(app.tray_icon.hwnd,app.tray_icon.MESSAGE,1,0x202)
                app.poll_tray(); root.update()
                assert not app.tray_icon.visible
                assert not ctypes.windll.user32.IsIconic(ctypes.c_void_p(hwnd))
            style=tk.ttk.Style(root)
            assert style.lookup('Overlay.Vertical.TScrollbar','troughcolor')=='#010203'
            assert 'arrow' not in str(style.layout('Overlay.Vertical.TScrollbar')).lower()
            report['checks'].append('surface drag + controls exclusion + minimize/restore + maximize/restore + arrowless dark scrollbars')
            app.show_tab('ping'); root.update()
            assert not app.event_section.winfo_ismapped() and app.ping_widgets
            assert app.list_area.body.winfo_children()[0].cget('text')=='COMMON / LOGIN'
            assert next(iter(app.ping_widgets))=='Japan:Common:LoginServer'
            assert all('193.202' not in w.cget('text') for w in app.ping_widgets.values())
            sid=next(iter(app.ping_widgets))
            for value,color in [(20,'#40ff68'),(120,'#ff9b42'),(250,'#ff5252')]:
                app.worker_queue.put(('ping',app.ping_generation,sid,value,'')); app.poll_network()
                assert app.ping_widgets[sid].cget('fg')==color
            old=app.ping_generation; app.ping_generation+=1
            app.worker_queue.put(('ping',old,sid,999,'')); app.poll_network()
            assert app.results[sid][0]==250
            report['checks'].append('Ping colors + stale generation rejection + vertical factions')
            app.open_ping_settings(); root.update()
            assert app._dialog_windows['ping'].winfo_ismapped()
            settings=app._dialog_windows['ping']
            assert settings.winfo_x()>=root.winfo_x()+root.winfo_width()
            assert str(settings.transient())==str(root)
            def settle():
                ready=tk.BooleanVar(root,value=False)
                root.after(120,lambda:ready.set(True)); root.wait_variable(ready)
            settle()
            top_check=next(w for w in settings.winfo_children() if isinstance(w,tk.Checkbutton) and '最前面' in w.cget('text'))
            top_check.invoke(); root.update()
            assert not bool(root.attributes('-topmost')) and not bool(app.drag_surface.attributes('-topmost'))
            top_check.invoke(); root.update()
            assert bool(root.attributes('-topmost')) and bool(app.drag_surface.attributes('-topmost'))
            report['checks'].append('topmost defaults on + checkbox toggles overlay and drag surface')
            settings.geometry('+220+180'); root.update()
            remembered=(settings.winfo_x(),settings.winfo_y())
            state=app._ping_selection_state; before=list(app.ping_cfg['selected'])
            state['faction'].set('すべて'); state['populate']()
            assert any('Israphel' in row.cget('text') for row in state['rows'])
            state['faction'].set('天族'); state['populate']()
            assert state['rows'][0].cget('text').startswith('1. Siel')
            assert state['rows'][1].cget('text').startswith('2. Nezekan')
            state['rows'][1].invoke()
            state['faction'].set('魔族'); state['populate'](); root.update()
            assert state['rows'][0].cget('text').startswith('1. Israphel')
            state['rows'][0].invoke()
            state['variables']['Japan:Common:LoginServer'].set(True)
            assert app.ping_cfg['selected']==before  # changes are drafts until Save
            state['faction'].set('天族'); state['populate']()
            assert state['variables']['Japan:Elyos:Nezekan'].get()
            assert state['save'].cget('text')=='保存'
            state['save'].invoke(); root.update()
            assert app.ping_cfg['selected']==['Japan:Elyos:Siel','Japan:Elyos:Nezekan','Japan:Asmodians:Israphel','Japan:Common:LoginServer']
            assert len(app.summary_rows)==4
            app.open_ping_settings(); root.update()
            assert (app._dialog_windows['ping'].winfo_x(),app._dialog_windows['ping'].winfo_y())==remembered
            probe=PingFeatureMixin(); probe.init_ping(data_dir)
            assert probe.dialog_positions['ping_settings']=={'x':remembered[0],'y':remembered[1]}
            report['checks'].append('settings open to right + owned foreground window + moved coordinates persist across reopen/restart')
            state=app._ping_selection_state
            assert state['variables']['Japan:Asmodians:Israphel'].get()
            state['rows'][0].invoke()
            win=app._dialog_windows['ping']; root.tk.call('eval',win.protocol('WM_DELETE_WINDOW'))
            assert 'Japan:Elyos:Siel' in app.ping_cfg['selected']  # cancellation discards draft
            report['checks'].append('numbered faction dropdown lists + multi-select retention + Save commit + cancel + persisted selections')
            app.edit_endpoint(app.visible_endpoints()[0]); root.update()
            app.ping_cfg['topmost']=False; app.apply_background_opacity()
            assert not root.attributes('-topmost')
            for opacity in (0.,1.):
                app.cfg['background_opacity']=opacity; app.apply_background_opacity()
                assert app.ping_cfg['transparency']==round((1-opacity)*100)
                assert app.drag_surface.cget('bg')=='#202020'
                assert abs(float(app.drag_surface.attributes('-alpha'))-max(0.01,opacity))<0.001
                assert float(root.attributes('-alpha'))==1.0
            report['checks'].append('server selection + transparency + endpoint dialogs')
            sample={'generatedAt':'2026-10-04T00:00:00Z','regions':[]}
            for code in ('EU','NAW','NAE','LA','AS'):
                servers=[]
                for name,faction,players,ident in [('Siel','Elyos',600,1),('Israphel','Asmodian',400,2)]:
                    servers.append(dict(name=name,faction=faction,players=players,serverId=ident,region=code,
                                        capacity=1000,queue=3,isRunning=True,inMaintenance=False,creationBlocked=True,
                                        load=players/1000,spark=[{'t':1,'value':None},{'t':2,'value':players}]))
                sample['regions'].append(dict(code=code,servers=servers,lastUpdated='2026-10-04T00:00:00Z'))
            app.worker_queue.put(('db',sample,'')); app.poll_network()
            for tab in ('status','balance'):
                app.show_tab(tab); root.update()
                for code in ('all','EU','NAW','NAE','LA','AS'):
                    app.choose_db_region(code); root.update()
                    assert app.list_area.body.winfo_children()
            assert balance_fraction(600,400)==.6 and balance_fraction(None,400) is None
            assert balance_fraction(0,0) is None and len(filtered_servers(sample,'EU'))==2
            assert len(balance_groups(sample,'EU')[0][2])==1
            app.show_tab('status'); app.table_var.set(True); app.render_db(); root.update()
            app.sort_status('players'); root.update()
            app.worker_queue.put(('db',None,'test network failure')); app.poll_network()
            assert app.db_snapshot is sample and '前回値' in app.db_info.cget('text')
            report['checks'].append('six region tabs + status table + red locks + 24H + balance + failure retains snapshot')
            app.overlay_width=900; app.fit_window_to_content(); root.update()
            assert root.winfo_width()==900
            app.manual_height=300; app.fit_window_to_content(); root.update()
            assert app.resize_handle.winfo_ismapped()
            assert app.resize_handle.winfo_y()+app.resize_handle.winfo_height()<=root.winfo_height()
            app.ping_cfg['simple']=True; app.rebuild_summary(); root.update()
            app.reset_size(); root.update()
            app.show_tab('ping'); app.stopwatch_button.invoke(); root.update()
            timer_win=app._dialog_windows['timer']
            assert timer_win.winfo_ismapped() and app.active_tab=='events'
            app.stopwatch_button.invoke(); root.update()
            assert app._dialog_windows['timer'] is timer_win and timer_win.winfo_ismapped()
            root.tk.call('eval',timer_win.protocol('WM_DELETE_WINDOW')); root.update()
            app.stopwatch_button.invoke(); root.update()
            assert app._dialog_windows['timer'].winfo_ismapped()
            assert app.timer_box.winfo_ismapped()
            report['checks'].append('resize + compact antenna + original timer panel')
            listener=socket.socket(); listener.bind(('127.0.0.1',0)); listener.listen(1)
            def accept():
                try:
                    conn,_=listener.accept(); conn.close()
                finally: listener.close()
            thread=threading.Thread(target=accept,daemon=True); thread.start()
            value,error=measure({'host':'127.0.0.1','port':listener.getsockname()[1]})
            assert value is not None and not error; thread.join(3)
            report['local_tcp_ms']=round(value,3)
            report['checks'].append('real localhost TCP measurement')
            for win in list(root.winfo_children()):
                if isinstance(win,tk.Toplevel): app._safe_dialog_close(win)
            app.on_close(); root=None
            report['passed']=True
    except Exception:
        report['error']=traceback.format_exc()
        if app:
            try: app.restore_selective_hit_test(); app.stop_workers.set()
            except Exception: pass
        if root:
            try: root.destroy()
            except Exception: pass
    result_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

