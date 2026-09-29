"""Existing navigation routing checks, reusable while DDS discovery settles."""


def routing_errors(node, prefix):
    errors = []
    checks = [
        ('/cmd_vel_guarded', 'navigation_guard', node.get_publishers_info_by_topic),
        ('/cmd_vel', 'collision_monitor', node.get_publishers_info_by_topic),
        ('/cmd_vel', 'limo_base_node', node.get_subscriptions_info_by_topic),
    ]
    for topic, expected, get_endpoints in checks:
        endpoints = get_endpoints(prefix + topic)
        observed = [(e.node_namespace, e.node_name) for e in endpoints]
        if observed != [(prefix, expected)]:
            errors.append(f'{topic}: expected only {prefix}/{expected}; observed {observed}')
    topics = {name for name, _ in node.get_topic_names_and_types()}
    for topic in ('/cmd_vel', '/scan', '/map', '/tf', '/tf_static'):
        if topic in topics:
            errors.append('Unexpected unnamespaced topic: ' + topic)
    return errors
