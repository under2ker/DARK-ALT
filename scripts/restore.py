from pathlib import Path
from hashlib import sha256
import argparse, json, sys, zipfile

root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root))

parser=argparse.ArgumentParser(description='Restore DARK//ALT database and provider configuration from a verified backup.')
parser.add_argument('archive',type=Path)
parser.add_argument('--force',action='store_true',help='Allow overwrite of existing files.')
args=parser.parse_args()
with zipfile.ZipFile(args.archive) as bundle:
    manifest=json.loads(bundle.read('manifest.json'))
    for entry in manifest['files']:
        target=(root/entry['path']).resolve()
        if root not in target.parents: raise RuntimeError('Unsafe archive path')
        data=bundle.read(entry['path'])
        if sha256(data).hexdigest()!=entry['sha256']: raise RuntimeError(f'Checksum mismatch: {entry["path"]}')
        if target.exists() and not args.force: raise RuntimeError(f'{target} already exists; use --force to overwrite')
        target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data)
        print(f'restored {target}')
