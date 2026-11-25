"""Double-click Python entry point (.pyw, not .phw)."""
import os
from pathlib import Path
import sys

SOURCE_DIR=Path(__file__).resolve().parent/'AION2-Event-Overlay'
sys.path.insert(0,str(SOURCE_DIR))

def main():
    from window_group import system_dpi_awareness
    system_dpi_awareness()
    import tkinter as tk
    from AION2_Event_Overlay import App
    root=tk.Tk()
    root.withdraw()
    App(root)
    root.mainloop()
    if getattr(root,'_startup_error',None) is not None:
        raise root._startup_error

if __name__=='__main__':
    if '--apply-update' in sys.argv:
        from update_install import run_plan
        run_plan(Path(sys.argv[sys.argv.index('--apply-update')+1]))
    elif '--visual-check' in sys.argv:
        from visual_check import run_check
        run_check(Path(sys.argv[sys.argv.index('--visual-check')+1]))
    elif '--cycle-check' in sys.argv:
        from cycle_check import run_check
        run_check(Path(sys.argv[sys.argv.index('--cycle-check')+1]))
    elif '--inputs-check' in sys.argv:
        from inputs_check import run_check
        run_check(Path(sys.argv[sys.argv.index('--inputs-check')+1]))
    elif '--weekday-check' in sys.argv:
        from weekday_check import run_check
        run_check(Path(sys.argv[sys.argv.index('--weekday-check')+1]))
    elif '--update-check' in sys.argv:
        from update_check import run_check
        run_check(Path(sys.argv[sys.argv.index('--update-check')+1]))
    elif '--audio-check' in sys.argv:
        from audio_check import run_check
        run_check(Path(sys.argv[sys.argv.index('--audio-check')+1]))
    elif '--editor-check' in sys.argv:
        from editor_check import run_check
        run_check(Path(sys.argv[sys.argv.index('--editor-check')+1]))
    elif '--repair-check' in sys.argv:
        from repair_check import run_check
        run_check(Path(sys.argv[sys.argv.index('--repair-check')+1]))
    elif '--minimal-ping-check' in sys.argv:
        from minimal_ping_check import run_check
        run_check(Path(sys.argv[sys.argv.index('--minimal-ping-check')+1]))
    elif '--feature-check' in sys.argv:
        from feature_check import run_check
        run_check(Path(sys.argv[sys.argv.index('--feature-check')+1]))
    elif '--startup-check' in sys.argv:
        from startup_check import run_check
        run_check(Path(sys.argv[sys.argv.index('--startup-check')+1]))
    elif '--notification-check' in sys.argv:
        from notification_check import run_check
        run_check(Path(sys.argv[sys.argv.index('--notification-check')+1]))
    elif '--check-public-json' in sys.argv:
        import json
        from server_data import fetch_snapshot
        target=Path(sys.argv[sys.argv.index('--check-public-json')+1])
        try:
            data=fetch_snapshot()
            report={'passed':True,'frozen':bool(getattr(sys,'frozen',False)),
                    'regions':{r['code']:len(r['servers']) for r in data['regions']}}
        except Exception as exc:
            report={'passed':False,'error':str(exc)}
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    elif '--tracker-check' in sys.argv:
        from tracker_check import run_check
        run_check(Path(sys.argv[sys.argv.index('--tracker-check')+1]))
    elif '--self-check' in sys.argv:
        from bundle_check import run_check
        run_check(Path(sys.argv[sys.argv.index('--self-check')+1]))
    else:
        try:
            main()
        except Exception:
            import traceback
            import tkinter.messagebox as messagebox
            detail=traceback.format_exc()
            directory=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).parent
            try: (directory/'startup_error.txt').write_text(detail,encoding='utf-8')
            except OSError: pass
            messagebox.showerror('AION2 Event Overlay + Ping 起動エラー',detail)

