"""SettingsFeatureMixin: feature-specific UI; loaded by the shared application shell."""
import os
import tkinter as tk
from tkinter import ttk,messagebox,filedialog

class SettingsFeatureMixin:
    def settings(self):
        from AION2_Event_Overlay import APP_VERSION,save_config
        if not hasattr(self, "_dialog_windows"):
            self._dialog_windows = {}
        existing=self._dialog_windows.get("settings")
        try:
            if existing is not None and existing.winfo_exists():
                existing.deiconify(); existing.lift()
                return
        except Exception:
            pass
        c=self.panel_colors()
        win=self._new_dialog(self.tr("設定","Settings"))
        self._dialog_windows["settings"]=win
        def close_dialog():
            self._dialog_windows.pop("settings",None)
            self._safe_dialog_close(win)
        win.protocol("WM_DELETE_WINDOW",close_dialog)
        win.configure(bg=c["root"])
        win.resizable(True,True)
        win.minsize(390,300)

        outer=tk.Frame(win,bg=c["root"])
        outer.pack(fill="both",expand=True,padx=8,pady=8)
        head=tk.Frame(outer,bg=c["header"]); head.pack(fill="x")
        # Header controls use the same vertical center line.
        head.configure(height=44)
        head.pack_propagate(False)
        tk.Label(head,text=self.tr("設定","SETTINGS"),font=self.ui(13,"bold"),
                 fg="white",bg=c["header"]).pack(side="left",padx=10,fill="y")
        tk.Button(head,text=self.tr("オーバーレイを閉じる","Close Overlay"),
                  bg="#5b2327",activebackground="#743038",
                  fg="white",activeforeground="white",
                  relief="flat",bd=0,font=self.ui(9,"bold"),cursor="hand2",
                  command=self.on_close).pack(side="right",padx=6,pady=7)

        emoji_row=tk.Frame(outer,bg=c['root']); emoji_row.pack(fill='x',pady=(3,0))
        self.event_emoji_var=self.build_event_emoji_checkbox(emoji_row)
        self.build_event_compact_checkbox(emoji_row)
        self.build_ping_layer_checkbox(emoji_row)
        tabs=tk.Frame(outer,bg=c["root"]); tabs.pack(fill="x",pady=(7,4))
        content=tk.Frame(outer,bg=c["root"]); content.pack(fill="both",expand=True)
        pages={}
        tab_buttons={}

        def fit_settings():
            if win.winfo_ismapped(): return
            event_area.canvas.configure(height=min(event_list.winfo_reqheight(),win.winfo_screenheight()-260))
            self._place_compact_dialog(win,390,260)

        def show_page(key):
            for k,p in pages.items(): p.pack_forget()
            pages[key].pack(fill="both",expand=True)
            for k,b in tab_buttons.items(): b.config(relief="sunken" if k==key else "flat")
            win.after_idle(fit_settings)

        for key,label in (("events",self.tr("イベント","Events")),("display",self.tr("表示","Display")),("alerts",self.tr("アラート","Alerts")),("info",self.tr("情報","Info"))):
            b=tk.Button(tabs,text=label,bg=c["button"],fg="white",relief="flat",font=self.ui(9,"bold"),command=lambda k=key:show_page(k))
            b.pack(side="left",padx=(0,4)); tab_buttons[key]=b
            pages[key]=tk.Frame(content,bg=c["root"])

        # Events page -- cards matching the overlay rather than a native ttk table.
        ef=pages["events"]
        from ping_feature import ScrollArea
        event_area=ScrollArea(ef,height=310,bg=c['root']); event_area.frame.pack(fill='both',expand=True)
        event_list=event_area.body
        event_actions=tk.Frame(ef,bg=c["root"]); event_actions.pack(fill="x",pady=(6,0))
        selected={"index":None}
        cards=[]
        def layout_settings_cards(event=None):
            width=max(1,event_area.canvas.winfo_width())
            columns=2 if width>=720 else 1
            for column in range(2): event_list.columnconfigure(column,weight=1 if column<columns else 0,uniform='cards' if column<columns else '')
            for index,card in enumerate(cards):
                card.grid(row=index//columns,column=index%columns,sticky='nsew',padx=(0,4 if columns>1 else 0),pady=3)
                for label in getattr(card,'_name_labels',[]): label.configure(wraplength=max(110,width//columns-190))
        event_area.canvas.bind('<Configure>',layout_settings_cards,add='+')
        win._event_settings_area=event_area

        def refresh_events():
            for w in event_list.winfo_children(): w.destroy()
            cards.clear()
            selected["index"]=None
            for i,e in enumerate(self.cfg["events"]):
                card=tk.Frame(event_list,bg=c["card"],highlightthickness=1,highlightbackground="#252c35")
                cards.append(card)
                left=tk.Frame(card,bg=c["card"]); left.pack(side="left",fill="both",expand=True,padx=9,pady=7)
                name_label=tk.Label(left,text=self.event_name(e),font=self.ui(10,"bold"),fg="#ffffff",bg=c["card"],justify='left')
                name_label.pack(anchor='w'); card._name_labels=[name_label]
                state=f'{e.get("type","daily")} / {"ON" if e.get("enabled",True) else "OFF"}'
                if not e.get('schedule_confirmed',True): state+=' / 未確認' 
                tk.Label(left,text=state,font=self.ui(8),fg="#8fa0b5",bg=c["card"]).pack(anchor="w",pady=(2,0))
                actions=tk.Frame(card,bg=c["card"]); actions.pack(side="right",padx=7,pady=7)
                tk.Button(actions,text=self.tr("編集","Edit"),bg=c["button"],fg="white",relief="flat",command=lambda i=i:self.edit_event(win,i,refresh_events)).pack(side="left",padx=2)
                tk.Button(actions,text=self.tr('音','Sound'),bg=c['button'],fg='white',relief='flat',
                          command=lambda e=e:self.open_event_notification_settings(e,refresh_events)).pack(side='left',padx=2)
                for widget in (card,left,actions): event_area.install_wheel(widget)
                def delete_event(i=i):
                    del self.cfg["events"][i]; save_config(self.cfg); self.rebuild_event_widgets(); refresh_events(); win.after_idle(fit_settings)
                tk.Button(actions,text=self.tr("削除","Delete"),bg="#4a2929",fg="white",relief="flat",command=delete_event).pack(side="left",padx=2)
            from boss_groups import boss_display_items
            for item in boss_display_items(self.tracker.catalog['bosses']):
                card=tk.Frame(event_list,bg=c['card'],highlightthickness=1,highlightbackground='#252c35')
                cards.append(card)
                actions=tk.Frame(card,bg=c['card']); actions.pack(side='right',padx=7,pady=7)
                tk.Button(actions,text='予定・通知',bg=c['button'],fg='white',relief='flat',command=lambda row=item:self.edit_boss_group(row,parent=win)).pack(side='left',padx=2)
                def delete_named(row=item):
                    self.delete_boss_group(row); refresh_events()
                tk.Button(actions,text='削除',bg='#4a2929',fg='white',relief='flat',command=delete_named).pack(side='left',padx=2)
                left=tk.Frame(card,bg=c['card']); left.pack(side='left',fill='both',expand=True,padx=9,pady=7)
                name_label=tk.Label(left,text=item['name'],font=self.ui(10,'bold'),fg='white',bg=c['card'],justify='left')
                name_label.pack(anchor='w'); card._name_labels=[name_label]
                tk.Label(left,text='ネームド / 装備IL '+str(item.get('equipment_il','未確認')),font=self.ui(8),fg='#8fa0b5',bg=c['card']).pack(anchor='w')
            layout_settings_cards()
            win.after_idle(fit_settings)

        self._refresh_event_settings=refresh_events
        tk.Button(event_actions,text="＋ "+self.tr("イベント追加","Add Event"),bg=c["button"],fg="white",relief="flat",command=lambda:self.edit_event(win,None,refresh_events)).pack(side="left")
        refresh_events()

        # Display page -- same charcoal cards/buttons as the main overlay.
        df=pages["display"]
        display_area=ScrollArea(df,height=460,bg=c['root']);display_area.frame.pack(fill='both',expand=True)
        df=display_area.body
        card=tk.Frame(df,bg=c["card"],highlightthickness=1,highlightbackground="#252c35"); card.pack(fill="x",pady=3)
        form=tk.Frame(card,bg=c["card"]); form.pack(fill="x",padx=10,pady=9)
        def form_label(txt): tk.Label(form,text=txt,font=self.ui(9,"bold"),fg="#f5f5f5",bg=c["card"]).pack(anchor="w",pady=(7,3))
        combo_style={"state":"readonly","font":self.ui(9)}
        form_label("Language")
        lv=tk.StringVar(value="English" if self.cfg.get("language")=="en" else "日本語")
        lbox=ttk.Combobox(form,textvariable=lv,values=["日本語","English"],**combo_style); lbox.pack(fill="x")
        form_label(self.tr("表示時間帯","Display Time Zone"))
        zv=tk.StringVar(value=self.cfg.get("display_timezone","JST")); ttk.Combobox(form,textvariable=zv,values=["JST","PDT","CEST"],**combo_style).pack(fill="x")
        form_label(self.tr("背景の透過度","HUD background opacity"))
        op=tk.Scale(form,from_=20,to=100,orient="horizontal",showvalue=True,bg=c["card"],fg="white",highlightthickness=0,troughcolor=c["header"],activebackground=c["button"],length=360,command=self.preview_background_opacity)
        _op=float(self.cfg.get("background_opacity",.70)); _op=_op/100.0 if _op>1.0 else _op; op.set(int(_op*100)); op.pack(fill="x")
        def apply_display():
            self.cfg["language"]="en" if lv.get()=="English" else "ja"
            self.cfg["display_timezone"]=zv.get()
            self.cfg["background_opacity"]=max(.05,min(1.0,op.get()/100))
            self.cfg.pop("opacity",None)
            save_config(self.cfg)

            # Apply language immediately. Previously the static HUD labels and timer
            # area were only rebuilt after another action (e.g. creating a timer).
            try:
                self.event_title.config(text=self.tr("イベント（右クリックで名前・時刻を編集）","EVENTS (right-click to edit)"))
                self.timer_title.config(text=self.tr("タイマー","TIMERS"))
                self.rebuild_event_widgets()
                self.rebuild_timers()
                self._tick_once()
            except Exception as exc:
                print(f"[AION2 Overlay] Language refresh warning: {exc}")

            self.apply_main_hud_surface_style()
            self.apply_frameless_mode()
            self.apply_background_opacity()
            self._safe_dialog_close(win)
        tk.Button(df,text=self.tr("適用","Apply"),command=apply_display,bg=c["button"],fg="white",relief="flat",font=self.ui(9,"bold")).pack(anchor="e",pady=(6,0))

        # Alerts page
        af=pages["alerts"]
        acard=tk.Frame(af,bg=c["card"],highlightthickness=1,highlightbackground="#252c35")
        acard.pack(fill="x",pady=3)
        aform=tk.Frame(acard,bg=c["card"]); aform.pack(fill="x",padx=10,pady=10)

        tk.Label(aform,text=self.tr("イベントアラート音量","Event alert volume"),
                 font=self.ui(9,"bold"),fg="#f5f5f5",bg=c["card"]).pack(anchor="w")
        av=tk.Scale(aform,from_=0,to=100,orient="horizontal",showvalue=True,bg=c["card"],fg="white",
                    highlightthickness=0,troughcolor=c["header"],activebackground=c["button"],length=360)
        av.set(int(self.cfg.get("alert_volume",45))); av.pack(fill="x",pady=(3,10))

        tk.Label(aform,text=self.tr("アラート音","Alert sound"),
                 font=self.ui(9,"bold"),fg="#f5f5f5",bg=c["card"]).pack(anchor="w")

        sound_var=tk.StringVar()
        custom_path=self.cfg.get("alert_sound_file","").strip()
        sound_var.set(custom_path if custom_path else self.tr("デフォルト（ソフトチャイム）","Default (soft chime)"))

        sound_row=tk.Frame(aform,bg=c["card"]); sound_row.pack(fill="x",pady=(3,5))
        sound_entry=tk.Entry(sound_row,textvariable=sound_var,state="readonly",
                             readonlybackground=c["header"],fg="white",relief="flat",font=self.ui(9))
        sound_entry.pack(side="left",fill="x",expand=True,ipady=4)

        def choose_sound():
            path=filedialog.askopenfilename(
                parent=win,
                title=self.tr("アラート音を選択","Choose alert sound"),
                filetypes=[(self.tr("音声ファイル","Audio files"),"*.wav *.mp3"),
                           ("WAV","*.wav"),("MP3","*.mp3")]
            )
            if path:
                sound_var.set(path)

        def use_default_sound():
            sound_var.set(self.tr("デフォルト（ソフトチャイム）","Default (soft chime)"))

        tk.Button(sound_row,text=self.tr("参照","Browse"),command=choose_sound,
                  bg=c["button"],fg="white",relief="flat",font=self.ui(9),padx=8).pack(side="left",padx=(6,0))
        tk.Button(sound_row,text=self.tr("既定","Default"),command=use_default_sound,
                  bg=c["button"],fg="white",relief="flat",font=self.ui(9),padx=8).pack(side="left",padx=(4,0))

        tk.Label(aform,text=self.tr(
            "WAV/MP3ファイルを選択できます。\n「既定」で内蔵のソフトチャイムに戻ります。",
            "Choose a WAV or MP3 file, or use Default to return to the built-in soft chime."
        ),font=self.ui(8),fg="#7d8795",bg=c["card"],justify="left",
           anchor="w",wraplength=330).pack(fill="x",pady=(0,8))

        def selected_sound_path():
            v=sound_var.get().strip()
            default_labels={
                "デフォルト（ソフトチャイム）",
                "Default (soft chime)"
            }
            return "" if v in default_labels else v

        alert_actions=tk.Frame(aform,bg=c["card"]); alert_actions.pack(fill="x")

        def preview_alert():
            old_volume=self.cfg.get("alert_volume",45)
            old_sound=self.cfg.get("alert_sound_file","")
            self.cfg["alert_volume"]=av.get()
            self.cfg["alert_sound_file"]=selected_sound_path()
            self.play_event_alert()
            self.cfg["alert_volume"]=old_volume
            self.cfg["alert_sound_file"]=old_sound

        def apply_alerts():
            path=selected_sound_path()
            if path and (not os.path.isfile(path) or os.path.splitext(path)[1].lower() not in (".wav",".mp3")):
                messagebox.showerror(
                    self.tr("音声ファイルエラー","Audio file error"),
                    self.tr("有効なWAVまたはMP3ファイルを選択してください。","Please choose a valid WAV or MP3 file."),
                    parent=win
                )
                return
            self.cfg["alert_volume"]=av.get()
            self.cfg["alert_sound_file"]=path
            save_config(self.cfg)

        tk.Button(alert_actions,text=self.tr("試聴","Preview"),command=preview_alert,
                  bg=c["button"],fg="white",relief="flat",font=self.ui(9),
                  padx=10,pady=3,cursor="hand2").pack(side="left")
        tk.Button(alert_actions,text=self.tr("適用","Apply"),command=apply_alerts,
                  bg=c["button"],fg="white",relief="flat",font=self.ui(9,"bold"),
                  padx=10,pady=3,cursor="hand2").pack(side="right")

        # Timer alerts (independent from event alerts)
        tcard=tk.Frame(af,bg=c["card"],highlightthickness=1,highlightbackground="#252c35")
        tcard.pack(fill="x",pady=(8,3))
        tf=tk.Frame(tcard,bg=c["card"]); tf.pack(fill="x",padx=10,pady=10)
        tk.Label(tf,text=self.tr("タイマーアラート音量","Timer alert volume"),
                 font=self.ui(9,"bold"),fg="#f5f5f5",bg=c["card"]).pack(anchor="w")
        tav=tk.Scale(tf,from_=0,to=100,orient="horizontal",showvalue=True,bg=c["card"],fg="white",
                     highlightthickness=0,troughcolor=c["header"],activebackground=c["button"],length=360)
        tav.set(int(self.cfg.get("timer_alert_volume",45))); tav.pack(fill="x",pady=(3,10))
        tk.Label(tf,text=self.tr("タイマーアラート音","Timer alert sound"),
                 font=self.ui(9,"bold"),fg="#f5f5f5",bg=c["card"]).pack(anchor="w")
        tsound_var=tk.StringVar()
        tp=self.cfg.get("timer_alert_sound_file","").strip()
        tsound_var.set(tp if tp else self.tr("デフォルト（タイマーチャイム）","Default (timer chime)"))
        tsrow=tk.Frame(tf,bg=c["card"]); tsrow.pack(fill="x",pady=(3,5))
        tse=tk.Entry(tsrow,textvariable=tsound_var,state="readonly",readonlybackground=c["header"],
                     fg="white",relief="flat",font=self.ui(9))
        tse.pack(side="left",fill="x",expand=True,ipady=4)
        def choose_timer_sound():
            path=filedialog.askopenfilename(parent=win,title=self.tr("タイマーアラート音を選択","Choose timer alert sound"),
                filetypes=[(self.tr("音声ファイル","Audio files"),"*.wav *.mp3"),("WAV","*.wav"),("MP3","*.mp3")])
            if path: tsound_var.set(path)
        def default_timer_sound():
            tsound_var.set(self.tr("デフォルト（タイマーチャイム）","Default (timer chime)"))
        tk.Button(tsrow,text=self.tr("参照","Browse"),command=choose_timer_sound,bg=c["button"],fg="white",
                  relief="flat",font=self.ui(9),padx=8).pack(side="left",padx=(6,0))
        tk.Button(tsrow,text=self.tr("既定","Default"),command=default_timer_sound,bg=c["button"],fg="white",
                  relief="flat",font=self.ui(9),padx=8).pack(side="left",padx=(4,0))
        tk.Label(tf,text=self.tr("WAV/MP3ファイルを選択できます。\n「既定」で内蔵のタイマーチャイムに戻ります。",
                                 "Choose a WAV/MP3 file.\nDefault restores the built-in timer chime."),
                 font=self.ui(8),fg="#7d8795",bg=c["card"],justify="left",anchor="w",wraplength=330).pack(fill="x",pady=(0,8))
        def timer_sound_path():
            v=tsound_var.get().strip()
            return "" if v in {"デフォルト（タイマーチャイム）","Default (timer chime)"} else v
        ta=tk.Frame(tf,bg=c["card"]); ta.pack(fill="x")
        def preview_timer_alert():
            ov=self.cfg.get("timer_alert_volume",45); osf=self.cfg.get("timer_alert_sound_file","")
            self.cfg["timer_alert_volume"]=tav.get(); self.cfg["timer_alert_sound_file"]=timer_sound_path()
            self.play_timer_alert()
            self.cfg["timer_alert_volume"]=ov; self.cfg["timer_alert_sound_file"]=osf
        def apply_timer_alert():
            path=timer_sound_path()
            if path and (not os.path.isfile(path) or os.path.splitext(path)[1].lower() not in (".wav",".mp3")):
                messagebox.showerror(self.tr("音声ファイルエラー","Audio file error"),
                                     self.tr("有効なWAVまたはMP3ファイルを選択してください。","Please choose a valid WAV or MP3 file."),parent=win)
                return
            self.cfg["timer_alert_volume"]=tav.get(); self.cfg["timer_alert_sound_file"]=path; save_config(self.cfg)
        tk.Button(ta,text=self.tr("試聴","Preview"),command=preview_timer_alert,bg=c["button"],fg="white",
                  relief="flat",font=self.ui(9),padx=10,pady=3,cursor="hand2").pack(side="left")
        tk.Button(ta,text=self.tr("適用","Apply"),command=apply_timer_alert,bg=c["button"],fg="white",
                  relief="flat",font=self.ui(9,"bold"),padx=10,pady=3,cursor="hand2").pack(side="right")

        # Information page
        inf=pages["info"]
        self.theme_controls(df)
        self.updater_controls(inf)
        info_card=tk.Frame(inf,bg=c["card"],highlightthickness=1,highlightbackground="#252c35")
        info_card.pack(fill="x",pady=3)
        tk.Label(info_card,text="AION2 Event Overlay",
                 font=self.ui(12,"bold"),fg="white",bg=c["card"]).pack(anchor="w",padx=12,pady=(12,3))
        tk.Label(info_card,text=f"Version {APP_VERSION}",
                 font=self.ui(10),fg="#dcecff",bg=c["card"]).pack(anchor="w",padx=12,pady=(0,4))
        audio_status=tk.Label(info_card,font=self.ui(9),fg='#bcdcff',bg=c['card'],justify='left',wraplength=340)
        audio_status.pack(anchor='w',padx=12,pady=(0,8))
        def update_audio_status():
            if not win.winfo_exists():return
            state='使用できます' if self.audio.ready.is_set() else '準備中'
            if self.audio.error:state=self.audio.error
            audio_status.configure(text='Windows音量ミキサー：AION2 Event Overlay Ping\n'+state)
            win.after(500,update_audio_status)
        update_audio_status()
        # Keep the Japanese notice marker aligned with the first text line.
        # A separate marker column also gives wrapped lines a clean hanging indent.
        if self.cfg.get("language", "ja") == "ja":
            tk.Label(info_card,
                     text="AION2のイベント時刻・タイマー・アラートを表示するオーバーレイです。",
                     font=self.ui(9),fg="#aeb9c7",bg=c["card"],justify="left",wraplength=340
                     ).pack(anchor="w",padx=12,pady=(0,10))
            notices=(
                "ゲーム内部の時刻を直接参照していないため、ゲーム内の時刻と数秒程度の差が生じる場合があります。",
                "本ツールは非公式のコミュニティツールであり、AION2およびNCSOFTの公式ツールではありません。",
            )
            for i, notice in enumerate(notices):
                row=tk.Frame(info_card,bg=c["card"])
                row.pack(fill="x",padx=12,pady=(0,10 if i == 0 else 12))
                tk.Label(row,text="※",font=self.ui(9),fg="#aeb9c7",bg=c["card"],
                         anchor="nw").pack(side="left",anchor="n")
                tk.Label(row,text=notice,font=self.ui(9),fg="#aeb9c7",bg=c["card"],
                         justify="left",wraplength=318,anchor="nw"
                         ).pack(side="left",anchor="n",padx=(5,0))
        else:
            tk.Label(info_card,
                     text=("An overlay for displaying AION2 event schedules, timers, and alerts.\n\n"
                           "Note: This application does not access the game's internal clock, so displayed times may differ from the in-game time by a few seconds.\n\n"
                           "This is an unofficial community tool and is not affiliated with or endorsed by AION2 or NCSOFT."),
                     font=self.ui(9),fg="#aeb9c7",bg=c["card"],justify="left",wraplength=340
                     ).pack(anchor="w",padx=12,pady=(0,12))

        show_page("events")
        def finish_settings_dialog():
            try:
                win.update_idletasks()
                fit_settings()
                win.deiconify()
                win.lift()
            except Exception:
                pass
        win.after_idle(finish_settings_dialog)
        win.after_idle(fit_settings)


