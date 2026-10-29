"""Opt-in single-device entropy CPT; default invocation is a read-only preflight."""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import shutil
import signal
import sys
import time

from .entropy_data import examples, file_sha256, inspect_dataset
from .training import lr_factor


ROOT = Path(__file__).resolve().parents[1]


class StopRequest:
    def __init__(self):
        self.requested = False
        self.previous = {}

    def request(self, number, frame):
        self.requested = True

    def install(self):
        for number in (signal.SIGTERM, signal.SIGUSR1):
            self.previous[number] = signal.signal(number, self.request)

    def restore(self):
        for number, handler in self.previous.items():
            signal.signal(number, handler)


def load_patcher(model_path):
    import torch
    from safetensors import safe_open
    from .model import configured_model
    from .patched.modeling_blt import BltPatcher
    config = configured_model(model_path, attention_mode='osc').patcher_config
    patcher = BltPatcher(config).to(dtype=torch.bfloat16)
    prefix = 'model.patcher.'
    with safe_open(str(Path(model_path) / 'model.safetensors'), framework='pt', device='cpu') as handle:
        state = {name[len(prefix):]: handle.get_tensor(name)
                 for name in handle.keys() if name.startswith(prefix)}
    if not state:
        raise ValueError('Converted checkpoint has no model.patcher tensors')
    patcher.load_state_dict(state, strict=True)
    if any(value.dtype != torch.bfloat16 for value in state.values()):
        raise ValueError('Expected BF16 source tensors')
    return patcher


def loss_sums(model, item, device):
    import torch
    inputs = torch.tensor([item['inputs']], dtype=torch.long, device=device)
    targets = torch.tensor(item['targets'], dtype=torch.long, device=device)
    logits = model(input_ids=inputs, use_cache=False)[2][0].float()
    losses = torch.nn.functional.cross_entropy(logits, targets, reduction='none')
    return losses.sum(), losses[targets >= 4].sum(), targets.numel()


def update(model, optimizer, batch, device, clip_norm):
    import torch
    optimizer.zero_grad(set_to_none=True)
    tokens = sum(len(item['targets']) for item in batch)
    byte_nll = 0.
    for item in batch:
        total, body, _ = loss_sums(model, item, device)
        if not torch.isfinite(total):
            raise ValueError('Nonfinite training loss')
        (total / tokens).backward()
        byte_nll += float(body.detach())
    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), clip_norm, error_if_nonfinite=True)
    optimizer.step()
    return byte_nll, float(norm)


def evaluate(model, path, chunk_bytes, device, deadline=None, stop=None):
    import torch
    model.eval()
    nll, byte_count = 0., 0
    with torch.inference_mode():
        for item in examples(path, chunk_bytes):
            if stop is not None and stop.requested:
                raise InterruptedError('Validation interrupted after saving training checkpoint')
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError('Validation did not complete within the approved time budget')
            _, body, _ = loss_sums(model, item, device)
            nll += float(body)
            byte_count += item['utf8_bytes']
    model.train()
    if not byte_count or not math.isfinite(nll):
        raise ValueError('Invalid validation loss')
    return {'byte_bpb': nll / byte_count / math.log(2), 'utf8_bytes': byte_count}


def save_state(path, model, optimizer, progress, signature):
    import torch
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    temporary = path.with_suffix('.partial')
    with temporary.open('xb') as handle:
        torch.save({'model': model.state_dict(), 'optimizer': optimizer.state_dict(),
                    'progress': progress, 'signature': signature,
                    'python_rng': random.getstate(), 'torch_rng': torch.get_rng_state(),
                    'cuda_rng': torch.cuda.get_rng_state_all() if torch.cuda.is_available() else []}, handle)
    temporary.rename(path)
    with path.with_suffix('.sha256').open('x') as handle:
        handle.write(file_sha256(path) + '\n')


def restore_state(path, model, optimizer, signature):
    import torch
    path = Path(path)
    if path.with_suffix('.sha256').read_text().strip() != file_sha256(path):
        raise ValueError('Checkpoint file hash mismatch')
    state = torch.load(path, map_location='cpu', weights_only=False)
    if state['signature'] != signature:
        raise ValueError('Checkpoint contract mismatch')
    model.load_state_dict(state['model'], strict=True)
    optimizer.load_state_dict(state['optimizer'])
    random.setstate(state['python_rng'])
    torch.set_rng_state(state['torch_rng'])
    if state['cuda_rng']:
        torch.cuda.set_rng_state_all(state['cuda_rng'])
    return state['progress']


