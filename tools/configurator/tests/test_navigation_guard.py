"""Navigation guard geometry and platform configuration; no robot access."""
import math
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, '/workspace/scripts')
from navigation_guard_core import (DEFAULT_POLICY, validate_policy, alignment_state, action_scale,
                                   angle_difference, forward_command, scan_map_score)


class NavigationGuardTest(unittest.TestCase):
    def test_reverse_and_sideways_rejected_including_rotation(self):
        self.assertFalse(forward_command([-.01, 0, 0, 0, 0, .1]))
        self.assertFalse(forward_command([.05, .01, 0, 0, 0, 0]))
        self.assertTrue(forward_command([.1, 0, 0, 0, 0, .25]))
        self.assertTrue(forward_command([0, 0, 0, 0, 0, -.25]))

    def test_invalid_and_excess_commands(self):
        for x in [math.nan, math.inf, .11, -.001]:
            self.assertFalse(forward_command([x, 0, 0, 0, 0, 0]))
        self.assertFalse(forward_command([0, 0, 0, 0, 0, .26]))

    def test_policy_defaults_continue_and_rejects_invalid_config(self):
        self.assertTrue(all(v == 'continue' for v in validate_policy(DEFAULT_POLICY).values()))
        for bad in [{}, {**DEFAULT_POLICY, 'aligned': 'guess'}, {**DEFAULT_POLICY, 'extra': 'hold'}]:
            with self.assertRaises(ValueError): validate_policy(bad)
        self.assertEqual(action_scale('slow'), .5)
        self.assertEqual(action_scale('hold'), 0)

    def test_decision_matrix_covers_joint_disagreements_and_missing_evidence(self):
        for map_state, orientation, expected in [
            ('match', True, 'aligned'), ('match', False, 'orientation_disagreement'),
            ('mismatch', True, 'map_disagreement'), ('mismatch', False, 'both_disagree'),
            ('insufficient', True, 'insufficient_geometry'), ('match', None, 'unavailable'),
            ('unavailable', False, 'unavailable')]:
            self.assertEqual(alignment_state(map_state, orientation), expected)

    def test_unknown_and_out_of_map_do_not_confirm_alignment(self):
        self.assertEqual(scan_map_score([(0, 0), (100, 100)], [-1]*100, 10, 10, .1, (0,0,0)), (0,0))

    def test_offset_scan_loses_alignment(self):
        cells = [0]*400
        for y in range(20): cells[y*20+5] = 100
        points = [(.55, y*.1+.05) for y in range(20)]
        self.assertEqual(scan_map_score(points,cells,20,20,.1,(0,0,0))[1],1)
        self.assertEqual(scan_map_score([(x+.5,y) for x,y in points],cells,20,20,.1,(0,0,0))[1],0)

    def test_rotated_map_origin(self):
        cells = [0]*100
        cells[2*10+1] = 100
        # Local (.15,.25), origin (1,2,pi/2) -> (.75,2.15)
        self.assertEqual(scan_map_score([(.75,2.15)],cells,10,10,.1,(1,2,math.pi/2))[1],1)

    def test_yaw_wrap_is_not_a_pickup(self):
        self.assertAlmostEqual(angle_difference(math.radians(-179), math.radians(179)), math.radians(2))

    def test_no_blind_recovery_in_either_tree(self):
        for name in ['navigate-forward.xml', 'navigate-through-forward.xml']:
            root = ET.parse('/workspace/config/robot/'+name)
            self.assertFalse(root.findall('.//BackUp'))
            self.assertFalse(root.findall('.//Spin'))
            self.assertTrue(root.findall('.//FollowPath'))

    def test_clearance_and_gate_route(self):
        import yaml
        import json
        from navigation_footprint import render_navigation
        root = Path('/workspace/config/robot')
        c=yaml.safe_load(render_navigation((root/'navigation.yaml').read_text(),
            json.loads((root/'navigation-footprint.json').read_text()), 'robot'))
        for name in ['global_costmap','local_costmap']:
            p=c[name][name]['ros__parameters']
            self.assertEqual(p['footprint_padding'],.10)
            self.assertEqual(p['inflation_layer']['inflation_radius'],.35)
        p=c['collision_monitor']['ros__parameters']
        self.assertEqual(p['cmd_vel_in_topic'],'cmd_vel_guarded')
        self.assertEqual(p['cmd_vel_out_topic'],'cmd_vel')
        import json
        self.assertEqual(json.loads(p['StopZone']['points']),[[.24,.20],[.24,-.20],[-.24,-.20],[-.24,.20]])
        self.assertEqual(c['behavior_server']['ros__parameters']['behavior_plugins'], ['wait'])
        self.assertEqual(c['velocity_smoother']['ros__parameters']['min_velocity'][0],0)


if __name__ == '__main__':
    unittest.main()
