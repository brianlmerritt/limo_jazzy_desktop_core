import json
import math
from pathlib import Path
import sys
import unittest
import yaml
sys.path.insert(0, '/workspace/scripts')
from navigation_footprint import render_navigation, footprint_replacements


class FootprintTest(unittest.TestCase):
    def test_one_clearance_controls_both_costmaps_and_monitor(self):
        root = Path('/workspace/config/robot')
        config = json.loads((root/'navigation-footprint.json').read_text())
        for margin in [0.0, 0.05, 0.10, 0.15]:
            config['clearance_m'] = margin
            c = yaml.safe_load(render_navigation((root/'navigation.yaml').read_text(), config, 'test_robot'))
            stop = json.loads(c['collision_monitor']['ros__parameters']['StopZone']['points'])
            for name in ['global_costmap', 'local_costmap']:
                params = c[name][name]['ros__parameters']
                body = json.loads(params['footprint'])
                self.assertAlmostEqual(max(p[0] for p in body)-min(p[0] for p in body), .28)
                self.assertAlmostEqual(max(p[1] for p in body)-min(p[1] for p in body), .20)
                self.assertEqual(params['footprint_padding'], margin)
                for (x,y),(sx,sy) in zip(body,stop):
                    self.assertAlmostEqual(abs(sx)-abs(x), margin)
                    self.assertAlmostEqual(abs(sy)-abs(y), margin)
                self.assertEqual(params['obstacle_layer']['scan']['topic'], '/test_robot/scan')

    def test_offset_and_invalid_dimensions(self):
        config = dict(length_m=.28, width_m=.20, clearance_m=.10, center_x_m=.03, center_y_m=-.01)
        polygon = json.loads(footprint_replacements(config)['<robot_footprint>'])
        self.assertAlmostEqual(sum(p[0] for p in polygon)/4, .03)
        self.assertAlmostEqual(sum(p[1] for p in polygon)/4, -.01)
        for key,value in [('length_m',0),('width_m',-1),('clearance_m',-.01),('width_m',math.nan),('length_m',True)]:
            with self.assertRaises(ValueError):
                footprint_replacements({**config,key:value})
