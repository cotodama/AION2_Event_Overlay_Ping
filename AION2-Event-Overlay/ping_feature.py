"""cotodama additions. Keep upstream event scheduling and HUD behavior intact."""
import copy
import ctypes
import json
import os
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from ping_catalog import build_default_profiles, SERVER_NAME_PAIRS
from ping_service import scan, latency_color
from server_data import (REGIONS, SOURCE_URL, PAIRING_SOURCE, fetch_snapshot,
                         filtered_servers, status_label, balance_groups, balance_fraction)

BG='#202020'; TEXT='#ffffff'; DIM='#c5ccd6'; BLUE='#79c9ff'; PURPLE='#c197ff'

class ScrollArea:
    def __init__(self,parent,height=350,bg=BG,horizontal=False):
        style=ttk.Style(parent)
        # Clone clam elements into the current theme: native Windows themes otherwise
        # ignore scrollbar colors. No arrow elements, and a compositor-colored track.
        for orient in ('Vertical','Horizontal'):
            prefix='Overlay.'+orient+'.Scrollbar'
            for part in ('trough','thumb'):
                name=prefix+'.'+part
                if name not in style.element_names():
                    style.element_create(name,'from','clam',orient+'.Scrollbar.'+part)
            name='Overlay.'+orient+'.TScrollbar'
            style.layout(name,[(prefix+'.trough',{'sticky':'nswe','children':[
                (prefix+'.thumb',{'sticky':'nswe','expand':1})]})])
            style.configure(name,background='#46515e',troughcolor='#010203',
                            bordercolor='#010203',lightcolor='#46515e',darkcolor='#46515e',
                            arrowcolor='#46515e',gripcount=0,width=9,borderwidth=0)
            style.map(name,background=[('active','#718091'),('pressed','#718091')])
        self.frame=tk.Frame(parent,bg=bg)
        self.canvas=tk.Canvas(self.frame,height=height,bg=bg,bd=0,highlightthickness=0)
        self.vbar=ttk.Scrollbar(self.frame,orient='vertical',command=self.canvas.yview,style='Overlay.Vertical.TScrollbar')
        self.canvas.configure(yscrollcommand=self.set_y)
        self.vbar.pack(side='right',fill='y'); self.canvas.pack(side='top',fill='both',expand=True)
        if horizontal:
            self.hbar=ttk.Scrollbar(self.frame,orient='horizontal',command=self.canvas.xview,style='Overlay.Horizontal.TScrollbar')
            self.canvas.configure(xscrollcommand=self.set_x)
            self.hbar.pack(side='bottom',fill='x')
        self.body=tk.Frame(self.canvas,bg=bg)
        self.item=self.canvas.create_window(0,0,anchor='nw',window=self.body)
        self.horizontal=horizontal
        self.body.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',self.resize)
        self.install_wheel(self.canvas); self.install_wheel(self.body)

    def set_y(self,first,last):
        self.vbar.set(first,last)
        needed=float(first)>0 or float(last)<1
        if needed and not self.vbar.winfo_manager(): self.vbar.pack(side='right',fill='y',before=self.canvas)
        elif not needed and self.vbar.winfo_manager(): self.vbar.pack_forget()

    def set_x(self,first,last):
        self.hbar.set(first,last)
        needed=float(first)>0 or float(last)<1
        if needed and not self.hbar.winfo_manager(): self.hbar.pack(side='bottom',fill='x')
        elif not needed and self.hbar.winfo_manager(): self.hbar.pack_forget()

    def resize(self,event):
        if not self.horizontal: self.canvas.itemconfigure(self.item,width=event.width)

    def install_wheel(self,widget):
        widget.bind('<MouseWheel>',lambda e:self.canvas.yview_scroll(-int(e.delta/120),'units'),add='+')

    def clear(self):
        for w in self.body.winfo_children(): w.destroy()
        self.canvas.yview_moveto(0)

