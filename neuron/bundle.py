"""Verify the entropy runtime maintained in blt-cache and its SLURM contract."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = Path('/scratch/r984a02/blt-cache')
SUBMIT_ROOT = Path('/scratch/r984a02')
FILES = (
    'blt_hf/__init__.py', 'blt_hf/entropy_data.py', 'blt_hf/entropy_train.py',
    'blt_hf/training.py', 'blt_hf/model.py', 'blt_hf/manifest.py',
    'blt_hf/data_adapter.py', 'blt_hf/attention.py', 'blt_hf/patching.py',
    'blt_hf/patched/__init__.py', 'blt_hf/patched/modeling_blt.py',
    'blt_hf_checks/check_env.py',
    'tests/test_hf_entropy.py', 'tests/test_hf_training.py',
    'plan/korean_entropy_preparation.json',
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refresh():
    destination = HERE / 'runtime'
    manifest_path = HERE / 'runtime-manifest.json'
    report = json.loads(manifest_path.read_text())
    for name in FILES:
        path = destination / name
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(destination.resolve()):
            raise ValueError(f'Missing or linked runtime file: {name}')
    report['files'] = {name: digest(destination / name) for name in FILES}
    with manifest_path.open('w') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    verify()


def verify(directory=HERE):
    manifest = json.loads((directory / 'runtime-manifest.json').read_text())
    if set(manifest['files']) != set(FILES):
        raise ValueError('Runtime allowlist changed')
    runtime = (directory / 'runtime').resolve()
    for name, expected in manifest['files'].items():
        path = runtime / name
        if not path.resolve().is_relative_to(runtime) or path.is_symlink() or digest(path) != expected:
            raise ValueError(f'Runtime hash/path mismatch: {name}')
    print(f'Runtime verified: {len(FILES)} files')


def validate_job(config, environment, job_details, root=ROOT, now=None):
    if environment.get('SLURM_SUBMIT_DIR') != str(SUBMIT_ROOT) or not environment.get('SLURM_JOB_ID'):
        raise ValueError(f'Submit directory must be {SUBMIT_ROOT} inside a SLURM job')
    if environment.get('SLURM_JOB_NUM_NODES') != '1' or environment.get('SLURM_NTASKS', '1') != '1':
        raise ValueError('Only one node/task is supported')
    if environment.get('SLURM_GPUS_ON_NODE') != '1':
        raise ValueError('Entropy runtime supports exactly one allocated GPU')
    partition = environment.get('SLURM_JOB_PARTITION')
    cpu_limits = {'amd_a100nv_8': 8, 'amd_a100_4': 16, 'amd_h200nv_8': 8}
    cpus = int(environment.get('SLURM_CPUS_PER_TASK', '0'))
    if partition not in cpu_limits or not 1 <= cpus <= cpu_limits[partition]:
        raise ValueError('Unreviewed partition or CPU/GPU ratio')
    fields = dict(field.split('=', 1) for field in job_details.split() if '=' in field)
    if fields.get('JobId') != environment['SLURM_JOB_ID'] or fields.get('Comment') != 'field=nlp;appl=pytorch':
        raise ValueError('SLURM job identity/comment mismatch')
    for key, base in [('model_path', root / 'artifacts'), ('run_dir', root / 'outputs/korean_entropy')]:
        path = Path(config[key])
        if not path.is_absolute() or not path.resolve().is_relative_to(base.resolve()) or path.resolve() == base.resolve():
            raise ValueError(f'{key} must stay under {base}')
    if config.get('dataset_manifest'):
        manifest = Path(config['dataset_manifest'])
        if not manifest.is_absolute() or not manifest.resolve().is_relative_to((root / 'data/korean_cpt').resolve()):
            raise ValueError('Dataset manifest must stay under data/korean_cpt')
    if type(config.get('threads')) is not int or not 1 <= config['threads'] <= cpus:
        raise ValueError('Config threads exceed allocated CPUs')
    mode = environment.get('MODE', 'preflight')
    if mode not in ('preflight', 'pilot', 'train'):
        raise ValueError('MODE must be preflight, pilot or train')
    if mode != 'preflight':
        if config.get('training_authorized') is not True:
            raise ValueError('Training is not authorized in this config')
        end = datetime.fromisoformat(fields['EndTime']).astimezone(timezone.utc)
        remaining = (end - (now or datetime.now(timezone.utc))).total_seconds()
        if type(config.get('max_seconds')) is not int or not 0 < config['max_seconds'] <= remaining - 900:
            raise ValueError('Approved runtime must leave at least15 minutes before job end')
        if mode == 'pilot' and not 1 <= int(environment.get('PILOT_STEPS', '2')) <= 100:
            raise ValueError('PILOT_STEPS must be1..100')
    return mode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('refresh', 'verify', 'validate-job'))
    parser.add_argument('--config', type=Path)
    args = parser.parse_args()
    if args.action == 'refresh':
        refresh()
    else:
        verify()
        if args.action == 'validate-job':
            if args.config is None:
                parser.error('--config is required')
            details = subprocess.check_output(['scontrol', 'show', 'job', '-o', os.environ['SLURM_JOB_ID']], text=True)
            mode = validate_job(json.loads(args.config.read_text()), os.environ, details)
            print(f'SLURM contract verified: {mode}')


if __name__ == '__main__':
    main()