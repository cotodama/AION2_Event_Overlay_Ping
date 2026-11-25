"""EventViewMixin: feature-specific UI; loaded by the shared application shell."""
import tkinter as tk

class EventViewMixin:
    def rebuild_event_widgets(self):
        from AION2_Event_Overlay import HUD_TRANSPARENT_KEY
        c=self.panel_colors()
        # event_box is the event-card container created by build().
        # v4.13.0 incorrectly referenced a non-existent events_body attribute.
        for w in self.event_box.winfo_children():
            w.destroy()
        self.event_widgets=[]
        self.bell_buttons=[]
        for e in self.cfg["events"]:
            if not e.get("enabled",True):
                continue
            compact=self.cfg.get('event_compact',False)
            tall=e.get('name_en') in ('Shugo Festa','Dimensional Invasion','Spacetime Rift')
            card_height=42 if compact else 84 if e.get('name_en')=='Spacetime Rift' else 100 if tall else 66
            card=tk.Canvas(self.event_box,height=card_height,bg=HUD_TRANSPARENT_KEY,highlightthickness=0,bd=0)
            card.pack(fill="x",padx=5,pady=3)
            # No stipple: transparent Canvas reveals the smooth alpha layer below.
            bg=card.create_rectangle(1,1,1000,card_height-1,fill=HUD_TRANSPARENT_KEY,outline="#555555",
                                     width=1,tags=("cardbg",))
            name_item=card.create_text(12,21 if compact else 17,text=self.event_name(e),anchor="w",
                                       fill="#f1f5f9",font=self.ui(9 if compact else 10,"bold"))
            header_clock=card.create_text(180,21 if compact else 17,text='',anchor='e',fill='#bcdcff',font=self.mono(9,'bold'),tags=('headerclock',))
            status_item=card.create_text(12,45,text="",anchor="w",
                                         fill="#dcecff",font=self.small_ui(10,"bold"))
            time_item=card.create_text(84,45,text="",anchor="w",
                                       fill="#bcdcff",font=self.mono(12,"bold"))
            alert_on=bool(e.get("alert_enabled",False))
            bell_item=card.create_text(100,17,text=("🔔" if alert_on else "🔕"),anchor="e",
                                       fill=("#dcecff" if alert_on else "#718096"),
                                       font=self.small_ui(10))

            if compact:
                card.itemconfigure(status_item,state='hidden'); card.itemconfigure(time_item,state='hidden')
            details=card.create_text(12,64,text='',anchor='nw',fill='#c5ccd6',font=self.ui(8),width=330,tags=('eventdetails',),state='hidden' if compact else 'normal') if tall else None
            links=e.get('map_links',[])
            links_width=len(links)*49
            def resize(ev,cv=card,bg=bg,bell=bell_item,h=card_height,details=details,title=name_item,clock=header_clock,links_width=links_width,label=self.event_name(e),compact=compact):
                cv.coords(bg,1,1,max(2,ev.width-1),h-1)
                if details: cv.itemconfigure(details,width=max(100,ev.width-25))
                right=ev.width-48-links_width
                self.layout_event_header(cv,title,clock,label,right,21 if compact else 17)
            card.bind("<Configure>",resize)

            # Genuine square button: same interaction model as timer/settings/+.
            # It covers a predictable area instead of relying on glyph hit testing.
            bell_holder={}
            def bell_button_toggle(e=e,cv=card,bell=bell_item,holder=bell_holder):
                self.toggle_event_alert(e)
                on=bool(e.get("alert_enabled",False))
                cv.itemconfigure(bell,text="",state="hidden")
                btn=holder.get("button")
                if btn:
                    btn.config(text=("🔔" if on else "🔕"),
                               fg=("#dcecff" if on else "#8b98a6"))
            card.itemconfigure(bell_item,text="",state="hidden")
            bell_btn=self.make_hud_square_button(
                card,("🔔" if alert_on else "🔕"),bell_button_toggle,size=34,
                font=self.small_ui(10))
            bell_holder["button"]=bell_btn
            bell_btn.config(fg=("#dcecff" if alert_on else "#8b98a6"))
            bell_btn.place(relx=1.0,x=-7,y=4 if compact else 7,width=34,height=34,anchor="ne")
            for index,link in enumerate(links):
                map_button=self.make_hud_square_button(card,link.get('label','MAP'),lambda url=link['url']:self.open_tracker_link(url),font=self.ui(8,'bold'))
                map_button.place(relx=1,x=-45-index*49,y=5 if compact else 8,width=45,height=28,anchor='ne')
            if not hasattr(self,"bell_buttons"): self.bell_buttons=[]
            self.bell_buttons.append(bell_btn)

            self.event_widgets.append((e,card,name_item,status_item,time_item))
            self.event_scroll.install_wheel(card)
            card.bind('<Button-3>',lambda event,row=e:self.open_event_edit(row))
            card.bind('<Double-Button-1>',lambda event,row=e:self.open_event_edit(row))
        self.append_field_boss_events()
        if hasattr(self,'event_scroll'):
            compact=self.cfg.get('event_compact',False)
            content=sum(48 if compact else 90 if e.get('name_en')=='Spacetime Rift' else 106 if e.get('name_en') in ('Shugo Festa','Dimensional Invasion') else 72 for e in self.cfg['events'] if e.get('enabled',True))
            content+=len(self.tracker.catalog['bosses'])*(48 if compact else 138)
            self.event_scroll.canvas.configure(height=min(350,max(42,content)))


