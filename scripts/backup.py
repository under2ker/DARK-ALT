from pathlib import Path
from datetime import datetime, timezone
from hashlib import sha256
import json, sys, zipfile

root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root))
from dark_alt.config import settings
settings.backup_dir.mkdir(parents=True,exist_ok=True)
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
archive=settings.backup_dir/f'dark-alt-backup-{stamp}.zip'
files=[root/'data'/'dark_alt.db',root/'providers.yaml']
manifest={'created_at':datetime.now(timezone.utc).isoformat(),'files':[]}
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as bundle:
    for source in files:
        if source.exists():
            data=source.read_bytes(); bundle.writestr(source.relative_to(root).as_posix(),data)
            manifest['files'].append({'path':source.relative_to(root).as_posix(),'sha256':sha256(data).hexdigest(),'bytes':len(data)})
    bundle.writestr('manifest.json',json.dumps(manifest,indent=2))
print(archive)