class PingFeatureMixin:
    def setup_dialog_position(self,win,title):
        win._position_key={'設定':'event_settings','Settings':'event_settings',
                           'Ping表示・オーバーレイ設定':'ping_settings',
                           'タイマー設定':'timer_settings','Timer Settings':'timer_settings'}.get(title,title)
        win.transient(self.root)
        win.attributes('-topmost',bool(self.root.attributes('-topmost')))
        saved=self.dialog_positions.get(win._position_key)
        win._remember_position=bool(saved); win._position_ready=False
        x,y=(saved['x'],saved['y']) if saved else (self.root.winfo_x()+self.root.winfo_width()+12,self.root.winfo_y())
        win.geometry(f'+{x}+{y}')
        def shown(event):
            if event.widget is not win: return
            win.lift()
            def ready():
                if win.winfo_exists():
                    win._auto_dialog_xy={'x':win.winfo_x(),'y':win.winfo_y()}
                    win._position_ready=True
            win.after(80,ready)
        win.bind('<Map>',shown,add='+')
        win.bind('<Configure>',lambda e:self.track_dialog_position(win,e),add='+')
        win.bind('<Destroy>',lambda e:self.track_dialog_position(win,e),add='+')

    def track_dialog_position(self,win,event):
        if event.widget is not win: return
        if event.type==tk.EventType.Destroy:
            if win._remember_position and hasattr(win,'_last_dialog_xy'):
                self.dialog_positions[win._position_key]=win._last_dialog_xy
                self.persist_dialog_positions()
            return
        if win.winfo_ismapped() and win._position_ready:
            win._last_dialog_xy={'x':win.winfo_x(),'y':win.winfo_y()}
            if win._last_dialog_xy!=win._auto_dialog_xy: win._remember_position=True
            if not win._remember_position: return
            self.dialog_positions[win._position_key]=win._last_dialog_xy
            old=getattr(self,'_dialog_position_after',None)
            if old: self.root.after_cancel(old)
            self._dialog_position_after=self.root.after(250,self.persist_dialog_positions)

    def persist_dialog_positions(self):
        self._dialog_position_after=None
        self.dialog_position_path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.dialog_position_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.dialog_positions,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(tmp,self.dialog_position_path)

    def install_surface_drag(self):
        self.window_maximized=False
        self.root.bind('<ButtonPress-1>',self.surface_drag_start,add='+')
        self.root.bind('<B1-Motion>',self.surface_drag_motion,add='+')
        self.root.bind('<ButtonRelease-1>',self.surface_drag_end,add='+')
        # Windows skips hit testing on color-key holes before WM_NCHITTEST.
        # An almost invisible surface underneath receives drags through those holes.
        self.drag_surface=tk.Toplevel(self.root)
        self.drag_surface.withdraw(); self.drag_surface.overrideredirect(True)
        self.drag_surface.configure(bg='#202020'); self.drag_surface.attributes('-alpha',0.88)
        self.drag_surface.bind('<ButtonPress-1>',self._move_handle_start)
        self.drag_surface.bind('<B1-Motion>',self._move_handle_drag)
        self.drag_surface.bind('<ButtonRelease-1>',self._move_handle_end)
        self.root.bind('<Configure>',lambda e:self.root.after_idle(self.sync_drag_surface) if e.widget is self.root else None,add='+')
        self.root.bind('<Map>',lambda e:self.root.after_idle(self.sync_drag_surface) if e.widget is self.root else None,add='+')
        self.root.bind('<Unmap>',lambda e:self.drag_surface.withdraw() if e.widget is self.root else None,add='+')
        self.root.after_idle(self.sync_drag_surface)
        self.root.bind('<Map>',self.restore_minimized_frame,add='+')
        self.tray_icon=None
        self.root.after(200,self.poll_tray)
        if not self._background_disabled: self.root.after(500,self.refresh_taskbar_entry)

    def refresh_taskbar_entry(self):
        # Let the Shell see the APPWINDOW style on a fresh show.
        if self.root.state()=='iconic' or self.stop_workers.is_set(): return
        self.root.withdraw(); self.root.after(30,self.root.deiconify)

    def poll_tray(self):
        if self.stop_workers.is_set(): return
        self.sync_drag_surface()
        if self.tray_icon and self.tray_icon.restore_requested:
            self.tray_icon.restore_requested=False; self.root.deiconify(); self.root.lift()
        if self.tray_icon and self.root.state()!='iconic': self.tray_icon.hide()
        self.root.after(200,self.poll_tray)

    def sync_drag_surface(self):
        # Tk popdown menus own a grab. Native restacking cancels that menu.
        if self.root.tk.call('grab','current'): return
        if getattr(self,'_syncing_drag',False): return
        self._syncing_drag=True
        try:
            if not self.drag_surface.winfo_exists(): return
            if not self.root.winfo_ismapped() or self.root.state()=='iconic':
                self.drag_surface.withdraw(); return
            if not self.drag_surface.winfo_ismapped(): self.drag_surface.deiconify()
            target=f'{self.root.winfo_width()}x{self.root.winfo_height()}+{self.root.winfo_x()}+{self.root.winfo_y()}'
            # Explicit '+' before signed coordinates keeps negative monitor positions
            # absolute; '-1920' in Tk geometry means distance from the right edge.
            current=(self.drag_surface.winfo_width(),self.drag_surface.winfo_height(),
                     self.drag_surface.winfo_x(),self.drag_surface.winfo_y())
            desired=(self.root.winfo_width(),self.root.winfo_height(),self.root.winfo_x(),self.root.winfo_y())
            if current!=desired:
                self.drag_surface.geometry(target)
                self.drag_surface.update_idletasks()
            opacity=float(self.cfg.get('background_opacity',0.88))
            if opacity>1: opacity/=100
            alpha=max(0.01,min(1.0,opacity))
            self.drag_surface.configure(bg='#202020')
            if abs(float(self.drag_surface.attributes('-alpha'))-alpha)>0.001:
                self.drag_surface.attributes('-alpha',alpha)
            top=bool(self.root.attributes('-topmost'))
            if bool(self.drag_surface.attributes('-topmost'))!=top: self.drag_surface.attributes('-topmost',top)
            self.drag_surface.lower(self.root)
        except tk.TclError: pass
        finally: self._syncing_drag=False

    def surface_drag_start(self,event):
        self._surface_dragging=False
        if event.widget.winfo_toplevel() is not self.root: return
        widget=event.widget
        controls={'Button','TButton','Checkbutton','TCheckbutton','Entry','TEntry',
                  'Combobox','TCombobox','Scale','TScale','Scrollbar','TScrollbar',
                  'Spinbox','TSpinbox','Listbox','Treeview'}
        while widget is not self.root:
            if widget.winfo_class() in controls: return
            widget=widget.master
        if self.window_maximized: return
        self._surface_dragging=True
        self._move_handle_start(event)

    def surface_drag_motion(self,event):
        if getattr(self,'_surface_dragging',False): self._move_handle_drag(event)

    def surface_drag_end(self,event):
        if getattr(self,'_surface_dragging',False):
            self._surface_dragging=False; self._move_handle_end(event)

    def minimize_window(self):
        if os.name=='nt':
            self.restore_selective_hit_test()
            self.root.overrideredirect(False)
            self._restore_frame_on_map=True
            self.root.iconify()
            try:
                if self.tray_icon is None:
                    from windows_tray import TrayIcon
                    from AION2_Event_Overlay import APP_ICON
                    self.tray_icon=TrayIcon(APP_ICON)
                self.tray_icon.show()
            except OSError as exc: print('通知アイコン:',exc)
        else:
            self.root.overrideredirect(False); self.root.iconify()
            self.root.bind('<Map>',lambda e:self.root.overrideredirect(True) if e.widget is self.root else None,add='+')

    def restore_minimized_frame(self,event):
        if event.widget is self.root and getattr(self,'_restore_frame_on_map',False):
            self._restore_frame_on_map=False
            self.root.after_idle(self.apply_frameless_mode)

    def toggle_window_maximize(self):
        if self.window_maximized:
            self.window_maximized=False
            geometry,self.overlay_width,self.manual_height=self._normal_window
            self.root.geometry(geometry); self.maximize_button.configure(text='□')
        else:
            self._normal_window=(self.root.geometry(),self.overlay_width,self.manual_height)
            x=y=0; w=self.root.winfo_screenwidth(); h=self.root.winfo_screenheight()
            if os.name=='nt':
                from ctypes import wintypes
                class MonitorInfo(ctypes.Structure):
                    _fields_=[('cbSize',wintypes.DWORD),('monitor',wintypes.RECT),
                              ('work',wintypes.RECT),('flags',wintypes.DWORD)]
                user32=ctypes.windll.user32
                user32.MonitorFromWindow.argtypes=[wintypes.HWND,wintypes.DWORD]
                user32.MonitorFromWindow.restype=wintypes.HANDLE
                user32.GetMonitorInfoW.argtypes=[wintypes.HANDLE,ctypes.POINTER(MonitorInfo)]
                info=MonitorInfo(); info.cbSize=ctypes.sizeof(info)
                monitor=user32.MonitorFromWindow(self.get_native_toplevel_hwnd(),2)
                if user32.GetMonitorInfoW(monitor,ctypes.byref(info)):
                    r=info.work; x,y,w,h=r.left,r.top,r.right-r.left,r.bottom-r.top
            self.window_maximized=True
            self.root.geometry(f'{w}x{h}+{x}+{y}'); self.maximize_button.configure(text='❐')
        self.root.after_idle(self.refresh_hud_control_rects)

    def init_ping(self,data_dir):
        self.dialog_position_path=Path(data_dir)/'dialog_positions.json'
        try:
            raw=json.loads(self.dialog_position_path.read_text(encoding='utf-8'))
            self.dialog_positions={k:{'x':int(v['x']),'y':int(v['y'])} for k,v in raw.items()}
        except (OSError,ValueError,TypeError,KeyError,AttributeError): self.dialog_positions={}
        self.ping_path=Path(data_dir)/'ping_settings.json'
        defaults={'profiles':build_default_profiles(),'selected':['Japan:Elyos:Siel'],
                  'region':'Japan','elyos':True,'asmodians':True,'topmost':True,
                  'transparency':12,'simple':False,'width':390,'height':None}
        try:
            saved=json.loads(self.ping_path.read_text(encoding='utf-8'))
            if not isinstance(saved,dict): raise ValueError('invalid settings')
            defaults.update(saved)
        except (OSError,ValueError): pass
        if not defaults.get('auto_size_default_v1'):
            defaults.update(width=390,height=None,auto_size_default_v1=True)
        self.ping_cfg=defaults
        self.profiles=defaults['profiles']
        # Ignore invalid saved endpoints rather than crashing the background loop.
        for region,profile in self.profiles.items():
            valid=[]
            for s in profile.get('servers',[]):
                try:
                    if not s.get('id') or not s.get('name') or not s.get('host'): continue
                    s['port']=int(s['port'])
                    if not 1 <= s['port'] <= 65535: continue
                    s.setdefault('faction','Common'); valid.append(s)
                except (ValueError,TypeError,KeyError): continue
            profile['servers']=valid
        self.repair_duplicate_names()
        if self.ping_cfg.get('selection_faction')=='天族・魔族': self.ping_cfg['selection_faction']='すべて'
        if self.ping_cfg['region'] not in self.profiles:
            self.ping_cfg['region']=next(iter(self.profiles),'Japan')
        self.active_tab='events'; self.db_region='all'; self.db_snapshot=None
        self.results={}; self.ping_generation=0; self.scan_busy=False
        self.worker_queue=queue.Queue(); self.stop_workers=threading.Event()
        self.next_scan=0.; self.next_fetch=0.; self.fetch_busy=False
        self.fetch_error=''; self.fetched_at=None; self.sort_field='name'; self.sort_desc=False
        self.overlay_width=max(340,min(1400,int(defaults.get('width',390))))
        self.manual_height=defaults.get('height')
        self.ping_widgets={}; self._background_disabled=False

    def repair_duplicate_names(self):
        # Repair a duplicated saved display name only when the saved endpoint
        # matches a missing catalog entry; do not invent a live world/IP mapping.
        reference=build_default_profiles()
        for region,profile in self.profiles.items():
            defaults=reference.get(region,{}).get('servers',[])
            for faction in ('Elyos','Asmodians'):
                servers=[s for s in profile['servers'] if s['faction']==faction]
                counts={s['name'].casefold():sum(t['name'].casefold()==s['name'].casefold() for t in servers) for s in servers}
                present=set(counts)
                for server in servers:
                    if counts[server['name'].casefold()]<2: continue
                    match=next((d for d in defaults if d['faction']==faction
                                and d['name'].casefold() not in present
                                and d['host']==server['host'] and d['port']==server['port']),None)
                    if match:
                        counts[server['name'].casefold()]-=1
                        server.update(name=match['name'],code=match.get('code',''),jp=match.get('jp',''))
                        present.add(match['name'].casefold())

    def save_ping(self):
        self.ping_cfg.update(profiles=self.profiles,width=self.overlay_width,height=self.manual_height)
        self.ping_path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.ping_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.ping_cfg,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(tmp,self.ping_path)

    def all_endpoints(self):
        return [(region,s) for region in self.profiles for faction in ('Elyos','Asmodians','Common')
                for s in self.ordered_faction_servers(region,faction)]

    def ordered_faction_servers(self,region,faction):
        index=0 if faction=='Elyos' else 1
        order={pair[index][0].casefold():i for i,pair in enumerate(SERVER_NAME_PAIRS)}
        servers=[s for s in self.profiles[region]['servers'] if s['faction']==faction]
        # Retain custom entries after the catalog, without changing their endpoints.
        return sorted(servers,key=lambda s:order.get(s['name'].casefold(),len(order)))

    def chosen_endpoints(self):
        ids=set(self.ping_cfg['selected'])
        return [(r,s) for r,s in self.all_endpoints() if s['id'] in ids]

    def label(self,parent,text,**kw):
        return tk.Label(parent,text=text,bg=BG,fg=TEXT,font=self.ui(9),**kw)

    def button(self,parent,text,command,**kw):
        return tk.Button(parent,text=text,command=command,bg='#202934',fg=TEXT,
                         activebackground='#344558',activeforeground=TEXT,
                         relief='flat',bd=0,font=self.ui(9),cursor='hand2',**kw)

    def build_ping_header(self,transparent):
        self.ping_widgets={}
        self.ping_header=tk.Frame(self.root,bg=transparent)
        self.ping_header.pack(fill='x',padx=7,pady=(0,3))
        head=tk.Frame(self.ping_header,bg=transparent); head.pack(fill='x')
        self.ping_gear=self.button(head,'⚙',self.open_ping_settings,width=3)
        self.ping_gear.pack(side='right')
        tk.Label(head,text='SERVER PING  ·  TCP',bg=transparent,fg=TEXT,
                 font=self.ui(8,'bold')).pack(side='left',padx=4)
        self.summary_area=ScrollArea(self.ping_header,height=30,bg=transparent)
        self.summary_area.frame.pack(fill='x')
        self.rebuild_summary(transparent)
        self.tab_bar=tk.Frame(self.root,bg=transparent); self.tab_bar.pack(fill='x',padx=7,pady=(2,3))
        self.tab_buttons={}
        for key,text in [('events','イベント'),('ping','Ping一覧'),('status','サーバー状態'),('balance','種族バランス')]:
            b=self.button(self.tab_bar,text,lambda k=key:self.show_tab(k),padx=7,pady=5)
            b.pack(side='left',fill='x',expand=True,padx=1); self.tab_buttons[key]=b
        self.tab_buttons['events'].configure(bg='#344558')

    def rebuild_summary(self,transparent='#010203'):
        self.summary_area.clear(); self.summary_rows=[]
        chosen=self.chosen_endpoints()
        self.summary_area.canvas.configure(height=min(4,max(1,len(chosen)))*28)
        if not chosen:
            tk.Label(self.summary_area.body,text='⚙ で表示するサーバーを選択',fg=TEXT,bg=transparent,
                     font=self.ui(9)).pack(anchor='w',padx=5,pady=5)
        for region,server in chosen:
            row=tk.Frame(self.summary_area.body,bg=transparent); row.pack(fill='x',pady=1)
            signal=tk.Canvas(row,width=22,height=22,bg=transparent,highlightthickness=0)
            signal.pack(side='left',padx=(4,5))
            for i,h in enumerate((4,8,12,17)):
                signal.create_rectangle(i*5+1,21-h,i*5+4,21,fill='#40ff68',outline='')
            text='ms' if self.ping_cfg.get('simple') else f"{server['name']} · {region}"
            name=tk.Label(row,text=text,bg=transparent,fg=TEXT,font=self.ui(9),anchor='w')
            name.pack(side='left',fill='x',expand=not self.ping_cfg.get('simple'))
            val=tk.Label(row,text='… ms',bg=transparent,fg=DIM,font=self.mono(10,'bold'))
            val.pack(side='left' if self.ping_cfg.get('simple') else 'right',padx=6)
            for w in (name,val,signal):
                w.bind('<Double-Button-1>',lambda e,s=server:self.edit_endpoint(s))
                self.summary_area.install_wheel(w)
            self.summary_rows.append((server['id'],val,row))
        self.paint_ping()

    def build_extra_tabs(self):
        self.extra_section=tk.Frame(self.root,bg=BG)
        # Resize handle also works when the upstream frameless window has no border.
        self.resize_handle=self.button(self.root,'◢',lambda:None,anchor='e')
        self.resize_handle.pack(side='bottom',fill='x',padx=7,before=self.event_section)
        self.resize_handle.bind('<ButtonPress-1>',self.resize_start)
        self.resize_handle.bind('<B1-Motion>',self.resize_drag)
        self.resize_handle.bind('<ButtonRelease-1>',self.resize_end)

    def resize_start(self,event):
        if self.window_maximized: self.toggle_window_maximize(); self.root.update_idletasks()
        self._resize_origin=(event.x_root,event.y_root,self.root.winfo_width(),self.root.winfo_height())

    def resize_drag(self,event):
        x,y,w,h=self._resize_origin
        self.overlay_width=max(340,min(1400,w+event.x_root-x))
        target=max(300,min(self.root.winfo_screenheight()-40,h+event.y_root-y))
        self.manual_height=target
        if hasattr(self,'db_info') and self.active_tab in ('status','balance'):
            self.db_info.configure(wraplength=self.overlay_width-30)
        if hasattr(self,'list_area') and self.active_tab!='events':
            self.list_area.canvas.configure(height=max(130,target-self.extra_section.winfo_y()-130))
        self.root.geometry(f'{self.overlay_width}x{target}')

    def resize_end(self,event):
        self.save_ping()

    def show_tab(self,key):
        self.active_tab=key
        for k,b in self.tab_buttons.items(): b.configure(bg='#344558' if k==key else '#202934')
        self.event_section.pack_forget(); self.timer_box.pack_forget(); self.extra_section.pack_forget()
        if key=='events':
            self.event_section.pack(fill='x',padx=7,pady=(7,3),after=self.resize_handle)
            if self.timer_panel_visible: self.timer_box.pack(fill='x',padx=7,pady=3,after=self.event_section)
        else:
            self.extra_section.pack(fill='both',expand=True,padx=7,pady=3,after=self.resize_handle)
            for w in self.extra_section.winfo_children(): w.destroy()
            self.ping_widgets={}
            if key=='ping': self.build_ping_list()
            else: self.build_db_view()
        self.apply_extension_surface()
        self.ping_generation+=1; self.next_scan=0
        self.paint_ping()
        self.root.after_idle(self.fit_window_to_content)

    def build_ping_list(self):
        controls=tk.Frame(self.extra_section,bg=BG); controls.pack(fill='x')
        self.ping_region_var=tk.StringVar(value=self.ping_cfg['region'])
        box=ttk.Combobox(controls,textvariable=self.ping_region_var,values=list(self.profiles),state='readonly',width=16)
        box.pack(side='left'); box.bind('<<ComboboxSelected>>',lambda e:self.change_ping_filter())
        self.elyos_var=tk.BooleanVar(value=self.ping_cfg['elyos'])
        self.asmo_var=tk.BooleanVar(value=self.ping_cfg['asmodians'])
        for text,var in [('天族',self.elyos_var),('魔族',self.asmo_var)]:
            tk.Checkbutton(controls,text=text,variable=var,command=self.change_ping_filter,
                           bg=BG,fg=TEXT,selectcolor=BG,activebackground=BG,activeforeground=TEXT,
                           font=self.ui(9)).pack(side='left')
        self.label(self.extra_section,'ダブルクリックで接続先を編集 · ＊対応未検証',anchor='w').pack(fill='x',pady=4)
        self.list_area=ScrollArea(self.extra_section,height=330); self.list_area.frame.pack(fill='both',expand=True)
        self.render_ping_list()

    def change_ping_filter(self):
        self.ping_cfg.update(region=self.ping_region_var.get(),elyos=self.elyos_var.get(),asmodians=self.asmo_var.get())
        self.ping_generation+=1; self.results.clear(); self.next_scan=0
        self.save_ping(); self.render_ping_list(); self.paint_ping()

    def visible_endpoints(self):
        region=self.ping_cfg['region']
        return [s for s in self.profiles[region]['servers'] if s['faction']=='Common' or
                (s['faction']=='Elyos' and self.ping_cfg['elyos']) or
                (s['faction']=='Asmodians' and self.ping_cfg['asmodians'])]

    def render_ping_list(self):
        self.list_area.clear(); self.ping_widgets={}
        for faction,title in [('Common','COMMON / LOGIN'),('Elyos','ELYOS / 天族'),('Asmodians','ASMODIANS / 魔族')]:
            servers=[s for s in self.visible_endpoints() if s['faction']==faction]
            if not servers: continue
            self.label(self.list_area.body,title,anchor='w').pack(fill='x',padx=7,pady=(9,4))
            for server in servers:
                row=tk.Frame(self.list_area.body,bg='#15191e'); row.pack(fill='x',pady=1,padx=3)
                star=' ＊' if '未検証' in server.get('endpoint_note','') else ''
                name=tk.Label(row,text=server['name']+star,fg=TEXT,bg='#15191e',font=self.ui(10),anchor='w')
                name.pack(side='left',fill='x',expand=True,padx=7,pady=5)
                value=tk.Label(row,text='… ms',fg=DIM,bg='#15191e',font=self.mono(10,'bold'))
                value.pack(side='right',padx=7)
                for w in (row,name,value):
                    w.bind('<Double-Button-1>',lambda e,s=server:self.edit_endpoint(s)); self.list_area.install_wheel(w)
                self.ping_widgets[server['id']]=value

    def edit_endpoint(self,server):
        win=self._new_dialog('サーバー接続先の編集'); win.configure(bg=BG)
        win.resizable(False,False)
        self.label(win,server['name']).pack(pady=8)
        fields={}
        for key,title in [('host','IPアドレス / ホスト名'),('port','TCPポート')]:
            self.label(win,title).pack(anchor='w',padx=12)
            var=tk.StringVar(value=str(server[key])); fields[key]=var
            tk.Entry(win,textvariable=var,bg='#10151b',fg=TEXT,insertbackground=TEXT,width=34).pack(padx=12,pady=5)
        self.label(win,server.get('endpoint_note','登録済み接続先'),wraplength=300).pack(padx=12,pady=5)
        def save():
            host=fields['host'].get().strip()
            try:
                port=int(fields['port'].get())
                if not host or any(c.isspace() for c in host) or not 1<=port<=65535: raise ValueError()
            except ValueError:
                messagebox.showerror('入力エラー','ホスト名と1〜65535のポートを指定してください。',parent=win); return
            server.update(host=host,port=port,endpoint_note='手動設定・対応は利用者確認')
            self.ping_generation+=1; self.results.clear(); self.next_scan=0; self.save_ping()
            if self.active_tab=='ping': self.render_ping_list()
            self.paint_ping(); self._safe_dialog_close(win)
        self.button(win,'保存',save,padx=20,pady=5).pack(pady=9)
        win.after_idle(lambda:(win.deiconify(),win.lift()))

    def open_ping_settings(self):
        existing=self._dialog_windows.get('ping')
        if existing is not None and existing.winfo_exists(): existing.lift(); return
        win=self._new_dialog('Ping表示・オーバーレイ設定'); self._dialog_windows['ping']=win
        win.configure(bg=BG); win.geometry('380x540'); win.minsize(340,400)
        top=tk.BooleanVar(value=self.ping_cfg['topmost'])
        simple=tk.BooleanVar(value=self.ping_cfg.get('simple',False))
        opacity=tk.IntVar(value=self.ping_cfg['transparency'])
        previous_opacity=self.cfg['background_opacity']
        previous_top=self.ping_cfg['topmost']
        def preview(value):
            self.cfg['background_opacity']=(100-float(value))/100
            self.apply_background_opacity()
        def preview_top():
            self.ping_cfg['topmost']=top.get(); self.root.attributes('-topmost',top.get())
            self.sync_drag_surface()
            for dialog in self._dialog_windows.values():
                if dialog.winfo_exists(): dialog.attributes('-topmost',top.get())
        for title,var in [('オーバーレイを最前面に表示',top),('簡易表示（アンテナ＋数値 ms）',simple)]:
            tk.Checkbutton(win,text=title,variable=var,bg=BG,fg=TEXT,selectcolor=BG,
                           command=preview_top if var is top else lambda:None,
                           activebackground=BG,activeforeground=TEXT,font=self.ui(9)).pack(anchor='w',padx=10,pady=2)
        self.label(win,'透過率 0%（不透明）〜100%（透明）').pack(anchor='w',padx=10)
        tk.Scale(win,from_=0,to=100,orient='horizontal',variable=opacity,bg=BG,fg=TEXT,
                 highlightthickness=0,troughcolor='#344558',length=330,command=preview).pack(fill='x',padx=10)
        tk.Label(win,text='100%でも操作文字・ボタンは残ります',bg=BG,fg=DIM,font=self.ui(8)).pack(anchor='w',padx=10)
        selected=set(self.ping_cfg['selected']); variables={}
        region_var=tk.StringVar(value=self.ping_cfg['region'])
        combo=ttk.Combobox(win,textvariable=region_var,values=list(self.profiles),state='readonly')
        combo.pack(fill='x',padx=10,pady=6)
        for _,s in self.all_endpoints(): variables[s['id']]=tk.BooleanVar(value=s['id'] in selected)
        filters=tk.Frame(win,bg=BG); filters.pack(fill='x',padx=10,pady=4)
        self.label(filters,'種族').pack(side='left')
        faction_var=tk.StringVar(value=self.ping_cfg.get('selection_faction','すべて'))
        faction_box=ttk.Combobox(filters,textvariable=faction_var,
                                values=['すべて','天族','魔族'],state='readonly',width=16)
        faction_box.pack(side='left',fill='x',expand=True,padx=(10,0))
        login_row=tk.Frame(win,bg=BG); login_row.pack(fill='x',padx=10)
        count_label=self.label(win,'',anchor='w'); count_label.pack(fill='x',padx=10,pady=4)
        area=ScrollArea(win,height=220); area.frame.pack(fill='both',expand=True,padx=10)
        rows=[]
        def refresh_count():
            total=sum(v.get() for v in variables.values())
            count_label.configure(text=f'選択中: {total} サーバー（他の地域・種族の選択も保持）')
        def populate(event=None):
            area.clear(); rows.clear()
            for child in login_row.winfo_children(): child.destroy()
            region=region_var.get()
            for server in self.ordered_faction_servers(region,'Common'):
                tk.Checkbutton(login_row,text='LoginServerを表示',variable=variables[server['id']],
                               command=refresh_count,bg=BG,fg=TEXT,selectcolor=BG,
                               activebackground=BG,activeforeground=TEXT,font=self.ui(9)).pack(anchor='w')
            factions={'天族':['Elyos'],'魔族':['Asmodians'],'すべて':['Elyos','Asmodians']}[faction_var.get()]
            for faction in factions:
                self.label(area.body,'天族' if faction=='Elyos' else '魔族',anchor='w').pack(fill='x',pady=(5,3))
                for number,server in enumerate(self.ordered_faction_servers(region,faction),1):
                    note=' ＊' if '未検証' in server.get('endpoint_note','') else ''
                    cb=tk.Checkbutton(area.body,text=f"{number}. {server['name']}{note}",
                                      variable=variables[server['id']],command=refresh_count,
                                      bg=BG,fg=TEXT,selectcolor=BG,activebackground=BG,
                                      activeforeground=TEXT,anchor='w',font=self.ui(9))
                    cb.pack(fill='x'); area.install_wheel(cb); rows.append(cb)
            refresh_count()
        combo.bind('<<ComboboxSelected>>',populate)
        faction_box.bind('<<ComboboxSelected>>',populate); populate()
        self.label(win,'先頭のチェックで複数選択 → 保存で表示に反映',wraplength=340).pack(padx=10,pady=5,before=area.frame)
        self.label(win,'＊既存IP候補・サーバーとの対応は未検証').pack(anchor='w',padx=10,pady=4,before=area.frame)
        def save():
            chosen=[server['id'] for _,server in self.all_endpoints() if variables[server['id']].get()]
            self.ping_cfg.update(selected=chosen,selection_faction=faction_var.get(),
                                 topmost=top.get(),simple=simple.get(),transparency=opacity.get())
            self.root.attributes('-topmost',top.get())
            self.cfg['background_opacity']=(100-opacity.get())/100
            self.bg_alpha=self.cfg['background_opacity']; self.apply_background_opacity()
            self.save_ping(); self.rebuild_summary(); self.ping_generation+=1
            self.results.clear(); self.next_scan=0; self.paint_ping()
            self.root.after_idle(self.fit_window_to_content)
            self._dialog_windows.pop('ping',None); self._safe_dialog_close(win)
        actions=tk.Frame(win,bg=BG); actions.pack(side='bottom',fill='x',padx=10,pady=8,before=area.frame)
        save_button=self.button(actions,'保存',save,padx=18,pady=5); save_button.pack(side='right')
        self._ping_selection_state=dict(variables=variables,region=region_var,faction=faction_var,
                                        rows=rows,populate=populate,save=save_button)
        self.button(actions,'サイズ自動調整',self.reset_size,padx=8,pady=5).pack(side='left')
        def cancel():
            self.cfg['background_opacity']=previous_opacity; self.ping_cfg['topmost']=previous_top
            self.apply_background_opacity(); self._dialog_windows.pop('ping',None); self._safe_dialog_close(win)
        win.protocol('WM_DELETE_WINDOW',cancel)
        win.after_idle(lambda:(win.deiconify(),win.lift()))

    def reset_size(self):
        self.overlay_width=390; self.manual_height=None
        if self.active_tab!='events': self.list_area.canvas.configure(height=350)
        self.save_ping(); self.fit_window_to_content()

    def build_db_view(self):
        sub=tk.Frame(self.extra_section,bg=BG); sub.pack(fill='x')
        self.region_buttons={}
        for code,title in REGIONS:
            b=self.button(sub,title,lambda c=code:self.choose_db_region(c),padx=3,pady=5)
            b.pack(side='left',expand=True,fill='x',padx=1)
            if code==self.db_region: b.configure(bg='#344558')
            self.region_buttons[code]=b
        controls=tk.Frame(self.extra_section,bg=BG); controls.pack(fill='x',pady=4)
        self.search_var=tk.StringVar()
        search=tk.Entry(controls,textvariable=self.search_var,width=14,bg='#10151b',fg=TEXT,insertbackground=TEXT)
        search.pack(side='left',fill='x',expand=True,padx=2)
        self.search_var.trace_add('write',lambda *args:self.render_db())
        self.db_filter=tk.StringVar(value='すべて')
        self.table_var=tk.BooleanVar(value=False)
        if self.active_tab=='status':
            box=ttk.Combobox(controls,textvariable=self.db_filter,values=['すべて','オンライン','問題あり'],state='readonly',width=9)
            box.pack(side='left',padx=3); box.bind('<<ComboboxSelected>>',lambda e:self.render_db())
            tk.Checkbutton(controls,text='表表示',variable=self.table_var,command=self.render_db,
                           bg=BG,fg=TEXT,selectcolor=BG,activebackground=BG,activeforeground=TEXT,
                           font=self.ui(8)).pack(side='left')
        self.db_info=self.label(self.extra_section,'取得中…',anchor='w',wraplength=self.overlay_width-30)
        self.db_info.pack(fill='x',pady=(0,3))
        self.list_area=ScrollArea(self.extra_section,height=350,horizontal=True)
        self.list_area.frame.pack(fill='both',expand=True)
        bottom=tk.Frame(self.extra_section,bg=BG); bottom.pack(fill='x',pady=4)
        self.button(bottom,'出典: gaming.tools',lambda:webbrowser.open(SOURCE_URL+('?view=balance' if self.active_tab=='balance' else '')),padx=5).pack(side='left')
        self.label(bottom,'60秒ごとに自動更新').pack(side='right')
        self.render_db()

    def choose_db_region(self,code):
        self.db_region=code
        for c,b in self.region_buttons.items(): b.configure(bg='#344558' if c==code else '#202934')
        self.render_db()

    def draw_lock(self,canvas,x,y):
        # Native vector lock stays red on systems where emoji fonts are monochrome.
        canvas.create_arc(x+3,y,x+11,y+11,start=0,extent=180,outline='#ff5252',width=2,style='arc')
        canvas.create_rectangle(x+1,y+6,x+13,y+16,fill='#ff5252',outline='')
        canvas.create_line(x+7,y+9,x+7,y+13,fill=BG,width=2)

    def draw_name(self,canvas,name,x,y,locked=False,font=None):
        item=canvas.create_text(x,y,text=name,fill=TEXT,anchor='w',font=font or self.ui(10,'bold'))
        if locked:
            bounds=canvas.bbox(item)
            if bounds: self.draw_lock(canvas,bounds[2]+6,y-8)
        return item

    def draw_spark(self,canvas,points,x,y,width=145,height=25,capacity=0):
        canvas.create_text(x,y-7,text='24H',fill=DIM,anchor='sw',font=self.ui(7))
        if not points:
            canvas.create_text(x,y+height/2,text='データなし',fill=DIM,anchor='w',font=self.ui(8)); return
        peak=max(1,max((p.get('value') or 0) for p in points)); step=width/len(points)
        for i,p in enumerate(points):
            value=p.get('value')
            if value is None:
                canvas.create_rectangle(x+i*step,y+height-2,x+(i+1)*step-1,y+height,fill='#59616b',outline=''); continue
            load=value/capacity if capacity else 0
            color='#ff5252' if load>=.9 else '#ff9b42' if load>=.7 else '#40c782'
            h=max(1,value/peak*height)
            canvas.create_rectangle(x+i*step,y+height-h,x+(i+1)*step-1,y+height,fill=color,outline='')

    def render_db(self):
        if self.active_tab not in ('status','balance') or not hasattr(self,'db_info'): return
        self.list_area.clear()
        if not self.db_snapshot:
            self.db_info.configure(text='取得失敗: '+self.fetch_error if self.fetch_error else 'サーバー情報を取得中…')
            return
        region_times=[r.get('lastUpdated','') for r in self.db_snapshot['regions']]
        times=[t for t in region_times if t]
        stamp=min(times) if times else '不明'
        age=int(time.monotonic()-self.fetched_at) if self.fetched_at else 0
        prefix='更新失敗・前回値を表示中  ' if self.fetch_error else ''
        self.db_info.configure(text=f'{prefix}データ時刻(最古): {stamp}  · 取得 {age}秒前',fg='#ff9b42' if self.fetch_error else DIM)
        if self.active_tab=='balance': self.render_balance(); return
        status={'すべて':'all','オンライン':'online','問題あり':'issues'}[self.db_filter.get()]
        worlds=filtered_servers(self.db_snapshot,self.db_region,self.search_var.get(),status)
        def sortkey(s):
            if self.sort_field=='status': return status_label(s)
            return s.get(self.sort_field,'')
        worlds.sort(key=sortkey,reverse=self.sort_desc)
        self.label(self.list_area.body,f'{len(worlds)} サーバー · 検索 / 項目をクリックして並べ替え',anchor='w').pack(fill='x',pady=4)
        if self.table_var.get(): self.render_status_table(worlds)
        else:
            for server in worlds:
                c=tk.Canvas(self.list_area.body,width=max(345,self.overlay_width-35),height=116,
                            bg='#15191e',highlightthickness=0)
                c.pack(fill='x',pady=2)
                self.draw_name(c,server['name'],8,17,server['creationBlocked'])
                color='#ff9b42' if server['inMaintenance'] else '#40ff68' if server['isRunning'] else '#ff5252'
                c.create_text(335,17,text=status_label(server),fill=color,anchor='e',font=self.ui(9))
                faction='天族' if server['faction']=='Elyos' else '魔族' if server['faction']=='Asmodian' else '不明'
                c.create_text(8,40,text=f"Faction: {faction}   Region: {server['region']}   Population: {server.get('load',0):.0%}",
                              fill=TEXT,anchor='w',font=self.ui(8))
                c.create_text(8,61,text=f"Current: {server['players']:,}   Max: {server['capacity']:,}   Queue: {server['queue']:,}",
                              fill=TEXT,anchor='w',font=self.ui(8))
                self.draw_spark(c,server['spark'],40,81,290,25,server['capacity']); self.list_area.install_wheel(c)
        if not worlds: self.label(self.list_area.body,'該当するサーバーがありません').pack(pady=20)
        self.apply_extension_surface()

    def render_status_table(self,worlds):
        columns=[('Status','status',92),('Server','name',165),('Faction','faction',65),
                 ('Region','region',60),('Population','load',85),('Current','players',75),
                 ('Max','capacity',70),('Queue','queue',60),('24H',None,150)]
        head=tk.Frame(self.list_area.body,bg=BG); head.pack(anchor='w')
        offsets=[]; x=0
        for title,field,width in columns:
            holder=tk.Frame(head,width=width,height=28,bg=BG); holder.pack(side='left'); holder.pack_propagate(False)
            self.button(holder,title,lambda f=field:self.sort_status(f),padx=1).pack(fill='both',expand=True)
            offsets.append(x); x+=width
        for server in worlds:
            c=tk.Canvas(self.list_area.body,width=x,height=43,bg='#15191e',highlightthickness=0)
            c.pack(anchor='w',pady=1)
            vals=[status_label(server),server['name'],server['faction'],server['region'],f"{server.get('load',0):.0%}",
                  f"{server['players']:,}",f"{server['capacity']:,}",f"{server['queue']:,}"]
            for i,value in enumerate(vals):
                if i==1: self.draw_name(c,value,offsets[i]+4,21,server['creationBlocked'],self.ui(9))
                else:
                    color=TEXT
                    if i==0: color='#ff9b42' if server['inMaintenance'] else '#40ff68' if server['isRunning'] else '#ff5252'
                    c.create_text(offsets[i]+4,21,text=value,fill=color,anchor='w',font=self.ui(8))
            self.draw_spark(c,server['spark'],offsets[-1]+3,16,140,24,server['capacity'])
            self.list_area.install_wheel(c)

    def sort_status(self,field):
        if field is None: return
        self.sort_desc=not self.sort_desc if field==self.sort_field else False
        self.sort_field=field; self.render_db()

    def draw_balance_bar(self,c,elyos,asmo,x,y,width=305):
        fraction=balance_fraction(elyos,asmo)
        if fraction is None:
            text='オンライン人数なし' if elyos==0 and asmo==0 else 'データなし'
            c.create_text(x,y,text=text,fill=DIM,anchor='w',font=self.ui(9)); return
        c.create_text(x,y,text=f'天族 {fraction:.1%} · {elyos:,} 人',anchor='w',fill=TEXT,font=self.ui(8))
        c.create_text(x+width,y,text=f'魔族 {1-fraction:.1%} · {asmo:,} 人',anchor='e',fill=TEXT,font=self.ui(8))
        c.create_rectangle(x,y+11,x+width*fraction,y+22,fill=BLUE,outline='')
        c.create_rectangle(x+width*fraction,y+11,x+width,y+22,fill=PURPLE,outline='')
        c.create_line(x+width/2,y+9,x+width/2,y+24,fill=TEXT)

    def render_balance(self):
        self.label(self.list_area.body,'Faction Balance · オンライン人口の比率',anchor='w').pack(fill='x',pady=5)
        groups=balance_groups(self.db_snapshot,self.db_region,self.search_var.get())
        for region,totals,pairs,unpaired in groups:
            c=tk.Canvas(self.list_area.body,width=max(345,self.overlay_width-35),height=87,bg=BG,highlightthickness=0)
            c.pack(fill='x',pady=3)
            title=dict(REGIONS).get(region['code'],region['code'])
            c.create_text(8,16,text=title+' · 地域全体',fill=TEXT,anchor='w',font=self.ui(10,'bold'))
            self.draw_balance_bar(c,totals['Elyos'],totals['Asmodian'],8,43); self.list_area.install_wheel(c)
            for ename,aname,e,a in pairs:
                c=tk.Canvas(self.list_area.body,width=max(345,self.overlay_width-35),height=98,bg='#15191e',highlightthickness=0)
                c.pack(fill='x',pady=2)
                self.draw_name(c,ename,8,17,bool(e and e['creationBlocked']),self.ui(9,'bold'))
                self.draw_name(c,aname,185,17,bool(a and a['creationBlocked']),self.ui(9,'bold'))
                self.draw_balance_bar(c,e['players'] if e else None,a['players'] if a else None,8,43)
                if e and a:
                    delta=e['players']-a['players']
                    text='均等' if delta==0 else f"{'天族' if delta>0 else '魔族'} +{abs(delta):,} 人"
                    c.create_text(8,87,text=text,anchor='w',fill=DIM,font=self.ui(8))
                self.list_area.install_wheel(c)
            for s in unpaired:
                self.label(self.list_area.body,f"{s['name']} · {s['players']:,} 人 · 公開ペアなし",anchor='w').pack(fill='x',padx=8,pady=3)
        if not groups: self.label(self.list_area.body,'該当するサーバーがありません').pack(pady=20)
        self.button(self.list_area.body,'公開ペアの出典（2026-10-02時点）',lambda:webbrowser.open(PAIRING_SOURCE),padx=8).pack(pady=10)
        self.apply_extension_surface()

    def apply_extension_surface(self):
        # Match upstream background-only transparency; text and controls remain opaque.
        for parent in (getattr(self,'ping_header',None),getattr(self,'extra_section',None)):
            if parent is None: continue
            stack=[parent]
            while stack:
                widget=stack.pop()
                try:
                    stack.extend(widget.winfo_children())
                    if isinstance(widget,(tk.Frame,tk.Label,tk.Canvas)):
                        widget.configure(bg='#010203')
                except tk.TclError: pass

    def paint_ping(self):
        widgets=list(getattr(self,'ping_widgets',{}).items())
        widgets.extend((sid,w) for sid,w,_ in getattr(self,'summary_rows',[]))
        for sid,w in widgets:
            if not w.winfo_exists(): continue
            result=self.results.get(sid)
            if result is None: w.configure(text='… ms',fg=DIM)
            elif result[0] is None: w.configure(text='応答なし',fg='#ff5252')
            else: w.configure(text=f'{result[0]:.1f} ms',fg=latency_color(result[0]))

    def poll_network(self):
        if self.stop_workers.is_set(): return
        changed=False
        while True:
            try: item=self.worker_queue.get_nowait()
            except queue.Empty: break
            if item[0]=='ping' and item[1]==self.ping_generation:
                self.results[item[2]]=(item[3],item[4]); changed=True
            elif item[0]=='scan_done': self.scan_busy=False
            elif item[0]=='db':
                self.fetch_busy=False
                if item[1] is not None:
                    self.db_snapshot=item[1]; self.fetched_at=time.monotonic(); self.fetch_error=''
                else: self.fetch_error=item[2]
                self.render_db()
        if changed: self.paint_ping()
        if self._background_disabled: return
        now=time.monotonic()
        if not self.scan_busy and now>=self.next_scan:
            targets={s['id']:copy.deepcopy(s) for _,s in self.chosen_endpoints()}
            if self.active_tab=='ping': targets.update({s['id']:copy.deepcopy(s) for s in self.visible_endpoints()})
            self.next_scan=now+2.5
            if targets:
                self.scan_busy=True
                threading.Thread(target=scan,args=(list(targets.values()),self.ping_generation,self.worker_queue,self.stop_workers),daemon=True).start()
        if not self.fetch_busy and now>=self.next_fetch:
            self.fetch_busy=True; self.next_fetch=now+60
            threading.Thread(target=self.fetch_db_worker,daemon=True).start()

    def fetch_db_worker(self):
        try: self.worker_queue.put(('db',fetch_snapshot(),''))
        except Exception as exc: self.worker_queue.put(('db',None,str(exc)))

    def close_ping(self):
        if getattr(self,'tray_icon',None): self.tray_icon.close()
        self.stop_workers.set(); self.save_ping(); self.persist_dialog_positions()
