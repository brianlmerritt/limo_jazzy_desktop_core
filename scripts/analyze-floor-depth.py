#!/usr/bin/env python3
"""Offline candidate floor-plane diagnostic; never publishes ROS commands."""
import argparse
import json
from pathlib import Path

import numpy as np


def analyze(depth, calibration, camera_height_m=None):
    if camera_height_m is not None and (not np.isfinite(camera_height_m) or camera_height_m <= 0):
        raise ValueError("Camera height must be finite and positive")
    if depth.ndim == 2:
        depth = depth[None, ...]
    if depth.ndim != 3 or depth.shape[1:] != (calibration['height'], calibration['width']):
        raise ValueError('Depth must be metres with shape [frames, height, width] or [height, width] matching calibration')
    h, w = depth.shape[1:]
    k = calibration['k']
    y, x = np.indices((h, w))
    rays = np.stack(((x-k[2])/k[0], (y-k[5])/k[4], np.ones_like(x)), axis=-1)
    roi = (y >= h*.6) & (x >= w*.2) & (x < w*.8)
    # Fit only measured nearby points. Missing pixels are never filled as floor.
    z = depth[0]
    select = roi & np.isfinite(z) & (z > .15) & (z < 2)
    points = rays[select] * z[select, None]
    if len(points) < 100:
        return {'status': 'insufficient near points', 'near_points': len(points)}
    rng = np.random.default_rng(42)
    sample = points[rng.choice(len(points), min(4000, len(points)), replace=False)]
    best = None
    for _ in range(400):
        a, b, c = sample[rng.choice(len(sample), 3, replace=False)]
        normal = np.cross(b-a, c-a)
        length = np.linalg.norm(normal)
        if length < 1e-8:
            continue
        normal /= length
        if normal[1] < 0:
            normal = -normal
        # Assumes approximately level camera; excludes walls, not reflections.
        if normal[1] < .8:
            continue
        offset = float(normal @ a)
        if not .05 < offset < .6:
            continue
        inliers = np.abs(sample @ normal-offset) < .025
        score = int(inliers.sum())
        if best is None or score > best[0]:
            best = (score, normal, offset, inliers)
    if best is None or best[0] < 100:
        return {'status': 'no candidate plane', 'near_points': len(points)}
    fit = sample[best[3]]
    center = fit.mean(axis=0)
    _, _, axes = np.linalg.svd(fit-center, full_matrices=False)
    normal = axes[-1]
    if normal[1] < 0:
        normal = -normal
    offset = float(normal @ center)
    denominator = rays @ normal
    expected = np.divide(offset, denominator, out=np.full((h,w), np.nan), where=denominator > .001)
    regions = {}
    for name, lo, hi in [('lower_middle', .6, .8), ('bottom', .8, 1)]:
        mask = roi & (y >= lo*h) & (y < hi*h) & (expected > .15) & (expected < 2)
        values = depth[:, mask]
        valid = np.isfinite(values) & (values > 0)
        residual = np.abs(values * denominator[mask] - offset)
        support = valid & (residual < .025)
        regions[name] = {
            'pixels_per_frame': int(mask.sum()),
            'nonzero_fraction': float(valid.mean()) if values.size else None,
            'plane_support_fraction': float(support.mean()) if values.size else None,
            'support_fraction_per_frame_min_max': [float(v) for v in (support.mean(axis=1).min(), support.mean(axis=1).max())] if values.size else None,
        }
    return {'status': 'candidate only; not verified ground', 'frames': len(depth),
            'normal_optical_xyz': normal.tolist(), 'camera_plane_distance_m': offset,
            'measured_camera_height_m': camera_height_m,
            'plane_distance_minus_measured_height_m': offset-camera_height_m if camera_height_m is not None else None,
            'fit_near_point_fraction': best[0]/len(sample), 'regions': regions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calibration', required=True, type=Path)
    parser.add_argument('--camera-height-m', type=float, help='Measured lens height; reports fit discrepancy without forcing the plane or changing TF')
    parser.add_argument('captures', nargs='+', type=Path)
    args = parser.parse_args()
    calibration = json.loads(args.calibration.read_text())
    if calibration.get('distortion_model') != 'plumb_bob' or any(calibration.get('d', [])):
        raise ValueError('This diagnostic requires zero-distortion aligned depth calibration')
    print(json.dumps({str(p): analyze(np.load(p, allow_pickle=False), calibration, args.camera_height_m) for p in args.captures}, indent=2))


if __name__ == '__main__':
    main()
