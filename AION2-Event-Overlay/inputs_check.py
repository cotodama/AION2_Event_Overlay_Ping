"""Offline UI regression for larger, shared selectors across the application."""
import copy,datetime as dt,json,os,sys,tempfile,traceback
from unittest.mock import patch

def run_check(target):
    report={'passed':False,'frozen':bool(getattr(sys,'frozen',False)),'checks':[]};app=root=None
    try:
        with tempfile.TemporaryDirectory(dir=target.parent,prefix='inputs-check-') as directory:
            os.environ['AION2_OVERLAY_DATA_DIR']=directory
            from window_group import system_dpi_awareness
            system_dpi_awareness()
            import tkinter as tk
            from tkinter import ttk
            import AION2_Event_Overlay as overlay
            from ping_feature import PingFeatureMixin
            from time_inputs import DatePicker,DateTimePicker,ClockPicker,MinutesPicker,WeekdayPicker,ClockList
            from schedule_table_model import GARTUA_NOVEMBER_DATES
            original=PingFeatureMixin.init_ping
            def offline(self,path):original(self,path);self._background_disabled=True
            errors=[]
            def descendants(w):
                for child in w.winfo_children():yield child;yield from descendants(child)
            with patch.object(PingFeatureMixin,'init_ping',offline),patch('webbrowser.open') as browser:
                root=tk.Tk();root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
                app=overlay.App(root);root.update()
                # Calendar selectors clamp invalid days and round-trip external values.
                win=app._new_dialog('入力セレクター検証');win.configure(bg='#202020')
                date=DatePicker(win,app,value='2028-01-31').pack(fill='x')
                date.month.set('02');assert date.get()=='2028-02-29' and len(date.combos[2].cget('values'))==29
                date.year.set('2027');assert date.get()=='2027-02-28'
                date.set('2026-11-25');assert [v.get() for v in date.variables]==['2026','11','25']
                stamp=DateTimePicker(win,app,value='2026-11-20T23:30:30+00:00').pack(fill='x')
                assert stamp.date.get()=='2026-11-21' and stamp.clock.get()=='08:30:30'
                stamp.clock.variables[1].set('31');assert stamp.get()=='2026-11-21 08:31:30'
                clock=ClockPicker(win,app,value='23:59:30').pack(fill='x');assert len(clock.combos[0].cget('values'))==24
                clock.variables[2].set('00');assert clock.get()=='23:59'
                minutes=MinutesPicker(win,app,value='720.5').pack(fill='x');assert [v.get() for v in minutes.variables]==['12','00','30']
                minutes.hour.set('11');assert float(minutes.get())==660.5
                for control in (date,stamp,clock,minutes):
                    for box in control.combos:assert str(box.cget('state'))=='readonly'
                app._safe_dialog_close(win);root.update()
                report['checks'].append('larger selectors: leap-year/month day limits, external synchronization, JST conversion, seconds and duration round-trip without manual text')
                # Common event editor date, duration and multi-window controls.
                e=next(e for e in app.cfg['events'] if e['name_en']=='Battlefield')
                app.open_event_edit(e);root.update();state=app._schedule_editor
                assert isinstance(state['date_picker'],DatePicker) and isinstance(state['remaining_picker'],MinutesPicker)
                assert not any(isinstance(w,tk.Spinbox) for w in descendants(state['win']))
                state['date_picker'].set('2026-11-25');assert state['date'].get()=='2026-11-25'
                assert any(isinstance(w,ttk.Combobox) and len(w.cget('values'))==60 for w in descendants(state['win']))
                app._safe_dialog_close(state['win']);root.update()
                # Advanced weekly event supports individual time rows and weekday checkboxes.
                index=next(n for n,e in enumerate(app.cfg['events']) if e['name_en']=='Artifact Siege')
                old=copy.deepcopy(app.cfg['events'][index]);app.edit_event_advanced(root,index,lambda:None);root.update();state=app._advanced_editor
                widgets=state['widgets'];assert isinstance(widgets['weekdays_text'],WeekdayPicker) and isinstance(widgets['times_text'],ClockList)
                assert widgets['weekdays_text'].get()=='3,5'
                widgets['weekdays_text'].checks[0].invoke()
                row=widgets['times_text'].add('22:30');row['clocks'][0].variables[1].set('31')
                with patch.object(overlay.messagebox,'showerror') as error:
                    state['save']();root.update();assert not error.called
                saved=app.cfg['events'][index];assert saved['weekdays']==[0,3,5] and saved['times']==['21:00','22:31']
                for key in ('alert_enabled','sound_enabled','sound_file','sound_volume'):
                    assert saved.get(key)==old.get(key)
                report['checks'].append('advanced weekly event: weekday checks and multiple clock rows save without CSV and preserve bell/audio fields')
                # Advanced interval and once selectors preserve maintenance anchors/seconds.
                index=next(n for n,e in enumerate(app.cfg['events']) if e['name_en']=='Spacetime Rift')
                app.edit_event_advanced(root,index,lambda:None);root.update();state=app._advanced_editor
                assert isinstance(state['widgets']['start'],ClockPicker) and isinstance(state['widgets']['interval_minutes'],MinutesPicker)
                state['widgets']['interval_minutes'].hour.set('4')
                state['save']();root.update();assert app.cfg['events'][index]['interval_minutes']==240
                app.edit_event_advanced(root,index,lambda:None);root.update();state=app._advanced_editor
                state['type'].set('once');state['rebuild']();root.update()
                picker=state['widgets']['at'];assert isinstance(picker,DateTimePicker)
                picker.date.set('2026-11-26');picker.clock.set('09:16:30');picker.clock.variables[1].set('17')
                state['save']();root.update();assert app.cfg['events'][index]['at']=='2026-11-26T09:17:30+09:00'
                # Windows permit explicit start/end rows, including overnight windows.
                index=next(n for n,e in enumerate(app.cfg['events']) if e['name_en']=='Battlefield')
                app.edit_event_advanced(root,index,lambda:None);root.update();state=app._advanced_editor;windows=state['widgets']['windows_text']
                assert isinstance(windows,ClockList) and len(windows.rows)==2
                windows.rows[0]['clocks'][0].variables[0].set('10')
                windows.add('23:00-01:00');state['save']();root.update()
                assert app.cfg['events'][index]['windows']==[['10:00','14:00'],['19:00','21:00'],['23:00','01:00']]
                report['checks'].append('interval, once and time-window editors use time/date selectors; exact seconds and overnight ranges save correctly')
                # Daily/Weekly reset clock and weekday menus are part of normal Settings flow.
                for group,mode in [('daily','毎日'),('weekly','毎週')]:
                    app.edit_tracker_schedule(group,parent=root);root.update();state=app._reset_editor
                    assert not any(w.winfo_class()=='Entry' for w in descendants(state['win']))
                    state['mode'].set(mode);state['clock'].variables[0].set('16');state['clock'].variables[1].set('05')
                    if group=='weekly':state['days'].set('1,4')
                    state['save']();root.update();schedule=app.tracker.catalog['resets'][group]
                    assert schedule['time']=='16:05' and schedule['utc_offset']==9
                    if group=='weekly':assert schedule['weekdays']==[1,4]
                report['checks'].append('Daily/Weekly resets use larger clock menus and weekday checks, preserve UTC offset and save correctly')
                # Timer dialog retains its hour range and Save/reset behavior.
                app.open_timer_settings();root.update()
                timer_win=app._dialog_windows['timer'];boxes=[w for w in descendants(timer_win) if isinstance(w,ttk.Combobox)]
                assert len(boxes)>=3 and len(boxes[0].cget('values'))==1000
                boxes[0].current(1);boxes[1].current(2);boxes[2].current(3)
                save=next(w for w in descendants(timer_win) if isinstance(w,tk.Button) and w.cget('text')=='保存')
                save.invoke();root.update();assert app.timers[0].duration==3723
                app._safe_dialog_close(timer_win);root.update()
                # NM date addition itself has no raw date Entry anymore.
                from boss_groups import boss_display_items
                item=boss_display_items(app.tracker.catalog['bosses'])[0];app.edit_boss_group(item);root.update();state=app._schedule_editor
                assert isinstance(state['tables'].date_picker,DatePicker)
                assert state['mode'].get()=='一定間隔' and state['interval_picker'].hour.get()=='11' and state['interval_picker'].minute.get()=='00'
                app._safe_dialog_close(state['win']);root.update()
                report['checks'].append('timer hours 0-999/minutes/seconds menus save duration; NM date addition uses year/month/day selectors and supplied week remains intact')
                expected_cfg=copy.deepcopy(app.cfg['events']);expected_catalog=copy.deepcopy(app.tracker.catalog)
                app.on_close();app=root=None
                root=tk.Tk();root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
                app=overlay.App(root);root.update()
                assert app.cfg['events']==expected_cfg and app.tracker.catalog==expected_catalog and app.timers[0].duration==3723
                assert not errors and not browser.called,(errors,browser.called)
                app.on_close();app=root=None;report['passed']=True
                report['checks'].append('restart retains edited event schedules, Daily/Weekly resets, timers and current NM dates; no Tk callback errors or browser startup')
    except Exception:report['error']=traceback.format_exc()
    finally:
        if app is not None:
            try:app.on_close()
            except Exception:pass
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
