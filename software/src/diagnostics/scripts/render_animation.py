#!/usr/bin/env python3
"""Offscreen MuJoCo animation renderer (runs under the .venv python).

Reads a recording.npz produced by the recorder node, replays the joint
trajectory through the MJCF, and writes an isometric video auto-framed so the
whole arm + line + fish stay in view while being zoomed in as far as possible.

This is intentionally NOT a ROS node: it needs `mujoco` (which lives in the
project virtualenv, not the ROS python). The recorder spawns it for you, or run
it manually:

    ~/fishing-bot/.venv/bin/python render_animation.py recording.npz \
        --output animation.mp4 --fps 30

Requires `imageio` (and `imageio-ffmpeg` for mp4) in that same environment:

    ~/fishing-bot/.venv/bin/pip install imageio imageio-ffmpeg
"""
import argparse
import math
import os
import sys

# Pick a GL backend before importing mujoco: EGL when headless, GLFW otherwise.
if 'MUJOCO_GL' not in os.environ:
    os.environ['MUJOCO_GL'] = 'glfw' if os.environ.get('DISPLAY') else 'egl'

import numpy as np  # noqa: E402


def _compute_framing(model, data, mujoco, qpos, indices):
    """Bounding sphere of every geom except the ground, over all frames."""
    ground_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, 'ground')
    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    for i in indices:
        data.qpos[:] = qpos[i]
        mujoco.mj_forward(model, data)
        for g in range(model.ngeom):
            if g == ground_id:
                continue
            p = data.geom_xpos[g]
            r = float(model.geom_rbound[g])
            lo = np.minimum(lo, p - r)
            hi = np.maximum(hi, p + r)
    center = (lo + hi) / 2.0
    radius = float(np.linalg.norm(hi - center))
    return center, max(radius, 1e-3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('npz', help='recording.npz from the recorder node')
    parser.add_argument('--output', default='animation.mp4')
    parser.add_argument('--mjcf', default='', help='override MJCF path')
    parser.add_argument('--fps', type=int, default=30)
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--height', type=int, default=720)
    parser.add_argument('--azimuth', type=float, default=135.0)
    parser.add_argument('--elevation', type=float, default=-20.0)
    parser.add_argument('--margin', type=float, default=1.15,
                        help='>1 leaves padding around the scene')
    args = parser.parse_args()

    try:
        import mujoco
        import imageio
    except ImportError as exc:
        sys.exit(f'[render] Missing dependency: {exc}. '
                 f'Install with: pip install mujoco imageio imageio-ffmpeg')

    rec = np.load(args.npz, allow_pickle=True)
    qpos = rec['qpos']
    times = rec['times']
    mjcf_path = args.mjcf or str(rec['mjcf_path'])
    if qpos.size == 0:
        sys.exit('[render] recording has no qpos frames.')

    model = mujoco.MjModel.from_xml_path(mjcf_path)
    if qpos.shape[1] != model.nq:
        sys.exit(f'[render] qpos width {qpos.shape[1]} != model.nq {model.nq}')
    data = mujoco.MjData(model)

    # Subsample the recorded frames down to the target playback fps.
    n = len(times)
    duration = float(times[-1] - times[0]) if n > 1 else 1.0
    src_rate = n / duration if duration > 0 else float(args.fps)
    stride = max(1, int(round(src_rate / args.fps)))
    indices = list(range(0, n, stride))

    center, radius = _compute_framing(model, data, mujoco, qpos, indices)
    fovy = float(model.vis.global_.fovy)
    distance = radius / math.sin(math.radians(fovy / 2.0)) * args.margin

    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.lookat[:] = center
    cam.distance = distance
    cam.azimuth = args.azimuth
    cam.elevation = args.elevation

    renderer = mujoco.Renderer(model, height=args.height, width=args.width)
    frames = []
    for i in indices:
        data.qpos[:] = qpos[i]
        mujoco.mj_forward(model, data)
        renderer.update_scene(data, camera=cam)
        frames.append(renderer.render())
    renderer.close()

    out = args.output
    try:
        imageio.mimsave(out, frames, fps=args.fps)
    except Exception as exc:  # ffmpeg missing for mp4, etc. -> fall back to gif
        gif = os.path.splitext(out)[0] + '.gif'
        print(f'[render] {out} failed ({exc}); writing {gif} instead.')
        imageio.mimsave(gif, frames, fps=args.fps, loop=0)
        out = gif
    print(f'[render] Wrote {out} ({len(frames)} frames @ {args.fps} fps).')


if __name__ == '__main__':
    main()
