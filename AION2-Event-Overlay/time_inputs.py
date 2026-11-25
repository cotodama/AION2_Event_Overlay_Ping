"""Larger, shared selectors. Existing JSON/text values remain the persistence format."""
import calendar
import datetime as dt
import math
import tkinter as tk
from tkinter import ttk

BG='#202020'

def stop_wheel(box):
    # Wheel scrolls the form, never silently changes a time under the pointer.
    def wheel(event):
        parent=box.master
        while parent is not None:
            canvas=getattr(parent,'_time_scroll_canvas',None)
            if canvas is not None:
                canvas.yview_scroll(-int(event.delta/120),'units');break
            parent=getattr(parent,'master',None)
        return 'break'
    box.bind('<MouseWheel>',wheel)

def protect_selectors(widget):
    if isinstance(widget,ttk.Combobox):stop_wheel(widget)
    for child in widget.winfo_children():protect_selectors(child)

class ValueControl:
    def __init__(self,parent,app,variable=None,value='',bg=None):
        self.app=app;self.bg=bg or parent.cget('bg');self.frame=tk.Frame(parent,bg=self.bg)
        self.variable=variable if variable is not None else tk.StringVar(parent,value=str(value))
        self.busy=False;self.combos=[];self.variables=[]
    def pack(self,**kw):self.frame.pack(**kw);return self
    def get(self):return self.variable.get()
    def set(self,value):self.variable.set(str(value))
    def delete(self,*_):self.set('')
    def insert(self,_,value):self.set(value)
    def configure(self,**kw):
        state=kw.pop('state',None)
        if state:
            for box in self.combos:box.configure(state='disabled' if state in ('readonly','disabled') else 'readonly')
        if kw:self.frame.configure(**kw)
    def box(self,values,initial,unit,width=3,parent=None):
        parent=parent or self.frame
        var=tk.StringVar(parent,value=str(initial));self.variables.append(var)
        box=ttk.Combobox(parent,textvariable=var,values=list(values),width=width,state='readonly',font=self.app.ui(12))
        box.pack(side='left',ipady=4,padx=(0,2));self.combos.append(box);stop_wheel(box)
        tk.Label(parent,text=unit,bg=self.bg,fg='white',font=self.app.ui(10)).pack(side='left',padx=(0,7))
        return var

class DatePicker(ValueControl):
    def __init__(self,parent,app,variable=None,value=None,**kw):
        super().__init__(parent,app,variable,value or dt.date.today().isoformat(),**kw)
        try:date=dt.date.fromisoformat(self.get())
        except ValueError:date=dt.date.today()
        years=sorted(set(range(2000,2101))|{date.year})
        self.year=self.box(years,date.year,'年',5)
        self.month=self.box([f'{n:02}' for n in range(1,13)],f'{date.month:02}','月')
        self.day=self.box([f'{n:02}' for n in range(1,32)],f'{date.day:02}','日')
        self._from_value()
        self.variable.trace_add('write',self._from_value)
        for v in self.variables:v.trace_add('write',self._to_value)
    def _from_value(self,*_):
        if self.busy:return
        try:date=dt.date.fromisoformat(self.get())
        except ValueError:return
        self.busy=True
        try:
            if str(date.year) not in tuple(str(v) for v in self.combos[0].cget('values')):
                self.combos[0].configure(values=sorted(set(map(int,self.combos[0].cget('values')))|{date.year}))
            self.year.set(str(date.year));self.month.set(f'{date.month:02}');self.day.set(f'{date.day:02}')
            self.combos[2].configure(values=[f'{n:02}' for n in range(1,calendar.monthrange(date.year,date.month)[1]+1)])
        finally:self.busy=False
    def _to_value(self,*_):
        if self.busy:return
        self.busy=True
        try:
            year,month=int(self.year.get()),int(self.month.get());last=calendar.monthrange(year,month)[1]
            day=min(int(self.day.get()),last);self.day.set(f'{day:02}')
            self.combos[2].configure(values=[f'{n:02}' for n in range(1,last+1)])
            self.set(dt.date(year,month,day).isoformat())
        finally:self.busy=False

