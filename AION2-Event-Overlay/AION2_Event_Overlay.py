import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.font as tkfont
import re
try:
    import winsound
except ImportError:
    winsound=None
import json, time, datetime, os, sys, calendar, ctypes, math, struct, wave, tempfile

# cotodama: Ping/status/balance extension; original scheduling and event UI retained.
from ping_feature import PingFeatureMixin
from tracker_feature import TrackerFeatureMixin
from event_feature import EventFeatureMixin
from event_model import migrate_config
from startup_feature import StartupFeatureMixin
from window_group import WindowGroup, hwnd
from pathlib import Path

# Tcl needs extended paths for frozen builds under redirected Windows folders.
if getattr(sys, "frozen", False):
    for variable, folder in (("TCL_LIBRARY", "_tcl_data"), ("TK_LIBRARY", "_tk_data")):
        library_path = (Path(sys._MEIPASS) / folder).as_posix()
        if sys.platform == "win32":
            library_path = "//?/UNC/" + library_path[2:] if library_path.startswith("//") else "//?/" + library_path
        os.environ[variable] = library_path

from app_version import VERSION as APP_VERSION
APP_DIR = os.path.dirname(os.path.abspath(__file__))

def resource_path(name):
    """Return a bundled resource path for source and PyInstaller one-file builds."""
    base=getattr(sys,"_MEIPASS",APP_DIR)
    path=os.path.join(base,name)
    if not getattr(sys,'frozen',False) and not os.path.exists(path):
        path=os.path.join(os.path.dirname(APP_DIR),name)
    return path

# Portable settings are separate from the original installed overlay.
PORTABLE_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(APP_DIR)
USER_DATA_DIR = os.environ.get("AION2_OVERLAY_DATA_DIR", os.path.join(PORTABLE_DIR, "data"))
CONFIG = os.path.join(USER_DATA_DIR, "aion2_overlay.json")
BUNDLED_CONFIG = resource_path("aion2_overlay.json")
APP_ICON = resource_path("AION2_Event_Overlay.ico")
MAIN_HUD_WIDTH = 390
POSITION_DIR = USER_DATA_DIR
POSITION_FILE = os.path.join(POSITION_DIR, "window_position.json")

DEFAULT_CONFIG = {
    "language": "ja",
    "display_timezone": "JST",
    "background_opacity": 0.88,
    "alert_volume": 45,
    "alert_sound_file": "",
    "timer_alert_volume": 45,
    "timer_alert_sound_file": "",
    "events": [
        {"name_ja":"時空の亀裂","name_en":"Spacetime Rift","type":"interval","start":"02:00","interval_minutes":180,"duration_minutes":60,"entry_minutes":10,"notify_before_minutes":5,"alert_timing":"start_only","enabled":True},
        {"name_ja":"シューゴフェスタ","name_en":"Shugo Festa","type":"interval","start":"00:00","interval_minutes":60,"duration_minutes":10,"entry_minutes":5,"notify_before_minutes":5,"alert_timing":"start_only","enabled":True},
        {"name_ja":"戦場","name_en":"Battlefield","type":"windows","windows":[["11:00","14:00"],["19:00","21:00"]],"notify_before_minutes":5,"alert_timing":"start_only","enabled":True},
        {"name_ja":"アーティファクト占領戦","name_en":"Artifact Siege","type":"weekly","weekdays":[2,5],"times":["21:00"],"duration_minutes":30,"entry_minutes":0,"notify_before_minutes":30,"alert_timing":"start_only","enabled":True}
    ],
    "timers": [
        {"name":"タイマー1","duration":300,"visible":False},
        {"name":"タイマー2","duration":600,"visible":False},
        {"name":"タイマー3","duration":900,"visible":False}
    ]
}

def deep_default():
    return json.loads(json.dumps(DEFAULT_CONFIG, ensure_ascii=False))

def load_config_raw():
    if not os.path.exists(CONFIG):
        initial=deep_default()
        try:
            if os.path.exists(BUNDLED_CONFIG):
                with open(BUNDLED_CONFIG,"r",encoding="utf-8") as f:
                    bundled=json.load(f)
                if isinstance(bundled,dict):
                    initial.update(bundled)
        except Exception as e:
            print(f"[AION2 Overlay] Bundled config read failed; using defaults: {e}")
        save_config(initial)
        return initial
    try:
        with open(CONFIG,"r",encoding="utf-8") as f:
            c=json.load(f)
        for k,v in DEFAULT_CONFIG.items():
            c.setdefault(k,json.loads(json.dumps(v)))

        return c
    except Exception as e:
        print(f"[AION2 Overlay] User config read failed; using defaults: {e}")
        return deep_default()

def load_config():
    original=load_config_raw()
    if not original.get('schedule_update_137') and os.path.isfile(CONFIG):
        import shutil
        if not os.path.exists(CONFIG+'.pre-1.3.7.bak'):shutil.copy2(CONFIG,CONFIG+'.pre-1.3.7.bak')
    result=migrate_config(original)
    if result!=original:
        import shutil
        if os.path.isfile(CONFIG) and not os.path.exists(CONFIG+'.pre-1.3.0.bak'):
            shutil.copy2(CONFIG,CONFIG+'.pre-1.3.0.bak')
        save_config(result)
    return result

def save_config(c):
    os.makedirs(USER_DATA_DIR,exist_ok=True)
    tmp=CONFIG+".tmp"
    with open(tmp,"w",encoding="utf-8") as f:
        json.dump(c,f,ensure_ascii=False,indent=2)
    os.replace(tmp,CONFIG)

def fmt(sec):
    sec=max(0,int(sec)); h,r=divmod(sec,3600); m,s=divmod(r,60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def parse_hm(s):
    parts=list(map(int,s.strip().split(':')))
    if len(parts) not in (2,3):raise ValueError
    h,m=parts[:2];second=parts[2] if len(parts)==3 else 0
    if not (0<=h<=23 and 0<=m<=59 and 0<=second<=59):raise ValueError
    return h*3600+m*60+second

def nth_weekday(year, month, weekday, n):
    c=calendar.Calendar().monthdayscalendar(year,month)
    days=[w[weekday] for w in c if w[weekday]]
    return days[n-1]

def last_weekday(year,month,weekday):
    c=calendar.Calendar().monthdayscalendar(year,month)
    days=[w[weekday] for w in c if w[weekday]]
    return days[-1]

# Dependency-free timezone conversion for the three requested display zones.
# PDT/PST: US DST = 2nd Sunday Mar 02:00 local to 1st Sunday Nov 02:00 local.
# CEST/CET: EU DST = last Sunday Mar 01:00 UTC to last Sunday Oct 01:00 UTC.
def us_pacific_offset(utc_dt):
    y=utc_dt.year
    mar=nth_weekday(y,3,6,2)
    nov=nth_weekday(y,11,6,1)
    start=datetime.datetime(y,3,mar,10,0,0,tzinfo=datetime.timezone.utc) # 02:00 PST
    end=datetime.datetime(y,11,nov,9,0,0,tzinfo=datetime.timezone.utc)   # 02:00 PDT
    return (-7,"PDT") if start<=utc_dt<end else (-8,"PST")

def europe_central_offset(utc_dt):
    y=utc_dt.year
    mar=last_weekday(y,3,6); octo=last_weekday(y,10,6)
    start=datetime.datetime(y,3,mar,1,0,0,tzinfo=datetime.timezone.utc)
    end=datetime.datetime(y,10,octo,1,0,0,tzinfo=datetime.timezone.utc)
    return (2,"CEST") if start<=utc_dt<end else (1,"CET")

def display_time(utc_dt, zone):
    if zone=="PDT":
        off,label=us_pacific_offset(utc_dt)
    elif zone=="CEST":
        off,label=europe_central_offset(utc_dt)
    else:
        off,label=9,"JST"
    return utc_dt+datetime.timedelta(hours=off),label


class TimerState:
    def __init__(self,d):
        self.name=d.get("name","Timer"); self.duration=max(1,int(d.get("duration",300)))
        self.visible=bool(d.get("visible",True)); self.alert_enabled=bool(d.get("alert_enabled",True))
        self.running=False; self.elapsed=0.0; self.started=None; self.alert_fired=False
    def start(self):
        if not self.running:
            if self.elapsed >= self.duration:
                self.elapsed=0.0
            self.started=time.monotonic()-self.elapsed; self.running=True
            if self.elapsed < self.duration:
                self.alert_fired=False
    def stop(self):
        if self.running: self.elapsed=time.monotonic()-self.started; self.running=False
    def reset(self): self.running=False; self.elapsed=0; self.started=None; self.alert_fired=False
    def vals(self):
        e=time.monotonic()-self.started if self.running else self.elapsed
        return max(0,self.duration-e), max(0,e-self.duration), e

# --- Windows native compositor backdrop (v4.16) ---
# Uses one HWND only. Unlike the old auxiliary Toplevel approach, the backdrop
# cannot move in front of the text/input surface when AION2 receives focus.
if os.name=="nt":
    class _ACCENTPOLICY(ctypes.Structure):
        _fields_=[
            ("AccentState",ctypes.c_int),
            ("AccentFlags",ctypes.c_int),
            ("GradientColor",ctypes.c_uint),
            ("AnimationId",ctypes.c_int),
        ]
    class _WINCOMPATTRDATA(ctypes.Structure):
        _fields_=[
            ("Attribute",ctypes.c_int),
            ("Data",ctypes.c_void_p),
            ("SizeOfData",ctypes.c_size_t),
        ]


HUD_TRANSPARENT_KEY="#010203"

if os.name=="nt":
    WM_NCHITTEST=0x0084
    HTTRANSPARENT=-1
    HTCLIENT=1
    GWL_WNDPROC=-4
    GWL_EXSTYLE=-20
    WS_EX_TRANSPARENT=0x00000020
    WS_EX_LAYERED=0x00080000
    _WNDPROC_TYPE=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,ctypes.c_void_p,ctypes.c_uint,ctypes.c_size_t,ctypes.c_ssize_t)


