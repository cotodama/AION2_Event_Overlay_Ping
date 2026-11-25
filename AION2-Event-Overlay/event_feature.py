"""Event notification controls and sound playback, separate from the legacy HUD."""
import array
import datetime as dt
import json
import hashlib
import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
import uuid
import wave
from event_model import event_name, due_notifications, notification_text, next_start, occurrences, JST
from event_maps import RIFT_MAP_LINKS, FIELD_BOSS_MAPS
from boss_groups import boss_display_items,members,next_boss_occurrence,map_label,boss_map_links

class EventFeatureMixin:
    def init_event_map_links(self):
        from AION2_Event_Overlay import save_config
        changed=False
        for e in self.cfg['events']:
            if e.get('name_en')=='Spacetime Rift' and 'map_links' not in e:
                e['map_links']=[dict(row) for row in RIFT_MAP_LINKS]; changed=True
        if changed: save_config(self.cfg)
        catalog_changed=False
        for item in self.tracker.catalog['bosses']:
            if item['id'] in FIELD_BOSS_MAPS and item.get('map_url') in (
                'https://aion2.gaming.tools/ja/maps/1010','https://aion2.gaming.tools/ja/maps/1110'):
                item['map_url']=FIELD_BOSS_MAPS[item['id']]; catalog_changed=True
        if catalog_changed: self.write_tracker_json(self.catalog_path,self.tracker.catalog)

    def event_header_clock(self,e,now):
        from AION2_Event_Overlay import fmt
        from schedule_edit_model import clock
        start=next_start(e,now)
        st,seconds,remain=self.event_status(e,now)
        active=st in ('entry','active')
        if active:
            previous=occurrences(e,now-dt.timedelta(days=1),now)
            if previous: start=previous[-1]
        if start is None:return '終了' if e.get('type')=='once' else '未確認'
        if self.cfg.get('event_compact',False):
            return clock(start)+'\n'+('入場 ' if st=='entry' else '開催 ' if st=='active' else '')+fmt(remain if st=='active' else seconds)
        return ('開始 ' if active else '次 ')+clock(start)+' JST'

    def fit_card_title(self,canvas,title,text,width):
        import tkinter.font as tkfont
        font=tkfont.Font(root=self.root,font=canvas.itemcget(title,'font'))
        shown=text;limit=max(0,width)
        if font.measure(shown)>limit:
            while shown and font.measure(shown+'…')>limit:shown=shown[:-1]
            shown=shown+'…' if font.measure('…')<=limit else ''
        canvas.itemconfigure(title,text=shown)

    def layout_event_header(self,canvas,title,clock,label,right,y):
        canvas.coords(clock,right,y)
        bounds=canvas.bbox(clock)
        clock_width=bounds[2]-bounds[0] if bounds else 0
        self.fit_card_title(canvas,title,label,right-clock_width-24)

    def append_field_boss_events(self):
        from AION2_Event_Overlay import HUD_TRANSPARENT_KEY
        self.field_boss_widgets=[]
        compact=self.cfg.get('event_compact',False)
        for item in boss_display_items(self.tracker.catalog['bosses']):
            height=42 if compact else 118
            canvas=tk.Canvas(self.event_box,height=height,bg=HUD_TRANSPARENT_KEY,highlightthickness=0,bd=0)
            canvas.pack(fill='x',padx=5,pady=3)
            border=canvas.create_rectangle(1,1,1000,height-1,fill=HUD_TRANSPARENT_KEY,outline='#555555')
            prefix=('🌀👹 ' if item.get('boss_type')=='abyss' else '👿 ') if self.cfg.get('show_event_emoji',True) else ''
            title=canvas.create_text(12,17 if not compact else 21,text=prefix+item['name'],anchor='w',fill='#f1f5f9',font=self.ui(9 if compact else 10,'bold'))
            clock=canvas.create_text(180,17 if not compact else 21,text='未確認',anchor='e',fill='#bcdcff',font=self.mono(9,'bold'))
            status=canvas.create_text(12,45,text='出現: 未確認',anchor='w',fill='#dcecff',font=self.small_ui(9,'bold'),state='hidden' if compact else 'normal')
            details=canvas.create_text(12,64,text='',anchor='nw',fill='#c5ccd6',font=self.ui(8),width=300,state='hidden' if compact else 'normal')
            bell=self.make_hud_square_button(canvas,'🔔' if self.boss_bell(item) else '🔕',lambda:None,font=self.small_ui(10))
            bell.configure(command=lambda item=item,b=bell:self.toggle_boss_bell(item,b))
            bell.place(relx=1,x=-7,y=4 if compact else 7,width=34,height=34,anchor='ne')
            for index,link in enumerate(boss_map_links(item)):
                map_button=self.make_hud_square_button(canvas,link['label'],lambda url=link['url']:self.open_tracker_link(url),font=self.ui(8,'bold'))
                map_button.place(relx=1,x=-45-index*56,y=5 if compact else 8,width=52,height=28,anchor='ne')
            right_margin=49+len(boss_map_links(item))*56
            schedule=self.make_hud_square_button(canvas,'編集',lambda row=item:self.edit_boss_group(row),font=self.ui(8))
            if not compact: schedule.place(relx=1,x=-7,y=64,width=32,height=28,anchor='ne')
            canvas._boss_right_margin=right_margin
            def resize(event,cv=canvas,border=border,height=height,title=title,clock=clock,details=details,label=prefix+item['name'],compact=compact,right_margin=right_margin):
                cv.coords(border,1,1,max(2,event.width-1),height-1)
                right=event.width-right_margin
                self.layout_event_header(cv,title,clock,label,right,21 if compact else 17)
                cv.itemconfigure(details,width=max(100,event.width-62))
            canvas.bind('<Configure>',resize)
            self.event_scroll.install_wheel(canvas)
            self.field_boss_widgets.append((item,canvas,clock,status,details,bell,title,prefix))
            canvas.bind('<Button-3>',lambda event,row=item:self.edit_boss_group(row))
            canvas.bind('<Double-Button-1>',lambda event,row=item:self.edit_boss_group(row))

    def update_field_boss_events(self,now):
        from tracker_model import next_occurrence,schedule_text
        from AION2_Event_Overlay import fmt
        compact=self.cfg.get('event_compact',False)
        for item,canvas,clock,status,details,bell,title,prefix in getattr(self,'field_boss_widgets',[]):
            nxt,row=next_boss_occurrence(item,now)
            clock_text=nxt.astimezone(JST).strftime('%m/%d %H:%M:%S' if nxt.second else '%m/%d %H:%M') if nxt else ('予定終了' if any((r.get('schedule') or {}).get('kind')=='dates' for r in members(item)) else '未確認')
            from display_format import remaining_text
            from display_format import precise_remaining
            countdown=(precise_remaining((nxt-now).total_seconds()) if row and (row.get('schedule') or {}).get('edited') else remaining_text((nxt-now).total_seconds())) if nxt else ('終了（今回のみ）' if any((r.get('schedule') or {}).get('kind')=='once' for r in members(item)) else '登録期間の予定は終了' if any((r.get('schedule') or {}).get('kind')=='dates' for r in members(item)) else '未確認（予定を登録）')
            if compact and nxt: clock_text+='\n'+countdown
            canvas.itemconfigure(clock,text=clock_text)
            self.layout_event_header(canvas,title,clock,prefix+item['name'],canvas.winfo_width()-canvas._boss_right_margin,21 if compact else 17)
            canvas.itemconfigure(status,text='次回まで '+countdown+(' / '+row.get('faction','') if row else ''))
            places=' / '.join(r.get('faction','未確認')+': '+r.get('area','未確認').split(' / ')[-1] for r in members(item))
            schedule_display=(row or item).get('schedule_display') or schedule_text((row or item).get('schedule'))
            canvas.itemconfigure(details,text=f"{places}\n装備IL {item.get('equipment_il','未確認')}：{item.get('drops','未確認')}\n{schedule_display}")
            bell.configure(text='🔔' if self.boss_bell(item) else '🔕')

    def init_event_notifications(self, directory):
        self.event_notice_path=Path(directory)/'event_notice_state.json'
        try:
            value=json.loads(self.event_notice_path.read_text(encoding='utf-8'))
            self.event_fired=value if isinstance(value,dict) else {}
        except (OSError,ValueError): self.event_fired={}
        self.event_previous=None; self.event_notice_text=''
        self._sound_queue=[]; self._sound_after=None
        self._event_emoji_controls=[]

    def persist_event_notices(self):
        self.event_notice_path.parent.mkdir(parents=True,exist_ok=True)
        self.event_fired=dict(list(self.event_fired.items())[-512:])
        tmp=self.event_notice_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.event_fired,ensure_ascii=False),encoding='utf-8')
        os.replace(tmp,self.event_notice_path)

    def event_name(self,e):
        return event_name(e,self.cfg.get('language','ja'),self.cfg.get('show_event_emoji',True))

    def set_event_emoji(self, value, refresh=None):
        from AION2_Event_Overlay import save_config
        self.cfg['show_event_emoji']=bool(value); save_config(self.cfg)
        controls=[]
        for widget,variable in getattr(self,'_event_emoji_controls',[]):
            if widget.winfo_exists():
                variable.set(bool(value)); controls.append((widget,variable))
        self._event_emoji_controls=controls
        self.rebuild_event_widgets()
        settings=self._dialog_windows.get('settings')
        if refresh: refresh()
        elif settings is not None and settings.winfo_exists():
            callback=getattr(self,'_refresh_event_settings',None)
            if callback: callback()
        if self.active_tab in ('il','daily','weekly','bosses'): self.show_tab(self.active_tab)
        self._tick_once()

    def build_event_emoji_checkbox(self,parent):
        value=tk.BooleanVar(value=self.cfg.get('show_event_emoji',True))
        background=parent.cget('bg')
        button=tk.Checkbutton(parent,text=self.tr('イベント名に絵文字を表示','Show event name emoji'),
                              variable=value,bg=background,fg='white',selectcolor='#26303a',
                              activebackground=background,activeforeground='white',font=self.ui(9),
                              command=lambda:self.set_event_emoji(value.get()))
        button.pack(anchor='w',padx=10,pady=3)
        controls=[(widget,var) for widget,var in getattr(self,'_event_emoji_controls',[]) if widget.winfo_exists()]
        self._event_emoji_controls=controls+[(button,value)]
        return value

    def set_event_compact(self,value):
        from AION2_Event_Overlay import save_config
        self.cfg['event_compact']=bool(value); save_config(self.cfg)
        for widget,var in getattr(self,'_event_compact_controls',[]):
            if widget.winfo_exists(): var.set(bool(value))
        self.rebuild_event_widgets(); self._tick_once()
        self.root.after_idle(self.fit_window_to_content)

    def build_event_compact_checkbox(self,parent):
        value=tk.BooleanVar(value=self.cfg.get('event_compact',False))
        background=parent.cget('bg')
        button=tk.Checkbutton(parent,text=self.tr('イベント一覧をシンプル表示（1行）','Compact event rows'),
                              variable=value,bg=background,fg='white',selectcolor='#26303a',
                              activebackground=background,activeforeground='white',font=self.ui(9),
                              command=lambda:self.set_event_compact(value.get()))
        button.pack(anchor='w',padx=10,pady=3)
        controls=[(widget,var) for widget,var in getattr(self,'_event_compact_controls',[]) if widget.winfo_exists()]
        self._event_compact_controls=controls+[(button,value)]
        return value

    def tick_event_notifications(self, now):
        messages=[]; changed=False
        for e in self.cfg['events']:
            try:
                for token,start,lead in due_notifications(e,self.event_previous,now):
                    if token in self.event_fired: continue
                    self.event_fired[token]=now.isoformat(); changed=True
                    messages.append(notification_text(e,start,lead,self.cfg.get('show_event_emoji',True)))
                    self._sound_queue.append(dict(e))
            except (ValueError,TypeError,KeyError):
                # A single malformed user event must not stop the other clocks.
                continue
        self.event_previous=now
        if changed:
            self.persist_event_notices()
            self.event_notice_text='\n'.join(messages)
            label=getattr(self,'event_notice_label',None)
            if label:
                label.configure(text=self.event_notice_text)
                label.pack(fill='x',before=self.event_scroll.frame,pady=(0,3))
            if self._sound_after is None: self._drain_sound_queue()

    def _drain_sound_queue(self):
        self._sound_after=None
        if not self._sound_queue: return
        self.play_event_alert(self._sound_queue.pop(0))
        if self._sound_queue: self._sound_after=self.root.after(1200,self._drain_sound_queue)

    def play_event_alert(self, event=None, preview=False):
        e=event or {}
        if not preview and not e.get('sound_enabled',True):return False
        try:
            configured=e.get('sound_volume')
            volume=max(0,min(100,int(self.cfg.get('alert_volume',45) if configured is None else configured)))
            if volume<=0:return False
            cache=self.event_notice_path.parent/'sound_cache';cache.mkdir(parents=True,exist_ok=True)
            signature=hashlib.sha256((str(volume)+str(e.get('id','preview'))).encode('utf-8')).hexdigest()[:16]
            target=cache/('event-default-'+signature+'.wav')
            if not target.exists():
                previous=self.cfg.get('alert_volume',45)
                try:self.cfg['alert_volume']=volume;self.build_alert_wav(output_path=str(target))
                finally:self.cfg['alert_volume']=previous
            custom=str(e.get('sound_file') or self.cfg.get('alert_sound_file','')).strip()
            if custom and Path(custom).is_file() and Path(custom).suffix.lower() in ('.wav','.mp3'):
                return self.audio.play_file(custom,volume/100,'event',fallback=str(target))
            return self.audio.play_file(str(target),1.,'event')
        except (OSError,ValueError,TypeError):return False

    def event_details(self,e,now):
        if e.get('schedule_edited') and e.get('name_en')!='Shugo Festa':
            if not e.get('schedule_confirmed'):return '未確認'
            if e.get('type')=='interval':return 'ユーザー編集：'+str(e['interval_minutes'])+'分間隔 / 基準 '+e.get('interval_anchor','')
            return 'ユーザー編集（日本時間） / '+str(e.get('windows') or e.get('times') or e.get('start') or e.get('at') or '')
        if e.get('name_en')=='Spacetime Rift':
            return '日本参考: 02時から3時間ごと / MAPは候補位置・現在の開通は未確認'
        if e.get('name_en')=='Battlefield' and e.get('schedule_reference'):
            return '日本参考: 11:00〜14:00 / 19:00〜21:00 JST（公開時間表）'
        if not e.get('schedule_confirmed',True): return e.get('schedule_note','未確認')+' / 編集で確認'
        if e.get('name_en')=='Shugo Festa':
            if e.get('schedule_edited'):
                from schedule_edit_model import clock
                previous=occurrences(e,now-dt.timedelta(days=1),now)
                prior=previous[-1] if previous else None
                start=prior if prior and now<prior+dt.timedelta(minutes=float(e.get('entry_minutes',3))) else next_start(e,now)
                if start is None:return '終了（今回のみ）'
                closing=start+dt.timedelta(minutes=float(e.get('entry_minutes',3)))
                nxt=next_start(e,start)
                return '開始 '+clock(start)+' JST / 締切 '+clock(closing)+' JST\n次回 '+(clock(nxt)+' JST' if nxt else '予定なし')+'  🔔 開始予定時刻'
            nxt=next_start(e,now)
            start=nxt-dt.timedelta(hours=1)
            if now>=start and (now-start).total_seconds()<180:
                return f'開始 {start:%H:%M} JST / 締切 {start+dt.timedelta(minutes=3):%H:%M} JST\n次回 {nxt:%H:%M} JST  🔔 開始予定時刻'
            return f'開始 {nxt:%H:%M} JST / 締切 {nxt+dt.timedelta(minutes=3):%H:%M} JST\n次回 {nxt+dt.timedelta(hours=1):%H:%M} JST  🔔 開始予定時刻'
        if e.get('name_en')=='Dimensional Invasion':
            return '陣営のフィールド／ゲーム内の次元侵攻アイコンをタップして入場'
        if e.get('name_en')=='Artifact Siege':
            days='・'.join('月火水木金土日'[n] for n in e.get('weekdays',[]))
            start=next_start(e,now)
            return days+' '+('/'.join(e.get('times',[])))+' JST'+(f'（{start-dt.timedelta(minutes=40):%H:%M}頃 入場推奨）' if start else '')
        return ''

    def open_event_notification_settings(self,e,refresh=None):
        from AION2_Event_Overlay import save_config
        key='event_notice_'+e['id']; existing=self._dialog_windows.get(key)
        if existing is not None and existing.winfo_exists(): existing.lift(); return
        win=self._new_dialog('イベント通知音'); self._dialog_windows[key]=win
        win.configure(bg='#202020'); win.resizable(False,False)
        tk.Label(win,text=self.event_name(e),bg='#202020',fg='white',font=self.ui(11,'bold')).pack(padx=10,pady=10)
        variables={k:tk.BooleanVar(value=e.get(k,True)) for k in ('alert_enabled','sound_enabled')}
        for k,title in [('alert_enabled','ベル通知を有効'),('sound_enabled','通知音を鳴らす')]:
            tk.Checkbutton(win,text=title,variable=variables[k],bg='#202020',fg='white',selectcolor='#26303a',
                           activebackground='#202020',activeforeground='white').pack(anchor='w',padx=10)
        sound=tk.StringVar(value=e.get('sound_file',''))
        tk.Label(win,text='音声ファイル（空欄＝共通設定を使用）',bg='#202020',fg='white').pack(anchor='w',padx=10,pady=(8,2))
        tk.Entry(win,textvariable=sound,bg='#26303a',fg='white',insertbackground='white').pack(fill='x',padx=10)
        row=tk.Frame(win,bg='#202020'); row.pack(fill='x',padx=10,pady=5)
        def choose():
            path=filedialog.askopenfilename(parent=win,filetypes=[('WAV / MP3','*.wav *.mp3')])
            if path: sound.set(path)
        self.button(row,'参照',choose).pack(side='left')
        self.button(row,'共通設定に戻す',lambda:sound.set('')).pack(side='left',padx=5)
        inherit=tk.BooleanVar(value=e.get('sound_volume') is None)
        tk.Checkbutton(win,text='音量も共通設定を使用',variable=inherit,bg='#202020',fg='white',selectcolor='#26303a',
                       activebackground='#202020',activeforeground='white').pack(anchor='w',padx=10)
        volume=tk.Scale(win,from_=0,to=100,orient='horizontal',bg='#202020',fg='white',highlightthickness=0)
        volume.set(e.get('sound_volume') if e.get('sound_volume') is not None else self.cfg.get('alert_volume',45))
        volume.pack(fill='x',padx=10)
        def selection():
            return dict(alert_enabled=variables['alert_enabled'].get(),sound_enabled=variables['sound_enabled'].get(),
                        sound_file=sound.get().strip(),sound_volume=None if inherit.get() else volume.get())
        def save():
            e.update(selection()); save_config(self.cfg); self.rebuild_event_widgets()
            if refresh: refresh()
            self._safe_dialog_close(win)
        footer=tk.Frame(win,bg='#202020'); footer.pack(fill='x',padx=10,pady=10)
        self.button(footer,'試聴',lambda:self.play_event_alert(selection(),preview=True)).pack(side='left')
        self.button(footer,'保存',save).pack(side='right')
        self._place_compact_dialog(win,390,300); win.deiconify(); win.lift()
