"""Prepare Tk/Windows surfaces while hidden; reveal only the completed HUD.

Tk construction and window styling stay on the GUI thread. Network workers
start after preparation and never hold up presentation of the first frame.
"""
import time

class StartupFeatureMixin:
    def initialize_startup(self,root):
        root.withdraw()
        self._startup_pending=True
        self._position_restore_in_progress=True
        self._startup_finishing=False
        self._startup_after=None
        self._startup_started=time.perf_counter()

    def finish_startup(self):
        self._startup_after=None
        if not self._startup_pending or self._startup_finishing or not self.root.winfo_exists(): return
        self._startup_finishing=True
        try:
            # No startup geometry, wrapper/style, or background changes are
            # allowed to show a provisional window at +30+40.
            self.fit_window_to_content()
            self.restore_window_position()
            # Recover the initial update launch in the full GUI once. Later launches
            # retain the user's chosen mode. --normal is an explicit recovery path.
            import sys
            recover=self.ping_cfg.get('startup_recovery_version')!=134 or '--normal' in sys.argv
            if recover:
                self.ping_cfg['ping_layer']=False
                self.ping_cfg['startup_recovery_version']=134
                self.save_ping()
            elif self.ping_cfg.get('ping_layer',False): self.set_ping_layer(True,persist=False)
            from window_placement import clamp_window
            size=self.ping_cfg.get('ping_layer_size',{}) if self._ping_layer else {}
            width=size.get('width') if self._ping_layer else self.overlay_width
            height=size.get('height') if self._ping_layer else (self.manual_height or min(self.root.winfo_reqheight(),self.root.winfo_screenheight()-60))
            clamp_window(self.root,width=width,height=height)
            self.root.update_idletasks()
            self.window_group.sync()
            self._tick_once()  # prepare clocks without starting network work
            self.root.update_idletasks()
            self._startup_pending=False
            self.apply_visual_theme()
            self.refresh_countdown_gauges()
            self.root.deiconify()
            self.root.update_idletasks()
            self.refresh_taskbar_entry()
            self.sync_drag_surface()
            self.window_group.sync()
            self._position_restore_in_progress=False
            self._startup_ready_seconds=time.perf_counter()-self._startup_started
            self.tick()
            self.start_update_checks()
        except Exception as exc:
            # An initialization error should remain hidden, not leave a partly
            # constructed overlay or repeatedly retry/show it.
            self._startup_pending=True
            self.root.withdraw()
            if getattr(self,'drag_surface',None) is not None: self.drag_surface.withdraw()
            self.root._startup_error=exc
            self.stop_workers.set()
            self.restore_selective_hit_test()
            self.cancel_pending_callbacks()
            self.root.destroy()
        finally:
            self._startup_finishing=False

    def cancel_pending_callbacks(self):
        # This application owns the interpreter. Do not leave recurring tray,
        # Configure or idle callbacks pointing at widgets that are destroyed.
        try:
            def widgets(parent):
                yield parent
                for child in parent.winfo_children(): yield from widgets(child)
            owners={name:widget for widget in widgets(self.root) for name in (widget._tclCommands or ())}
            for callback in self.root.tk.call('after','info'):
                script=self.root.tk.call('after','info',callback)[0]
                owner=owners.get(str(script),self.root)
                owner.after_cancel(callback)
        except Exception:
            pass
