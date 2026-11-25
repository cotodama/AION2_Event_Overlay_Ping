"""Offline GUI regression for per-weekday and dated NM schedules."""
import copy,datetime as dt,json,os,sys,tempfile,traceback
from unittest.mock import patch

def run_check(target):
    report={'passed':False,'frozen':bool(getattr(sys,'frozen',False)),'checks':[]}
    app=root=None
    try:
        with tempfile.TemporaryDirectory(dir=target.parent,prefix='weekday-check-') as directory:
            os.environ['AION2_OVERLAY_DATA_DIR']=directory
            from window_group import system_dpi_awareness
            system_dpi_awareness()
            import tkinter as tk
            import AION2_Event_Overlay as overlay
            from ping_feature import PingFeatureMixin
            from boss_groups import boss_display_items,members
            from tracker_model import next_occurrence
            from schedule_table_model import JST,GARTUA_NOVEMBER_DATES,table_schedule
            original=PingFeatureMixin.init_ping
            def offline(self,path):original(self,path);self._background_disabled=True
            errors=[]
            with patch.object(PingFeatureMixin,'init_ping',offline),patch('webbrowser.open') as browser:
                root=tk.Tk();root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
                app=overlay.App(root);root.update()
                initial_state=copy.deepcopy(app.tracker.state)
                baseline={r['id']:copy.deepcopy(r) for r in app.tracker.catalog['bosses']}
                def grouped(prefix):return next(r for r in boss_display_items(app.tracker.catalog['bosses']) if r['id'].startswith(prefix))
                app.edit_boss_group(grouped('gartua-'));root.update();e=app._schedule_editor;t=e['tables']
                assert e['mode'].get()=='一定間隔'
                t.load(table_schedule('dates',GARTUA_NOVEMBER_DATES),dt.datetime.now(JST))
                e['mode'].set('日付別・複数時刻');root.update()
                assert e['mode'].get()=='日付別・複数時刻' and t.frame.winfo_ismapped()
                assert not e['legacy_frame'].winfo_ismapped()
                assert sum(len(rows) for rows in t.rows['dates'].values())==16
                assert t.schedule('dates')['table']==GARTUA_NOVEMBER_DATES
                sample=t.rows['dates']['2026-11-26'][0]
                assert len(sample['combos'][0].cget('values'))==24 and len(sample['combos'][1].cget('values'))==60
                assert str(sample['combos'][0].cget('state'))=='readonly'
                hour=sample['values'][0].get()
                sample['combos'][0].event_generate('<MouseWheel>',delta=-120);root.update()
                assert sample['values'][0].get()==hour
                # Add/remove a date and one time through the actual callbacks.
                t.date.set('2026-12-03');t.add_date();row=t.add_time('dates','2026-12-03','09:15:30')
                row['combos'][0].current(10);row['combos'][1].current(16)
                assert t.schedule('dates')['table']['2026-12-03']==['10:16:30']
                row['remove'].invoke();t.remove_group('dates','2026-12-03')
                assert t.schedule('dates')['table']==GARTUA_NOVEMBER_DATES
                e['win'].geometry('440x550');root.update()
                assert e['save'].winfo_ismapped()
                report['checks'].append('dated UI loads all 16 supplied spawns; 24/60 dropdowns, seconds, date/time add/remove and fixed Save footer work')
                e['mode'].set('曜日別・複数時刻');root.update()
                assert not e['legacy_frame'].winfo_ismapped() and t.pages['weekly_times'].winfo_ismapped()
                assert len(t.groups['weekly_times'])==7
                for key in list(t.rows['weekly_times']):
                    for row in list(t.rows['weekly_times'][key]):row['remove'].invoke()
                r=t.add_time('weekly_times','0','09:30')
                r['combos'][0].current(10);r['combos'][1].current(31)
                t.add_time('weekly_times','0','21:00');t.add_time('weekly_times','3','07:00');t.add_time('weekly_times','3','18:00')
                for clock in ('01:00','12:00','23:00'):t.add_time('weekly_times','6',clock)
                expected=table_schedule('weekly_times',{'0':['10:31','21:00'],'3':['07:00','18:00'],'6':['01:00','12:00','23:00']})
                assert t.schedule('weekly_times')==expected
                e['save'].invoke();root.update()
                assert all(r['schedule']==expected for r in members(grouped('gartua-')))
                report['checks'].append('each weekday has independent multiple times; empty weekdays are omitted; Save applies to both existing faction IDs')
                app.edit_boss_group(grouped('gartua-'));root.update();e=app._schedule_editor;t=e['tables']
                assert t.schedule('weekly_times')==expected
                e['scope'].set('魔族のみ (2)');root.update()
                t.rows['weekly_times']['0'][0]['combos'][0].current(11)
                e['save'].invoke();root.update()
                rows=members(grouped('gartua-'))
                assert next(r for r in rows if r['id']=='gartua-elyos')['schedule']==expected
                assert next(r for r in rows if r['id']=='gartua-asmo')['schedule']['table']['0'][0]=='11:31'
                report['checks'].append('scope switch reloads table; Asmodian-only edit leaves Elyos weekdays unchanged')
                # Ragta gets the same UI without assuming its new spawn times.
                for r in members(grouped('ragta-')):assert r['schedule']==baseline[r['id']]['schedule']
                app.edit_boss_group(grouped('ragta-'));root.update();e=app._schedule_editor;t=e['tables']
                e['mode'].set('曜日別・複数時刻');root.update()
                t.add_time('weekly_times','2','20:15');t.add_time('weekly_times','3','07:15');t.add_time('weekly_times','3','18:15')
                e['save'].invoke();root.update()
                ragta=grouped('ragta-')
                assert all(r['schedule']['table']=={'2':['20:15'],'3':['07:15','18:15']} for r in members(ragta))
                app.edit_boss_group(ragta);root.update();e=app._schedule_editor
                e['name'].set('軍団長ラグタ 編集');e['save'].invoke();root.update()
                assert all(r['schedule']['table']=={'2':['20:15'],'3':['07:15','18:15']} for r in members(grouped('ragta-')))
                report['checks'].append('Ragta existing schedule survives migration; weekday edit and name-only save preserve its independent new table')
                # Empty/invalid saves never mutate the persisted catalog.
                before=copy.deepcopy(app.tracker.catalog)
                app.edit_boss_group(grouped('gartua-'));root.update();e=app._schedule_editor;t=e['tables']
                for key in t.rows['weekly_times']:
                    for row in list(t.rows['weekly_times'][key]):row['remove'].invoke()
                with patch('schedule_editor.messagebox.showerror') as error:
                    e['save'].invoke();root.update();assert error.called
                assert app.tracker.catalog==before
                app._safe_dialog_close(e['win']);root.update()
                # A finite date table must show its end in both display modes/tabs.
                for r in members(grouped('gartua-')):
                    r['schedule']=table_schedule('dates',GARTUA_NOVEMBER_DATES)
                app.write_tracker_json(app.catalog_path,app.tracker.catalog);app.rebuild_event_widgets();root.update()
                end=dt.datetime(2026,12,2,17,30,tzinfo=JST)
                app.update_field_boss_events(end)
                widget=next(w for w in app.field_boss_widgets if w[0]['id'].startswith('gartua-'))
                assert widget[1].itemcget(widget[2],'text')=='予定終了'
                app.show_tab('bosses');root.update();app.update_tracker_labels(end)
                label=next(w[3] for w in app.tracker_widgets if w[1]['id'].startswith('gartua-'))
                assert '予定は終了' in label.cget('text')
                report['checks'].append('empty save is rejected without data changes; finite schedules display ended after final date and never repeat the next week')
                # Notifications preserve group dedupe and configured lead across dates.
                from tracker_model import Tracker
                probe=copy.deepcopy(app.tracker.catalog)
                for row in probe['bosses']:
                    if row['id'].startswith('gartua-'):row['schedule']=table_schedule('dates',GARTUA_NOVEMBER_DATES)
                ids=[r['id'] for r in probe['bosses'] if r['id'].startswith('gartua-')]
                tracker=Tracker(probe,{'bells':{i:True for i in ids},'leads':{i:5 for i in ids}})
                at=dt.datetime(2026,11,29,1,25,tzinfo=JST);tracker.tick(at-dt.timedelta(seconds=1))
                assert len(tracker.tick(at)[1])==1 and tracker.tick(at)[1]==[]
                for row in app.tracker.catalog['bosses']:
                    assert row['map_url']==baseline[row['id']]['map_url'] and row['npc_url']==baseline[row['id']]['npc_url']
                for key in ('bells','leads','checks','fired'):assert app.tracker.state[key]==initial_state[key]
                wanted=copy.deepcopy(app.tracker.catalog)
                app.on_close();app=root=None
                root=tk.Tk();root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
                app=overlay.App(root);root.update();assert app.tracker.catalog==wanted
                assert not errors and not browser.called,(errors,browser.called)
                app.on_close();app=root=None
                report['checks'].append('lead time, both-faction notification dedupe, bells/history/MAP IDs and restart persistence are preserved; no Tk errors or browser startup')
                report['passed']=True
    except Exception:report['error']=traceback.format_exc()
    finally:
        if app is not None:
            try:app.on_close()
            except Exception:pass
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
