"""Double-click Python entry point (.pyw, not .phw)."""
import os
from pathlib import Path
import sys

SOURCE_DIR=Path(__file__).resolve().parent/'AION2-Event-Overlay'
sys.path.insert(0,str(SOURCE_DIR))

def main():
    import tkinter as tk
    from AION2_Event_Overlay import App
    root=tk.Tk()
    App(root)
    root.mainloop()

if __name__=='__main__':
    if '--check-public-json' in sys.argv:
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
