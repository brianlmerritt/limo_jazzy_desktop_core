"""Translate platform body dimensions into consistent native Nav2 parameters."""
import json
import math


def footprint_replacements(config):
    required = {'length_m', 'width_m', 'clearance_m', 'center_x_m', 'center_y_m'}
    if set(config) != required:
        raise ValueError('Navigation footprint requires: ' + ', '.join(sorted(required)))
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           for v in config.values()):
        raise ValueError('Navigation footprint values must be finite numbers in metres')
    if config['length_m'] <= 0 or config['width_m'] <= 0 or config['clearance_m'] < 0:
        raise ValueError('Body dimensions must be positive and clearance nonnegative')

    def rectangle(padding):
        x = config['length_m']/2 + padding
        y = config['width_m']/2 + padding
        return [[round(config['center_x_m']+sx*x, 9),
                 round(config['center_y_m']+sy*y, 9)]
                for sx, sy in [(1, 1), (1, -1), (-1, -1), (-1, 1)]]

    return {'<robot_footprint>': json.dumps(rectangle(0)),
            '<robot_clearance>': str(float(config['clearance_m'])),
            '<robot_stop_zone>': json.dumps(rectangle(config['clearance_m']))}


def render_navigation(template, footprint, namespace):
    for key, value in {**footprint_replacements(footprint), '<robot_namespace>': namespace}.items():
        template = template.replace(key, value)
    return template
