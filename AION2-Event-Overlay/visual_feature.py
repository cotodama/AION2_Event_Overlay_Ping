"""Selectable palettes, local portraits, pictograms and countdown gauges."""
import datetime as dt,math,re,shutil
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog

PALETTES={
 'Abyss':dict(root='#101e24',card='#152b32',button='#203f48',border='#54747a',text='#edf5f4',muted='#a4b9bd',accent='#65bdc8'),
 'Black':dict(root='#080a0c',card='#14171a',button='#242c32',border='#46515a',text='#eef3f6',muted='#9caab5',accent='#1d9bf0'),
 'Midnight':dict(root='#0c1726',card='#14243a',button='#213c57',border='#43637e',text='#e8f2fc',muted='#9db0c8',accent='#53aeea'),
 'Discord':dict(root='#232428',card='#2b2d31',button='#383a40',border='#535762',text='#f2f3f5',muted='#b5bac1',accent='#929bff'),
 'Adobe':dict(root='#232323',card='#303030',button='#424242',border='#5a5a5a',text='#f0f0f0',muted='#b8b8b8',accent='#54a6ec'),
 'Classic':dict(root='#202020',card='#15191e',button='#202934',border='#555555',text='#ffffff',muted='#c5ccd6',accent='#79c9ff'),
}
ACCENTS={'Default':None,'Blue':'#399fe9','Cyan':'#65c8d5','Green':'#69c6a8','Gold':'#ccb477','Purple':'#ae9deb'}

class Switch(tk.Canvas):
    def __init__(self,parent,value,command):
        super().__init__(parent,width=46,height=25,bg=parent.cget('bg'),highlightthickness=0,takefocus=1,cursor='hand2')
        self.value=bool(value);self.command=command;self.draw()
        self.bind('<Button-1>',lambda e:self.invoke());self.bind('<space>',lambda e:self.invoke())
    def draw(self):
        self.delete('all');color='#399fe9' if self.value else '#46505b'
        self.create_line(13,12,33,12,fill=color,width=21,capstyle='round')
        x=33 if self.value else 13;self.create_oval(x-8,4,x+8,20,fill='#f0f6fc',outline='')
    def invoke(self):self.value=not self.value;self.draw();self.command(self.value)

