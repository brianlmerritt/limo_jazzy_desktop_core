"""Pure geometry and command checks for the platform navigation guard."""
import math


def angle_difference(a, b):
    return math.atan2(math.sin(a - b), math.cos(a - b))


def forward_command(values):
    """Reject the whole command, including rotation, for reverse/lateral motion."""
    x, y, z, roll, pitch, yaw = values
    return (all(math.isfinite(v) for v in values) and x >= 0.0 and
            y == z == roll == pitch == 0.0 and x <= 0.100001 and abs(yaw) <= 0.250001)


def scan_map_score(points, cells, width, height, resolution, origin, tolerance=0.15):
    """Count known scan endpoints near occupied map cells; unknown is not a match."""
    ox, oy, heading = origin
    c, s = math.cos(heading), math.sin(heading)
    radius = math.ceil(tolerance / resolution)
    offsets = [(i, j) for i in range(-radius, radius + 1)
               for j in range(-radius, radius + 1)
               if math.hypot(i, j) * resolution <= tolerance + 1e-9]
    known = matched = 0
    for x, y in points:
        dx, dy = x - ox, y - oy
        ix = math.floor((c * dx + s * dy) / resolution)
        iy = math.floor((-s * dx + c * dy) / resolution)
        if not (0 <= ix < width and 0 <= iy < height):
            continue
        if cells[iy * width + ix] < 0:
            continue
        known += 1
        if any(0 <= ix + a < width and 0 <= iy + b < height and
               cells[(iy + b) * width + ix + a] >= 65 for a, b in offsets):
            matched += 1
    return known, matched / known if known else 0.0


ALIGNMENT_STATES = ('aligned', 'orientation_disagreement', 'map_disagreement',
                    'both_disagree', 'insufficient_geometry', 'unavailable')
DEFAULT_POLICY = {state: 'continue' for state in ALIGNMENT_STATES}


def validate_policy(policy):
    if not isinstance(policy, dict) or set(policy) != set(ALIGNMENT_STATES):
        raise ValueError('Alignment policy must specify every known state exactly once')
    if any(action not in ('continue', 'slow', 'hold') for action in policy.values()):
        raise ValueError('Alignment actions must be continue, slow, or hold')
    return policy


def alignment_state(map_state, orientation_ok):
    """Missing evidence is distinct from an observed disagreement."""
    if map_state == 'unavailable' or orientation_ok is None:
        return 'unavailable'
    if map_state == 'insufficient':
        return 'insufficient_geometry'
    if map_state == 'match':
        return 'aligned' if orientation_ok else 'orientation_disagreement'
    return 'map_disagreement' if orientation_ok else 'both_disagree'


def action_scale(action):
    return {'continue': 1.0, 'slow': 0.5, 'hold': 0.0}[action]
