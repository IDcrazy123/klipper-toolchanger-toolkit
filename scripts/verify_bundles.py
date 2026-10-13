"""Build allowlist ZIPs, validate manifests and test fresh extracted packages. MIT."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

root=Path(__file__).resolve().parents[1]
for project,entry,version in [('oxplow','generate_oxplow_gcode.py','2.3.2'),('purge-lines','build_purge.py','1.0.0')]:
    folder=root/'projects'/project
    # Ephemeral candidates; never overwrite an existing published release ZIP.
    with tempfile.TemporaryDirectory() as tmp:
        dest=Path(tmp)/f'{project}-{version}.zip'
        subprocess.run([sys.executable,entry,'package','-o',str(dest)],cwd=folder,check=True)
        unpack=Path(tmp)/'unpacked'
        with zipfile.ZipFile(dest) as z:
            manifest=json.loads(z.read('MANIFEST.sha256.json'))
            assert set(z.namelist())==set(manifest)|{'MANIFEST.sha256.json'},'unexpected package paths'
            for name,expected in manifest.items():
                assert not Path(name).is_absolute() and '..' not in Path(name).parts,'unsafe archive path'
                assert hashlib.sha256(z.read(name)).hexdigest()==expected,name
                assert '.local.' not in name and not any(p in {'private','output','archive'} for p in Path(name).parts),name
            z.extractall(unpack)
        subprocess.run([sys.executable,'-m','unittest','discover','-s','tests'],cwd=unpack,check=True)
        print(f'{project} {version}: {len(manifest)} manifest entries verified and extracted tests passed',flush=True)
