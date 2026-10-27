import json
from pathlib import Path
import tempfile
import unittest
from xml.etree import ElementTree as ET
from .engine import PaperEngine
from .patterns import generate_pattern


class PanelMeasurementTests(unittest.TestCase):
    def test_all_twelve_components_report_the_same_bounds_as_actual_dimension_svg(self):
        engine=PaperEngine(model=object())
        with tempfile.TemporaryDirectory() as directory:
            for component in engine.names:
                with self.subTest(component=component):
                    folder=Path(directory)/component
                    result=generate_pattern(engine.defaults(component),engine.template,{},folder)
                    rows=result['panel_measurements']
                    svg=ET.parse(folder/'body-layout-dimensions.svg').getroot()
                    ns='{http://www.w3.org/2000/svg}'
                    groups=svg.find(ns+'g[@id="net-layout"]').findall(ns+'g')
                    self.assertEqual(len(rows),len(groups))
                    self.assertEqual(len(rows),result['panel_count'])
                    for row,group in zip(rows,groups):
                        caption=group.find(ns+'text[@class="panel-size-label"]')
                        self.assertEqual(row['panel_id'],group.attrib['data-panel'])
                        self.assertAlmostEqual(row['width_cm'],float(caption.attrib['data-width-cm']),places=6)
                        self.assertAlmostEqual(row['height_cm'],float(caption.attrib['data-height-cm']),places=6)
                        self.assertEqual(row['units'],'cm')
                        self.assertTrue(any('\u4e00'<=char<='\u9fff' for char in row['label']))
                    before=json.loads((folder/'pattern.json').read_text(encoding='utf-8'))
                    self.assertTrue(before['panels'])
