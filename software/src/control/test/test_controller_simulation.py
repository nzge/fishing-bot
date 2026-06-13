"""Headless simulation tests for admittance and force-feedback controllers."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / 'scripts' / 'simulate_controllers.py'


def _load_sim_module():
    sys.path.insert(0, str(REPO_ROOT / 'software/src/control'))
    spec = importlib.util.spec_from_file_location('simulate_controllers', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


pytest.importorskip('mujoco')


@pytest.fixture(scope='module')
def sim():
    return _load_sim_module()


@pytest.mark.parametrize('controller_type', ['admittance', 'force_feedback', 'baseline'])
def test_controller_simulation_produces_finite_metrics(sim, controller_type, tmp_path):
    adm_cfg, ffb_cfg = sim.configs_from_params_yaml()
    cfg = ffb_cfg if controller_type == 'force_feedback' else adm_cfg

    data = sim.run_simulation(controller_type, cfg, duration=8.0, settle_steps=100)
    metrics = sim.compute_metrics(data['time_s'], data['tension_filtered_N'], cfg)

    assert data['time_s'].size > 100
    assert np.all(np.isfinite(data['tension_filtered_N']))
    assert np.isfinite(metrics['rms_error_N'])

    sim.save_recording(tmp_path, controller_type, data, cfg, metrics)
    assert (tmp_path / f'{controller_type}.npz').exists()
    assert (tmp_path / f'{controller_type}.csv').exists()
    with (tmp_path / f'{controller_type}_metrics.json').open() as f:
        saved = json.load(f)
    assert 'rms_error_N' in saved


def test_plot_and_export_bundle(sim, tmp_path):
    adm_cfg, ffb_cfg = sim.configs_from_params_yaml()
    runs = {}
    metrics = {}
    for name, ctrl, cfg in (
        ('baseline', 'baseline', adm_cfg),
        ('admittance', 'admittance', adm_cfg),
        ('force_feedback', 'force_feedback', ffb_cfg),
    ):
        data = sim.run_simulation(ctrl, cfg, duration=6.0, settle_steps=50)
        metrics[name] = sim.compute_metrics(data['time_s'], data['tension_filtered_N'], cfg)
        runs[name] = data
        sim.save_recording(tmp_path, name, data, cfg, metrics[name])

    pytest.importorskip('matplotlib')
    sim.plot_results(tmp_path, runs, adm_cfg, metrics)

    for stem in (
        'comparison_tension',
        'comparison_position',
        'admittance_detail',
        'force_feedback_detail',
        'metrics_summary',
    ):
        assert (tmp_path / f'{stem}.png').exists()
        assert (tmp_path / f'{stem}.pdf').exists()
