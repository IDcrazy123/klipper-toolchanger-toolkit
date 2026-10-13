"""Run each independent project suite without touching a printer. MIT."""
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
for project in ('oxplow','purge-lines'):
    result=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=root/'projects'/project)
    if result.returncode:
        raise SystemExit(result.returncode)
