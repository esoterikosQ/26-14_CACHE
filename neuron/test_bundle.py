from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from bundle import FILES, ROOT, digest, validate_job, verify


class BundleContracts(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((Path(__file__).parent / 'entropy.template.json').read_text())
        self.env = {'SLURM_SUBMIT_DIR': str(ROOT), 'SLURM_JOB_ID': '123',
                    'SLURM_JOB_NUM_NODES': '1', 'SLURM_NTASKS': '1',
                    'SLURM_GPUS_ON_NODE': '1', 'SLURM_CPUS_PER_TASK': '8',
                    'SLURM_JOB_PARTITION': 'amd_a100nv_8'}
        self.job = 'JobId=123 Comment=field=nlp;appl=pytorch EndTime=2026-10-29T10:00:00+00:00'
        self.now = datetime(2026, 10, 29, 8, tzinfo=timezone.utc)

    def check(self):
        return validate_job(self.config, self.env, self.job, now=self.now)

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
        self.config['max_seconds'] = 7100
        with self.assertRaisesRegex(ValueError, '15 minutes'):
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