def preflight(config):
    blockers, summary = [], None
    if config.get('training_authorized') is not True:
        blockers.append('training_authorized must be explicitly true after budget approval')
    for key in ('max_steps', 'max_train_bytes', 'max_seconds', 'max_run_bytes', 'max_gpu_memory_bytes'):
        if type(config.get(key)) is not int or config[key] < 1:
            blockers.append(f'positive approved {key} required')
    if not config.get('dataset_manifest'):
        blockers.append('dataset_manifest missing; corpus has not been ingested')
    else:
        manifest, summary = inspect_dataset(config['dataset_manifest'])
        for key in ('license_approved', 'pii_review_approved', 'near_duplicate_split_review_approved'):
            if manifest.get(key) is not True:
                blockers.append(f'dataset {key} required')
    if config.get('checkpoint_revision') != 'f2aae511e44e2086b1204bc4ddec6ac6c9651332':
        blockers.append('unreviewed entropy checkpoint revision')
    if not Path(config['model_path'], 'model.safetensors').is_file():
        blockers.append('local converted checkpoint unavailable')
    for key in ('chunk_bytes', 'accumulation', 'save_every', 'threads', 'min_free_disk_bytes'):
        if type(config.get(key)) is not int or config[key] < 1:
            blockers.append(f'positive {key} required')
    if type(config.get('chunk_bytes')) is int and config['chunk_bytes'] > 512:
        blockers.append('initial preparation supports at most 512 payload bytes per chunk')
    for key in ('lr', 'clip_norm'):
        if not isinstance(config.get(key), (int, float)) or not math.isfinite(config[key]) or config[key] <= 0:
            blockers.append(f'positive finite {key} required')
    for key in ('warmup_steps', 'seed'):
        if type(config.get(key)) is not int or config[key] < 0:
            blockers.append(f'nonnegative integer {key} required')
    if (not isinstance(config.get('weight_decay'), (int, float)) or
            not math.isfinite(config['weight_decay']) or config['weight_decay'] < 0):
        blockers.append('nonnegative finite weight_decay required')
    return {'training_ready': not blockers, 'blockers': blockers, 'dataset': summary}


def check_storage(root, config, reserve=0):
    if shutil.disk_usage(root).free < config['min_free_disk_bytes'] + reserve:
        raise ValueError('Free disk guard triggered before writing')
    occupied = sum(path.stat().st_size for path in root.rglob('*') if path.is_file())
    if occupied + reserve > config['max_run_bytes']:
        raise ValueError('Run artifact budget would be exceeded')


