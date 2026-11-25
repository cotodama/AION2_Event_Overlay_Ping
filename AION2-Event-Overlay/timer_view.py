"""TimerViewMixin: feature-specific UI; loaded by the shared application shell."""
import re
import tkinter as tk
from tkinter import ttk,messagebox

class TimerViewMixin:
    def localized_timer_name(self,name):
        """Translate only built-in/default timer names; preserve user-defined names."""
        name=str(name or "")
        lang=self.cfg.get("language","ja")
        if lang=="en":
            if name=="新しいタイマー":
                return "New Timer"
            m=re.fullmatch(r"タイマー-(\d+)",name)
            if m:
                return f"Timer {m.group(1)}"
        else:
            if name=="New Timer":
                return "新しいタイマー"
            m=re.fullmatch(r"Timer\s+(\d+)",name,re.IGNORECASE)
            if m:
                return f"タイマー-{m.group(1)}"
        return name


    def rebuild_timers(self):
        from AION2_Event_Overlay import HUD_TRANSPARENT_KEY,fmt
        for w in self.timer_content.winfo_children():w.destroy()
        self.timer_widgets=[]
        c=self.panel_colors()
        for timer in self.timers:
            if not timer.visible: continue
            f=tk.Frame(self.timer_content,bg=HUD_TRANSPARENT_KEY,
                       highlightthickness=1,highlightbackground="#52606b")
            f.pack(fill="x",padx=5,pady=4)

            top=tk.Frame(f,bg=HUD_TRANSPARENT_KEY)
            top.pack(fill="x",padx=8,pady=(5,2))
            display_timer_name=self.localized_timer_name(timer.name)
            tk.Label(top,text=display_timer_name,font=self.ui(10,"bold"),fg="white",
                     bg=HUD_TRANSPARENT_KEY).pack(side="left",anchor="center")

            def square(parent,text,command,font=None):
                holder=tk.Frame(parent,bg=HUD_TRANSPARENT_KEY,width=34,height=34)
                holder.pack(side="right")
                holder.pack_propagate(False)
                b=self.make_hud_square_button(holder,text,command,size=34,font=font)
                b.place(relx=.5,rely=.5,anchor="center",width=34,height=34)
                return b

            def hide_timer(tmr=timer):
                tmr.visible=False; self.save_timers(); self.rebuild_timers()
                self.root.after_idle(self.fit_window_to_content)

            minus=square(top,"−",hide_timer,self.ui(11,"bold"))

            time_row=tk.Frame(f,bg=HUD_TRANSPARENT_KEY)
            time_row.pack(fill="x",padx=8,pady=(0,2))
            val=tk.Label(time_row,text=fmt(timer.duration),font=self.mono(18,"bold"),
                         fg="white",bg=HUD_TRANSPARENT_KEY)
            val.pack(side="left",anchor="center")
            finish=tk.Label(time_row,text="",font=self.ui(9,"bold"),fg="#f0b3b3",
                            bg=HUD_TRANSPARENT_KEY,anchor="e")
            finish.pack(side="right",anchor="center",padx=(10,0))

            controls=tk.Frame(f,bg=HUD_TRANSPARENT_KEY)
            controls.pack(fill="x",padx=8,pady=(3,7))

            # Left controls all share exactly the same 34x34 geometry.
            left=tk.Frame(controls,bg=HUD_TRANSPARENT_KEY)
            left.pack(side="left")
            def left_square(text,command,font=None):
                holder=tk.Frame(left,bg=HUD_TRANSPARENT_KEY,width=34,height=34)
                holder.pack(side="left",padx=(0,5))
                holder.pack_propagate(False)
                b=self.make_hud_square_button(holder,text,command,size=34,font=font)
                b.place(relx=.5,rely=.5,anchor="center",width=34,height=34)
                return b

            play_pause=left_square("▶",lambda:None,self.ui(11,"bold"))
            try:
                play_pause.place_configure(relx=.5, x=1)
            except Exception:
                pass
            def toggle_timer(tmr=timer,button=play_pause):
                if tmr.running:
                    tmr.stop(); button.config(text="▶")
                else:
                    tmr.start(); button.config(text="⏸")
            play_pause.config(command=toggle_timer)

            def reset_timer(tmr=timer,button=play_pause):
                tmr.reset(); button.config(text="▶")
            reset_btn=left_square("↻",reset_timer,self.ui(14,"bold"))

            def toggle_timer_alert(tmr=timer,button=None):
                tmr.alert_enabled=not tmr.alert_enabled
                if button is not None:
                    button.config(text=("🔔" if tmr.alert_enabled else "🔕"),
                                  fg=("#dcecff" if tmr.alert_enabled else "#6f7885"))
                self.save_timers()
            bell_holder=tk.Frame(controls,bg=HUD_TRANSPARENT_KEY,width=34,height=34)
            bell_holder.pack(side="right")
            bell_holder.pack_propagate(False)
            bell=self.make_hud_square_button(bell_holder,
                    "🔔" if timer.alert_enabled else "🔕",lambda:None,size=34,font=self.ui(10))
            bell.config(fg=("#dcecff" if timer.alert_enabled else "#6f7885"))
            bell.config(command=lambda tmr=timer,b=bell: toggle_timer_alert(tmr,b))
            bell.place(relx=.5,rely=.5,anchor="center",width=34,height=34)

            self.timer_widgets.append((timer,val,finish,play_pause))

        if not self.timer_widgets:
            tk.Label(self.timer_content,text=self.tr(
                "表示中のタイマーはありません。+ で追加・設定できます。",
                "No visible timers. Use + to add or configure."),
                fg="#e1e7ee",bg=HUD_TRANSPARENT_KEY,font=self.ui(9,"bold"),
                justify="center",anchor="center").pack(fill="x",padx=8,pady=12)
        if getattr(self,"timer_panel_visible",False):
            self.root.after_idle(self.fit_window_to_content)


    def open_timer_settings(self):
        from AION2_Event_Overlay import TimerState
        if not hasattr(self, "_dialog_windows"):
            self._dialog_windows = {}
        existing=self._dialog_windows.get("timer")
        try:
            if existing is not None and existing.winfo_exists():
                existing.deiconify(); existing.lift()
                return
        except Exception:
            pass
        c=self.panel_colors()
        win=self._new_dialog(self.tr("タイマー設定","Timer Settings"))
        self._dialog_windows["timer"]=win
        def close_dialog():
            self._dialog_windows.pop("timer",None)
            self._safe_dialog_close(win)
        win.protocol("WM_DELETE_WINDOW",close_dialog)
        win.configure(bg=c["root"])
        win.resizable(False,False)

        # Keep this dialog deliberately narrow: the overlay's design language is
        # vertical and compact, not a wide desktop settings sheet.
        outer=tk.Frame(win,bg=c["root"])
        outer.pack(fill="both",expand=True,padx=8,pady=8)

        head=tk.Frame(outer,bg=c["header"],height=38)
        head.pack(fill="x"); head.pack_propagate(False)
        tk.Label(head,text=self.tr("タイマー設定","TIMER SETTINGS"),
                 font=self.ui(12,"bold"),fg="white",bg=c["header"]).pack(
                     side="left",padx=9)

        def save_all():
            self.save_timers()
            self.rebuild_timers()
            if getattr(self,"timer_panel_visible",False):
                self.root.after_idle(self.fit_window_to_content)

        def delete_one(timer):
            if timer in self.timers:
                self.timers.remove(timer)
            save_all(); refresh()

        def add_timer():
            self.timers.append(TimerState({
                "name":self.tr("新しいタイマー","New Timer"),
                "duration":300,"visible":False,"alert_enabled":True
            }))
            save_all(); refresh()

        add_holder=tk.Frame(head,bg=c["header"],width=30,height=30)
        add_holder.pack(side="right",padx=5,pady=4); add_holder.pack_propagate(False)
        self.make_hud_square_button(add_holder,"+",add_timer,size=30).place(
            x=0,y=0,width=30,height=30)

        body_wrap=tk.Frame(outer,bg=c["root"])
        body_wrap.pack(fill="both",expand=True,pady=(5,0))
        canvas=tk.Canvas(body_wrap,bg=c["root"],highlightthickness=0,
                         borderwidth=0,width=346,height=360)
        scrollbar=tk.Scrollbar(body_wrap,orient="vertical",command=canvas.yview)
        body=tk.Frame(canvas,bg=c["root"])
        body_id=canvas.create_window((0,0),window=body,anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left",fill="both",expand=True)
        scrollbar.pack(side="right",fill="y")

        def wheel(event):
            d=getattr(event,"delta",0)
            if d: canvas.yview_scroll(-1 if d>0 else 1,"units")
            return "break"
        win.bind("<MouseWheel>",wheel,add="+")
        def bind_wheel(w):
            try: w.bind("<MouseWheel>",wheel,add="+")
            except Exception: pass
            for ch in w.winfo_children(): bind_wheel(ch)

        def sync_scroll(_=None):
            try:
                canvas.configure(scrollregion=canvas.bbox("all"))
                canvas.itemconfigure(body_id,width=canvas.winfo_width())
            except Exception: pass
        body.bind("<Configure>",sync_scroll)
        canvas.bind("<Configure>",sync_scroll)

        def fit_settings():
            # Same outer width as the main Settings dialog.
            # Height follows the timer-card content and is capped; overflow scrolls.
            try:
                win.update_idletasks()
                content_h=max(1, body.winfo_reqheight())
                # header/outer chrome ~= 64px; keep a practical minimum for 1 timer.
                target_h=max(205, min(525, content_h + 64))
            except Exception:
                target_h=360
            self._place_compact_dialog(win,480,target_h)

        def refresh():
            for child in body.winfo_children(): child.destroy()
            if not self.timers:
                tk.Label(body,text=self.tr("タイマーはありません。＋で追加できます。",
                    "No timers. Use + to add one."),fg="#b8c4d0",bg=c["root"],
                    font=self.ui(9,"bold")).pack(fill="x",pady=20)
                win.after_idle(sync_scroll); win.after_idle(fit_settings); return

            for index,timer in enumerate(self.timers,1):
                card=tk.Frame(body,bg=c["card"],highlightthickness=1,
                              highlightbackground="#303842")
                card.pack(fill="x",pady=(0,5))

                # One compact title strip.
                title=tk.Frame(card,bg=c["header"],height=28)
                title.pack(fill="x"); title.pack_propagate(False)
                tk.Label(title,text=f"{self.tr('タイマー','Timer')} {index}",
                         fg="white",bg=c["header"],
                         font=self.ui(9,"bold")).pack(side="left",padx=8)

                inner=tk.Frame(card,bg=c["card"])
                inner.pack(fill="x",padx=8,pady=6)

                # Name and duration use short, dense rows instead of large form blocks.
                name_row=tk.Frame(inner,bg=c["card"]); name_row.pack(fill="x",pady=(0,4))
                tk.Label(name_row,text=self.tr("名称","Name"),fg="#bcdcff",bg=c["card"],
                         font=self.ui(8,"bold"),width=5,anchor="w").pack(side="left")
                name=tk.Entry(name_row,bg=c["header"],fg="white",insertbackground="white",
                              relief="flat",font=self.ui(9))
                name.insert(0,self.localized_timer_name(timer.name))
                name.pack(side="left",fill="x",expand=True,ipady=2)

                time_row=tk.Frame(inner,bg=c["card"]); time_row.pack(fill="x")
                tk.Label(time_row,text=self.tr("時間","Time"),fg="#bcdcff",bg=c["card"],
                         font=self.ui(8,"bold"),width=5,anchor="w").pack(side="left")
                total=max(1,int(timer.duration))
                hv=tk.IntVar(value=total//3600); mv=tk.IntVar(value=(total%3600)//60)
                sv=tk.IntVar(value=total%60)
                controls=tk.Frame(time_row,bg=c["card"]); controls.pack(side="left")
                def spin(var,maximum,unit):
                    box=tk.Frame(controls,bg=c["card"]); box.pack(side="left",padx=(0,3))
                    sp=ttk.Combobox(box,values=list(range(maximum+1)),textvariable=var,width=4 if maximum>99 else 3,
                                    state='readonly',font=self.ui(12),justify='center')
                    sp.pack(side='left',ipady=4)
                    from time_inputs import stop_wheel
                    stop_wheel(sp)
                    tk.Label(box,text=unit,fg="#f5f5f5",bg=c["card"],
                             font=self.ui(8)).pack(side="left",padx=(2,0))
                spin(hv,999,self.tr("時","h")); spin(mv,59,self.tr("分","m"))
                spin(sv,59,self.tr("秒","s"))

                # Save/Delete share the same row as the duration controls.
                # This uses the otherwise empty right-hand space and shortens each card.
                actions=tk.Frame(inner,bg=c['card']);actions.pack(fill='x',pady=(5,0))
                def apply_one(timer=timer,name=name,hv=hv,mv=mv,sv=sv):
                    try:
                        h=int(hv.get()); m=int(mv.get()); s=int(sv.get())
                        if h<0 or not 0<=m<=59 or not 0<=s<=59: raise ValueError
                        duration=h*3600+m*60+s
                        if duration<=0: raise ValueError
                        timer.name=name.get().strip() or self.tr("タイマー","Timer")
                        timer.duration=duration; timer.visible=True; timer.reset()
                        save_all()
                    except Exception:
                        messagebox.showerror("Error",self.tr(
                            "時間は「時・分・秒」で正しく入力してください。0秒にはできません。",
                            "Enter a valid hours/minutes/seconds duration. Duration cannot be zero."
                        ),parent=win)
                tk.Button(actions,text=self.tr("削除","Delete"),
                          command=lambda timer=timer:delete_one(timer),
                          bg="#4a2929",fg="white",activebackground="#623235",
                          activeforeground="white",relief="flat",cursor="hand2",
                          font=self.ui(8),padx=6,pady=1).pack(side="right")
                tk.Button(actions,text=self.tr("保存","Save"),command=apply_one,
                          bg=c["button"],fg="white",activebackground="#26394d",
                          activeforeground="white",relief="flat",cursor="hand2",
                          font=self.ui(8,"bold"),padx=7,pady=1).pack(
                              side="right",padx=(0,4))

            bind_wheel(body)
            from time_inputs import protect_selectors
            body._time_scroll_canvas=canvas;protect_selectors(body)
            win.after_idle(sync_scroll); win.after_idle(fit_settings)

        refresh()
        win.after_idle(lambda:(fit_settings(),win.deiconify(),win.lift()))


