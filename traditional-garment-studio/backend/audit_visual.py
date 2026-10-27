"""Small, manually inspected image cases; not a population accuracy estimate."""
import json
from pathlib import Path
import time

from .engine import PaperEngine
from .settings import STUDIO_ROOT


def main():
    engine = PaperEngine()
    cases = [
        ('R-C.jpg', 'ruqun-skirt'),
        ('微信图片_20260403213843_3_13.jpg', 'mamian-skirt'),
        ('OIP-C.jpg', None),
    ]
    report = {'scope': 'Three manually inspected local images; component identification only.', 'cases': []}
    for filename, expected in cases:
        start = time.monotonic()
        try:
            result = engine.model.image_local(STUDIO_ROOT.parent/'中国传统服饰'/filename, engine.names)
        except Exception as exc:
            result = {'component': None, 'error': str(exc)}
        row = {'filename': filename, 'expected_component': expected,
               'seconds': round(time.monotonic()-start, 3), 'result': result,
               'matched': 'error' not in result and result.get('component') == expected}
        report['cases'].append(row)
        print(json.dumps(row, ensure_ascii=True), flush=True)
        (STUDIO_ROOT/'docs/visual-component-audit-2026-10-18.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
