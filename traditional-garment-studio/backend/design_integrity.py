"""Detect incomplete commits and accidental edits to stored drafting files.

Legacy designs remain readable through structural validation. This local receipt
is not a digital signature and does not claim protection from deliberate edits.
Reference photos are optional; downloadable PDF/ZIP caches are not drafting data.
"""
import hashlib
import json

from .exporting import REQUIRED, OPTIONAL

VERSION='saved-design-sha256-v1'
RECEIPT='design-receipt.json'
FILES=REQUIRED+OPTIONAL+['preview.svg','preview-dimensions.svg']


def _records(folder):
    records={}
    bases=[folder]+[folder/name for name in ('upper','outer','lower','accessory','drape') if (folder/name).is_dir()]
    for base in bases:
        for name in FILES:
            path=base/name
            if not path.is_file():
                if name in REQUIRED:
                    raise ValueError('Incomplete saved drafting files')
                continue
            if not path.resolve().is_relative_to(folder.resolve()):
                raise ValueError('Saved drafting file leaves its design')
            content=path.read_bytes()
            records[path.relative_to(folder).as_posix()]={
                'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()}
    return records


def seal_design(folder):
    records=_records(folder)
    temporary=folder/(RECEIPT+'.tmp')
    temporary.write_text(json.dumps({'version':VERSION,'files':records},indent=2),encoding='utf-8')
    temporary.replace(folder/RECEIPT)


def verify_design(folder,version):
    receipt=folder/RECEIPT
    if version is None and not receipt.exists():
        return  # Existing pre-receipt designs still undergo all structural checks.
    if version!=VERSION or not receipt.resolve().is_relative_to(folder.resolve()):
        raise ValueError('Unknown saved design integrity version')
    value=json.loads(receipt.read_text(encoding='utf-8'))
    if not isinstance(value,dict) or value.get('version')!=VERSION or value.get('files')!=_records(folder):
        raise ValueError('Saved drafting files changed or are incomplete')