class ClockPicker(ValueControl):
    def __init__(self,parent,app,variable=None,value='00:00',**kw):
        super().__init__(parent,app,variable,value,**kw)
        for limit,unit in ((24,'時'),(60,'分'),(60,'秒')):self.box([f'{n:02}' for n in range(limit)],'00',unit)
        self._from_value();self.variable.trace_add('write',self._from_value)
        for v in self.variables:v.trace_add('write',self._to_value)
    def _from_value(self,*_):
        if self.busy:return
        try:value=dt.time.fromisoformat(self.get())
        except ValueError:return
        self.busy=True
        try:
            for v,n in zip(self.variables,(value.hour,value.minute,value.second)):v.set(f'{n:02}')
        finally:self.busy=False
    def _to_value(self,*_):
        if self.busy:return
        h,m,s=(int(v.get()) for v in self.variables)
        self.set(f'{h:02}:{m:02}'+(f':{s:02}' if s else ''))

class DateTimePicker(ValueControl):
    def __init__(self,parent,app,variable=None,value='',**kw):
        super().__init__(parent,app,variable,value,**kw)
        try:
            at=dt.datetime.fromisoformat(self.get())
            if at.tzinfo:at=at.astimezone(dt.timezone(dt.timedelta(hours=9)))
        except ValueError:at=dt.datetime.now()
        self.date=DatePicker(self.frame,app,value=at.date().isoformat()).pack(fill='x',pady=3)
        self.clock=ClockPicker(self.frame,app,value=at.strftime('%H:%M:%S')).pack(fill='x',pady=3)
        self.combos=self.date.combos+self.clock.combos
        self.variable.trace_add('write',self._from_value)
        self.date.variable.trace_add('write',self._to_value);self.clock.variable.trace_add('write',self._to_value)
    def _from_value(self,*_):
        if self.busy:return
        try:
            at=dt.datetime.fromisoformat(self.get())
            if at.tzinfo:at=at.astimezone(dt.timezone(dt.timedelta(hours=9)))
        except ValueError:return
        self.busy=True
        try:self.date.set(at.date().isoformat());self.clock.set(at.strftime('%H:%M:%S'))
        finally:self.busy=False
    def _to_value(self,*_):
        if self.busy:return
        self.busy=True
        try:self.set(self.date.get()+' '+self.clock.get())
        finally:self.busy=False