def run(config, resume=None, stop_after_steps=None):
    import torch
    check = preflight(config)
    if not check['training_ready']:
        raise ValueError(json.dumps(check['blockers']))
    if not torch.cuda.is_available():
        raise ValueError('CUDA required for approved pretrained CPT')
    if stop_after_steps is not None and stop_after_steps < 1:
        raise ValueError('Positive invocation step limit required')
    root = Path(config['run_dir']).resolve()
    if root.exists() and not resume:
        raise FileExistsError('New run directory required; use explicit --resume for an existing run')
    if resume and not root.is_dir():
        raise ValueError('Resume requires the original run directory')
    if shutil.disk_usage(root.parent).free < config['min_free_disk_bytes']:
        raise ValueError('Insufficient free disk')
    torch.set_num_threads(config['threads'])
    random.seed(config['seed'])
    torch.manual_seed(config['seed'])
    torch.cuda.manual_seed_all(config['seed'])
    torch.backends.cuda.matmul.allow_tf32 = False
    available = torch.cuda.get_device_properties(0).total_memory
    if config['max_gpu_memory_bytes'] >= available:
        raise ValueError('Approved GPU budget must leave space for the CUDA runtime')
    torch.cuda.set_per_process_memory_fraction(config['max_gpu_memory_bytes'] / available, device=0)
    model = load_patcher(config['model_path']).to('cuda').train()
    checkpoint_reserve = sum(value.numel() * value.element_size() for value in model.parameters()) * 4 + 67108864
    optimizer = torch.optim.AdamW(model.parameters(), lr=config['lr'], betas=(.9, .95),
                                 weight_decay=config['weight_decay'])
    identity = {'config': config, 'manifest_sha256': file_sha256(config['dataset_manifest']),
                'source_sha256': {str(path.relative_to(ROOT)): file_sha256(path)
                                  for path in [Path(__file__), ROOT / 'blt_hf/entropy_data.py',
                                               ROOT / 'blt_hf/training.py', ROOT / 'blt_hf/model.py',
                                               ROOT / 'blt_hf/attention.py', ROOT / 'blt_hf/patching.py',
                                               ROOT / 'blt_hf/manifest.py', ROOT / 'blt_hf/data_adapter.py',
                                               *sorted((ROOT / 'blt_hf/patched').glob('*.py'))]},
                'weights_sha256': file_sha256(Path(config['model_path']) / 'model.safetensors'),
                'model_config_sha256': file_sha256(Path(config['model_path']) / 'config.json'),
                'torch': torch.__version__, 'device': torch.cuda.get_device_name(),
                'transformers': __import__('transformers').__version__}
    signature = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    progress = {'step': 0, 'epoch': 0, 'cursor': 0, 'exposed_bytes': 0, 'elapsed_seconds': 0.}
    if resume:
        progress = restore_state(resume, model, optimizer, signature)
    else:
        root.mkdir()
        (root / 'contract.json').write_text(json.dumps(identity, indent=2) + '\n')
        (root / 'trainable.json').write_text(json.dumps(
            {name: list(parameter.shape) for name, parameter in model.named_parameters()}, indent=2) + '\n')
    lock = root / '.active'
    with lock.open('x'):
        pass
    stop = StopRequest()
    try:
        stop.install()
        started = time.monotonic()
        elapsed_before = progress['elapsed_seconds']
        train_path = check['dataset']['train']['path']
        iterator = itertools.islice(examples(train_path, config['chunk_bytes']), progress['cursor'], None)
        invocation_steps = 0
        while progress['step'] < config['max_steps'] and not stop.requested:
            progress['elapsed_seconds'] = elapsed_before + time.monotonic() - started
            if progress['elapsed_seconds'] >= config['max_seconds']:
                break
            if stop_after_steps is not None and invocation_steps >= stop_after_steps:
                break
            batch = list(itertools.islice(iterator, config['accumulation']))
            if not batch:
                progress['epoch'] += 1
                progress['cursor'] = 0
                iterator = iter(examples(train_path, config['chunk_bytes']))
                continue
            byte_count = sum(item['utf8_bytes'] for item in batch)
            if progress['exposed_bytes'] + byte_count > config['max_train_bytes']:
                break
            check_storage(root, config, checkpoint_reserve)
            optimizer.param_groups[0]['lr'] = config['lr'] * lr_factor(
                progress['step'], config['max_steps'], config['warmup_steps'])
            torch.cuda.synchronize()
            step_start = time.monotonic()
            nll, norm = update(model, optimizer, batch, 'cuda', config['clip_norm'])
            torch.cuda.synchronize()
            seconds = time.monotonic() - step_start
            progress['step'] += 1
            progress['cursor'] += len(batch)
            progress['exposed_bytes'] += byte_count
            progress['elapsed_seconds'] = elapsed_before + time.monotonic() - started
            invocation_steps += 1
            event = {**progress, 'byte_bpb': nll / byte_count / math.log(2),
                     'gradient_norm': norm, 'optimizer_step_seconds': seconds,
                     'training_bytes_per_second': byte_count / seconds,
                     'peak_allocated_bytes': torch.cuda.max_memory_allocated()}
            with (root / 'metrics.jsonl').open('a') as handle:
                handle.write(json.dumps(event) + '\n')
            print(json.dumps(event), flush=True)
            if event['peak_allocated_bytes'] > config['max_gpu_memory_bytes']:
                raise ValueError('GPU memory budget exceeded')
            if progress['step'] % config['save_every'] == 0:
                check_storage(root, config, checkpoint_reserve)
                save_state(root / f"step-{progress['step']:08d}.pt", model, optimizer, dict(progress), signature)
        checkpoint = root / f"step-{progress['step']:08d}.pt"
        if not checkpoint.exists():
            check_storage(root, config, checkpoint_reserve)
            save_state(checkpoint, model, optimizer, dict(progress), signature)
        if stop.requested:
            print(json.dumps({'status': 'paused_signal', 'checkpoint': str(checkpoint)}), flush=True)
            return 75
        deadline = started + max(0., config['max_seconds'] - elapsed_before)
        try:
            report = evaluate(model, check['dataset']['validation']['path'], config['chunk_bytes'], 'cuda', deadline, stop)
        except InterruptedError:
            print(json.dumps({'status': 'paused_signal', 'checkpoint': str(checkpoint),
                              'validation': 'incomplete'}), flush=True)
            return 75
        progress['elapsed_seconds'] = elapsed_before + time.monotonic() - started
        report.update(progress)
        report['checkpoint'] = str(checkpoint)
        report['signature'] = signature
        with (root / f"validation-{progress['step']:08d}.json").open('x') as handle:
            handle.write(json.dumps(report, indent=2) + '\n')
    finally:
        stop.restore()
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--resume', help='Trusted local checkpoint only; torch pickle loading required')
    parser.add_argument('--stop-after-steps', type=int)
    parser.add_argument('--check-model', action='store_true', help='CPU-only strict model load, no optimizer')
    parser.add_argument('--report', help='Fresh preflight report JSON; refuses to overwrite')
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    if args.execute:
        return run(config, args.resume, args.stop_after_steps)
    else:
        report = preflight(config)
        if args.check_model:
            model = load_patcher(config['model_path'])
            report['model'] = {'parameters': sum(value.numel() for value in model.parameters()),
                               'strict_load': True, 'dtype': str(next(model.parameters()).dtype)}
        print(json.dumps(report, indent=2))
        if args.report:
            with Path(args.report).open('x') as handle:
                handle.write(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    sys.exit(main())