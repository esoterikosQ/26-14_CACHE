from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from bundle import FILES, ROOT, SUBMIT_ROOT, digest, validate_job, verify


class BundleContracts(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((Path(__file__).parent / 'entropy.template.json').read_text())
        self.env = {'SLURM_SUBMIT_DIR': str(SUBMIT_ROOT), 'SLURM_JOB_ID': '123',
                    'SLURM_JOB_NUM_NODES': '1', 'SLURM_NTASKS': '1',
                    'SLURM_GPUS_ON_NODE': '1', 'SLURM_CPUS_PER_TASK': '8',
                    'SLURM_JOB_PARTITION': 'amd_a100nv_8'}
        self.job = 'JobId=123 Comment=field=nlp;appl=pytorch EndTime=2026-10-29T10:00:00+00:00'
        self.now = datetime(2026, 10, 29, 8, tzinfo=timezone.utc)

    def check(self):
        return validate_job(self.config, self.env, self.job, now=self.now)

    def test_reference_project_is_not_a_submission_or_output_root(self):
        self.assertEqual(ROOT, Path('/scratch/r984a02/blt-cache'))
        self.assertEqual(SUBMIT_ROOT, ROOT)
        self.assertEqual(self.check(), 'preflight')
        for directory in ('/scratch/r984a02', '/scratch/r984a02/phdq3', str(ROOT / 'neuron')):
            self.env['SLURM_SUBMIT_DIR'] = directory
            with self.assertRaisesRegex(ValueError, 'Submit directory'):
                self.check()
        self.env['SLURM_SUBMIT_DIR'] = str(SUBMIT_ROOT)
        self.config['run_dir'] = '/scratch/r984a02/phdq3/outputs/korean_entropy/wrong'
        with self.assertRaisesRegex(ValueError, 'run_dir'):
            self.check()

    def test_shell_submission_guard_reaches_environment_only_from_submit_root(self):
        script = Path(__file__).with_name('train_entropy.sh')
        with tempfile.TemporaryDirectory() as directory:
            environment = {'BUNDLE': '/unused/bundle', 'CONFIG': '/unused/config.json',
                           'CONDA_SH': str(Path(directory) / 'missing.sh'), 'SLURM_JOB_ID': '123'}
            for submit_dir in (str(SUBMIT_ROOT), '/scratch/r984a02', '/scratch/r984a02/phdq3'):
                environment['SLURM_SUBMIT_DIR'] = submit_dir
                result = subprocess.run(['/bin/bash', str(script)], env=environment,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                expected = ('Existing conda activation script missing' if submit_dir == str(SUBMIT_ROOT)
                            else 'Submit with sbatch from /scratch/r984a02/blt-cache')
                self.assertIn(expected, result.stderr)

    def test_default_preflight_and_explicit_training_gates(self):
        for partition in ('amd_a100nv_8', 'amd_a100_4', 'amd_h200nv_8'):
            self.env['SLURM_JOB_PARTITION'] = partition
            self.assertEqual(self.check(), 'preflight')
        self.assertEqual(self.check(), 'preflight')
        self.env['MODE'] = 'pilot'
        with self.assertRaisesRegex(ValueError, 'not authorized'):
            self.check()
        self.config.update(training_authorized=True, max_seconds=1800)
        self.assertEqual(self.check(), 'pilot')
        self.config['max_seconds'] = 30 * 86400
        self.assertEqual(self.check(), 'pilot')
        self.now = datetime(2026, 10, 29, 9, 40, tzinfo=timezone.utc)
        with self.assertRaisesRegex(ValueError, '30 minutes'):
            self.check()

    def test_allocation_paths_and_comment_fail_closed(self):
        for key, value in [('SLURM_GPUS_ON_NODE', '2'), ('SLURM_JOB_PARTITION', 'cas_v100_4'),
                           ('SLURM_CPUS_PER_TASK', '16'), ('SLURM_SUBMIT_DIR', '/tmp'),
                           ('SLURM_JOB_NUM_NODES', '2'), ('MODE', 'unknown')]:
            with self.subTest(key=key):
                original = dict(self.env)
                self.env[key] = value
                with self.assertRaises(ValueError):
                    self.check()
                self.env = original
        self.job = self.job.replace('field=nlp', 'field=other')
        with self.assertRaises(ValueError):
            self.check()
        self.job = self.job.replace('field=other', 'field=nlp')
        self.config['run_dir'] = '/tmp/unsafe'
        with self.assertRaises(ValueError):
            self.check()

    def test_latest_checkpoint_needs_sidecar_and_idle_run(self):
        from bundle import latest_checkpoint
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            with self.assertRaisesRegex(ValueError, 'No completed'):
                latest_checkpoint(run)
            for step in (50, 2000, 4000):
                (run / f'step-{step:08d}.pt').write_text('x')
                (run / f'step-{step:08d}.sha256').write_text('x')
            (run / 'step-00006000.pt').write_text('partial: sidecar not written yet')
            (run / 'final-00009000.pt').write_text('not a rolling checkpoint')
            self.assertEqual(latest_checkpoint(run), run / 'step-00004000.pt')
            (run / '.active').write_text('')
            with self.assertRaisesRegex(ValueError, 'active'):
                latest_checkpoint(run)

    def test_snapshot_hash_and_allowlist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in FILES:
                path = root / 'runtime' / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('synthetic')
            manifest = {'files': {name: digest(root / 'runtime' / name) for name in FILES}}
            (root / 'runtime-manifest.json').write_text(json.dumps(manifest))
            verify(root)
            (root / 'runtime' / FILES[0]).write_text('changed')
            with self.assertRaisesRegex(ValueError, 'hash/path mismatch'):
                verify(root)
            manifest['files']['../outside'] = 'bad'
            (root / 'runtime-manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'allowlist'):
                verify(root)


if __name__ == '__main__':
    unittest.main()