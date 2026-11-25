"""IL, daily/weekly and named boss panels integrated into the existing HUD."""
import datetime as dt
import json
import os
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
import webbrowser
from boss_groups import boss_display_items,members,next_boss_occurrence,map_label,boss_map_links
from tracker_model import (Tracker, defaults, validate_catalog, next_occurrence,
                           schedule_text, validate_schedule, safe_link, UTC, UNKNOWN)

class TrackerFeatureMixin:
    def init_tracker(self,data_dir):
        self.catalog_path=Path(data_dir)/'tracker_catalog.json'
        self.state_path=Path(data_dir)/'tracker_state.json'
        catalog=defaults(); state={}; self.tracker_error=''
        try:
            if self.catalog_path.exists(): catalog=validate_catalog(json.loads(self.catalog_path.read_text(encoding='utf-8')))
        except (OSError,ValueError,TypeError,KeyError) as exc:
            self.tracker_error=f'データ定義の読み込み失敗: {exc}（標準定義を表示）'
        try:
            if self.state_path.exists():
                state=json.loads(self.state_path.read_text(encoding='utf-8'))
                if not isinstance(state,dict): raise ValueError('状態の形式が不正です')
                for key in ('checks','bells','leads','fired','periods'):
                    if key in state and not isinstance(state[key],dict): raise ValueError(key)
                state['leads']={k:max(0,min(10080,int(v))) for k,v in state.get('leads',{}).items()}
        except (OSError,ValueError,TypeError) as exc:
            self.tracker_error+=f' 状態の読み込み失敗: {exc}'; state={}
        self.tracker=Tracker(catalog,state); self.tracker_widgets=[]
        from boss_catalog import upgrade_boss_catalog
        if catalog.get('named_catalog_version',0)<7 and self.catalog_path.exists():
            import shutil
            backup=self.catalog_path.with_name(self.catalog_path.name+'.pre-1.3.10.bak')
            if not backup.exists():shutil.copy2(self.catalog_path,backup)
        changed=upgrade_boss_catalog(catalog)
        if changed or not self.catalog_path.exists(): self.write_tracker_json(self.catalog_path,catalog)

    def write_tracker_json(self,path,value):
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix('.tmp'); tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(tmp,path)

    def save_tracker(self): self.write_tracker_json(self.state_path,self.tracker.state)

    def boss_bell(self,item):
        return any(self.tracker.bell(r['id']) for r in members(item))

    def toggle_boss_bell(self,item,button):
        enabled=not self.boss_bell(item)
        for row in members(item): self.tracker.state['bells'][row['id']]=enabled
        button.configure(text='🔔' if enabled else '🔕'); self.save_tracker()

    def edit_boss_notifications(self,item,parent=None):
        win=self._new_dialog(item['name']+'の予定・通知',parent=parent)
        win.configure(bg='#202020')
        for row in members(item):
            frame=tk.Frame(win,bg='#202020'); frame.pack(fill='x',padx=10,pady=8)
            self.tracker_label(frame,row.get('faction','未確認')+' / '+row.get('area','未確認'))
            controls=tk.Frame(frame,bg='#202020'); controls.pack(fill='x')
            self.button(controls,'予定を編集',lambda r=row:self.edit_tracker_schedule('bosses',r,parent=win)).pack(side='left')
            bell=self.button(controls,'🔔' if self.tracker.bell(row['id']) else '🔕',lambda:None)
            bell.configure(command=lambda r=row,b=bell:self.toggle_tracker_bell(r['id'],b)); bell.pack(side='left',padx=4)
            self.label(controls,'何分前').pack(side='left')
            lead=tk.StringVar(value=str(self.tracker.lead(row['id'])))
            from time_inputs import MinutesPicker
            MinutesPicker(frame,self,variable=lead,maximum=10080,seconds=False).pack(fill='x',pady=4)
            self.button(controls,'適用',lambda r=row,v=lead:self.set_tracker_lead(r['id'],v.get())).pack(side='left',padx=4)
        self._place_compact_dialog(win,440,110*len(members(item))+35); win.deiconify()

    def delete_boss_group(self,item):
        ids={r['id'] for r in members(item)}
        self.tracker.catalog['bosses']=[r for r in self.tracker.catalog['bosses'] if r['id'] not in ids]
        self.write_tracker_json(self.catalog_path,self.tracker.catalog)
        # Keep existing notification history; deleting a display entry must not
        # reset unrelated checks, schedules, custom sounds or timers.
        self.rebuild_event_widgets()
        if self.active_tab=='bosses': self.show_tab('bosses')

    def build_tracker_tabs(self):
        row=tk.Frame(self.tab_bar,bg='#010203'); row.grid(row=1,column=0,columnspan=4,sticky='ew')
        for key,text in [('il','IL育成'),('daily','Daily'),('weekly','Weekly'),('bosses','Named Boss')]:
            b=self.button(row,text,lambda k=key:self.show_tab(k),padx=7,pady=5)
            b.pack(side='left',fill='x',expand=True,padx=1); self.tab_buttons[key]=b

    def tracker_label(self,parent,text,**kw):
        kw.setdefault('wraplength',max(260,self.overlay_width-52))
        w=self.label(parent,text,anchor='w',justify='left',**kw); w.pack(fill='x',padx=6,pady=2)
        return w

    def build_tracker_view(self):
        from ping_feature import ScrollArea
        key=self.active_tab
        top=tk.Frame(self.extra_section,bg='#202020'); top.pack(fill='x')
        self.button(top,'定義・時刻を編集',self.edit_tracker_catalog).pack(side='right')
        self.label(top,{'il':'育成の目安','daily':'日次チェック','weekly':'週次チェック','bosses':'ワールドネームド'}[key]).pack(side='left')
        height=max(150,(self.manual_height or 680)-self.extra_section.winfo_y()-90)
        self.list_area=ScrollArea(self.extra_section,height=min(420,height))
        self.list_area.frame.pack(fill='both',expand=True)
        self.tracker_widgets=[]
        self.tracker_notice=self.tracker_label(self.list_area.body,self.tracker_error or 'ベルは登録した予定の通知。未確認の予定は通知しません。',fg='#c5ccd6')
        self.reset_label=None
        if key in ('daily','weekly'):
            self.reset_label=self.tracker_label(self.list_area.body,'リセット: '+schedule_text(self.tracker.catalog['resets'].get(key)),fg='#79c9ff')
            self.button(self.list_area.body,'リセット時刻を登録',lambda:self.edit_tracker_schedule(key)).pack(anchor='w',padx=6,pady=3)
            self.button(self.list_area.body,'この一覧のチェックを手動解除',lambda:self.clear_tracker_checks(key)).pack(anchor='w',padx=6,pady=4)
        if key=='il': self.tracker_label(self.list_area.body,'900 → 1000 → 1400 → 1600 → 1900 → 2000 → 2100+\n解放条件はゲーム内で確認。装備IL70と総合ILは別の値です。')
        items=boss_display_items(self.tracker.catalog[key]) if key=='bosses' else self.tracker.catalog[key]
        if key=='bosses':
            search=tk.StringVar(value=getattr(self,'_boss_search',''))
            entry=tk.Entry(top,textvariable=search,bg='#15191e',fg='white',insertbackground='white',width=13)
            entry.pack(side='left',fill='x',expand=True,padx=5)
            def search_changed(event=None):
                self._boss_search=search.get();self.build_tracker_view_refresh()
            entry.bind('<Return>',search_changed)
            self.button(top,'検索',search_changed).pack(side='left')
            needle=search.get().casefold();items=[item for item in items if needle in ' '.join(str(item.get(k,'')) for k in ('name','drops','area','faction','equipment_il')).casefold()]
        for item in items:
            card=tk.Frame(self.list_area.body,bg='#15191e'); card.pack(fill='x',pady=3)
            head=tk.Frame(card,bg='#15191e'); head.pack(fill='x',padx=6,pady=3)
            ident=item['id']; check=None
            if key=='bosses':
                photo=self.boss_picture(item,32)
                if photo:tk.Label(head,image=photo,bg='#15191e').pack(side='left',padx=(0,6))
            if key!='bosses':
                check=tk.BooleanVar(value=self.tracker.done(ident))
                tk.Checkbutton(head,text=item['name'],variable=check,bg='#202020',fg='white',selectcolor='#344558',
                    activebackground='#344558',activeforeground='white',font=self.ui(9,'bold'),anchor='w',
                    command=lambda i=ident,v=check:self.set_tracker_check(i,v.get())).pack(side='left',fill='x',expand=True)
            else:
                prefix=('🌀👹 ' if item.get('boss_type')=='abyss' else '👿 ') if self.cfg.get('show_event_emoji',True) else ''
                self.label(head,prefix+item['name'],font=self.ui(9,'bold')).pack(side='left',fill='x',expand=True)
            if key!='il':
                bell=self.button(head,'🔔' if (self.boss_bell(item) if key=='bosses' else self.tracker.bell(ident)) else '🔕',lambda:None,width=3)
                bell.configure(command=(lambda row=item,b=bell:self.toggle_boss_bell(row,b)) if key=='bosses' else (lambda i=ident,b=bell:self.toggle_tracker_bell(i,b)))
                bell.pack(side='right')
                leadrow=tk.Frame(card,bg='#202020'); leadrow.pack(fill='x',padx=6)
                self.label(leadrow,'通知リードタイム（分）').pack(side='left')
                lead=tk.StringVar(value=str(self.tracker.lead(ident)))
                from time_inputs import MinutesPicker
                spin=MinutesPicker(card,self,variable=lead,maximum=10080,seconds=False)
                spin.pack(fill='x',padx=6,pady=4)
                self.button(leadrow,'適用',lambda row=item,i=ident,v=lead:self.set_boss_lead(row,v.get()) if key=='bosses' else self.set_tracker_lead(i,v.get())).pack(side='left')
            countdown=None
            if key=='il': self.tracker_label(card,item.get('hint',UNKNOWN))
            if key=='bosses':
                self.tracker_label(card,f"装備IL: {item.get('equipment_il') or UNKNOWN} / 主ドロップ: {item.get('drops') or UNKNOWN}")
                self.tracker_label(card,f"勢力: {item.get('faction') or UNKNOWN} / エリア: {item.get('area') or UNKNOWN}")
                coords=item.get('coordinates')
                self.tracker_label(card,'確認済み座標: '+(str(coords)+' / '+item['coordinate_source'] if coords and item.get('coordinate_source') else UNKNOWN))
                self.tracker_label(card,'出現時刻 / 間隔: '+' / '.join(r.get('faction','')+': '+schedule_text(r.get('schedule')) for r in members(item)))
            if key!='il': countdown=self.tracker_label(card,'次回: '+UNKNOWN,fg='#bcdcff')
            self.tracker_label(card,item.get('note',UNKNOWN),fg='#c5ccd6',font=self.ui(8))
            links=tk.Frame(card,bg='#202020'); links.pack(fill='x',padx=6,pady=(2,5))
            if key=='bosses':
                self.button(links,'画像',lambda row=item:self.choose_boss_picture(row),padx=5).pack(side='right')
                for link in boss_map_links(item):
                    self.button(links,link['label'],lambda url=link['url']:self.open_tracker_link(url),padx=5).pack(side='left',padx=2)
            for field,title,fallback in ([] if key=='bosses' else [('map_url','MAP','https://aion2.gaming.tools/ja/maps'),('npc_url','NPC','https://aion2.gaming.tools/ja/npcs')]):
                url=item.get(field) or fallback
                label=title+('一覧' if url==fallback else ' ↗')
                self.button(links,label,lambda u=url:self.open_tracker_link(u),padx=9).pack(side='left',padx=2)
            if item.get('source') and safe_link(item['source']):
                self.button(links,'確認元',lambda u=item['source']:self.open_tracker_link(u)).pack(side='left',padx=2)
            if key=='bosses': self.button(links,'予定・通知',lambda i=item:self.edit_boss_group(i)).pack(side='left',padx=2)
            self.tracker_widgets.append((key,item,check,countdown))
        def bind_tree(w):
            self.list_area.install_wheel(w)
            for child in w.winfo_children(): bind_tree(child)
        bind_tree(self.list_area.body)
        self.update_tracker_labels(dt.datetime.now(UTC))

    def edit_tracker_schedule(self,group,item=None,parent=None):
        if group=='bosses' and item is not None:return self.open_schedule_editor('boss',item,parent)
        from tkinter import ttk
        from time_inputs import ClockPicker,WeekdayPicker,protect_selectors
        win=self._new_dialog('出現・リセット時刻',parent=parent);win.configure(bg='#202020')
        old=(item.get('schedule') if item else self.tracker.catalog['resets'].get(group)) or {}
        self.tracker_label(win,group+'のリセット予定（確認した時刻を登録してください）',wraplength=410)
        kinds={'未確認':None,'毎日':'daily','毎週':'weekly'}
        mode=tk.StringVar(win,value=next((k for k,v in kinds.items() if v==old.get('kind')),'未確認'))
        box=ttk.Combobox(win,textvariable=mode,values=['未確認','毎日' if group=='daily' else '毎週'],state='readonly',font=self.ui(12))
        box.pack(fill='x',padx=10,pady=6,ipady=4)
        self.tracker_label(win,'リセット時刻')
        clock=ClockPicker(win,self,value=old.get('time','00:00')).pack(fill='x',padx=10,pady=5)
        self.tracker_label(win,'開催する曜日（Weekly）')
        days=WeekdayPicker(win,self,value=','.join(str(n) for n in old.get('weekdays',[old.get('weekday',2)]))).pack(fill='x',padx=10,pady=5)
        self.tracker_label(win,'UTCとの差（日本時間は +9）')
        offset=tk.StringVar(win,value=str(old.get('utc_offset',9)))
        offsets=sorted(set(range(-12,15))|{float(old.get('utc_offset',9))})
        ttk.Combobox(win,textvariable=offset,values=offsets,state='readonly',font=self.ui(12),width=8).pack(anchor='w',padx=10,pady=5,ipady=4)
        def visibility(*_):
            if kinds[mode.get()]=='weekly':days.frame.pack(fill='x',padx=10,pady=5,after=clock.frame)
            else:days.frame.pack_forget()
        mode.trace_add('write',visibility);visibility()
        def save():
            try:
                kind=kinds[mode.get()];schedule=None
                if kind:
                    schedule=dict(kind=kind,time=clock.get(),utc_offset=float(offset.get()))
                    if kind=='weekly':schedule['weekdays']=[int(n) for n in days.get().split(',') if n]
                validate_schedule(schedule)
                import copy
                catalog=copy.deepcopy(self.tracker.catalog);catalog['resets'][group]=schedule
                self.write_tracker_json(self.catalog_path,catalog);self.tracker.catalog=catalog;self.tracker.previous=None
                self.tracker.state['periods'].pop(group,None);self.save_tracker();self._safe_dialog_close(win)
                if self.active_tab in ('daily','weekly','bosses'):self.show_tab(self.active_tab)
                elif self.active_tab=='events':self.rebuild_event_widgets()
            except (ValueError,KeyError,OSError) as exc:messagebox.showerror('時刻設定',str(exc),parent=win)
        self.button(win,'保存',save,padx=24,pady=8).pack(pady=8)
        win._reset_editor=dict(mode=mode,clock=clock,days=days,offset=offset,save=save,win=win)
        self._reset_editor=win._reset_editor;protect_selectors(win)
        self._place_compact_dialog(win,480,400);self.reveal_dialog(win)

    def open_tracker_link(self,url):
        if safe_link(url): webbrowser.open(url)

    def set_tracker_check(self,ident,value):
        self.tracker.checked(ident,value); self.save_tracker()

    def toggle_tracker_bell(self,ident,button):
        self.tracker.state['bells'][ident]=not self.tracker.bell(ident)
        button.configure(text='🔔' if self.tracker.bell(ident) else '🔕'); self.save_tracker()

    def set_tracker_lead(self,ident,value):
        try:
            n=int(value)
            if not 0<=n<=10080: raise ValueError()
            self.tracker.state['leads'][ident]=n; self.save_tracker()
        except ValueError: messagebox.showerror('通知設定','0〜10080分の整数を入力してください',parent=self.root)

    def set_boss_lead(self,item,value):
        try:
            n=int(value)
            if not 0<=n<=10080: raise ValueError()
        except ValueError:
            messagebox.showerror('通知設定','0〜10080分の整数を入力してください',parent=self.root); return
        for row in members(item): self.tracker.state['leads'][row['id']]=n
        self.save_tracker()

    def clear_tracker_checks(self,key):
        for item in self.tracker.catalog[key]: self.tracker.checked(item['id'],False)
        self.save_tracker(); self.update_tracker_labels(dt.datetime.now(UTC))

    def update_tracker_labels(self,now):
        from AION2_Event_Overlay import fmt,display_time
        for key,item,check,label in self.tracker_widgets:
            if label is not None and not label.winfo_exists(): continue
            if check is not None: check.set(self.tracker.done(item['id']))
            if label is not None:
                s=item.get('schedule') if key=='bosses' else self.tracker.catalog['resets'].get(key)
                nxt=next_boss_occurrence(item,now)[0] if key=='bosses' else next_occurrence(s,now)
                if nxt:
                    shown,zone=display_time(nxt,self.cfg.get('display_timezone','JST'))
                    from display_format import remaining_text
                    label.configure(text='次回 '+shown.strftime('%m/%d %H:%M')+' '+zone+' / あと'+remaining_text((nxt-now).total_seconds()))
                else:
                    dated=key=='bosses' and any((r.get('schedule') or {}).get('kind')=='dates' for r in members(item))
                    label.configure(text='次回: 登録期間の予定は終了（日付を追加できます）' if dated else '次回: 未確認（時刻を登録するとカウントダウン）')
        reset=getattr(self,'reset_label',None)
        if reset is not None and reset.winfo_exists():
            key=self.active_tab; s=self.tracker.catalog['resets'].get(key)
            nxt=next_occurrence(s,now)
            reset.configure(text='リセット: '+schedule_text(s)+((' / '+fmt((nxt-now).total_seconds())) if nxt else ' / 自動解除なし'))
        notice=getattr(self,'tracker_notice',None)
        if notice is not None and notice.winfo_exists() and self.tracker.messages:
            notice.configure(text='🔔 '+ ' / '.join(self.tracker.messages))

    def tick_tracker(self,now):
        changed,alerts=self.tracker.tick(now)
        if changed: self.save_tracker()
        if alerts: self.play_event_alert()
        self.update_tracker_labels(now)

    def build_tracker_view_refresh(self):
        self.show_tab(self.active_tab)

    def edit_tracker_catalog(self):
        existing=self._dialog_windows.get('tracker')
        if existing and existing.winfo_exists(): existing.lift(); return
        win=self._new_dialog('育成・タスク・ネームド定義'); win.configure(bg='#202020')
        self._dialog_windows['tracker']=win
        self.tracker_label(win,'定義はJSON形式で編集できます。空欄の予定は null。\n時刻・座標はゲーム内で確認して登録してください。',wraplength=550)
        self.tracker_label(win,'毎日: {"kind":"daily","time":"01:00","utc_offset":9}\n毎週: 上記kindをweekly、"weekday":2 を追加（0=月）\n間隔: {"kind":"interval","anchor":"2026-10-06T02:00:00+09:00","minutes":180}\n以上は形式例であり、ゲームの確定時刻ではありません。',font=self.ui(8),wraplength=550)
        frame=tk.Frame(win,bg='#202020'); frame.pack(fill='both',expand=True,padx=6)
        text=tk.Text(frame,bg='#15191e',fg='white',insertbackground='white',wrap='none',height=18,width=70)
        bar=tk.Scrollbar(frame,command=text.yview); text.configure(yscrollcommand=bar.set)
        bar.pack(side='right',fill='y'); text.pack(fill='both',expand=True)
        text.insert('1.0',json.dumps(self.tracker.catalog,ensure_ascii=False,indent=2))
        def save():
            try:
                value=validate_catalog(json.loads(text.get('1.0','end')))
                self.write_tracker_json(self.catalog_path,value)
                self.tracker.catalog=value; self.tracker.previous=None
                # A changed reset definition starts a new baseline, not a false reset.
                self.tracker.state['periods'].clear(); self.save_tracker()
            except (OSError,ValueError,TypeError,KeyError) as exc:
                messagebox.showerror('保存できません',str(exc),parent=win); return
            self._safe_dialog_close(win)
            if self.active_tab in ('il','daily','weekly','bosses'): self.show_tab(self.active_tab)
            elif self.active_tab=='events': self.rebuild_event_widgets()
        self.button(win,'保存して反映',save).pack(pady=6)
        win.geometry('610x650'); win.deiconify()
