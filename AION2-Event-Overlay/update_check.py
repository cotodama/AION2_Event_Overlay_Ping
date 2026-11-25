"""Offline GUI regression for November schedules, period dropdown and endpoint editing."""
import copy,datetime as dt,json,os,sys,tempfile,traceback
from unittest.mock import patch
from pathlib import Path

def run_check(target):
    report={'passed':False,'frozen':bool(getattr(sys,'frozen',False)),'checks':[]}
    app=root=None
    try:
        with tempfile.TemporaryDirectory(dir=target.parent,prefix='november-check-') as directory:
            os.environ['AION2_OVERLAY_DATA_DIR']=directory
            from window_group import system_dpi_awareness
            system_dpi_awareness()
            import tkinter as tk
            import AION2_Event_Overlay as overlay
            from ping_feature import PingFeatureMixin
            from boss_groups import boss_display_items
            from tracker_model import next_occurrence
            from event_model import JST
            original=PingFeatureMixin.init_ping
            def offline(self,path):original(self,path);self._background_disabled=True
            errors=[]
            with patch.object(PingFeatureMixin,'init_ping',offline),patch('webbrowser.open') as browser:
                root=tk.Tk();root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
                app=overlay.App(root);root.update()
                artifact=next(e for e in app.cfg['events'] if e['name_en']=='Artifact Siege')
                assert artifact['weekdays']==[3,5] and artifact['times']==['21:00']
                assert '20:20' in app.event_details(artifact,dt.datetime(2026,11,4,12,tzinfo=JST))
                for row in app.tracker.catalog['bosses']:
                    if row['id'].startswith('gartua-'):
                        assert row['schedule']==dict(kind='interval',anchor='2026-11-25T20:30:00+09:00',minutes=660,edited=True)
                report['checks'].append('new and existing schedules: Thursday/Saturday 21:00 and Gartua supplied November 11-18 dated timetable')
                item=next(r for r in boss_display_items(app.tracker.catalog['bosses']) if r['id'].startswith('gartua'))
                app.edit_boss_group(item);root.update();state=app._schedule_editor
                assert len(state['interval_picker'].combos[1].cget('values'))==60
                assert state['mode'].get()=='一定間隔'
                assert state['interval_picker'].hour.get()=='11' and state['interval_picker'].minute.get()=='00'
                anchor=state['target'].get()
                state['interval_picker'].hour.set('9');root.update()
                assert state['interval'].get()=='540' and state['target'].get()==anchor
                state['interval'].set('660');assert state['interval_picker'].hour.get()=='11'
                state['save'].invoke();root.update()
                for row in app.tracker.catalog['bosses']:
                    if row['id'].startswith('gartua-'):assert row['schedule']['minutes']==660
                report['checks'].append('period dropdown 1-24h and detailed minutes synchronize; changing period keeps anchor and saves both factions')
                # Daily double-spawn schedule must survive a name-only edit and restart.
                item=next(r for r in app.tracker.catalog['bosses'] if r['id']=='spirit-king-argo')
                app.edit_boss_group(item);root.update();state=app._schedule_editor
                state['name'].set('精霊王アグロⅡ');state['save'].invoke();root.update()
                assert next(r for r in app.tracker.catalog['bosses'] if r['id']==item['id'])['schedule']['times']==['10:30','22:30']
                app.open_ping_settings();root.update();state=app._ping_selection_state
                settings=app._dialog_windows['ping'];settings.geometry('380x600');root.update()
                assert state['area'].canvas.winfo_ismapped() and state['area'].canvas.winfo_height()>200,state['area'].canvas.winfo_height()
                settings.geometry('340x400');root.update()
                assert state['area'].canvas.winfo_height()>40 and state['save'].winfo_ismapped()
                settings.geometry('700x850');root.update();assert state['area'].canvas.winfo_height()>400
                state['region'].set('Japan');state['faction'].set('魔族');state['populate']();root.update()
                rows=state['rows'];assert rows[0].cget('text').startswith('1. Israphel')
                assert rows[1].cget('text').startswith('2. Zikel')
                selected=copy.deepcopy(app.ping_cfg['selected'])
                server=app.ordered_faction_servers('Japan','Asmodians')[0];ident=server['id']
                before=state['variables'][ident].get()
                # Two actual button presses exercise Tk's double-click binding and selection restoration.
                row=rows[0]
                for stamp in (10000,10100):
                    row.event_generate('<ButtonPress-1>',x=80,y=10,time=stamp)
                    row.event_generate('<ButtonRelease-1>',x=80,y=10,time=stamp+30)
                root.update();editor=app._endpoint_editor
                assert editor['win'].winfo_ismapped() and str(editor['win'].transient())==str(settings)
                assert state['variables'][ident].get()==before
                editor['fields']['name'].set('編集テスト');editor['fields']['host'].set('127.0.0.1');editor['fields']['port'].set('13329')
                editor['save'].invoke();root.update()
                assert server['id']==ident and server['name']=='編集テスト' and server['host']=='127.0.0.1' and server['port']==13329
                assert state['rows'][0].cget('text').startswith('1. 編集テスト')
                assert app.ping_cfg['selected']==selected
                state['variables'][ident].set(True)
                state['faction'].set('天族');state['populate']();root.update()
                assert state['rows'][0].cget('text').startswith('1. Siel')
                state['variables']['Japan:Elyos:Siel'].set(True)
                state['save'].invoke();root.update()
                assert ident in app.ping_cfg['selected'] and 'Japan:Elyos:Siel' in app.ping_cfg['selected']
                report['checks'].append('380x600 and 340x400 settings retain usable server viewport/footer; larger window expands list; faction numbering and selected endpoints persist')
                report['checks'].append('real double-click opens owned name/IP/port editor without changing selection; stable ID and numbered order survive rename')
                catalog=copy.deepcopy(app.tracker.catalog);selected=copy.deepcopy(app.ping_cfg['selected'])
                app.on_close();app=root=None
                root=tk.Tk();root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
                app=overlay.App(root);root.update()
                assert app.tracker.catalog==catalog and app.ping_cfg['selected']==selected
                server=next(s for _,s in app.all_endpoints() if s['id']==ident)
                assert (server['name'],server['host'],server['port'])==('編集テスト','127.0.0.1',13329)
                assert not browser.called and not errors,errors
                app.on_close();app=root=None
                report['checks'].append('restart retains all schedules, both daily spawns, renamed endpoint and selections; no browser or Tk callback errors')
                report['passed']=True
    except Exception:report['error']=traceback.format_exc()
    finally:
        if app is not None:
            try:app.on_close()
            except Exception:pass
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
