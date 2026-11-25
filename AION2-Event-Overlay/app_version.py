import sys
from pathlib import Path
VERSION=(Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))/'VERSION').read_text(encoding='utf-8').strip()
