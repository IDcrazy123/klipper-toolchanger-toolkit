"""Check tracked/staged publication paths; no private filesystem crawl. MIT."""
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
result=subprocess.run(['git','ls-files','-z'],cwd=root,capture_output=True,check=True)
paths=[p for p in result.stdout.decode().split('\0') if p]
errors=[]
for name in paths:
    path=Path(name)
    if any(s in {'private','archive','output','dist','__pycache__','.venv'} for s in path.parts) or '.local.' in name or name=='.env':
        errors.append(name)
    if '/profiles/' in name and name.endswith('.json') and not name.endswith('.example.json'):
        errors.append(name)
    if path.suffix.lower() in {'.jpg','.png'} and not name.startswith('projects/purge-lines/photos/'):
        errors.append('unauthorized image path: '+name)
print(f'{len(paths)} tracked files checked')
if errors:
    print('\n'.join(errors),file=sys.stderr)
    raise SystemExit(1)
