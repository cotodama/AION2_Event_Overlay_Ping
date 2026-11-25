"""Common event/NM editor with 30-second and one-minute countdown adjustments."""
import copy
import datetime as dt
import tkinter as tk
from tkinter import ttk,messagebox
from time_inputs import DatePicker,ClockList,MinutesPicker,PeriodPicker,protect_selectors
from boss_groups import members,next_boss_occurrence
from event_model import next_start
from schedule_edit_model import JST,local_datetime,event_edit,boss_schedule,minutes

MODES={'未確認':'unknown','今回のみ':'once','一定間隔':'interval','毎日':'daily','毎週':'weekly','開催時間帯':'windows','曜日別・複数時刻':'weekly_times','日付別・複数時刻':'dates'}

class ScheduleEditorMixin:
    def edit_event(self,parent,index,refresh):
        if index is None:return self.edit_event_advanced(parent,index,refresh)
        return self.open_schedule_editor('event',self.cfg['events'][index],parent,refresh)

    def edit_boss_group(self,item,parent=None):
        return self.open_schedule_editor('boss',item,parent)

    def open_event_edit(self,item):return self.open_schedule_editor('event',item)

    def open_schedule_editor(self,kind,item,parent=None,refresh=None):
        from ping_feature import ScrollArea
        key='schedule_edit_'+kind+'_'+item['id']
        existing=self._dialog_windows.get(key)
        if existing is not None and existing.winfo_exists():self.reveal_dialog(existing);return existing
        win=self._new_dialog('イベント名・時刻を編集',parent=parent);self._dialog_windows[key]=win
        win.configure(bg='#202020');win.minsize(390,430)
        footer=tk.Frame(win,bg='#202020');footer.pack(side='bottom',fill='x',padx=10,pady=8)
        area=ScrollArea(win,height=620);area.frame.pack(fill='both',expand=True,padx=10,pady=7)
        body=area.body
        def label(text):self.label(body,text,anchor='w',wraplength=390).pack(fill='x',pady=(6,2))
        fields={};dirty=[False];syncing=[False];target_dirty=[False];pattern_dirty=[False];days_dirty=[False]
        name=tk.StringVar(win,value=item.get('name_ja') if kind=='event' else item['name'])
        label('イベント名（絵文字も入力できます）')
        entry=tk.Entry(body,textvariable=name,bg='#202934',fg='white',insertbackground='white');entry.pack(fill='x')
        scope=tk.StringVar(win,value='天族・魔族まとめて')
        rows=members(item) if kind=='boss' else [item]
        scopes={'天族・魔族まとめて':rows}
        if kind=='boss' and len(rows)>1:
            for i,row in enumerate(rows):scopes[f"{row.get('faction','未確認')}のみ ({i+1})"]=[row]
            label('変更する対象')
            ttk.Combobox(body,textvariable=scope,values=list(scopes),state='readonly').pack(fill='x')
        now=dt.datetime.now(JST).replace(microsecond=0)
        selected=rows[0]
        nxt=next_start(item,now) if kind=='event' else next_boss_occurrence(item,now)[0]
        schedule=selected.get('schedule') or {}
        initial_kind=item.get('type','daily') if kind=='event' else schedule.get('kind','unknown')
        mode=tk.StringVar(win,value=next((k for k,v in MODES.items() if v==initial_kind),'未確認'))
        label('予定の種類')
        modes=[k for k,v in MODES.items() if v not in ('weekly_times','dates')] if kind=='event' else [k for k in MODES if k!='開催時間帯']
        combo=ttk.Combobox(body,textvariable=mode,values=modes,state='readonly');combo.pack(fill='x')
        form_body=body;tables=None
        if kind=='boss':
            from schedule_table_ui import ScheduleTables
            tables=ScheduleTables(form_body,self,lambda:dirty.__setitem__(0,True),area)
            tables.frame.pack(fill='x');tables.load(schedule,now)
        legacy_frame=tk.Frame(form_body,bg='#202020');legacy_frame.pack(fill='x')
        body=legacy_frame
        at=(nxt or now+dt.timedelta(hours=1)).astimezone(JST)
        target=tk.StringVar(win,value=at.strftime('%Y-%m-%d %H:%M:%S'))
        label('次回／基準日時（日本時間）')
        clock_row=tk.Frame(body,bg='#202020');clock_row.pack(fill='x',pady=3)
        date_value=tk.StringVar(win,value=at.strftime('%Y-%m-%d'))
        hour_value=tk.StringVar(win,value=at.strftime('%H'))
        minute_value=tk.StringVar(win,value=at.strftime('%M'))
        second_value=tk.StringVar(win,value=at.strftime('%S'))
        date_entry=DatePicker(clock_row,self,variable=date_value).pack(fill='x',pady=4)
        clock_fields=tk.Frame(clock_row,bg='#202020');clock_fields.pack(fill='x',pady=4)
        combos=[]
        for value,values,title in ((hour_value,[f'{n:02}' for n in range(24)],'時'),
                (minute_value,[f'{n:02}' for n in range(60)],'分'),
                (second_value,[f'{n:02}' for n in range(60)],'秒')):
            box=ttk.Combobox(clock_fields,textvariable=value,values=values,width=4,state='readonly',font=self.ui(12))
            box.pack(side='left',ipady=3);self.label(clock_fields,title).pack(side='left',padx=(2,5));combos.append(box)
        clock_sync=[False]
        def clock_from_target(*_):
            if clock_sync[0]:return
            try:value=local_datetime(target.get())
            except ValueError:return
            clock_sync[0]=True
            try:
                date_value.set(value.strftime('%Y-%m-%d'));hour_value.set(value.strftime('%H'))
                minute_value.set(value.strftime('%M'));second_value.set(value.strftime('%S'))
            finally:clock_sync[0]=False
        def clock_to_target(*_):
            if clock_sync[0]:return
            clock_sync[0]=True
            try:target.set(f'{date_value.get()} {hour_value.get()}:{minute_value.get()}:{second_value.get()}')
            finally:clock_sync[0]=False
        target.trace_add('write',clock_from_target)
        for variable in (date_value,hour_value,minute_value,second_value):variable.trace_add('write',clock_to_target)
        label('毎日・毎週・時間帯は時刻を使用。一定間隔は日時を基準に繰り返します。')
        remaining=tk.StringVar(win,value=f'{max(0,(at-now).total_seconds())/60:.6f}'.rstrip('0').rstrip('.'))
        label('あと何時間・何分（下の▲▼で30秒／1分調整）')
        adjust=tk.Frame(body,bg='#202020');adjust.pack(fill='x')
        remaining_picker=MinutesPicker(adjust,self,variable=remaining).pack(fill='x',pady=4)
        exact=self.label(body,'',anchor='w',fg='#bcdcff');exact.pack(fill='x',pady=3)
        bumps=tk.Frame(body,bg='#202020');bumps.pack(fill='x')
        def set_target(at):
            syncing[0]=True
            target.set(at.strftime('%Y-%m-%d %H:%M:%S'))
            remaining.set(f'{max(0,(at-dt.datetime.now(JST)).total_seconds())/60:.6f}'.rstrip('0').rstrip('.'))
            exact.configure(text='設定する日時：'+target.get()+' JST')
            syncing[0]=False;dirty[0]=True;target_dirty[0]=True
        def ensure_mode():
            if MODES[mode.get()]=='unknown':mode.set('一定間隔')
        def nudge(seconds):
            try:set_target(local_datetime(target.get())+dt.timedelta(seconds=seconds));ensure_mode()
            except ValueError:messagebox.showerror('時刻編集','日時を入力してください',parent=win)
        for text,delta in [('▲ 30秒',30),('▼ 30秒',-30),('▲ 1分',60),('▼ 1分',-60)]:
            button=self.button(bumps,text,lambda delta=delta:nudge(delta),padx=8);button.pack(side='left',padx=2)
            fields[text]=button
        def target_changed(*_):
            if syncing[0]:return
            dirty[0]=True;target_dirty[0]=True
            try:
                if len(target.get().strip())<16:raise ValueError('日時を入力してください')
                at=local_datetime(target.get());syncing[0]=True
                remaining.set(f'{max(0,(at-dt.datetime.now(JST)).total_seconds())/60:.6f}'.rstrip('0').rstrip('.'))
                exact.configure(text='設定する日時：'+at.strftime('%Y-%m-%d %H:%M:%S')+' JST')
                ensure_mode()
            except ValueError:exact.configure(text='日時は YYYY-MM-DD HH:MM:SS で入力')
            finally:syncing[0]=False
        def remaining_changed(*_):
            if syncing[0]:return
            dirty[0]=True;target_dirty[0]=True
            try:
                value=minutes(remaining.get());at=dt.datetime.now(JST).replace(microsecond=0)+dt.timedelta(seconds=round(value*60))
                syncing[0]=True;target.set(at.strftime('%Y-%m-%d %H:%M:%S'))
                exact.configure(text='設定する日時：'+target.get()+' JST');syncing[0]=False
                ensure_mode()
            except ValueError:exact.configure(text='残り分数は0〜525600です')
            finally:syncing[0]=False
        target.trace_add('write',target_changed);remaining.trace_add('write',remaining_changed)
        interval=tk.StringVar(win,value=str(item.get('interval_minutes',60) if kind=='event' else schedule.get('minutes',720)))
        label('開催周期（時間・分を選択）')
        interval_picker=PeriodPicker(body,self,variable=interval).pack(fill='x',pady=4)
        label('メンテナンスで時刻が変わったら、上の日時を変更してください。周期だけの変更では保存済みの基準日時を維持します。')
        def period_changed(*_):
            if not syncing[0]:mode.set('一定間隔')
        interval.trace_add('write',period_changed)
        days=[];day_values=item.get('weekdays',[]) if kind=='event' else schedule.get('weekdays',[schedule.get('weekday',0)])
        label('毎週の曜日（日本時間）')
        weekdays=tk.Frame(body,bg='#202020');weekdays.pack(fill='x')
        for n,text in enumerate('月火水木金土日'):
            value=tk.BooleanVar(win,value=n in day_values);days.append(value)
            tk.Checkbutton(weekdays,text=text,variable=value,bg='#202020',fg='white',selectcolor='#26303a',
                command=lambda:(dirty.__setitem__(0,True),days_dirty.__setitem__(0,True))).pack(side='left')
        windows=tk.StringVar(win,value=','.join('-'.join(w) for w in item.get('windows',[])))
        entry_minutes=tk.StringVar(win,value=str(item.get('entry_minutes',0)))
        duration=tk.StringVar(win,value=str(item.get('duration_minutes',0)))
        if kind=='event':
            label('開催時間帯（開始・終了を選択。＋で追加）')
            windows_picker=ClockList(body,self,variable=windows,windows=True).pack(fill='x')
            for title,var in [('入場受付時間（分、0＝なし）',entry_minutes),('開催時間（分、0＝開始時刻のみ）',duration)]:
                label(title);MinutesPicker(body,self,variable=var).pack(fill='x',pady=4)
        body=form_body
        def show_mode(*_):
            table_mode=MODES[mode.get()] in ('weekly_times','dates')
            if tables:
                tables.show(MODES[mode.get()])
                if table_mode:
                    legacy_frame.pack_forget()
                    tables.frame.pack(fill='x',after=combo)
                else:
                    legacy_frame.pack(fill='x',after=combo)
        mode.trace_add('write',show_mode);show_mode()
        for variable in (mode,interval,windows,entry_minutes,duration):variable.trace_add('write',lambda *_:dirty.__setitem__(0,True))
        windows.trace_add('write',lambda *_:pattern_dirty.__setitem__(0,True))
        if kind=='boss' and len(rows)>1:
            def scope_changed(*_):
                nonlocal at
                selected_rows=scopes[scope.get()];row=selected_rows[0];schedule=row.get('schedule') or {}
                next_time=next_boss_occurrence({'_members':selected_rows},dt.datetime.now(JST))[0]
                at=(next_time or dt.datetime.now(JST)+dt.timedelta(hours=1)).astimezone(JST)
                syncing[0]=True
                if tables:tables.load(schedule,dt.datetime.now(JST))
                name.set(item['name'] if len(selected_rows)>1 else row['name'])
                mode.set(next((k for k,v in MODES.items() if v==schedule.get('kind','unknown')),'未確認'))
                interval.set(str(schedule.get('minutes',720)));target.set(at.strftime('%Y-%m-%d %H:%M:%S'))
                remaining.set(f'{max(0,(at-dt.datetime.now(JST)).total_seconds())/60:.6f}')
                values=schedule.get('weekdays',[schedule.get('weekday',0)])
                for n,value in enumerate(days):value.set(n in values)
                syncing[0]=False;dirty[0]=target_dirty[0]=days_dirty[0]=False
            scope.trace_add('write',scope_changed)
        label('保存で反映します。名前だけの変更では、既存の出現周期や通知設定を変更しません。')
        def save():
            try:
                editing_mode=MODES[mode.get()] if dirty[0] else 'keep'
                day_numbers=[n for n,v in enumerate(days) if v.get()]
                if editing_mode=='weekly' and target_dirty[0] and not days_dirty[0]:
                    shift=(local_datetime(target.get()).date()-at.date()).days
                    day_numbers=[(n+shift)%7 for n in day_numbers]
                if not name.get().strip():raise ValueError('名前を入力してください')
                if kind=='event':
                    window_text=windows.get()
                    if editing_mode=='windows' and target_dirty[0] and not pattern_dirty[0] and item.get('windows'):
                        delta=local_datetime(target.get())-at
                        def shift_clock(text):return (dt.datetime.combine(at.date(),dt.time.fromisoformat(text),JST)+delta).strftime('%H:%M:%S')
                        window_text=','.join('-'.join(shift_clock(t) for t in pair) for pair in item['windows'])
                    value=event_edit(item,name.get(),editing_mode,target.get(),interval.get(),
                        day_numbers,window_text,entry_minutes.get(),duration.get())
                    if editing_mode==item.get('type') and not target_dirty[0]:
                        if editing_mode=='weekly':value['times']=copy.deepcopy(item.get('times',[]))
                        if editing_mode=='interval' and float(interval.get())==float(item.get('interval_minutes',60)):
                            if item.get('interval_anchor'):value['interval_anchor']=item['interval_anchor']
                            else:value.pop('interval_anchor',None);value['start']=item.get('start','00:00')
                    cfg=copy.deepcopy(self.cfg)
                    index=next(n for n,row in enumerate(cfg['events']) if row['id']==item['id']);cfg['events'][index]=value
                    from AION2_Event_Overlay import save_config
                    save_config(cfg);self.cfg=cfg;self.event_previous=None
                else:
                    changed_schedule=(tables.schedule(editing_mode) if editing_mode in ('weekly_times','dates') else
                        boss_schedule(editing_mode,target.get(),interval.get(),day_numbers) if editing_mode!='keep' else None)
                    catalog=copy.deepcopy(self.tracker.catalog);ids={r['id'] for r in scopes[scope.get()]}
                    if len(rows)>1:
                        all_ids={r['id'] for r in rows}
                        for row in catalog['bosses']:
                            if row['id'] in all_ids:row.setdefault('boss_group','group:'+','.join(sorted(all_ids)))
                    for row in catalog['bosses']:
                        if row['id'] not in ids:continue
                        row.update(name=name.get().strip(),display_name=name.get().strip())
                        if editing_mode!='keep':
                            value=copy.deepcopy(changed_schedule)
                            old=row.get('schedule') or {}
                            if editing_mode=='interval' and old.get('kind')=='interval' and not target_dirty[0]:
                                value['anchor']=old['anchor']
                            if editing_mode=='daily' and old.get('kind')=='daily' and old.get('times'):
                                delta=local_datetime(target.get())-at if target_dirty[0] else dt.timedelta()
                                value['times']=[(dt.datetime.combine(at.date(),dt.time.fromisoformat(t),JST)+delta).strftime('%H:%M:%S') for t in old['times']]
                                value['time']=value['times'][0]
                            row['schedule']=value;row.pop('schedule_display',None)
                            row['note']='ユーザー編集の予定（JST）。メンテナンス等による変更時は再調整できます。'
                    from tracker_model import validate_catalog
                    validate_catalog(catalog);self.write_tracker_json(self.catalog_path,catalog)
                    self.tracker.catalog=catalog;self.tracker.previous=None
                self.rebuild_event_widgets()
                if self.active_tab=='bosses':self.show_tab('bosses')
                if refresh:refresh()
                elif (window:=self._dialog_windows.get('settings')) is not None and window.winfo_exists():self._refresh_event_settings()
                self._tick_once();self._safe_dialog_close(win)
            except (ValueError,KeyError,TypeError,OSError,OverflowError) as exc:
                messagebox.showerror('イベント編集',str(exc),parent=win)
        save_button=self.button(footer,'保存',save,padx=22,pady=5);save_button.pack(side='right')
        self.button(footer,'キャンセル',lambda:self._safe_dialog_close(win)).pack(side='right',padx=8)
        if kind=='event':
            def advanced():
                self._safe_dialog_close(win)
                index=next(i for i,row in enumerate(self.cfg['events']) if row['id']==item['id'])
                self.edit_event_advanced(parent or self.root,index,refresh or (lambda:None))
            self.button(footer,'詳細設定',advanced).pack(side='left')
        else:self.button(footer,'通知設定',lambda:self.edit_boss_notifications(item,parent=win)).pack(side='left')
        for child in body.winfo_children():area.install_wheel(child)
        fields.update(name=name,mode=mode,target=target,remaining=remaining,remaining_picker=remaining_picker,interval=interval,
            days=days,scope=scope,windows=windows,save=save_button,dirty=dirty,win=win,nudge=nudge,
            date=date_value,date_picker=date_entry,interval_picker=interval_picker,hour=hour_value,minute=minute_value,second=second_value,
            tables=tables,legacy_frame=legacy_frame,mode_combo=combo,
            hour_combo=combos[0],minute_combo=combos[1],second_combo=combos[2])
        self._schedule_editor=fields;win._schedule_editor=fields
        area.body._time_scroll_canvas=area.canvas
        protect_selectors(body)
        self._place_compact_dialog(win,480,600);self.reveal_dialog(win)
        return win
