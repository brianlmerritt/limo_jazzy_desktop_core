"""Exercise partial DDS discovery and preserve rejection of conflicting routes."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
from navigation_graph_check import routing_errors


class GraphTest(unittest.TestCase):
    def test_partial_discovery_then_ready_and_conflict(self):
        publishers = {}
        subscribers = {}
        node = SimpleNamespace(get_publishers_info_by_topic=lambda t: publishers.get(t, []),
                               get_subscriptions_info_by_topic=lambda t: subscribers.get(t, []),
                               get_topic_names_and_types=lambda: [])
        endpoint = lambda name: SimpleNamespace(node_namespace='/robot', node_name=name)
        self.assertEqual(len(routing_errors(node, '/robot')), 3)
        publishers['/robot/cmd_vel_guarded'] = [endpoint('navigation_guard')]
        self.assertEqual(len(routing_errors(node, '/robot')), 2)
        publishers['/robot/cmd_vel'] = [endpoint('collision_monitor')]
        subscribers['/robot/cmd_vel'] = [endpoint('limo_base_node')]
        self.assertEqual(routing_errors(node, '/robot'), [])
        publishers['/robot/cmd_vel'].append(endpoint('other_publisher'))
        self.assertIn('other_publisher', routing_errors(node, '/robot')[0])
