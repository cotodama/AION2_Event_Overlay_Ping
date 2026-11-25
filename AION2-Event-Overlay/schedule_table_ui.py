"""Dropdown schedule tables used by the NM editor."""
import datetime as dt
import tkinter as tk
from tkinter import ttk,messagebox
from schedule_table_model import JST,clock_text,table_schedule

BG='#202020'

class ScheduleTables:
    def __init__(self,parent,app,changed,area):
        self.app=app;self.changed=changed;self.area=area;self.loading=False
        self.frame=tk.Frame(parent,bg=BG)
        self.hint=app.label(self.frame,'',anchor='w',wraplength=380,fg='#bcdcff');self.hint.pack(fill='x',pady=4)
        self.pages={};self.groups={};self.rows={};self.kind=None
        for kind in ('weekly_times','dates'):
            self.pages[kind]=tk.Frame(self.frame,bg=BG);self.groups[kind]={};self.rows[kind]={}
        addbar=tk.Frame(self.pages['dates'],bg=BG);addbar.pack(fill='x',pady=4)
        self.date=tk.StringVar(parent,value=dt.datetime.now(JST).date().isoformat())
        from time_inputs import DatePicker
        self.date_picker=DatePicker(addbar,app,variable=self.date).pack(fill='x')
        app.button(addbar,'日付を追加',self.add_date).pack(anchor='w',pady=4)

    def touch(self,*_):
        if not self.loading:self.changed()

    def add_date(self):
        try:
            value=self.date.get().strip()
            if dt.date.fromisoformat(value).isoformat()!=value:raise ValueError('日付は YYYY-MM-DD で入力してください')
            if value not in self.groups['dates']:self.group('dates',value);self.touch()
        except ValueError as exc:messagebox.showerror('日付の追加',str(exc),parent=self.frame.winfo_toplevel())

    def group(self,kind,key):
        card=tk.Frame(self.pages[kind],bg=BG,highlightthickness=1,highlightbackground='#38414b')
        card.pack(fill='x',pady=4)
        heading=tk.Frame(card,bg=BG);heading.pack(fill='x',padx=5,pady=3)
        text='月火水木金土日'[int(key)]+'曜日' if kind=='weekly_times' else key+'（'+'月火水木金土日'[dt.date.fromisoformat(key).weekday()]+'）'
        self.app.label(heading,text,anchor='w',font=self.app.ui(10,'bold')).pack(side='left')
        add=self.app.button(heading,'＋時刻',lambda:self.add_time(kind,key,'00:00'));add.pack(side='right')
        if kind=='dates':self.app.button(heading,'日付削除',lambda:self.remove_group(kind,key)).pack(side='right',padx=4)
        self.groups[kind][key]=card;self.rows[kind][key]=[]
        self.area.install_wheel(card);self.area.install_wheel(heading)
        for child in heading.winfo_children():self.area.install_wheel(child)

    def remove_group(self,kind,key):
        self.groups[kind].pop(key).destroy();self.rows[kind].pop(key);self.touch()

    def add_time(self,kind,key,value='00:00'):
        at=dt.time.fromisoformat(value)
        row=tk.Frame(self.groups[kind][key],bg=BG);row.pack(fill='x',padx=8,pady=3)
        record={'frame':row,'values':[],'combos':[]}
        for n,title in ((at.hour,'時'),(at.minute,'分'),(at.second,'秒')):
            var=tk.StringVar(row,value=f'{n:02}')
            box=ttk.Combobox(row,textvariable=var,values=[f'{i:02}' for i in range(24 if title=='時' else 60)],
                state='readonly',width=4,font=self.app.ui(12));box.pack(side='left',ipady=4)
            self.app.label(row,title).pack(side='left',padx=(1,6));record['values'].append(var);record['combos'].append(box)
            var.trace_add('write',self.touch)
        def remove():
            self.rows[kind][key].remove(record);row.destroy();self.touch()
        record['remove']=self.app.button(row,'削除',remove);record['remove'].pack(side='right')
        self.rows[kind][key].append(record)
        def wheels(w):
            self.area.install_wheel(w)
            if isinstance(w,ttk.Combobox):
                def scroll(event):
                    self.area.canvas.yview_scroll(-int(event.delta/120),'units')
                    return 'break'
                w.bind('<MouseWheel>',scroll)
            for child in w.winfo_children():wheels(child)
        wheels(row);self.touch()
        return record

    def load(self,schedule,now):
        self.loading=True
        try:
            for kind in self.groups:
                for card in self.groups[kind].values():card.destroy()
                self.groups[kind]={};self.rows[kind]={}
            for n in range(7):self.group('weekly_times',str(n))
            schedule=schedule or {};kind=schedule.get('kind')
            if kind in self.groups:
                for key,values in schedule['table'].items():
                    if key not in self.groups[kind]:self.group(kind,key)
                    for value in values:self.add_time(kind,key,value)
                if kind=='dates':
                    # Seed each weekday from its next supplied date, never merge two Wednesdays.
                    for n in range(7):
                        dates=sorted(key for key in schedule['table'] if dt.date.fromisoformat(key).weekday()==n)
                        future=[key for key in dates if dt.date.fromisoformat(key)>=now.date()]
                        key=(future[0] if future else dates[-1]) if dates else None
                        if key:
                            for value in schedule['table'][key]:self.add_time('weekly_times',str(n),value)
            elif kind in ('daily','weekly'):
                for day in (range(7) if kind=='daily' else schedule.get('weekdays',[schedule.get('weekday',0)])):
                    for value in schedule.get('times',[schedule['time']]):self.add_time('weekly_times',str(day),value)
        finally:self.loading=False

    def show(self,kind):
        self.kind=kind
        for page in self.pages.values():page.pack_forget()
        if kind not in self.pages:self.frame.pack_forget();return
        self.hint.configure(text=('曜日ごとに複数の時刻を設定します。毎週繰り返します。空の曜日は通知しません。' if kind=='weekly_times' else
            '指定日だけの予定です。最後の予定が過ぎると終了し、翌週には繰り返しません。')+' 時刻は日本時間。通知の何分前に鳴らすかは下の「通知設定」で変更できます。')
        self.pages[kind].pack(fill='x')

    def schedule(self,kind):
        values={key:[clock_text(':'.join(v.get() for v in row['values'])) for row in rows]
            for key,rows in self.rows[kind].items()}
        return table_schedule(kind,values)