from schedule_editor import ScheduleEditorMixin
from visual_feature import VisualFeatureMixin
from update_feature import UpdateFeatureMixin
from server_charts import ServerChartsMixin

from settings_feature import SettingsFeatureMixin
from timer_view import TimerViewMixin
from event_view import EventViewMixin

class App(SettingsFeatureMixin, TimerViewMixin, EventViewMixin, ServerChartsMixin, VisualFeatureMixin, UpdateFeatureMixin, ScheduleEditorMixin, StartupFeatureMixin, EventFeatureMixin, TrackerFeatureMixin, PingFeatureMixin):
    def __init__(self,root):
        self.initialize_startup(root)
        self._dialog_windows = {}
        self.root=root; self.cfg=load_config()
        self.init_visuals()
        self.init_updater()
        self.init_ping(USER_DATA_DIR)
        self.init_tracker(USER_DATA_DIR)
        self.init_event_notifications(USER_DATA_DIR)
        self.init_event_map_links()
        self.timers=[TimerState(x) for x in self.cfg["timers"]]
        self.event_alert_state={}
        self.alert_wav=os.path.join(tempfile.gettempdir(),"aion2_event_overlay_alert.wav")
        root.title("AION2 Event Overlay + Ping")
        try:
            root.iconbitmap(APP_ICON)
        except Exception as e:
            print(f"[AION2 Overlay] Window icon load failed: {e}")
        root.geometry("+30+40"); root.minsize(290,1)
        root.configure(bg="#101215"); root.attributes("-topmost",True)
        self.bg_alpha=float(self.cfg.get("background_opacity",.88)); self.bg_alpha=self.bg_alpha/100.0 if self.bg_alpha>1.0 else self.bg_alpha
        self.cfg["background_opacity"]=(100-self.ping_cfg['transparency'])/100
        self.bg_alpha=self.cfg["background_opacity"]
        root.attributes("-topmost",self.ping_cfg['topmost'])
        self.setup_fonts()
        self.build()
        self.install_surface_drag()
        self.window_group=WindowGroup(self)
        self.apply_main_hud_surface_style()
        self.apply_background_opacity()
        self.initialize_ping_layer()
        from app_audio import AppAudio
        self.audio=AppAudio(APP_ICON,USER_DATA_DIR)
        root.bind('<Destroy>',lambda e:self.audio.close() if e.widget is root else None,add='+')
        print(f"[AION2 Overlay] Version {APP_VERSION}; user data={USER_DATA_DIR}")
        root.bind("<Configure>",self.schedule_window_position_save,add="+")
        root.protocol("WM_DELETE_WINDOW",self.on_close)
        self._startup_after=self.root.after_idle(self.finish_startup)

    def setup_fonts(self):
        """Choose Noto Sans JP for UI text and Consolas for clocks/countdowns."""
        try:
            families=set(tkfont.families(self.root))
        except Exception:
            families=set()
        self.ui_font="Noto Sans JP" if "Noto Sans JP" in families else "Yu Gothic UI"
        self.mono_font="Consolas" if "Consolas" in families else "Courier New"

    def ui(self,size=9,weight="normal"):
        return (self.ui_font,size,weight)

    def small_ui(self,size=9,weight="normal"):
        return ("Meiryo UI",size,weight)

    def mono(self,size=10,weight="normal"):
        return (self.mono_font,size,weight)

    def tr(self,ja,en): return en if self.cfg.get("language")=="en" else ja


    def panel_colors(self):
        return {
            "root":"#202020",
            "header":"#202020",
            "card":"#202020",
            "button":"#202934",
            "timerbutton":"#202934",
        }




    def _native_backdrop_color(self, alpha):
        """Return ABGR gradient color used by Windows AccentPolicy."""
        # Windows-dark neutral tint: #202020. Alpha controls backdrop strength.
        a=max(0,min(255,int(alpha*255)))
        color=self.theme_colors()['root'].lstrip('#')
        r,g,b=(int(color[i:i+2],16) for i in (0,2,4))
        return (a<<24)|(b<<16)|(g<<8)|r

    def apply_native_backdrop(self):
        """Single-HWND alpha-tint experiment (no auxiliary Toplevel).

        Windows draws the translucent dark surface in the SAME native HWND as Tk.
        Tk foreground glyphs/icons stay opaque; only transparent-key structural
        areas reveal the compositor tint.
        """
        if os.name!="nt":
            return False
        try:
            self.root.update_idletasks()
            hwnd=self.get_native_toplevel_hwnd()
            opacity=float(self.cfg.get("background_opacity",0.70))
            if opacity>1.0: opacity/=100.0
            opacity=max(0.0,min(1.0,opacity))

            self.root.attributes("-alpha",1.0)
            try:self.root.wm_attributes("-transparentcolor",HUD_TRANSPARENT_KEY)
            except Exception:pass

            policy=_ACCENTPOLICY()
            # Disable Accent tint: some Windows/GPU combinations render it white.
            # The explicitly dark backing surface provides background-only alpha.
            policy.AccentState=0
            policy.AccentFlags=0
            policy.GradientColor=self._native_backdrop_color(opacity)
            policy.AnimationId=0

            data=_WINCOMPATTRDATA()
            data.Attribute=19
            data.Data=ctypes.cast(ctypes.pointer(policy),ctypes.c_void_p)
            data.SizeOfData=ctypes.sizeof(policy)

            fn=ctypes.windll.user32.SetWindowCompositionAttribute
            ok=bool(fn(hwnd,ctypes.byref(data)))
            print(f"[AION2 Overlay] Dark overlay background opacity={opacity:.2f}, native={ok}")
            return ok
        except Exception as exc:
            print(f"[AION2 Overlay] Single-HWND alpha tint failed: {exc}")
            return False

    def _new_dialog(self, title, parent=None):
        """Build dialogs hidden; reveal only after their first page is complete."""
        parent=parent or self.root
        win=tk.Toplevel(parent)
        win.withdraw()
        win.title(title)
        self.setup_dialog_position(win,title)
        self.window_group.register(win,parent)
        return win

    def _safe_dialog_close(self, win):
        # Cancel callbacks on their owning Tk widget before destroying it.
        # Otherwise a short-lived editor can leave an invalid Tcl command queued.
        try:
            def descendants(widget):
                yield widget
                for child in widget.winfo_children():yield from descendants(child)
            owners={name:w for w in descendants(win) for name in (w._tclCommands or ())}
            for callback in self.root.tk.call('after','info'):
                command=str(self.root.tk.call('after','info',callback)[0])
                if command in owners:owners[command].after_cancel(callback)
        except tk.TclError:pass
        try: win.grab_release()
        except Exception: pass
        try: win.destroy()
        except Exception: pass

    def _place_compact_dialog(self, win, width=390, min_height=260):
        try:
            win.update_idletasks()
            sw,sh=win.winfo_screenwidth(),win.winfo_screenheight()
            h=max(min_height,min(win.winfo_reqheight()+8,sh-90))
            rx,ry=self.root.winfo_x(),self.root.winfo_y()
            rw=self.root.winfo_width()
            if win.winfo_ismapped():
                x,y=win.winfo_x(),win.winfo_y()
            elif win._position_key in self.dialog_positions:
                pos=self.dialog_positions[win._position_key]; x,y=pos['x'],pos['y']
            else:
                x=rx+rw+12; y=ry
            win.geometry(f"{width}x{h}+{x}+{y}")
            from window_placement import clamp_window
            clamp_window(win)
        except Exception:
            pass

    def preview_background_opacity(self, value):
        """Preview native background opacity without saving settings."""
        try:
            old=self.cfg.get("background_opacity",70)
            self.cfg["background_opacity"]=float(value)
            self.apply_background_opacity()
            self.cfg["background_opacity"]=old
        except Exception:
            pass



    def apply_background_opacity(self):
        """Keep foreground opaque and render opacity on the dark backing surface."""
        opacity=float(self.cfg.get("background_opacity",0.70))
        if opacity>1.0: opacity/=100.0
        opacity=max(0.0,min(1.0,opacity))
        self.ping_cfg['transparency']=round((1-opacity)*100)
        try:
            self.root.attributes("-alpha",1.0)
            self.root.attributes("-topmost",self.ping_cfg['topmost'])
        except Exception:
            pass
        self.apply_native_backdrop()
        if hasattr(self,'drag_surface'): self.sync_drag_surface()


    def _interactive_widget_at_screen(self, sx, sy):
        """Only explicit HUD controls consume clicks.

        Labels, text, frames, cards, canvas backgrounds and empty HUD space are
        intentionally click-through. This avoids Tk class/binding inheritance
        accidentally making whole card/header regions interactive.
        """
        try:
            w=self.root.winfo_containing(int(sx),int(sy))
        except Exception:
            return False
        if w is None:
            return False

        # Explicit native Tk controls.
        interactive_classes={
            "Button","TButton","Checkbutton","TCheckbutton","Scale","TScale",
            "Entry","TEntry","Spinbox","TSpinbox","Combobox","TCombobox",
            "Listbox","Scrollbar","TScrollbar"
        }

        cur=w
        while cur is not None:
            try:
                cls=cur.winfo_class()
            except Exception:
                cls=""
            if cls in interactive_classes:
                return True
            if getattr(cur,'_hud_interactive',False):
                return True

            # Do NOT use generic <Button-1> binding detection here.
            # Tk bindings can be inherited/class-level and caused labels,
            # card canvases and header areas to block click-through in v4.18.0.
            if cur is self.root:
                break
            try:
                cur=cur.master
            except Exception:
                break

        # Canvas-based HUD controls (bell / icon hit areas) are handled by
        # explicit screen rectangles registered below.
        for rect in getattr(self,"_hud_control_rects",()):
            try:
                x1,y1,x2,y2=rect
                if x1 <= sx < x2 and y1 <= sy < y2:
                    return True
            except Exception:
                pass
        return False

    def refresh_hud_control_rects(self):
        """Register only visible HUD widgets that are meant to be clickable."""
        rects=[]
        # Existing explicit Button widgets are already detected by class.
        # For canvas/label controls, register widgets that the app marks here.
        for name in ("btn_timer","btn_settings","ping_layer_grip"):
            w=getattr(self,name,None)
            if w is None:
                continue
            try:
                if w.winfo_ismapped():
                    x=w.winfo_rootx(); y=w.winfo_rooty(); pad=8
                    rects.append((x-pad,y-pad,x+w.winfo_width()+pad,y+w.winfo_height()+pad))
            except Exception:
                pass

        # Timer + is always an interactive control, even in frameless mode.
        w=getattr(self,"timer_add_btn",None)
        if w is not None:
            try:
                if w.winfo_ismapped():
                    x=w.winfo_rootx(); y=w.winfo_rooty(); pad=10
                    rects.append((x-pad,y-pad,x+w.winfo_width()+pad,y+w.winfo_height()+pad))
            except Exception:
                pass
        # New scroll surfaces and summary rows support scrolling and double-click editing.
        for area in (getattr(self,'list_area',None),getattr(self,'summary_area',None)):
            w=getattr(area,'canvas',None)
            try:
                if w is not None and w.winfo_exists() and w.winfo_ismapped():
                    x=w.winfo_rootx(); y=w.winfo_rooty()
                    rects.append((x,y,x+w.winfo_width(),y+w.winfo_height()))
            except Exception:
                pass
        self._hud_control_rects=rects


    def _enum_child_hwnds(self, parent_hwnd):
        if os.name!="nt":
            return []
        result=[]
        try:
            user32=ctypes.windll.user32
            ENUMPROC=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_ssize_t)
            @ENUMPROC
            def cb(hwnd,lparam):
                result.append(int(hwnd))
                return True
            user32.EnumChildWindows(ctypes.c_void_p(parent_hwnd),cb,0)
        except Exception:
            pass
        return result

    def install_selective_hit_test(self):
        """Subclass root AND Tk child HWNDs.

        Tk labels/frames/canvases can own child HWND hit-test paths, so the hook
        is applied to every HUD HWND rather than only the native root wrapper.
        """
        if os.name!="nt":
            return
        try:
            self.root.update_idletasks()
            user32=ctypes.PyDLL('user32.dll')
            user32.CallWindowProcW.restype=ctypes.c_ssize_t
            user32.CallWindowProcW.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint,ctypes.c_size_t,ctypes.c_ssize_t]
            get_wlp=getattr(user32,"GetWindowLongPtrW",user32.GetWindowLongW)
            set_wlp=getattr(user32,"SetWindowLongPtrW",user32.SetWindowLongW)

            root_hwnd=int(self.root.winfo_id())
            hwnds=list(dict.fromkeys([self.get_native_toplevel_hwnd(),root_hwnd]+self._enum_child_hwnds(root_hwnd)))
            self._subclass_records={}

            for hwnd in hwnds:
                try:
                    old_proc=int(get_wlp(ctypes.c_void_p(hwnd),GWL_WNDPROC))
                    if not old_proc:
                        continue

                    @_WNDPROC_TYPE
                    def _proc(hWnd,msg,wParam,lParam,_old=old_proc):
                        try:
                            if msg in (0x007E,0x02E0,0x001A) and hasattr(self,"window_group"):
                                self.root.after_idle(self.window_group.display_changed)
                            if msg==WM_NCHITTEST:
                                self.refresh_hud_control_rects()
                                x=ctypes.c_short(lParam & 0xFFFF).value
                                y=ctypes.c_short((lParam >> 16) & 0xFFFF).value
                                # The overlay surface now accepts drag input everywhere.
                                return HTCLIENT
                        except Exception:
                            pass
                        return user32.CallWindowProcW(
                            ctypes.c_void_p(_old),hWnd,msg,wParam,lParam
                        )

                    set_wlp(ctypes.c_void_p(hwnd),GWL_WNDPROC,
                            ctypes.cast(_proc,ctypes.c_void_p).value)
                    self._subclass_records[hwnd]=(old_proc,_proc)
                except Exception:
                    continue

            self._selective_hit_test_installed=bool(self._subclass_records)
        except Exception:
            self._selective_hit_test_installed=False


    def restore_selective_hit_test(self):
        if os.name!="nt" or not getattr(self,"_selective_hit_test_installed",False):
            return
        try:
            user32=ctypes.windll.user32
            set_wlp=getattr(user32,"SetWindowLongPtrW",user32.SetWindowLongW)
            for hwnd,(old_proc,callback) in list(getattr(self,"_subclass_records",{}).items()):
                try:
                    set_wlp(ctypes.c_void_p(hwnd),GWL_WNDPROC,old_proc)
                except Exception:
                    pass
        except Exception:
            pass
        self._subclass_records={}
        self._selective_hit_test_installed=False


    def print_native_hwnd_diagnostics(self):
        if os.name!="nt":
            return
        try:
            client=int(self.root.winfo_id())
            top=self.get_native_toplevel_hwnd()
            user32=ctypes.windll.user32
            GWL_EXSTYLE_LOCAL=-20
            get_wlp=getattr(user32,"GetWindowLongPtrW",user32.GetWindowLongW)
            ex=int(get_wlp(ctypes.c_void_p(top),GWL_EXSTYLE_LOCAL))
            transparent=bool(ex & 0x20)
            print(f"[AION2 Overlay] Tk client HWND={client:#x}, top-level HWND={top:#x}, EXSTYLE={ex:#x}, frameless=True, clickthrough={transparent}")
        except Exception as exc:
            print(f"[AION2 Overlay] HWND diagnostic failed: {exc}")








    def get_native_toplevel_hwnd(self):
        """Return the real Windows top-level wrapper HWND for the Tk root."""
        if os.name!="nt":
            return int(self.root.winfo_id())
        return hwnd(self.root)


    def set_frameless_clickthrough(self, enabled):
        """Pass through non-controls only; buttons/bells remain clickable."""
        if os.name!="nt":
            return
        try:
            self.root.update_idletasks()
            hwnd=self.get_native_toplevel_hwnd()
            user32=ctypes.windll.user32
            get_wlp=getattr(user32,"GetWindowLongPtrW",user32.GetWindowLongW)
            set_wlp=getattr(user32,"SetWindowLongPtrW",user32.SetWindowLongW)
            ex=int(get_wlp(ctypes.c_void_p(hwnd),GWL_EXSTYLE))
            # Never make the whole HWND transparent to input.
            ex &= ~WS_EX_TRANSPARENT
            ex = (ex & ~0x80) | 0x40000  # taskbar app, not a hidden tool window
            ex |= WS_EX_LAYERED
            set_wlp(ctypes.c_void_p(hwnd),GWL_EXSTYLE,ex)
            if enabled:
                self.restore_selective_hit_test()
                self.install_selective_hit_test()
            else:
                self.restore_selective_hit_test()
            SWP_NOMOVE=0x0002; SWP_NOSIZE=0x0001
            SWP_NOZORDER=0x0004; SWP_NOACTIVATE=0x0010; SWP_FRAMECHANGED=0x0020
            user32.SetWindowPos(ctypes.c_void_p(hwnd),None,0,0,0,0,
                SWP_NOMOVE|SWP_NOSIZE|SWP_NOZORDER|SWP_NOACTIVATE|SWP_FRAMECHANGED)
        except Exception:
            pass




    def apply_frameless_mode(self):
        """Apply the permanent, stable frameless HUD mode."""
        self.root.overrideredirect(True)
        try:
            self.root.update_idletasks()
            self.set_frameless_clickthrough(True)
        except Exception:
            pass

    def fit_window_to_content(self):
        """Fit height only; keep the overlay deliberately narrow and stable."""
        try:
            if getattr(self,'_ping_layer',False): self.size_ping_layer(); return
            if getattr(self,'_restoring_ping_gui',False): return
            if getattr(self,'window_maximized',False): return
            self.root.update_idletasks()
            x=self.root.winfo_x(); y=self.root.winfo_y()
            # The HUD is intentionally portrait/vertical. Never let a child widget
            # silently grow the main window horizontally.
            w=getattr(self,'overlay_width',MAIN_HUD_WIDTH)
            requested=max(1,self.root.winfo_reqheight())
            h=getattr(self,'manual_height',None) or min(requested,self.root.winfo_screenheight()-60)
            self.root.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def build_alert_wav(self, volume_key="alert_volume", output_path=None):
        """Create a short, gentle two-note chime at the configured volume."""
        try:
            rate=44100
            volume=max(0,min(100,int(self.cfg.get(volume_key,45))))/100.0
            # Soft attack/decay and modest peak level so it is noticeable but not intrusive.
            notes=[(659.25,0.16),(783.99,0.24)]
            samples=[]
            for freq,dur in notes:
                count=int(rate*dur)
                for i in range(count):
                    t=i/rate
                    attack=min(1.0,t/0.025)
                    release=min(1.0,max(0.0,(dur-t)/0.10))
                    env=attack*release
                    s=math.sin(2*math.pi*freq*t)
                    samples.append(int(32767*0.20*volume*env*s))
                samples.extend([0]*int(rate*0.045))
            with wave.open(output_path or self.alert_wav,"wb") as wf:
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(rate)
                wf.writeframes(b"".join(struct.pack("<h",x) for x in samples))
        except Exception:
            pass

    def play_mp3(self,path,volume_key="alert_volume",alias="aion2_alert"):
        """Route custom MP3 through the same process-owned mixer session."""
        volume=max(0,min(100,int(self.cfg.get(volume_key,45))))/100
        return bool(volume and self.audio.play_file(path,volume,'timer' if 'timer' in alias else 'event'))

    def play_event_alert(self,event=None,preview=False):
        return EventFeatureMixin.play_event_alert(self,event,preview)

    def play_timer_alert(self):
        """Timer completion uses its independent gain within the app mixer."""
        volume=max(0,min(100,int(self.cfg.get('timer_alert_volume',45))))
        if volume<=0:return False
        try:
            cache=Path(USER_DATA_DIR)/'sound_cache';cache.mkdir(parents=True,exist_ok=True)
            path=cache/f'timer-default-{volume}.wav'
            if not path.exists():
                rate=44100;gain=volume/100; samples=[]
                for freq,dur in ((523.25,.16),(659.25,.16),(783.99,.24)):
                    count=int(rate*dur)
                    for i in range(count):
                        tt=i/rate;env=min(1.0,tt/.025)*min(1.0,max(0.0,(dur-tt)/.09))
                        samples.append(int(32767*.18*gain*env*math.sin(2*math.pi*freq*tt)))
                    samples.extend([0]*int(rate*.045))
                with wave.open(str(path),'wb') as wf:
                    wf.setnchannels(1);wf.setsampwidth(2);wf.setframerate(rate)
                    wf.writeframes(b''.join(struct.pack('<h',x) for x in samples))
            custom=str(self.cfg.get('timer_alert_sound_file','')).strip()
            if custom and Path(custom).is_file() and Path(custom).suffix.lower() in ('.wav','.mp3'):
                return self.audio.play_file(custom,volume/100,'timer',fallback=str(path))
            return self.audio.play_file(str(path),1.,'timer')
        except (ValueError,OSError):return False

    def toggle_event_alert(self,e,button=None):
        e["alert_enabled"]=not bool(e.get("alert_enabled",False))
        save_config(self.cfg)
        if button is not None:
            on=e["alert_enabled"]
            button.config(text=("🔔" if on else "🔕"),fg=("#dcecff" if on else "#6f7885"))

    def apply_main_hud_surface_style(self):
        """Make HUD structure transparent while keeping glyphs/icons opaque.

        Background tint/alpha is provided once by the Windows compositor.
        Tk structural widgets use the transparent key so they do not add a second,
        non-adjustable dark rectangle.
        """
        key=HUD_TRANSPARENT_KEY
        try:self.root.configure(bg=key)
        except Exception:pass
        for name in ("header","header_info","header_buttons","event_section","event_box","timer_box","timer_content"):
            w=getattr(self,name,None)
            if w is not None:
                try:w.configure(bg=key)
                except Exception:pass

        # Buttons remain intentionally opaque/interactive. Everything else that is
        # merely structural becomes a compositor hole.
        for parent_name in ("header","event_box","timer_box"):
            parent=getattr(self,parent_name,None)
            if parent is None: continue
            stack=[parent]
            while stack:
                w=stack.pop()
                try: stack.extend(w.winfo_children())
                except Exception: pass
                try:
                    if isinstance(w,(tk.Frame,tk.LabelFrame)):
                        w.configure(bg=key)
                except Exception:
                    pass

        # Canvas surfaces use the same key; Canvas text itself stays fully opaque.
        for w in getattr(self,"event_widgets",[]):
            try:w[1].configure(bg=key)
            except Exception:pass
        try:self.header_canvas.configure(bg=key)
        except Exception:pass




    def event_name(self,e):
        return EventFeatureMixin.event_name(self,e)

    def event_status(self,e,jst):
        if e.get('schedule_edited'):
            from schedule_edit_model import edited_event_status
            return edited_event_status(e,jst)
        if not e.get('schedule_confirmed',True): return 'unknown',0,None
        sod=jst.hour*3600+jst.minute*60+jst.second
        typ=e.get("type","daily")
        if typ=="interval":
            start=parse_hm(e.get("start","00:00"))
            iv=max(60,int(e.get("interval_minutes",60))*60)
            x=(sod-start)%iv
            entry=max(0,int(e.get("entry_minutes",0))*60)
            if entry and x<entry:
                return "entry",entry-x,entry-x
            return "next",iv-x,None
        if typ=="daily":
            target=parse_hm(e.get("start","00:00"))
            entry=max(0,int(e.get("entry_minutes",0))*60)
            if entry and target<=sod<target+entry:
                return "entry",target+entry-sod,target+entry-sod
            return "next",(target-sod)%86400,None
        if typ=="windows":
            wins=e.get("windows",[])
            for a,b in wins:
                aa,bb=parse_hm(a),parse_hm(b)
                if aa<=sod<bb:return "active",0,bb-sod
                if sod<aa:return "next",aa-sod,None
            return ("next",86400-sod+parse_hm(wins[0][0]),None) if wins else ("next",0,None)
        if typ=="weekly":
            cand=[]; wd=jst.weekday()
            for add in range(8):
                d=(wd+add)%7
                if d not in e.get("weekdays",[]):continue
                for hm in e.get("times",[]):
                    target=parse_hm(hm); delta=add*86400+target-sod
                    if delta>=0:cand.append(delta)
            return "next",min(cand) if cand else 7*86400,None
        return "next",0,None


    def tick(self):
        pending=getattr(self,'_tick_after',None)
        if pending:
            try: self.root.after_cancel(pending)
            except tk.TclError: pass
        self._tick_after=None
        try:
            self._tick_once()
        except Exception:
            import traceback
            detail=traceback.format_exc()
            self.fetch_error='画面更新処理でエラーが発生しました。data/runtime_errors.log を確認してください'
            try:
                os.makedirs(USER_DATA_DIR,exist_ok=True)
                if detail!=getattr(self,'_last_tick_error',None):
                    with open(os.path.join(USER_DATA_DIR,'runtime_errors.log'),'a',encoding='utf-8') as log:
                        log.write(datetime.datetime.now(datetime.timezone.utc).isoformat()+'\n'+detail+'\n')
                    self._last_tick_error=detail
                self.update_db_request_label()
            except Exception: pass
        finally:
            if self.root.winfo_exists(): self._tick_after=self.root.after(500,self.tick)

    def _tick_once(self):
        self.poll_network()
        self.tick_tracker(datetime.datetime.now(datetime.timezone.utc))
        # Capture one shared wall-clock snapshot for this entire UI tick.
        # Normalize to the displayed whole second so the clock and every
        # countdown are calculated from exactly the same second boundary.
        utc=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        shown,label=display_time(utc,self.cfg.get("display_timezone","JST"))
        self.header_canvas.itemconfigure(self.clock_item,text=shown.strftime("%H:%M:%S")+" "+label)
        jst=utc.astimezone(datetime.timezone(datetime.timedelta(hours=9)))
        self.tick_event_notifications(jst)
        self.update_field_boss_events(jst)
        reset=jst.replace(hour=16,minute=0,second=0,microsecond=0)
        if jst>=reset:reset+=datetime.timedelta(days=1)
        reset_utc=reset.astimezone(datetime.timezone.utc)
        reset_show,reset_label=display_time(reset_utc,self.cfg.get("display_timezone","JST"))
        self.header_canvas.itemconfigure(self.daily_item,text=self.tr("日次参考 ","Daily reference ")+reset_show.strftime("%H:%M")+" "+reset_label+"  ("+fmt((reset-jst).total_seconds())+")")
        for e,event_canvas,name_item,status_text,status_time in getattr(self,"event_widgets",[]):
            st,sec,remain=self.event_status(e,jst)
            links_width=len(e.get('map_links',[]))*49
            right=event_canvas.winfo_width()-48-links_width
            event_canvas.itemconfigure('headerclock',text=self.event_header_clock(e,jst))
            header_clock=event_canvas.find_withtag('headerclock')[0]
            self.layout_event_header(event_canvas,name_item,header_clock,self.event_name(e),right,21 if self.cfg.get('event_compact',False) else 17)

            event_canvas.itemconfigure('eventdetails',text=self.event_details(e,jst))
            if st=='unknown':
                event_canvas.itemconfigure(status_text,text='未確認（編集で時刻を確認）')
                event_canvas.itemconfigure(status_time,text='')
                continue
            if st=='finished':
                event_canvas.itemconfigure(status_text,text='終了（右クリックで再設定）')
                event_canvas.itemconfigure(status_time,text=''); continue
            if st=="entry":
                label_txt=self.tr("入場時間","ENTRY TIME")
                time_txt=fmt(sec)
            elif st=="active":
                label_txt=self.tr("● 開催中  残り","● ACTIVE")
                time_txt=fmt(remain)
            else:
                label_txt=self.tr("次回まで","Next")
                time_txt=fmt(sec)
                if e.get('schedule_edited'):
                    from display_format import precise_remaining
                    label_txt='次回まで あと'; time_txt=precise_remaining(sec)
                elif e.get('name_en') in ('Spacetime Rift','Battlefield'):
                    import math
                    label_txt='次回まで あと'
                    from display_format import remaining_text
                    time_txt=remaining_text(sec)
            event_canvas.itemconfigure(status_text,text=label_txt)

            # Color only the time value:
            # - green = the event is currently in an entry/active state
            # - yellow = upcoming event is inside its configured notification window
            # - pale blue = normal countdown
            notify_before=max(0,int(e.get("notify_before_minutes",0) or 0))*60
            active_fg="#78dba2"
            if st in ("entry","active"):
                countdown_fg=active_fg
            elif notify_before>0 and sec<=notify_before:
                countdown_fg="#ffd54a"
            else:
                countdown_fg="#bcdcff"
            event_canvas.itemconfigure(status_time,text=time_txt,fill=countdown_fg)
            bbox=event_canvas.bbox(status_text)
            if bbox:
                event_canvas.coords(status_time,bbox[2]+7,45)
        self.refresh_countdown_gauges()
        self.refresh_button_icons()
        for t,val,finish,play_pause in getattr(self,"timer_widgets",[]):
            rem,o,e=t.vals(); val.config(text=fmt(rem))
            if t.running and rem<=0 and not t.alert_fired:
                t.alert_fired=True
                if t.alert_enabled:
                    self.play_timer_alert()
            if t.running:
                if play_pause.cget("text")!="⏸️":
                    play_pause.config(text="⏸️")
                finish_utc=utc+datetime.timedelta(seconds=(t.duration-e))
                finish_show,finish_label=display_time(finish_utc,self.cfg.get("display_timezone","JST"))
                finish.config(text=self.tr("終了予定 ","Ends at ")+finish_show.strftime("%H:%M:%S")+" "+finish_label)
            else:
                if play_pause.cget("text")!="▶️":
                    play_pause.config(text="▶️")
                finish.config(text="")

    def on_close(self):
        self.close_updater()
        for callback in (getattr(self,'_tick_after',None),getattr(self,'_sound_after',None),getattr(self,'_startup_after',None)):
            if callback:
                try: self.root.after_cancel(callback)
                except tk.TclError: pass
        if getattr(self,'window_maximized',False): self.toggle_window_maximize()
        self.audio.close()
        self.save_tracker()
        self.close_ping()
        self.restore_selective_hit_test()
        if not getattr(self,'_startup_pending',False):
            self._position_restore_in_progress=False
            self.save_window_position()
        try:
            self.save_timers()
        except Exception:
            pass
        self.cancel_pending_callbacks()
        self.root.destroy()


    def _finish_position_restore(self):
        self._position_restore_in_progress=False

    def restore_window_position(self):
        """Restore the last main-HUD position from the persistent user store."""
        try:
            x=y=None
            try:
                with open(POSITION_FILE,"r",encoding="utf-8") as f:
                    pos=json.load(f)
                x=pos.get("x"); y=pos.get("y")
            except FileNotFoundError:
                print(f"[AION2 Overlay] No saved window position yet: {POSITION_FILE}")
                return
            except Exception as e:
                print(f"[AION2 Overlay] Window position file read failed: {e}")
                return
            if x is None or y is None:
                return
            x=int(x); y=int(y)

            self.root.update_idletasks()
            ww=max(120,self.root.winfo_reqwidth())
            wh=max(80,self.root.winfo_reqheight())
            try:
                user32=ctypes.windll.user32
                vx=int(user32.GetSystemMetrics(76))
                vy=int(user32.GetSystemMetrics(77))
                vw=max(1,int(user32.GetSystemMetrics(78)))
                vh=max(1,int(user32.GetSystemMetrics(79)))
            except Exception:
                vx=vy=0
                vw=max(1,self.root.winfo_screenwidth())
                vh=max(1,self.root.winfo_screenheight())
            x=max(vx-ww+80,min(x,vx+vw-80))
            y=max(vy,min(y,vy+vh-40))
            self.root.geometry(f"+{x}+{y}")
            self.root.update_idletasks()
            self._last_saved_position=(x,y)
            print(f"[AION2 Overlay] Restored window position x={x}, y={y} source=position_file")
        except Exception as e:
            print(f"[AION2 Overlay] Window position restore failed: {e}")

    def save_window_position(self):
        """Persist the main-HUD X/Y independently of the versioned app folder."""
        try:
            if getattr(self,"_position_restore_in_progress",False):
                return
            if getattr(self,'_ping_layer',False):
                self.ping_cfg['ping_layer_position']={'x':self.root.winfo_x(),'y':self.root.winfo_y()}
                self.save_ping(); return
            if self.root.state() not in ("normal","zoomed"):
                return
            self.root.update_idletasks()
            x=int(self.root.winfo_x()); y=int(self.root.winfo_y())
            if getattr(self,"_last_saved_position",None)==(x,y):
                return
            os.makedirs(POSITION_DIR,exist_ok=True)
            tmp=POSITION_FILE+".tmp"
            with open(tmp,"w",encoding="utf-8") as f:
                json.dump({"x":x,"y":y},f,ensure_ascii=False,indent=2)
            os.replace(tmp,POSITION_FILE)
            self._last_saved_position=(x,y)
            print(f"[AION2 Overlay] Saved window position x={x}, y={y} source=position_file")
        except Exception as e:
            print(f"[AION2 Overlay] Window position save failed: {e}")

    def schedule_window_position_save(self,event=None):
        if getattr(self,"_position_restore_in_progress",False):
            return
        if event is not None and event.widget is not self.root:
            return
        old=getattr(self,"_position_save_after",None)
        if old:
            try:self.root.after_cancel(old)
            except Exception:pass
        self._position_save_after=self.root.after(350,self.save_window_position)


    def _move_handle_start(self,event):
        try:
            self._move_origin=(event.x_root,event.y_root,self.root.winfo_x(),self.root.winfo_y())
        except Exception:
            self._move_origin=None

    def _move_handle_drag(self,event):
        o=getattr(self,"_move_origin",None)
        if not o:return
        try:
            nx=o[2]+event.x_root-o[0]; ny=o[3]+event.y_root-o[1]
            self.root.geometry(f"+{nx}+{ny}")
        except Exception:pass

    def _move_handle_end(self,event=None):
        self._move_origin=None
        self.schedule_window_position_save()

    def make_hud_square_button(self,parent,text,command,size=34,font=None):
        """Consistent square HUD control with a restrained, lighter surface."""
        # Slightly lighter than the old button surface, intentionally low-contrast
        # so controls do not dominate when the HUD background is translucent.
        bg="#26303a"
        active="#34404c"
        b=tk.Button(parent,text=text,command=command,
                    bg=bg,activebackground=active,fg="#f4f7fa",
                    activeforeground="#ffffff",relief="flat",bd=0,
                    highlightthickness=1,highlightbackground="#43505c",
                    highlightcolor="#596878",cursor="hand2",takefocus=0,
                    font=(font or self.ui(11,"bold")))
        # place/pack callers control geometry; width/height are pixel dimensions
        # when place() is used.
        return b

    def build(self):
        for w in self.root.winfo_children(): w.destroy()
        c=self.panel_colors()
        self.root.configure(bg=HUD_TRANSPARENT_KEY)
        self.header=tk.Frame(self.root,bg=HUD_TRANSPARENT_KEY); self.header.pack(fill="x")
        self.header_info=tk.Frame(self.header,bg=HUD_TRANSPARENT_KEY,height=70,width=250)
        self.header_info.pack(side="left",fill="both",expand=True)
        self.header_info.pack_propagate(False)
        self.header_canvas=tk.Canvas(self.header_info,height=70,bg=HUD_TRANSPARENT_KEY,
                                     highlightthickness=0,bd=0)
        self.header_canvas.pack(fill="both",expand=True)
        self.clock_item=self.header_canvas.create_text(
            10,21,text="",anchor="w",fill="white",font=self.ui(18,"bold"))
        self.daily_item=self.header_canvas.create_text(
            10,50,text="",anchor="w",fill="#e2edf7",font=self.ui(10,"bold"))
        # Buttons live in their own right-side row so they never overlap the clock/reset text.
        self.header_buttons=tk.Frame(self.header,bg=HUD_TRANSPARENT_KEY)
        self.header_buttons.pack(side="right",anchor="ne",padx=0,pady=(0,2),before=self.header_info)
        self.window_controls=tk.Frame(self.header_buttons,bg=HUD_TRANSPARENT_KEY)
        self.window_controls.pack(fill='x',pady=(0,6))
        self.minimize_button=self.make_hud_square_button(self.window_controls,'—',self.minimize_window)
        self.maximize_button=self.make_hud_square_button(self.window_controls,'□',self.toggle_window_maximize)
        self.close_button=self.make_hud_square_button(self.window_controls,'×',self.on_close)
        for btn in (self.close_button,self.maximize_button,self.minimize_button):
            btn.pack(side='right',ipadx=7,ipady=1,padx=(2,0))
        self.close_button.configure(bg='#823139',activebackground='#b43b43')
        self.header_actions=tk.Frame(self.header_buttons,bg=HUD_TRANSPARENT_KEY)
        self.header_actions.pack(fill='x',padx=(0,7))
        def header_square(text,command):
            holder=tk.Frame(self.header_actions,bg=HUD_TRANSPARENT_KEY,width=34,height=34)
            holder.pack(side="left",padx=2)
            holder.pack_propagate(False)
            btn=self.make_hud_square_button(holder,text,command,size=34)
            btn.place(x=0,y=0,width=34,height=34)
            return btn
        self.stopwatch_button=header_square("⏱",self.show_timer_window)
        # Dedicated move handle for the default frameless/click-through HUD.
        self.move_button=header_square("✥",lambda:None)
        self.move_button.bind("<ButtonPress-1>",self._move_handle_start)
        self.move_button.bind("<B1-Motion>",self._move_handle_drag)
        self.move_button.bind("<ButtonRelease-1>",self._move_handle_end)
        self.ping_layer_button=header_square('',lambda:self.set_ping_layer(True))
        self.install_antenna_icon(self.ping_layer_button)
        self.settings_button=header_square("⚙",self.settings)

        self.build_ping_header(HUD_TRANSPARENT_KEY)

        self.event_section=tk.Frame(self.root,bg=HUD_TRANSPARENT_KEY)
        self.event_section.pack(fill="both",expand=True,padx=7,pady=(7,3))
        self.event_title=tk.Label(self.event_section,text=self.tr("イベント（右クリックで名前・時刻を編集）","EVENTS (right-click to edit)"),
                                  font=self.ui(10,"bold"),fg="#f5f5f5",
                                  bg=HUD_TRANSPARENT_KEY)
        self.event_title.pack(anchor="w",padx=4,pady=(0,3))
        self.event_notice_label=tk.Label(self.event_section,text='',font=self.ui(8),fg='#ffd54a',
                                         bg=HUD_TRANSPARENT_KEY,justify='left',anchor='w',wraplength=350)
        from ping_feature import ScrollArea
        self.event_scroll=ScrollArea(self.event_section,height=350,bg=HUD_TRANSPARENT_KEY)
        self.event_scroll.frame.pack(fill='both',expand=True)
        self.event_box=self.event_scroll.body

        self.event_widgets=[]
        self.rebuild_event_widgets()
        self.timer_box=tk.Frame(self.root,bg=c["root"])
        self.timer_head=tk.Frame(self.timer_box,bg=c["root"])
        self.timer_head.pack(fill="x",padx=(5,13),pady=(3,1))
        self.timer_title=tk.Label(self.timer_head,text=self.tr("タイマー","TIMERS"),
                                  font=self.ui(10,"bold"),fg="#f5f5f5",
                                  bg=HUD_TRANSPARENT_KEY)
        self.timer_title.pack(side="left")
        self.timer_add_holder=tk.Frame(self.timer_head,bg=HUD_TRANSPARENT_KEY,width=34,height=34)
        self.timer_add_holder.pack(side="right")
        self.timer_add_holder.pack_propagate(False)
        self.timer_add_btn=self.make_hud_square_button(self.timer_add_holder,"+",self.open_timer_settings,size=34)
        self.timer_add_btn.place(x=0,y=0,width=34,height=34)
        self.timer_content=tk.Frame(self.timer_box,bg=c["root"])
        self.timer_content.pack(fill="x")
        self.timer_widgets=[]
        self.timer_panel_visible=False
        self.rebuild_timers()

        self.build_extra_tabs()
        self.apply_frameless_mode()
        self.root.after_idle(self.fit_window_to_content)

    def show_timer_window(self):
        # The clock button opens the editor; keep timer controls visible as well.
        if self.active_tab != 'events': self.show_tab('events')
        if not self.timer_panel_visible: self.toggle_timer_panel()
        self.open_timer_settings()

    def toggle_timer_panel(self):
        if self.active_tab != "events": self.show_tab("events")
        self.timer_panel_visible=not getattr(self,"timer_panel_visible",False)
        if self.timer_panel_visible:
            self.timer_box.pack(fill="x",expand=False,padx=7,pady=3,after=self.event_section)
            self.stopwatch_button.config(relief="sunken")
        else:
            self.timer_box.pack_forget()
            self.stopwatch_button.config(relief="flat")
        self.root.after_idle(self.fit_window_to_content)






    def edit_event_advanced(self,parent,index,refresh):
        old=self.cfg["events"][index] if index is not None else {
            "name_ja":"新規イベント","name_en":"New Event","type":"daily",
            "start":"12:00","entry_minutes":0,"notify_before_minutes":0,
            "alert_timing":"both","enabled":True,"alert_enabled":False
        }
        e=json.loads(json.dumps(old))
        c=self.panel_colors()
        w=tk.Toplevel(parent); w.withdraw(); w.title(self.tr("イベント編集","Edit Event"))
        w.configure(bg=c["root"]); w.transient(parent); w.resizable(False,False)
        self.window_group.register(w,parent)

        from ping_feature import ScrollArea
        editor_area=ScrollArea(w,height=520,bg=c['root']); editor_area.frame.pack(fill='both',expand=True,padx=9,pady=9)
        outer=editor_area.body
        w._position_key='event_editor' 
        head=tk.Frame(outer,bg=c["header"]); head.pack(fill="x")
        tk.Label(head,text=self.tr("イベント編集","EDIT EVENT"),font=self.ui(12,"bold"),
                 fg="white",bg=c["header"]).pack(anchor="w",padx=10,pady=8)

        common=tk.Frame(outer,bg=c["card"],highlightthickness=1,highlightbackground="#252c35")
        common.pack(fill="x",pady=(7,4))
        ci=tk.Frame(common,bg=c["card"]); ci.pack(fill="x",padx=10,pady=8)
        def lab(p,s):
            tk.Label(p,text=s,fg="#f5f5f5",bg=c["card"],font=self.ui(9,"bold")).pack(anchor="w",pady=(5,2))
        lab(ci,self.tr("日本語名（絵文字もここで編集）","Japanese name (including emoji)"))
        name_ja=tk.Entry(ci,bg=c["header"],fg="white",insertbackground="white",relief="flat")
        name_ja.insert(0,e.get("name_ja","")); name_ja.pack(fill="x")
        lab(ci,self.tr("英語名","English name"))
        name_en=tk.Entry(ci,bg=c["header"],fg="white",insertbackground="white",relief="flat")
        name_en.insert(0,e.get("name_en_display",e.get("name_en",""))); name_en.pack(fill="x")
        lab(ci,self.tr("種類","Type"))
        typ=tk.StringVar(value=e.get("type","daily"))
        typebox=ttk.Combobox(ci,textvariable=typ,state="readonly",values=["interval","daily","windows","weekly","once"])
        typebox.pack(fill="x")
        enabled=tk.BooleanVar(value=e.get("enabled",True))
        tk.Checkbutton(ci,text=self.tr("表示する","Enabled"),variable=enabled,bg=c["card"],fg="white",
                       selectcolor=c["header"],activebackground=c["card"],activeforeground="white").pack(anchor="w",pady=(8,2))

        confirmed=tk.BooleanVar(value=e.get('schedule_confirmed',False))
        tk.Checkbutton(ci,text='ゲーム内で確認した時刻を使用（未確認ならOFF）',variable=confirmed,
                       bg=c['card'],fg='white',selectcolor=c['header'],activebackground=c['card'],
                       activeforeground='white',wraplength=330).pack(anchor='w',pady=4)
        tk.Label(ci,text=e.get('schedule_note','未確認'),bg=c['card'],fg='#8fa0b4',wraplength=330).pack(anchor='w')
        detail=tk.Frame(outer,bg=c["card"],highlightthickness=1,highlightbackground="#252c35")
        detail.pack(fill="x",pady=4)
        di=tk.Frame(detail,bg=c["card"]); di.pack(fill="x",padx=10,pady=8)
        widgets={}

        from time_inputs import ClockPicker,DateTimePicker,MinutesPicker,WeekdayPicker,ClockList,protect_selectors
        def entry(key,title,value):
            lab(di,title)
            if key=='start':x=ClockPicker(di,self,value=str(value))
            elif key=='at':x=DateTimePicker(di,self,value=str(value))
            elif key=='weekdays_text':x=WeekdayPicker(di,self,value=str(value))
            elif key in ('times_text','windows_text'):x=ClockList(di,self,value=str(value),windows=key=='windows_text')
            else:x=MinutesPicker(di,self,value=str(value),seconds=key!='notify_before_minutes')
            x.pack(fill='x',pady=4);widgets[key]=x

        def fit():
            self._place_compact_dialog(w,480,590)

        def rebuild(*_):
            for x in di.winfo_children(): x.destroy()
            widgets.clear()
            t=typ.get()
            if t=="interval":
                entry("start",self.tr("基準開始時刻","Base start HH:MM"),e.get("start","00:00"))
                entry("interval_minutes",self.tr("開催間隔（分）","Interval (minutes)"),e.get("interval_minutes",60))
                entry("entry_minutes",self.tr("入場カウントダウン（分）","Entry countdown (minutes)"),e.get("entry_minutes",0))
            elif t=="daily":
                entry("start",self.tr("開始時刻","Start HH:MM"),e.get("start","12:00"))
                entry("entry_minutes",self.tr("入場カウントダウン（分）","Entry countdown (minutes)"),e.get("entry_minutes",0))
            elif t=='once':
                entry('at','今回の日付・時刻（日本時間）',e.get('at',''))
            elif t=="windows":
                entry("windows_text",self.tr("開催時間帯（＋で追加）","Windows (11:00-14:00,19:00-21:00)"),
                      ",".join("-".join(x) for x in e.get("windows",[])))
            elif t=="weekly":
                entry("weekdays_text",self.tr("開催する曜日","Weekdays 0=Mon…6=Sun"),
                      ",".join(map(str,e.get("weekdays",[]))))
                entry("times_text",self.tr("開始時刻（＋で追加）","Start times (21:20,21:50)"),
                      ",".join(e.get("times",[])))
                entry("entry_minutes",self.tr("入場カウントダウン（分）","Entry countdown (minutes)"),e.get("entry_minutes",0))

            # Alert timing is independent of the entry countdown.
            entry("notify_before_minutes",
                  self.tr("何分前から通知するか（0=事前通知なし）",
                          "Notify before start (minutes, 0=off)"),
                  e.get("notify_before_minutes",0))

            lab(di,self.tr("アラートのタイミング","Alert timing"))
            timing=tk.StringVar(value=e.get("alert_timing","both"))
            timing_box=ttk.Combobox(
                di,state="readonly",textvariable=timing,
                values=["both","start_only"])
            timing_box.pack(fill="x")
            widgets["alert_timing_var"]=timing
            widgets["alert_timing_box"]=timing_box

            timing_help=tk.Label(
                di,
                text=self.tr(
                    "both：設定した分前と開始時刻の両方 / start_only：開始時刻のみ",
                    "both: before-start + start / start_only: start only"),
                fg="#8fa0b4",bg=c["card"],font=self.ui(8),
                justify="left",anchor="w",wraplength=340)
            timing_help.pack(fill="x",pady=(3,2))
            if e.get('name_en') in ('Shugo Festa','Dimensional Invasion','Artifact Siege'):
                before=widgets['notify_before_minutes']
                before.delete(0,'end'); before.insert(0,'40' if e.get('name_en')=='Artifact Siege' else '0')
                before.configure(state='readonly')
                timing.set('both' if e.get('name_en')=='Artifact Siege' else 'start_only')
                timing_box.configure(state='disabled')
                timing_help.configure(text='40分前・30分前・開始時刻に通知（確認済み予定のみ）' if e.get('name_en')=='Artifact Siege' else '開始時刻のみ通知。事前通知はありません。')
            w.after_idle(fit)

        typebox.bind("<<ComboboxSelected>>",rebuild)
        rebuild()

        actions=tk.Frame(outer,bg=c["root"]); actions.pack(fill="x",pady=(6,0))
        def intval(k,minimum=0):
            v=int(widgets[k].get().strip())
            if v<minimum: raise ValueError
            return v

        def minuteval(k,minimum=0):
            from schedule_edit_model import minutes
            return minutes(widgets[k].get().strip(),minimum)

        def save():
            try:
                ne=dict(old)
                ne.update({"name_ja":name_ja.get().strip() or "イベント",
                    "name_en_display":name_en.get().strip() or "Event","emoji_in_name":True,
                    "type":typ.get(),"enabled":enabled.get(),"alert_enabled":bool(old.get("alert_enabled",True))})
                # Keep the built-in scheduling identity independent of display names.
                ne.setdefault('name_en',name_en.get().strip() or 'Event')
                import uuid
                ne.setdefault('id','custom-'+uuid.uuid4().hex)
                ne['schedule_confirmed']=confirmed.get()
                ne['schedule_note']='ゲーム内確認済み（ユーザー登録）' if confirmed.get() else '未確認'
                ne["notify_before_minutes"]=intval("notify_before_minutes",0)
                ne["alert_timing"]=widgets["alert_timing_var"].get()
                if ne["alert_timing"] not in ("both","start_only"):
                    ne["alert_timing"]="both"
                t=typ.get()
                if t=="interval":
                    ne["start"]=widgets["start"].get().strip(); parse_hm(ne["start"])
                    ne["interval_minutes"]=minuteval("interval_minutes",.5)
                    ne["entry_minutes"]=minuteval("entry_minutes",0)
                elif t=="daily":
                    ne["start"]=widgets["start"].get().strip(); parse_hm(ne["start"])
                    ne["entry_minutes"]=minuteval("entry_minutes",0)
                elif t=='once':
                    from schedule_edit_model import local_datetime
                    ne['at']=local_datetime(widgets['at'].get()).isoformat()
                elif t=="windows":
                    raw=widgets["windows_text"].get().strip()
                    if not raw: raise ValueError
                    ne["windows"]=[]
                    for p in raw.split(","):
                        ab=p.strip().split("-",1)
                        if len(ab)!=2: raise ValueError
                        a,b=ab[0].strip(),ab[1].strip()
                        aa,bb=parse_hm(a),parse_hm(b)
                        if bb==aa: raise ValueError
                        ne["windows"].append([a,b])
                elif t=="weekly":
                    ne["weekdays"]=[int(x.strip()) for x in widgets["weekdays_text"].get().split(",") if x.strip()]
                    if not ne["weekdays"] or any(x<0 or x>6 for x in ne["weekdays"]): raise ValueError
                    ne["times"]=[x.strip() for x in widgets["times_text"].get().split(",") if x.strip()]
                    if not ne["times"]: raise ValueError
                    for tm in ne["times"]: parse_hm(tm)
                    ne["entry_minutes"]=minuteval("entry_minutes",0)
                if t!='interval':ne.pop('interval_anchor',None)
                elif old.get('interval_anchor') and ne['start']!=old.get('start'):
                    from schedule_edit_model import local_datetime,JST
                    anchor=local_datetime(old['interval_anchor'])
                    ne['interval_anchor']=datetime.datetime.combine(anchor.date(),datetime.time.fromisoformat(ne['start']),JST).isoformat()
                ne['schedule_edited']=True
            except Exception:
                messagebox.showerror(self.tr("入力エラー","Input error"),
                    self.tr("イベント種類に必要な項目・時刻・数値を確認してください。",
                            "Check the fields, times, and numeric values required for this event type."),parent=w)
                return

            if index is None:self.cfg["events"].append(ne)
            else:self.cfg["events"][index]=ne
            save_config(self.cfg)
            self.event_previous=None
            self.rebuild_event_widgets()
            self.root.after_idle(self.fit_window_to_content)
            refresh()
            self._safe_dialog_close(w)

        tk.Button(actions,text=self.tr("キャンセル","Cancel"),command=lambda:self._safe_dialog_close(w),bg=c["button"],fg="white",relief="flat").pack(side="right",padx=(4,0))
        tk.Button(actions,text=self.tr("保存","Save"),command=save,bg=c["button"],fg="white",relief="flat",
                  font=self.ui(9,"bold")).pack(side="right")
        def reveal_editor():
            def bind_wheel(widget):
                editor_area.install_wheel(widget)
                for child in widget.winfo_children(): bind_wheel(child)
            bind_wheel(outer)
            fit()
            outer._time_scroll_canvas=editor_area.canvas
            protect_selectors(outer)
            w.deiconify()
            w.lift()
        w.after_idle(reveal_editor)
        w._advanced_editor=dict(widgets=widgets,type=typ,typebox=typebox,rebuild=rebuild,save=save,name_ja=name_ja,win=w)
        self._advanced_editor=w._advanced_editor


    def save_timers(self):
        self.cfg["timers"]=[{"name":t.name,"duration":t.duration,"visible":t.visible,
                            "alert_enabled":t.alert_enabled} for t in self.timers]; save_config(self.cfg)



if __name__=="__main__":
    root=tk.Tk(); App(root); root.mainloop()

