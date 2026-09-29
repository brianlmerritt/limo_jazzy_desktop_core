# Stationary stair and reflective-floor depth checks

On 2026-09-08, the owner positioned LIMO first facing descending stairs, then
facing uninterrupted reflective tiled floor. No movement commands were published
for these checks. These results do not establish stair detection or protection.

Aligned RealSense depth and color were captured under the ignored directory
`.deps/validation/stairs/`: `current-depth.npy` (one stair-view frame),
`flat-floor-depth.npy` (30 floor-view frames), corresponding color PNGs, and
`calibration.json`. Depth arrays are in metres. Calibration was acquired after
both captures from the unchanged live aligned-depth camera configuration; it
was not recorded synchronously with the original frames.

The color views show strong reflections. A central bottom-quarter comparison
found nonzero depth in 48% of stair-view pixels and 68% of flat-floor pixels.
Median nonzero depth was respectively 0.77 m and 9.06 m. Nonzero measurements
therefore must not be equated with reliable ground returns.

## Candidate floor-plane diagnostic

Run inside the development container, using its existing NumPy dependency:

```bash
python3 scripts/analyze-floor-depth.py \
  --calibration .deps/validation/stairs/calibration.json \
  .deps/validation/stairs/current-depth.npy \
  .deps/validation/stairs/flat-floor-depth.npy
```

This offline tool publishes nothing and modifies neither TF nor navigation.
It reconstructs optical-frame points from aligned depth using zero-distortion
camera intrinsics. It fits a candidate plane from the first frame's near points
(0.15–2 m) in the central 60% of the image below 60% image height. RANSAC assumes
an approximately level camera, a mostly downward plane normal, and a camera to
plane distance between 5 and 60 cm. Those are diagnostic assumptions, not
measured mounting calibration. Plane agreement uses a 2.5 cm perpendicular
residual and is evaluated over all supplied frames. Missing values remain
unsupported. Reflection planes can still satisfy the fit.

| Candidate result | Stair view | Flat-floor view |
| --- | ---: | ---: |
| Camera to fitted plane | 16.2 cm | 20.9 cm |
| Plane support in bottom 20%, central 60% | 52.2% | 43.8% |
| Plane support between 60–80% image height | 17.8% | 15.5% |

The bottom region is the same image region in both captures. The middle region
also excludes rays where the fitted plane predicts a distance outside 0.15–2 m,
so its evaluated pixel counts differ. These regions differ from the earlier
bottom-quarter statistics. Flat-floor bottom support varied only from 43.6%
to 44.1% across the 30 frames: the failure is persistent in that short sample.
The stair capture has only one frame, so temporal comparisons are limited.

The fitted heights disagree by about 5 cm. Neither fit is verified ground;
these data do not justify selecting a cliff threshold or changing TF. The
current `config/robot/geometry.json` declares only the laser extrinsic, so the
camera's relationship to the chassis/wheels is also not established there.

Validation: synthetic 20 cm floor reconstruction passed; all-missing input
reported insufficient points; removing alternate columns reduced reported
support to 50% rather than inventing ground.

## Next physical checks

1. Measure the depth camera lens height above the floor and describe whether
   it is level or tilted down. Measure its fore/aft position relative to the
   front wheels before converting visible floor coverage to wheel clearance.
2. With the robot stationary facing flat floor, place a matte, non-reflective
   mat or cardboard in the lower camera view. Capture another depth sequence to
   separate material/reflection effects from plane-fit or mounting errors.
3. Validate the measured floor model and nearest visible ground distance before
   testing a protected mock edge. Current code has no cliff-stop integration;
   these captures do not authorize a drive toward stairs.

## Measured-height and cloth comparison

The owner supplied a lens height of **225 mm above floor**. A subsequent
stationary capture visibly includes a cloth covering the foreground tiles.
`measured-floor-depth.npy` contains 30 frames; `measured-floor-color.png` and
`measured-calibration.json` accompany it. Calibration matches the earlier file.

The diagnostic now accepts `--camera-height-m 0.225` and reports the difference
between the fitted plane distance and that measurement. This is an independent
comparison, not a forced fit or a camera TF calibration.

| Candidate result | Bare flat tiles | Cloth foreground |
| --- | ---: | ---: |
| Bottom-region plane support | 43.8% | 99.94% |
| Lower-middle plane support | 15.5% | 99.56% |
| Fitted camera to plane distance | 209 mm | 208 mm |
| Difference from measured 225 mm | -16 mm | -17 mm |

This strongly implicates the reflective surface as the cause of poor usable
floor coverage. The cloth is not perfectly flat; its thickness, fitting error,
and the physical measurement reference remain possible contributors to the
17 mm discrepancy. Do not silently correct camera TF from this result.
The earlier stair fit differs from measured height by 63 mm and is especially
unsuitable as a mounting calibration.

The bottom central ten rows of the cloth view have optical depths of
0.450/0.478/0.490 m at the 10th/50th/90th percentiles. This demonstrates a
substantial foreground blind region with the current camera orientation;
these are optical-axis distances, not distances from the wheels or verified
stopping margins. A single front view does not establish ground support under
the wheels.

Reproduce with:

```bash
python3 scripts/analyze-floor-depth.py \
  --calibration .deps/validation/stairs/measured-calibration.json \
  --camera-height-m 0.225 \
  .deps/validation/stairs/flat-floor-depth.npy \
  .deps/validation/stairs/measured-floor-depth.npy
```

Validation passed for a synthetic 225 mm floor, measured-height discrepancy,
and rejection of zero, negative and nonfinite height arguments. No robot
commands were published and no TF/navigation parameters were changed.

Next physical input: camera fore/aft position relative to the front wheel
contact line and whether the mount can tilt downward. Those determine how much
of the approach is invisible and whether changing camera orientation can
improve coverage. Reflective-floor reliability remains a separate limitation;
cloth success does not establish protection on the uncovered tiles.
