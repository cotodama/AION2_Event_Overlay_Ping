"""Minimal Ping view and owned context popup on the existing overlay HWND."""
import tkinter as tk

class PingLayerMixin:
    def initialize_ping_layer(self):
        from ping_feature import ScrollArea
        self._ping_layer=False; self.ping_layer_rows=[]; self._layer_controls=[]
        self._layer_popup=None; self._layer_opacity_save_after=None
        self.ping_cfg.setdefault('ping_layer_show_names',False)
        self.ping_cfg.setdefault('ping_layer_show_grip',False)
        self.ping_cfg.setdefault('ping_layer_clear_background',True)
        self.ping_layer_frame=tk.Frame(self.root,bg='#010203')
        self.ping_layer_area=ScrollArea(self.ping_layer_frame,height=1,bg='#010203')
        self.ping_layer_area.canvas._hud_interactive=False
        self.ping_layer_area.frame.pack(fill='both',expand=True,pady=(0,8))
        self.ping_layer_body=self.ping_layer_area.body
        self.ping_layer_grip=tk.Canvas(self.ping_layer_frame,width=12,height=12,
            bg='#202934',highlightthickness=0,cursor='size_nw_se')
        self.ping_layer_grip.create_polygon(11,1,11,11,1,11,fill='#f1f5f9',outline='')
        self.ping_layer_grip._hud_interactive=True
        if self.ping_cfg['ping_layer_show_grip']:
            self.ping_layer_grip.place(relx=1,rely=1,x=-1,y=-1,anchor='se',width=12,height=12)
        self.ping_layer_grip.bind('<ButtonPress-1>',self._start_ping_layer_resize)
        self.ping_layer_grip.bind('<B1-Motion>',self.resize_drag)
        self.ping_layer_grip.bind('<ButtonRelease-1>',self.resize_end)
        self.root.bind('<Button-3>',self.open_ping_layer_menu,add='+')
        self.drag_surface.bind('<Button-3>',self.open_ping_layer_menu,add='+')

    def install_antenna_icon(self,button):
        # Four ascending signal bars; keep the existing image and button sizes.
        icon=tk.PhotoImage(master=self.root,width=24,height=24)
        for x,height in zip((3,8,13,18),(5,9,13,17)):
            icon.put('#e8f2fc',to=(x,20-height,x+3,20))
        self._antenna_icon=icon; button.configure(image=icon,text='')

    def set_ping_layer_grip(self,value):
        self.ping_cfg['ping_layer_show_grip']=bool(value)
        if value: self.ping_layer_grip.place(relx=1,rely=1,x=-1,y=-1,anchor='se',width=12,height=12)
        else: self.ping_layer_grip.place_forget()
        self.save_ping(); self.refresh_hud_control_rects()

    def set_ping_layer_clear_background(self,value):
        self.ping_cfg['ping_layer_clear_background']=bool(value)
        self.save_ping(); self.sync_drag_surface()

    def build_ping_layer_checkbox(self,parent):
        value=tk.BooleanVar(value=self.ping_cfg.get('ping_layer',False))
        button=tk.Checkbutton(parent,text='シンプルPingレイヤー（アンテナ＋ms）',variable=value,
            command=lambda:self.set_ping_layer(value.get()),bg=parent.cget('bg'),fg='white',
            selectcolor='#26303a',activebackground=parent.cget('bg'),activeforeground='white',font=self.ui(9))
        button.pack(anchor='w',padx=10,pady=3)
        self._layer_controls.append((button,value))

    def size_ping_layer(self):
        self.root.update_idletasks()
        size=self.ping_cfg.get('ping_layer_size') or {}
        width=max(120,min(1400,int(size.get('width',160))))
        height=max(28,min(self.root.winfo_screenheight()-40,int(size.get('height',max(28,len(self.ping_layer_rows)*26+10)))))
        self.ping_cfg['ping_layer_size']={'width':width,'height':height}
        self.root.geometry(f'{width}x{height}+{self.root.winfo_x()}+{self.root.winfo_y()}')

    def rebuild_ping_layer(self):
        for child in self.ping_layer_body.winfo_children(): child.destroy()
        self.ping_layer_rows=[]
        for region,server in self.chosen_endpoints():
            row=tk.Frame(self.ping_layer_body,bg='#010203'); row.pack(fill='x',padx=5,pady=2)
            signal=tk.Canvas(row,width=22,height=22,bg='#010203',highlightthickness=0); signal.pack(side='left',padx=(0,3))
            for i,h in enumerate((4,8,12,17)): signal.create_rectangle(i*5+1,21-h,i*5+4,21,fill='#40ff68',outline='')
            value=self.label(row,'… ms',bg='#010203',font=self.mono(10,'bold')); value.pack(side='left',padx=(0,5))
            if self.ping_cfg['ping_layer_show_names']:
                self.label(row,server['name'],bg='#010203',font=self.ui(8),anchor='w').pack(side='left',fill='x',expand=True)
            for widget in (row,signal,value): self.ping_layer_area.install_wheel(widget)
            self.ping_layer_rows.append((server['id'],value,row))
        self.paint_ping()
        if self._ping_layer: self.size_ping_layer()

    def _start_ping_layer_resize(self,event):
        self._surface_dragging=False
        self.resize_start(event)
        return 'break'

    def resize_ping_layer(self,event):
        x,y,width,height=self._resize_origin
        width=max(120,min(1400,width+event.x_root-x))
        height=max(28,min(self.root.winfo_screenheight()-40,height+event.y_root-y))
        self.ping_cfg['ping_layer_size']={'width':width,'height':height}
        self.root.geometry(f'{width}x{height}')

    def set_ping_layer_names(self,value):
        self.ping_cfg['ping_layer_show_names']=bool(value)
        self.rebuild_ping_layer()
        if value:
            self.root.update_idletasks()
            size=self.ping_cfg['ping_layer_size']
            size['width']=max(size['width'],min(1400,self.ping_layer_body.winfo_reqwidth()+12))
            self.size_ping_layer()
        self.save_ping()

    def set_ping_layer_transparency(self,value):
        self.ping_cfg['transparency']=max(0,min(100,round(float(value))))
        self.cfg['background_opacity']=(100-self.ping_cfg['transparency'])/100
        self.bg_alpha=self.cfg['background_opacity']
        self.apply_background_opacity()
        if self._layer_opacity_save_after:
            self.root.after_cancel(self._layer_opacity_save_after)
        self._layer_opacity_save_after=self.root.after(200,self._save_layer_opacity)

    def _save_layer_opacity(self):
        self._layer_opacity_save_after=None
        self.save_ping()

    def close_ping_layer_menu(self):
        win=self._layer_popup; self._layer_popup=None
        if win is not None and win.winfo_exists(): win.destroy()
        self.sync_drag_surface(); self.window_group.sync()

    def open_ping_layer_menu(self,event):
        if not self._ping_layer: return
        if event.widget.winfo_toplevel() not in (self.root,self.drag_surface): return
        self.close_ping_layer_menu()
        win=tk.Toplevel(self.root); win.withdraw(); win.overrideredirect(True)
        win.configure(bg='#202020',highlightthickness=1,highlightbackground='#596878')
        win.attributes('-topmost',bool(self.root.attributes('-topmost')))
        self.window_group.register(win,self.root)
        self._layer_popup=win
        self.label(win,'透過率',anchor='w').pack(fill='x',padx=10,pady=(8,0))
        opacity=tk.IntVar(win,value=self.ping_cfg['transparency'])
        scale=tk.Scale(win,from_=0,to=100,orient='horizontal',variable=opacity,
            command=self.set_ping_layer_transparency,bg='#202020',fg='white',
            troughcolor='#344558',highlightthickness=0,length=220)
        scale.pack(fill='x',padx=10)
        names=tk.BooleanVar(win,value=self.ping_cfg['ping_layer_show_names'])
        tk.Checkbutton(win,text='サーバー名を表示',variable=names,
            command=lambda:self.set_ping_layer_names(names.get()),bg='#202020',fg='white',
            selectcolor='#26303a',activebackground='#202020',activeforeground='white').pack(fill='x',padx=10,pady=3)
        for title,key,callback in (('サイズ変更マークを表示','ping_layer_show_grip',self.set_ping_layer_grip),
                ('背景を完全透過（空白はクリック透過）','ping_layer_clear_background',self.set_ping_layer_clear_background)):
            value=tk.BooleanVar(win,value=self.ping_cfg[key])
            tk.Checkbutton(win,text=title,variable=value,command=lambda v=value,c=callback:c(v.get()),
                bg='#202020',fg='white',selectcolor='#26303a',activebackground='#202020',
                activeforeground='white').pack(fill='x',padx=10,pady=3)
        def normal(): self.close_ping_layer_menu(); self.set_ping_layer(False)
        def settings(): self.close_ping_layer_menu(); self.open_ping_settings()
        self.button(win,'通常表示に戻す',normal,anchor='w').pack(fill='x',padx=7,pady=3)
        self.button(win,'表示するサーバーを選択',settings,anchor='w').pack(fill='x',padx=7,pady=(0,7))
        win.bind('<Escape>',lambda e:self.close_ping_layer_menu())
        def lost_focus(event):
            def check():
                if self._layer_popup is not win or not win.winfo_exists(): return
                focus=win.focus_displayof()
                if focus is None or focus.winfo_toplevel() is not win: self.close_ping_layer_menu()
            self.root.after_idle(check)
        win.bind('<FocusOut>',lost_focus)
        win.update_idletasks()
        x,y=int(event.x_root),int(event.y_root)
        # Work-area clamping uses absolute origins, including negative monitors.
        try:
            import ctypes
            from ctypes import wintypes
            class MonitorInfo(ctypes.Structure):
                _fields_=[('size',wintypes.DWORD),('monitor',wintypes.RECT),('work',wintypes.RECT),('flags',wintypes.DWORD)]
            u=ctypes.windll.user32
            u.MonitorFromPoint.argtypes=[wintypes.POINT,wintypes.DWORD]; u.MonitorFromPoint.restype=ctypes.c_void_p
            u.GetMonitorInfoW.argtypes=[ctypes.c_void_p,ctypes.POINTER(MonitorInfo)]
            info=MonitorInfo(); info.size=ctypes.sizeof(info)
            monitor=u.MonitorFromPoint(wintypes.POINT(x,y),2)
            if u.GetMonitorInfoW(monitor,ctypes.byref(info)):
                r=info.work
                x=max(r.left,min(x,r.right-win.winfo_reqwidth()))
                y=max(r.top,min(y,r.bottom-win.winfo_reqheight()))
        except (AttributeError,OSError): pass
        win.geometry(f'+{x}+{y}'); win.deiconify(); win.lift(); win.focus_force()
        return 'break'

    def set_ping_layer(self,enabled,persist=True):
        enabled=bool(enabled)
        if enabled==self._ping_layer: return
        self.close_ping_layer_menu()
        if enabled:
            if self.window_maximized: self.toggle_window_maximize()
            self._normal_layer_geometry=self.ping_cfg.get('normal_layer_geometry',self.root.geometry()) if not persist else self.root.geometry()
            self.ping_cfg['normal_layer_geometry']=self._normal_layer_geometry
            self._normal_layer_packs=[(w,w.pack_info()) for w in self.root.pack_slaves()]
            for w,_ in self._normal_layer_packs: w.pack_forget()
            self._ping_layer=True; self.root.minsize(120,28)
            self.ping_layer_frame.pack(fill='both',expand=True)
            self.rebuild_ping_layer()
            pos=self.ping_cfg.get('ping_layer_position')
            if isinstance(pos,dict): self.root.geometry(f"+{int(pos['x'])}+{int(pos['y'])}")
        else:
            self.ping_cfg['ping_layer_position']={'x':self.root.winfo_x(),'y':self.root.winfo_y()}
            self._ping_layer=False; self.ping_layer_frame.pack_forget()
            self.root.minsize(290,1)
            for w,info in self._normal_layer_packs:
                if w.winfo_exists(): w.pack(**info)
            self._restoring_ping_gui=True
            try:
                self.show_tab(self.active_tab); self.root.geometry(self._normal_layer_geometry)
                self.root.update_idletasks()
            finally: self._restoring_ping_gui=False
        self.ping_cfg['ping_layer']=enabled
        for button,var in self._layer_controls:
            if button.winfo_exists(): var.set(enabled)
        if persist: self.save_ping()
        self.root.update_idletasks(); self.sync_drag_surface(); self.window_group.sync()
