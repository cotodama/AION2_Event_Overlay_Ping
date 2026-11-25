"""Exercise actual edit controls, saved schedules, grouping and notifications."""
import copy,datetime as dt,json,os,sys,tempfile,traceback
from pathlib import Path
from unittest.mock import patch

def run_check(target):
    report={'passed':False,'frozen':bool(getattr(sys,'frozen',False)),'checks':[]}
    app=root=None
    try:
        with tempfile.TemporaryDirectory(dir=target.parent,prefix='editor-135-') as directory:
            os.environ['AION2_OVERLAY_DATA_DIR']=directory
            from window_group import system_dpi_awareness,hwnd
            system_dpi_awareness()
            import tkinter as tk
            import AION2_Event_Overlay as overlay
            from ping_feature import PingFeatureMixin
            from event_model import next_start,due_notifications,JST
            from boss_groups import boss_display_items,boss_map_links,members
            from window_placement import work_area
            from schedule_edit_model import local_datetime
            init=PingFeatureMixin.init_ping
            def offline(self,path):init(self,path);self._background_disabled=True
            errors=[]
            def descendants(w):
                for child in w.winfo_children():yield child;yield from descendants(child)
            with patch.object(PingFeatureMixin,'init_ping',offline),patch('webbrowser.open',return_value=True) as browser:
                root=tk.Tk();root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
                app=overlay.App(root);root.update();root.geometry('460x800+-1800+80');root.update()
                base_catalog=copy.deepcopy(app.tracker.catalog);base_state=copy.deepcopy(app.tracker.state)
                initial_events=copy.deepcopy(app.cfg['events'])
                # Every regular event opens through its actual canvas binding.
                for original in initial_events:
                    widget=next(w[1] for w in app.event_widgets if w[0]['id']==original['id'])
                    widget.event_generate('<Button-3>',x=14,y=17);root.update()
                    state=app._schedule_editor;win=state['win'];assert win.winfo_ismapped()
                    left,top,right,bottom=work_area(win.winfo_x(),win.winfo_y())
                    assert left<=win.winfo_x()<right and top<=win.winfo_y()<bottom
                    state['name'].set(original['name_ja']+' 編集済')
                    state['save'].invoke();root.update()
                    saved=next(e for e in app.cfg['events'] if e['id']==original['id'])
                    for key,value in original.items():
                        if key not in ('name_ja','emoji_in_name'):assert saved[key]==value,(key,saved,original)
                report['checks'].append('right-click opens a visible owned editor for all five regular events; renaming preserves original time, bell, sound and interval')
                event=app.cfg['events'][0];app.open_event_edit(event);root.update();state=app._schedule_editor
                initial=local_datetime(state['target'].get())
                assert len(state['hour_combo'].cget('values'))==24
                assert len(state['minute_combo'].cget('values'))==60
                assert str(state['hour_combo'].cget('state'))=='readonly'
                state['hour_combo'].current(6);state['minute_combo'].current(59);state['second_combo'].current(30)
                assert local_datetime(state['target'].get()).strftime('%H:%M:%S')=='06:59:30'
                state['▲ 30秒'].invoke()
                assert (state['hour'].get(),state['minute'].get(),state['second'].get())==('07','00','00')
                state['target'].set(initial.strftime('%Y-%m-%d %H:%M:%S'))
                report['checks'].append('separate readonly hour 00-23 and minute 00-59 dropdowns update the saved timestamp; 30s nudges and direct target changes synchronize the dropdowns')
                state['▲ 30秒'].invoke();assert local_datetime(state['target'].get())==initial+dt.timedelta(seconds=30)
                state['▼ 30秒'].invoke();assert local_datetime(state['target'].get())==initial
                state['▲ 1分'].invoke();assert local_datetime(state['target'].get())==initial+dt.timedelta(minutes=1)
                state['▼ 1分'].invoke();assert local_datetime(state['target'].get())==initial
                state['remaining_picker'].hour.set('1');state['remaining_picker'].minute.set('05');state['remaining_picker'].second.set('00')
                assert float(state['remaining'].get())==65
                state['remaining'].set('720');assert state['remaining'].get()=='720'
                now=dt.datetime.now(JST);at=local_datetime(state['target'].get());assert abs((at-now).total_seconds()-43200)<2
                state['mode'].set('一定間隔');state['interval'].set('720')
                target_time=(now+dt.timedelta(hours=2)).replace(microsecond=0,second=30)
                state['target'].set(target_time.strftime('%Y-%m-%d %H:%M:%S'));state['save'].invoke();root.update()
                e=app.cfg['events'][0];assert next_start(e,now)==target_time
                assert next_start(e,target_time)==target_time+dt.timedelta(hours=12)
                assert app.event_status(e,target_time-dt.timedelta(seconds=30))[1]==30
                assert len(due_notifications(e,target_time-dt.timedelta(seconds=1),target_time))==1
                assert due_notifications(e,target_time,target_time+dt.timedelta(seconds=1))==[]
                saved_json=json.loads(Path(directory,'aion2_overlay.json').read_text(encoding='utf-8'))
                assert saved_json['events'][0]['interval_anchor']==target_time.isoformat()
                report['checks'].append('real 30s/1m arrow buttons and spinbox step selector work; remaining minutes do not rewrite typed input; exact-second maintenance anchor repeats every 12h with one due notification')
                battlefield=next(row for row in app.cfg['events'] if row.get('name_en')=='Battlefield')
                app.open_event_edit(battlefield);root.update();state=app._schedule_editor
                state['▲ 30秒'].invoke();state['save'].invoke();root.update()
                battlefield=next(row for row in app.cfg['events'] if row.get('name_en')=='Battlefield')
                assert battlefield['windows']==[['11:00:30','14:00:30'],['19:00:30','21:00:30']],battlefield['windows']
                artifact=next(row for row in app.cfg['events'] if row.get('name_en')=='Artifact Siege')
                app.open_event_edit(artifact);root.update();state=app._schedule_editor
                reference=local_datetime(state['target'].get())
                state['target'].set(reference.replace(hour=23,minute=59,second=45).strftime('%Y-%m-%d %H:%M:%S'))
                state['▲ 30秒'].invoke();state['save'].invoke();root.update()
                artifact=next(row for row in app.cfg['events'] if row.get('name_en')=='Artifact Siege')
                assert artifact['times']==['00:00:15'] and artifact['weekdays']==[4,6],artifact
                report['checks'].append('30s nudge shifts all battlefield windows; weekly nudge across midnight shifts weekday set consistently to keep the requested next time')
                # Each named card, including unknown schedules, is editable.
                for displayed in boss_display_items(app.tracker.catalog['bosses']):
                    widget=next(w[1] for w in app.field_boss_widgets if w[0]['id']==displayed['id'])
                    widget.event_generate('<Button-3>',x=14,y=17);root.update()
                    state=app._schedule_editor;state['name'].set(displayed['name']+' 編集済')
                    assert state['hour'].get()==local_datetime(state['target'].get()).strftime('%H')
                    assert state['minute'].get()==local_datetime(state['target'].get()).strftime('%M')
                    if displayed['id'].startswith('gartua'):
                        state['mode'].set('一定間隔');state['interval'].set('720')
                        state['date'].set(target_time.strftime('%Y-%m-%d'))
                        state['hour_combo'].current(target_time.hour);state['minute_combo'].current(target_time.minute)
                        state['second_combo'].current(target_time.second)
                    state['save'].invoke();root.update()
                rows=[r for r in app.tracker.catalog['bosses'] if r['id'].startswith('gartua')]
                assert len(rows)==2 and all(r['schedule']['anchor']==target_time.isoformat() for r in rows)
                assert len(boss_display_items(app.tracker.catalog['bosses']))==7
                assert all(r.get('display_name','').endswith('編集済') for r in app.tracker.catalog['bosses'])
                for original in base_catalog['bosses']:
                    row=next(r for r in app.tracker.catalog['bosses'] if r['id']==original['id'])
                    assert row['map_url']==original['map_url'] and row['npc_url']==original['npc_url']
                for key in ('bells','leads','checks','fired'):assert app.tracker.state[key]==base_state[key]
                report['checks'].append('all seven NM cards edit names; Gartua both-faction reset saves matching anchors without changing IDs, MAPs, bell state or dedupe history')
                gartua=next(g for g in boss_display_items(app.tracker.catalog['bosses']) if g['id'].startswith('gartua'))
                app.edit_boss_group(gartua);root.update();state=app._schedule_editor
                state['scope'].set(next(k for k in ['天族のみ (1)','魔族のみ (2)'] if k.startswith('魔族')))
                state['target'].set((target_time+dt.timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S'))
                state['save'].invoke();root.update()
                assert next(r for r in app.tracker.catalog['bosses'] if r['id']=='gartua-elyos')['schedule']['anchor']==target_time.isoformat()
                assert next(r for r in app.tracker.catalog['bosses'] if r['id']=='gartua-asmo')['schedule']['anchor']==(target_time+dt.timedelta(minutes=1)).isoformat()
                report['checks'].append('faction-only edit changes Asmodian schedule while retaining Elyos anchor in the same single card')
                for _,canvas,*_ in app.field_boss_widgets:
                    labels=[w.cget('text') for w in canvas.winfo_children() if isinstance(w,tk.Button)]
                    assert labels.count('天族MAP')==1 and labels.count('魔族MAP')==1,labels
                # Synthetic imported faction duplicates are one card per matching name.
                for name in ('精霊王アグロⅡ','執行者カイラ','守護神将ナフマ'):
                    original=dict(id='shared',name=name,faction='天族・魔族',map_url='https://aion2.gaming.tools/ja/map?map=20')
                    pair=[dict(original,id='e',faction='天族'),dict(original,id='a',faction='魔族')]
                    grouped=boss_display_items(pair);assert len(grouped)==1
                    assert len(boss_map_links(grouped[0]))==2 and len(members(grouped[0]))==2
                report['checks'].append('all NM cards have one Elyos and one Asmodian MAP button; same-name imported faction duplicates group into one card without inventing shared-map locations')
                app.open_event_edit(app.cfg['events'][0]);root.update();state=app._schedule_editor
                before=copy.deepcopy(app.cfg);state['interval'].set('nan')
                with patch('schedule_editor.messagebox.showerror') as error:
                    state['save'].invoke();root.update();assert error.called
                assert app.cfg==before and state['win'].winfo_exists()
                app._safe_dialog_close(state['win']);root.update()
                app.edit_event_advanced(root,0,lambda:None);root.update()
                advanced=next(w for w in descendants(root) if isinstance(w,tk.Toplevel) and w.title()=='イベント編集')
                with patch.object(overlay.messagebox,'showerror') as error:
                    next(w for w in descendants(advanced) if isinstance(w,tk.Button) and w.cget('text')=='保存').invoke();root.update()
                    assert not error.called and not advanced.winfo_exists()
                assert app.cfg['events'][0]['interval_anchor']==target_time.isoformat()
                report['checks'].append('legacy advanced editor accepts second precision and decimal interval without losing the saved maintenance anchor')
                expected=copy.deepcopy(app.tracker.catalog);events=copy.deepcopy(app.cfg['events'])
                app.on_close();app=root=None
                root=tk.Tk();root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
                app=overlay.App(root);root.update()
                assert app.tracker.catalog==expected and app.cfg['events']==events
                assert not errors,errors
                assert not browser.called
                report['checks'].append('invalid interval is rejected without changing saved data; reopening and restarting preserve all names/anchors/seconds and do not launch a browser')
                app.on_close();app=root=None;report['passed']=True
    except Exception:report['error']=traceback.format_exc()
    finally:
        if app is not None:
            try:app.on_close()
            except Exception:pass
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