class MinutesPicker(ValueControl):
    def __init__(self,parent,app,variable=None,value='0',maximum=525600,seconds=True,**kw):
        super().__init__(parent,app,variable,value,**kw)
        self.hour=self.box(range(int(maximum)//60+1),0,'時間',4)
        self.minute=self.box([f'{n:02}' for n in range(60)],'00','分')
        self.second=self.box([f'{n:02}' for n in range(60)],'00','秒') if seconds else None
        self._from_value();self.variable.trace_add('write',self._from_value)
        for v in self.variables:v.trace_add('write',self._to_value)
    def _from_value(self,*_):
        if self.busy:return
        try:
            n=float(self.get())
            if not math.isfinite(n) or n<0:return
            total=round(n*60);hours,rest=divmod(total,3600);minutes,seconds=divmod(rest,60)
        except ValueError:return
        self.busy=True
        try:
            self.hour.set(str(hours));self.minute.set(f'{minutes:02}')
            if self.second:self.second.set(f'{seconds:02}')
        finally:self.busy=False
    def _to_value(self,*_):
        if self.busy:return
        n=int(self.hour.get())*60+int(self.minute.get())+(int(self.second.get())/60 if self.second else 0)
        self.set(f'{n:.10f}'.rstrip('0').rstrip('.') if isinstance(n,float) else str(n))

class PeriodPicker(MinutesPicker):
    """Hours/minutes first, with optional seconds for existing precise periods."""
    def __init__(self,parent,app,variable=None,value='660',**kw):
        self.optional_ready=False
        outer=tk.Frame(parent,bg=parent.cget('bg'))
        super().__init__(outer,app,variable=variable,value=value,seconds=True,**kw)
        self.row=self.frame;self.row.pack(fill='x');self.frame=outer
        children=self.row.winfo_children();self.second_label=children[children.index(self.combos[2])+1]
        self.show_seconds=tk.BooleanVar(outer,value=int(self.second.get())!=0)
        tk.Checkbutton(outer,text='秒も指定',variable=self.show_seconds,command=self.toggle_seconds,
            bg=self.bg,fg='white',selectcolor='#26303a',activebackground=self.bg,activeforeground='white',
            font=app.ui(10)).pack(anchor='w',pady=(3,0))
        self.optional_ready=True;self.toggle_seconds()
    def toggle_seconds(self):
        if self.show_seconds.get():
            self.combos[2].pack(side='left',ipady=4,padx=(0,2));self.second_label.pack(side='left',padx=(0,7))
        else:
            # Never hide a nonzero saved period remainder from the user.
            if int(self.second.get()):self.show_seconds.set(True);return
            self.combos[2].pack_forget();self.second_label.pack_forget()
    def _from_value(self,*_):
        super()._from_value()
        if getattr(self,'optional_ready',False):
            if int(self.second.get()):self.show_seconds.set(True)
            self.toggle_seconds()

class WeekdayPicker(ValueControl):
    def __init__(self,parent,app,variable=None,value='',**kw):
        super().__init__(parent,app,variable,value,**kw)
        self.checks=[]
        for n,title in enumerate('月火水木金土日'):
            var=tk.BooleanVar(self.frame);self.variables.append(var)
            cb=tk.Checkbutton(self.frame,text=title,variable=var,bg=self.bg,fg='white',selectcolor='#26303a',
                activebackground=self.bg,activeforeground='white',font=app.ui(11),command=self._to_value)
            cb.pack(side='left');self.checks.append(cb)
        self._from_value();self.variable.trace_add('write',self._from_value)
    def _from_value(self,*_):
        if self.busy:return
        values=self.get().split(',');self.busy=True
        try:
            for n,v in enumerate(self.variables):v.set(str(n) in values)
        finally:self.busy=False
    def _to_value(self):self.set(','.join(str(n) for n,v in enumerate(self.variables) if v.get()))

class ClockList(ValueControl):
    def __init__(self,parent,app,variable=None,value='',windows=False,**kw):
        super().__init__(parent,app,variable,value,**kw);self.rows=[];self.windows=windows
        self.body=tk.Frame(self.frame,bg=self.bg);self.body.pack(fill='x')
        tk.Button(self.frame,text='＋時間帯' if windows else '＋時刻',bg='#26303a',fg='white',relief='flat',
            font=app.ui(10),command=lambda:self.add('00:00-01:00' if windows else '00:00')).pack(anchor='w',pady=4)
        self._from_value();self.variable.trace_add('write',self._from_value)
    def _from_value(self,*_):
        if self.busy:return
        self.busy=True
        try:
            for row in self.rows:row['frame'].destroy()
            self.rows=[]
            for value in filter(None,self.get().split(',')):self.add(value,False)
        finally:self.busy=False
    def add(self,value='00:00',notify=True):
        row=tk.Frame(self.body,bg=self.bg);row.pack(fill='x',pady=4)
        record={'frame':row,'clocks':[]};self.rows.append(record)
        for n,time in enumerate(value.split('-') if self.windows else [value]):
            if self.windows:tk.Label(row,text='開始' if n==0 else '終了',bg=self.bg,fg='#bcdcff',font=self.app.ui(10)).pack(anchor='w')
            clock=ClockPicker(row,self.app,value=time).pack(anchor='w',pady=2);record['clocks'].append(clock)
            clock.variable.trace_add('write',self._to_value)
        def remove():self.rows.remove(record);row.destroy();self._to_value()
        record['remove']=tk.Button(row,text='削除',command=remove,bg='#402c2c',fg='white',relief='flat',font=self.app.ui(10))
        record['remove'].pack(anchor='e')
        if notify:self._to_value()
        return record
    def _to_value(self,*_):
        if self.busy:return
        self.busy=True
        try:self.set(','.join('-'.join(clock.get() for clock in row['clocks']) for row in self.rows))
        finally:self.busy=False
