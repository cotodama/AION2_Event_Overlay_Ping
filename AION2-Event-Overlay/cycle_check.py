"""Default 11-hour cycle, hour/minute controls and maintenance anchor persistence."""
import copy,datetime as dt,json,os,sys,tempfile,traceback
from unittest.mock import patch

def run_check(target):
    report={'passed':False,'frozen':bool(getattr(sys,'frozen',False)),'checks':[]};app=root=None
    try:
        with tempfile.TemporaryDirectory(dir=target.parent,prefix='cycle-check-') as directory:
            os.environ['AION2_OVERLAY_DATA_DIR']=directory
            from window_group import system_dpi_awareness
            system_dpi_awareness()
            import tkinter as tk
            import AION2_Event_Overlay as overlay
            from ping_feature import PingFeatureMixin
            from boss_groups import boss_display_items,members
            from tracker_model import next_occurrence
            from schedule_table_model import JST,GARTUA_NOVEMBER_DATES
            original=PingFeatureMixin.init_ping
            def offline(self,path):original(self,path);self._background_disabled=True
            errors=[]
            with patch.object(PingFeatureMixin,'init_ping',offline),patch('webbrowser.open') as browser:
                root=tk.Tk();root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
                app=overlay.App(root);root.update()
                initial_state=copy.deepcopy(app.tracker.state);baseline=copy.deepcopy(app.tracker.catalog)
                def group():return next(g for g in boss_display_items(app.tracker.catalog['bosses']) if g['id'].startswith('gartua-'))
                def opened():
                    app.edit_boss_group(group());root.update();return app._schedule_editor
                e=opened();period=e['interval_picker']
                assert e['mode'].get()=='一定間隔' and not e['tables'].frame.winfo_ismapped()
                assert period.hour.get()=='11' and period.minute.get()=='00'
                assert not period.show_seconds.get() and not period.combos[2].winfo_ismapped()
                assert len(period.combos[1].cget('values'))==60
                period.hour.set('10');period.minute.set('30');assert float(e['interval'].get())==630
                e['save'].invoke();root.update()
                assert all(r['schedule']['minutes']==630 and r['schedule']['anchor']=='2026-11-25T20:30:00+09:00' for r in members(group()))
                report['checks'].append('default is interval with visible 11h/00m selectors; changing only period to 10h30m preserves both faction anchors')
                e=opened();period=e['interval_picker'];assert (period.hour.get(),period.minute.get())==('10','30')
                e['date_picker'].set('2026-11-26');e['hour'].set('21');e['minute'].set('15');e['second'].set('30')
                period.hour.set('11');period.minute.set('00');e['save'].invoke();root.update()
                maintenance='2026-11-26T21:15:30+09:00'
                assert all(r['schedule']['anchor']==maintenance and r['schedule']['minutes']==660 for r in members(group()))
                e=opened();period=e['interval_picker'];period.show_seconds.set(True);period.toggle_seconds();root.update()
                assert period.combos[2].winfo_ismapped()
                period.second.set('30');e['save'].invoke();root.update()
                e=opened();period=e['interval_picker'];assert period.show_seconds.get() and period.second.get()=='30'
                period.second.set('00');period.show_seconds.set(False);period.toggle_seconds()
                assert not period.combos[2].winfo_ismapped()
                e['save'].invoke();root.update()
                report['checks'].append('maintenance date/time reset and optional second precision save and reopen correctly; normal cycle UI needs only hour/minute choices')
                e=opened();period=e['interval_picker'];before=copy.deepcopy(app.tracker.catalog)
                period.hour.set('0');period.minute.set('00')
                with patch('schedule_editor.messagebox.showerror') as error:
                    e['save'].invoke();root.update();assert error.called
                assert app.tracker.catalog==before;app._safe_dialog_close(e['win']);root.update()
                e=opened();e['scope'].set('魔族のみ (2)');root.update();e['interval_picker'].hour.set('12');e['interval_picker'].minute.set('15')
                e['save'].invoke();root.update()
                for row in members(group()):
                    assert row['schedule']['anchor']==maintenance
                    assert row['schedule']['minutes']==(735 if row['id'].endswith('asmo') else 660)
                report['checks'].append('zero cycle is rejected before saving; faction-only cycle edit leaves the other faction and both original anchors intact')
                # Original baseline agrees with all supplied examples and continues past December 2.
                schedule=baseline['bosses'][0]['schedule'];previous=dt.datetime(2026,11,25,20,29,59,tzinfo=JST)
                for day,values in GARTUA_NOVEMBER_DATES.items():
                    for value in values:
                        expected=dt.datetime.combine(dt.date.fromisoformat(day),dt.time.fromisoformat(value),JST)
                        previous=next_occurrence(schedule,previous);assert previous==expected
                assert next_occurrence(schedule,previous)==dt.datetime(2026,12,3,4,30,tzinfo=JST)
                for key in ('bells','leads','checks','fired'):assert app.tracker.state[key]==initial_state[key]
                wanted=copy.deepcopy(app.tracker.catalog);app.on_close();app=root=None
                root=tk.Tk();root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
                app=overlay.App(root);root.update();assert app.tracker.catalog==wanted
                assert not errors and not browser.called,(errors,browser.called)
                app.on_close();app=root=None;report['passed']=True
                report['checks'].append('all 16 reference spawns match 11h interval; December 3 continues automatically; edited cycles/anchors, bells/history and restart remain stable')
    except Exception:report['error']=traceback.format_exc()
    finally:
        if app is not None:
            try:app.on_close()
            except Exception:pass
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
