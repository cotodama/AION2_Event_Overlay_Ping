"""Isolated offline GUI checks for themes, charts, switches and update controls."""
import copy,json,os,sys,tempfile,traceback
from pathlib import Path
from unittest.mock import patch

def run_check(target):
    target=Path(target);report=dict(passed=False,frozen=bool(getattr(sys,'frozen',False)),checks=[]);app=root=None
    try:
        with tempfile.TemporaryDirectory(dir=target.parent,prefix='visual-check-') as directory:
            os.environ['AION2_OVERLAY_DATA_DIR']=directory
            import tkinter as tk
            from window_group import system_dpi_awareness
            system_dpi_awareness()
            import AION2_Event_Overlay as overlay
            from ping_feature import PingFeatureMixin
            from visual_feature import PALETTES
            original=PingFeatureMixin.init_ping
            def offline(self,path):original(self,path);self._background_disabled=True
            errors=[]
            with patch.object(PingFeatureMixin,'init_ping',offline),patch('webbrowser.open') as browser,patch('update_feature.check_release') as network:
                root=tk.Tk();root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
                app=overlay.App(root);root.update();assert not app.cfg['auto_update_enabled'];network.assert_not_called()
                for theme,colors in PALETTES.items():
                    app.cfg['ui_theme']=theme;app.apply_visual_theme();root.update();assert app.drag_surface.cget('bg')==colors['root']
                app.cfg['ui_theme']='Abyss';app.apply_visual_theme();app._tick_once();root.update()
                for item,canvas,*_ in app.field_boss_widgets:
                    assert app.boss_picture(item,28) is not None
                    assert canvas.find_withtag('gauge')
                report['checks'].append('six themes, local images/icons and non-overlapping countdown gauges load')
                for tab in ('events','ping','status','balance','il','daily','weekly','bosses'):
                    app.show_tab(tab);root.update();app._tick_once()
                app.settings();root.update();assert app._theme_controls and app._update_auto_vars
                app._theme_controls['theme'].set('Midnight');root.update();assert app.cfg['ui_theme']=='Midnight'
                app._safe_dialog_close(app._dialog_windows['settings'])
                app.open_alert_dashboard();root.update();switch=app._alert_switches[0][2];before=switch.value;switch.invoke();assert switch.value!=before
                assert app.cfg['events'][0]['alert_enabled']==switch.value
                app._safe_dialog_close(app._dialog_windows['alert_dashboard']);root.update()
                report['checks'].append('eight tabs, settings, updater opt-in, theme persistence and actual alert switches work')
                servers=[]
                for index,(name,faction,load) in enumerate([('Siel','Elyos',.14),('Ariel','Elyos',.13),('Israphel','Asmodian',.13),('Lumiel','Asmodian',.13)]):
                    servers.append(dict(name=name,serverId=index,region='AS',faction=faction,load=load,state='live',isRunning=True,inMaintenance=False,creationBlocked=False,busyAt=.45,spark=[dict(t=1795554000000+i*3600000,value=None if i==10 else .1+(i%7)*.03) for i in range(24)]))
                region=dict(code='AS',servers=servers,lastUpdated='2026-11-25T20:00:00Z',onlineCount=4,load=.13,spark=servers[0]['spark'])
                app.db_snapshot=dict(regions=[region],fullAt=1,steamPlayers=100000,steamHistory=dict(hourly=dict(start=1795554000000,values=[100000+i*100 for i in range(48)])))
                for tab in ('status','balance'):
                    app.show_tab(tab);root.update();assert len(app.list_area.body.winfo_children())>=4
                    old=app.next_fetch
                    with patch('ping_feature.threading.Thread') as worker:
                        app.db_refresh_button.invoke();assert app.next_fetch>old;assert app._manual_db_schedule
                        app.db_refresh_button.invoke();worker.return_value.start.assert_called_once()
                    app.fetch_busy=False;app.update_db_request_label()
                    app.overlay_width=750;app.manual_height=850;app.fit_window_to_content();root.update();app.render_db();root.update()
                report['checks'].append('actual chart widgets render hourly gaps, Steam, same-faction pairs; manual refresh prevents duplicates and resets deadline')
                app.open_update_progress('1.4.1');root.update();app._update_queue.put(('progress',50,100));app.poll_updates();assert app._update_dialog_state['bar']['value']==50
                app._update_cancel.set();app._update_queue.put(('error','cancelled',True));app.poll_updates();root.update()
                assert not getattr(app,'_last_tick_error',None);assert not errors,errors;browser.assert_not_called()
                report['checks'].append('progress/cancel leaves application running; no callback errors or startup browser')
                app.on_close();app=None;root=None
            config=json.loads((Path(directory)/'aion2_overlay.json').read_text(encoding='utf-8'));assert config['ui_theme']=='Midnight'
            report['passed']=True
    except Exception:report['error']=traceback.format_exc()
    finally:
        if app is not None:
            try:app.on_close()
            except Exception:pass
        elif root is not None:
            try:root.destroy()
            except Exception:pass
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