class VisualFeatureMixin:
    def init_visuals(self):
        self.cfg.setdefault('ui_theme','Abyss');self.cfg.setdefault('ui_accent','Default');self.cfg.setdefault('show_countdown_gauges',True)
        self._picture_cache={};self._theme_busy=False;self._theme_after=None
        def mapped(event):
            if isinstance(event.widget,(tk.Toplevel,tk.Tk)) and not self._theme_busy:self.root.after_idle(self.apply_visual_theme)
        self.root.bind('<Map>',mapped,add='+')

    def theme_colors(self):
        colors=dict(PALETTES.get(self.cfg.get('ui_theme'),PALETTES['Abyss']))
        colors['accent']=ACCENTS.get(self.cfg.get('ui_accent')) or colors['accent'];return colors

    def theme_controls(self,parent):
        self.label(parent,self.tr('配色・表示','Appearance'),font=self.ui(10,'bold')).pack(anchor='w',padx=10,pady=(10,4))
        row=tk.Frame(parent,bg=parent.cget('bg'));row.pack(fill='x',padx=10,pady=4)
        theme=tk.StringVar(parent,value=self.cfg['ui_theme']);accent=tk.StringVar(parent,value=self.cfg['ui_accent'])
        for var,values,width in ((theme,list(PALETTES),14),(accent,list(ACCENTS),11)):
            box=ttk.Combobox(row,textvariable=var,values=values,state='readonly',width=width,font=self.ui(11));box.pack(side='left',padx=(0,7),ipady=4)
        def change(*_):
            from AION2_Event_Overlay import save_config
            self.cfg.update(ui_theme=theme.get(),ui_accent=accent.get());save_config(self.cfg);self.apply_visual_theme()
        theme.trace_add('write',change);accent.trace_add('write',change)
        gauge=tk.BooleanVar(parent,value=self.cfg['show_countdown_gauges'])
        def set_gauge():
            from AION2_Event_Overlay import save_config
            self.cfg['show_countdown_gauges']=gauge.get();save_config(self.cfg);self.refresh_countdown_gauges()
        tk.Checkbutton(parent,text=self.tr('通常表示に出現ゲージを表示','Show countdown gauges in normal view'),variable=gauge,command=set_gauge,
            bg=parent.cget('bg'),fg='white',selectcolor='#26303a',font=self.ui(10)).pack(anchor='w',padx=8,pady=5)
        self.button(parent,self.tr('通知一覧・スイッチ','Alert dashboard'),self.open_alert_dashboard,padx=12,pady=5).pack(anchor='w',padx=10,pady=5)
        self._theme_controls=dict(theme=theme,accent=accent,gauge=gauge)

    def _theme_color(self,value):
        colors=self.theme_colors();value=str(value).lower()
        if value in ('#202020','#101215'):return colors['root']
        if value in ('#15191e','#10151b','#181e25'):return colors['card']
        if value in ('#202934','#26303a','#344558','#26394d'):return colors['button']
        if value in ('#555555','#52606b','#596878','#38414b','#43505c','#303842','#252c35'):return colors['border']
        if value in ('white','#ffffff','#f5f5f5','#f1f5f9','#dcecff'):return colors['text']
        if value in ('#c5ccd6','#b8c4d0','#aeb9c7','#8fa0b4'):return colors['muted']
        if value in ('#79c9ff','#bcdcff'):return colors['accent']
        return value

    def asset_picture(self,path,size=24):
        path=Path(path)
        if not path.is_file():return None
        key=(str(path),size,path.stat().st_mtime_ns)
        if key not in self._picture_cache:
            try:
                photo=tk.PhotoImage(master=self.root,file=str(path));factor=max(1,math.ceil(max(photo.width(),photo.height())/size))
                self._picture_cache[key]=photo.subsample(factor)
            except tk.TclError:return None
        return self._picture_cache[key]

    def boss_picture(self,item,size=32):
        from AION2_Event_Overlay import resource_path,USER_DATA_DIR
        from boss_groups import members
        row=members(item)[0]
        if row.get('icon_file'):
            try:
                # Custom assets are explicitly allowed only below data/assets/bosses.
                path=(Path(USER_DATA_DIR)/row['icon_file']).resolve()
                path.relative_to((Path(USER_DATA_DIR)/'assets'/'bosses').resolve())
                picture=self.asset_picture(path,size)
                if picture:return picture
            except Exception:pass
        ident=row['id'];name=next((name for prefix,name in [('gartua','gartua'),('ragta','ragta'),('spirit-king','argo'),('executor-argo','argo'),('executor-kaira','kaira'),('watcher-kaira','kaira'),('guardian-nafma','nafma')] if ident.startswith(prefix)),'')
        return self.asset_picture(resource_path('assets/bosses/'+name+'.png'),size) if name else self.asset_picture(resource_path('assets/icons/boss.png'),size)

    def choose_boss_picture(self,item):
        from AION2_Event_Overlay import USER_DATA_DIR
        from boss_groups import members
        path=filedialog.askopenfilename(parent=self.root,filetypes=[('PNG / GIF','*.png *.gif')])
        if not path or not self.asset_picture(path,32):return
        for row in members(item):
            relative='assets/bosses/'+re.sub('[^a-zA-Z0-9_-]','_',row['id'])+Path(path).suffix.lower()
            target=Path(USER_DATA_DIR)/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
            actual=next(r for r in self.tracker.catalog['bosses'] if r['id']==row['id']);actual['icon_file']=relative
        self.write_tracker_json(self.catalog_path,self.tracker.catalog);self.rebuild_event_widgets()
        if self.active_tab=='bosses':self.show_tab('bosses')

    def apply_visual_theme(self):
        if self._theme_busy or not self.root.winfo_exists():return
        self._theme_busy=True
        try:
            def walk(widget):
                for option in ('bg','fg','activebackground','activeforeground','selectcolor','highlightbackground','insertbackground'):
                    try:
                        base=getattr(widget,'_theme_base',{});current=widget.cget(option)
                        if option not in base:base[option]=current;widget._theme_base=base
                        widget.configure(**{option:self._theme_color(base[option])})
                    except tk.TclError:pass
                if isinstance(widget,tk.Canvas):
                    for item in widget.find_all():
                        if 'gauge' in widget.gettags(item):continue
                        for option in ('fill','outline'):
                            try:
                                key=(item,option);base=getattr(widget,'_theme_items',{})
                                if key not in base:base[key]=widget.itemcget(item,option);widget._theme_items=base
                                if base[key]:widget.itemconfigure(item,**{option:self._theme_color(base[key])})
                            except tk.TclError:pass
                if isinstance(widget,tk.Button):
                    text=widget.cget('text');icon={'⚙':'settings','⏱':'timer','⏱️':'timer','✥':'move','✥️':'move','🔔':'bell','🔕':'bell-off','▶️':'play','▶':'play','⏸️':'pause','+':'plus','×':'close'}.get(text)
                    if icon:
                        from AION2_Event_Overlay import resource_path
                        photo=self.asset_picture(resource_path('assets/icons/'+icon+'.png'))
                        if photo:widget.configure(image=photo,compound='none');widget._pictogram=photo
                for child in widget.winfo_children():walk(child)
            walk(self.root)
            c=self.theme_colors();style=ttk.Style(self.root)
            style.configure('TCombobox',fieldbackground=c['card'],background=c['button'],foreground=c['text'],arrowcolor=c['accent'])
            style.map('TCombobox',fieldbackground=[('readonly',c['card'])],foreground=[('readonly',c['text'])])
            style.configure('TProgressbar',background=c['accent'],troughcolor=c['card'])
            self.sync_drag_surface()
        finally:self._theme_busy=False

    def refresh_countdown_gauges(self):
        from event_model import next_start,JST
        from boss_groups import next_boss_occurrence
        from display_format import precise_remaining
        now=dt.datetime.now(JST);enabled=self.cfg.get('show_countdown_gauges',True) and not self.cfg.get('event_compact',False)
        rows=[(e,cv,next_start(e,now),False) for e,cv,*_ in getattr(self,'event_widgets',[])]
        rows += [(e,cv,next_boss_occurrence(e,now)[0],True) for e,cv,*_ in getattr(self,'field_boss_widgets',[])]
        for e,cv,title,status,clock in getattr(self,'event_widgets',[]):
            for ident in (status,clock):cv.itemconfigure(ident,state='hidden' if enabled or self.cfg.get('event_compact',False) else 'normal')
        for e,cv,clock,status,*_ in getattr(self,'field_boss_widgets',[]):
            cv.itemconfigure(status,state='hidden' if enabled or self.cfg.get('event_compact',False) else 'normal')
        for item,canvas,nxt,boss in rows:
            canvas.delete('gauge')
            if not enabled:continue
            width=canvas.winfo_width();right=max(80,width-12);left=48
            schedule=item.get('schedule') or {}
            if boss:
                from boss_groups import members
                schedule=members(item)[0].get('schedule') or {}
            remaining=(nxt-now).total_seconds() if nxt else 0;span=float(schedule.get('minutes',item.get('interval_minutes',1440)))*60
            active=False
            if not boss:
                status,secs,remain=self.event_status(item,now)
                if status in ('entry','active'):
                    active=True;remaining=remain if status=='active' else secs
                    span=max(1,float(item.get('duration_minutes' if status=='active' else 'entry_minutes',1))*60)
            fraction=max(0,min(1,1-remaining/max(1,span))) if nxt or active else 0
            c=self.theme_colors();color='#d7b96f' if 0<remaining<=300 else c['accent']
            canvas.create_rectangle(left,35,right,57,fill=c['card'],outline=c['border'],tags='gauge')
            if fraction:canvas.create_rectangle(left+1,36,left+1+(right-left-2)*fraction,56,fill=color,outline='',tags='gauge')
            text=(self.tr('開催中 あと ','Active · ')+precise_remaining(remaining) if active else
                (precise_remaining(remaining)+' · '+nxt.astimezone(JST).strftime('%H:%M JST') if nxt else self.tr('予定未確認','Schedule unknown')))
            canvas.create_text((left+right)/2,46,text=text,fill=c['text'],font=self.ui(8,'bold'),tags='gauge')
            picture=self.boss_picture(item,28) if boss else None
            if not picture:
                from AION2_Event_Overlay import resource_path
                picture=self.asset_picture(resource_path('assets/icons/boss.png'),24)
            if picture:canvas.create_image(27,46,image=picture,tags='gauge')

    def refresh_button_icons(self):
        from AION2_Event_Overlay import resource_path
        def walk(widget):
            if isinstance(widget,tk.Button):
                text=widget.cget('text');icon={'⚙':'settings','⏱':'timer','✥':'move','🔔':'bell','🔕':'bell-off','▶️':'play','▶':'play','⏸️':'pause','+':'plus','×':'close'}.get(text)
                if icon and getattr(widget,'_icon_name',None)!=icon:
                    photo=self.asset_picture(resource_path('assets/icons/'+icon+'.png'))
                    if photo:widget.configure(image=photo,compound='none');widget._pictogram=photo;widget._icon_name=icon
            for child in widget.winfo_children():walk(child)
        walk(self.root)

    def open_alert_dashboard(self):
        from boss_groups import boss_display_items,members,next_boss_occurrence
        from event_model import next_start,JST
        from tracker_model import next_occurrence
        from display_format import precise_remaining
        from time_inputs import MinutesPicker,protect_selectors
        from ping_feature import ScrollArea
        from AION2_Event_Overlay import save_config
        existing=self._dialog_windows.get('alert_dashboard')
        if existing is not None and existing.winfo_exists():existing.lift();return
        win=self._new_dialog(self.tr('イベントアラート','Event alerts'));win.configure(bg='#202020');win.resizable(True,True)
        self._dialog_windows['alert_dashboard']=win;self.label(win,self.tr('通知を個別に切り替え・音を試聴','Enable alerts and preview sounds'),font=self.ui(11,'bold')).pack(anchor='w',padx=12,pady=10)
        area=ScrollArea(win,height=480);area.frame.pack(fill='both',expand=True,padx=8,pady=8);rows=[];self._alert_switches=[]
        def persist_event(e,key,value):
            e[key]=value;save_config(self.cfg)
            if key=='enabled':self.rebuild_event_widgets()
        def persist_boss(item,value):
            for r in members(item):self.tracker.state['bells'][r['id']]=value
            self.save_tracker();self.rebuild_event_widgets()
        items=[('event',e) for e in self.cfg['events']]+[('boss',b) for b in boss_display_items(self.tracker.catalog['bosses'])]
        items += [(key,item) for key in ('daily','weekly') for item in self.tracker.catalog[key]]
        for kind,item in items:
            card=tk.Frame(area.body,bg='#15191e');card.pack(fill='x',pady=3);head=tk.Frame(card,bg='#15191e');head.pack(fill='x',padx=8,pady=6)
            name=self.event_name(item) if kind=='event' else item['name']
            if kind=='boss':
                photo=self.boss_picture(item,32)
                if photo:tk.Label(head,image=photo,bg='#15191e').pack(side='left',padx=(0,8))
            self.label(head,name,font=self.ui(10,'bold'),wraplength=300,justify='left').pack(side='left',fill='x',expand=True)
            enabled=item.get('alert_enabled',True) if kind=='event' else self.boss_bell(item) if kind=='boss' else self.tracker.bell(item['id'])
            def change(value,k=kind,e=item):
                if k=='event':persist_event(e,'alert_enabled',value)
                elif k=='boss':persist_boss(e,value)
                else:self.tracker.state['bells'][e['id']]=value;self.save_tracker()
            self.label(head,'通知').pack(side='left',padx=4);switch=Switch(head,enabled,change);switch.pack(side='left');self._alert_switches.append((kind,item,switch))
            label=self.label(card,'',fg='#bcdcff');label.pack(anchor='w',padx=8);rows.append((kind,item,label))
            controls=tk.Frame(card,bg='#15191e');controls.pack(fill='x',padx=8,pady=5)
            if kind=='event':
                self.label(controls,'音').pack(side='left');Switch(controls,item.get('sound_enabled',True),lambda v,e=item:persist_event(e,'sound_enabled',v)).pack(side='left',padx=4)
                self.button(controls,'通知音・リードタイム',lambda e=item:self.open_event_notification_settings(e)).pack(side='left',padx=4)
                self.button(controls,'試聴',lambda e=item:self.play_event_alert(e,preview=True)).pack(side='left')
                lead=tk.StringVar(win,value=str(item.get('notify_before_minutes',0)));MinutesPicker(card,self,variable=lead,maximum=10080,seconds=False).pack(fill='x',padx=8)
                def apply_lead(e=item,v=lead):
                    e['notify_before_minutes']=int(v.get());e.pop('notification_leads',None);save_config(self.cfg)
                self.button(card,'通知リードタイムを適用',apply_lead).pack(anchor='w',padx=8,pady=4)
            else:
                lead=tk.StringVar(win,value=str(self.tracker.lead(item['id'])));MinutesPicker(card,self,variable=lead,maximum=10080,seconds=False).pack(fill='x',padx=8)
                self.button(controls,'通知時刻を適用',lambda e=item,v=lead,k=kind:self.set_boss_lead(e,v.get()) if k=='boss' else self.set_tracker_lead(e['id'],v.get())).pack(side='left')
                self.button(controls,'試聴',lambda:self.play_event_alert(preview=True)).pack(side='left',padx=4)
            if kind=='boss':self.button(controls,'画像を変更',lambda e=item:self.choose_boss_picture(e)).pack(side='right')
            area.install_wheel(card)
        for timer in self.timers:
            card=tk.Frame(area.body,bg='#15191e');card.pack(fill='x',pady=3)
            self.label(card,timer.name,font=self.ui(10,'bold')).pack(side='left',padx=8,pady=8)
            def set_running(value,t=timer):
                t.start() if value else t.stop();self.save_timers()
            Switch(card,timer.running,set_running).pack(side='left',padx=5)
            self.label(card,'通知音').pack(side='left')
            def set_alert(value,t=timer):t.alert_enabled=value;self.save_timers()
            Switch(card,timer.alert_enabled,set_alert).pack(side='left',padx=5)
        def refresh():
            if not win.winfo_exists():return
            now=dt.datetime.now(JST)
            for kind,item,label in rows:
                nxt=next_start(item,now) if kind=='event' else next_boss_occurrence(item,now)[0] if kind=='boss' else next_occurrence(self.tracker.catalog['resets'].get(kind),now)
                label.configure(text=(precise_remaining((nxt-now).total_seconds())+' · '+nxt.astimezone(JST).strftime('%m/%d %H:%M JST')) if nxt else '予定未確認')
            for kind,item,switch in self._alert_switches:
                enabled=item.get('alert_enabled',True) if kind=='event' else self.boss_bell(item) if kind=='boss' else self.tracker.bell(item['id'])
                if switch.value!=enabled:switch.value=enabled;switch.draw()
            win.after(500,refresh)
        refresh();protect_selectors(win);self._place_compact_dialog(win,660,600);self.reveal_dialog(win)
