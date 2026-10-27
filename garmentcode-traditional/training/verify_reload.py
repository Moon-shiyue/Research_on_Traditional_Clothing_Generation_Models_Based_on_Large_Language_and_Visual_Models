from __future__ import annotations

import argparse
import json

from .common import read_jsonl, resolve


def compare(before, after):
    def index(rows):
        mapped = {row['id']: row['prediction'].strip() for row in rows}
        if len(mapped) != len(rows) or not rows:
            raise ValueError('Predictions must have nonempty, unique IDs')
        return mapped
    a, b = index(before), index(after)
    if a.keys() != b.keys():
        raise ValueError('Reload comparison must use exactly the same examples')
    changed = [ident for ident in a if a[ident] != b[ident]]
    return {'rows': len(a), 'identical_predictions': len(a) - len(changed), 'changed_ids': changed}


def main():
    parser = argparse.ArgumentParser(description='Compare generation before and after adapter reload on identical IDs')
    parser.add_argument('--before', required=True)
    parser.add_argument('--after', required=True)
    args = parser.parse_args()
    result = compare(read_jsonl(resolve(args.before)), read_jsonl(resolve(args.after)))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result['changed_ids']:
        raise SystemExit('Reload predictions changed; investigate before continuing')


if __name__ == '__main__':
    main()
