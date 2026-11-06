"""Opt-in single-device entropy CPT; default invocation is a read-only preflight.

Packed 4096-byte-class sequences under the original sliding window and EOS isolation, FP32 master
weights with BF16 forward/backward, and a warmup-stable-decay schedule whose decay starts when the
fixed validation sample plateaus (or before the max_steps cap).
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import random
import shutil
import signal
import sys
import threading
import time

from .entropy_data import PackedStream, file_sha256, inspect_dataset_cached


ROOT = Path(__file__).resolve().parents[1]
POSITIVE_INTEGERS = ('sequence_length', 'micro_batch', 'accumulation', 'save_every', 'keep_checkpoints',
                     'threads', 'min_free_disk_bytes', 'eval_every', 'eval_documents', 'plateau_patience',
                     'min_decay_steps')


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


def load_patcher(model_path, backend='eager'):
    import torch
    from safetensors import safe_open
    from .model import configured_model
    from .patched.modeling_blt import BltPatcher
    config = configured_model(model_path, attention_mode='osc',
                              backend='sdpa' if backend == 'flex_attention' else backend).patcher_config
    patcher = BltPatcher(config).to(dtype=torch.bfloat16)
    patcher.config._attn_implementation = backend
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


def learning_rate(step, config, decay):
    peak = config['lr']
    if step < config['warmup_steps']:
        return peak * (step + 1) / config['warmup_steps']
    if decay is None:
        return peak
    done = min(max(step - decay['start'], 0) / decay['length'], 1.)
    return peak * (1 - (1 - config['min_lr_ratio']) * done)


def decay_length(step, config):
    return max(config['min_decay_steps'], math.ceil(config['decay_fraction'] * step))


def plateaued(history, config):
    """Best of the last `patience` evaluations improves on the earlier best by less than min_delta."""
    patience = config['plateau_patience']
    if len(history) <= patience:
        return False
    earlier = min(bpb for _, bpb in history[:-patience])
    recent = min(bpb for _, bpb in history[-patience:])
    return earlier - recent < config['plateau_min_delta']


def sequences(stream, count):
    import numpy as np
    rows = []
    while len(rows) < count:
        row = stream.next_sequence()
        if row is None:
            break
        rows.append(row)
    if not rows:
        return None
    return np.stack([row[0] for row in rows]), np.stack([row[1] for row in rows])


class Batches:
    """Background packing of whole optimizer steps; each item carries the stream state after it."""

    def __init__(self, path, config, context, state):
        self.stream = PackedStream(path, config['sequence_length'], context, state, wrap=True)
        self.size = config['micro_batch'] * config['accumulation']
        self.queue = queue.Queue(maxsize=4)
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _put(self, item):
        while not self.stopped.is_set():
            try:
                self.queue.put(item, timeout=1)
                return
            except queue.Full:
                pass

    def _run(self):
        try:
            while not self.stopped.is_set():
                batch = sequences(self.stream, self.size)
                if batch is None:
                    self._put(ValueError('Training split produced no sequences'))
                    return
                self._put((*batch, dict(self.stream.state)))
        except BaseException as error:
            self._put(error)

    def get(self):
        item = self.queue.get()
        if isinstance(item, BaseException):
            raise item
        return item

    def close(self):
        self.stopped.set()
        self.thread.join(timeout=30)
        self.stream.close()


def window_block_mask(ids, window, eos_id=2):
    """The osc patcher mask (causal, same EOS segment, distance < window) as a sparse flex BlockMask."""
    from torch.nn.attention.flex_attention import create_block_mask
    from .attention import segment_ids
    segments = segment_ids(ids, eos_id)

    def visible(batch, head, query, key):
        return (key <= query) & (query - key < window) & (segments[batch, query] == segments[batch, key])

    return create_block_mask(visible, ids.shape[0], None, ids.shape[1], ids.shape[1], device=ids.device)


def patcher_logits(model, ids):
    """BltPatcher logits; the flex path skips the dense T x T mask and the unused entropy/patch outputs."""
    import torch
    config = getattr(model, 'config', None)
    if getattr(config, '_attn_implementation', None) != 'flex_attention':
        return model(input_ids=ids, use_cache=False)[2]
    spec = config.original_spec
    hidden = model.embed_tokens(ids)
    embeddings = model.rotary_emb(hidden, torch.arange(ids.shape[1], device=ids.device)[None])
    mask = window_block_mask(ids, spec['entropy_sliding_window'], spec['eos_id'])
    for layer in model.layers:
        hidden = layer(hidden, position_embeddings=embeddings, attention_mask=mask)
    return model.lm_head(model.norm(hidden))


def token_losses(model, tokens, keep, device):
    import torch
    ids = torch.from_numpy(tokens).to(device)
    mask = torch.from_numpy(keep).to(device)
    logits = patcher_logits(model, ids[:, :-1]).float()
    targets = ids[:, 1:]
    losses = torch.nn.functional.cross_entropy(logits.reshape(-1, logits.shape[-1]), targets.reshape(-1),
                                               reduction='none').view_as(targets)
    return losses * mask, mask & (targets >= 4)


def train_step(model, master, optimizer, tokens, keep, micro_batch, clip_norm, device):
    """Global-token mean loss over the step; BF16 grads accumulate into FP32 master weights."""
    import torch
    total = int(keep.sum())
    if not total:
        raise ValueError('Optimizer step without trained targets')
    parameters = list(model.parameters())
    for weight in master:
        weight.grad = torch.zeros_like(weight)
    body = torch.zeros((), device=device)
    for start in range(0, len(tokens), micro_batch):
        losses, bytes_mask = token_losses(model, tokens[start:start + micro_batch], keep[start:start + micro_batch], device)
        (losses.sum() / total).backward()
        body += (losses * bytes_mask).sum().detach()
        for weight, parameter in zip(master, parameters):
            weight.grad += parameter.grad.float()
            parameter.grad = None
    norm = torch.nn.utils.clip_grad_norm_(master, clip_norm, error_if_nonfinite=True)
    optimizer.step()
    with torch.no_grad():
        for weight, parameter in zip(master, parameters):
            parameter.copy_(weight)
            weight.grad = None
    return float(body), float(norm)


def evaluate(model, path, config, context, device, max_documents=None, stop=None):
    import torch
    stream = PackedStream(path, config['sequence_length'], context, max_documents=max_documents)
    nll, byte_count = torch.zeros((), device=device, dtype=torch.float64), 0
    model.eval()
    try:
        with torch.inference_mode():
            while (batch := sequences(stream, config['micro_batch'])) is not None:
                if stop is not None and stop.requested:
                    raise InterruptedError('Validation interrupted by a stop request')
                losses, bytes_mask = token_losses(model, *batch, device)
                nll += (losses * bytes_mask).double().sum()
                byte_count += int(bytes_mask.sum())
    finally:
        model.train()
        stream.close()
    nll = float(nll)
    if not byte_count or not math.isfinite(nll):
        raise ValueError('Invalid validation loss')
    return {'byte_bpb': nll / byte_count / math.log(2), 'utf8_bytes': byte_count,
            'documents': stream.state['documents']}


def save_state(path, names, master, optimizer, progress, signature):
    import torch
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    temporary = path.with_suffix('.partial')
    with temporary.open('xb') as handle:
        torch.save({'master': {name: weight.detach().cpu() for name, weight in zip(names, master)},
                    'optimizer': optimizer.state_dict(), 'progress': progress, 'signature': signature,
                    'python_rng': random.getstate(), 'torch_rng': torch.get_rng_state(),
                    'cuda_rng': torch.cuda.get_rng_state_all() if torch.cuda.is_available() else []}, handle)
    temporary.rename(path)
    with path.with_suffix('.sha256').open('x') as handle:
        handle.write(file_sha256(path) + '\n')


def restore_state(path, model, names, master, optimizer, signature):
    import torch
    path = Path(path)
    if path.with_suffix('.sha256').read_text().strip() != file_sha256(path):
        raise ValueError('Checkpoint file hash mismatch')
    state = torch.load(path, map_location='cpu', weights_only=False)
    if state['signature'] != signature:
        raise ValueError('Checkpoint contract mismatch')
    if list(state['master']) != list(names):
        raise ValueError('Checkpoint parameter names differ')
    with torch.no_grad():
        for weight, parameter, name in zip(master, model.parameters(), names):
            weight.copy_(state['master'][name])
            parameter.copy_(weight)
    optimizer.load_state_dict(state['optimizer'])
    random.setstate(state['python_rng'])
    torch.set_rng_state(state['torch_rng'])
    if state['cuda_rng']:
        torch.cuda.set_rng_state_all(state['cuda_rng'])
    return state['progress']


def save_rolling(root, names, master, optimizer, progress, signature, keep):
    path = root / f"step-{progress['step']:08d}.pt"
    if not path.exists():
        save_state(path, names, master, optimizer, progress, signature)
    for old in sorted(root.glob('step-*.pt'))[:-keep]:
        old.unlink()
        old.with_suffix('.sha256').unlink(missing_ok=True)
    return path


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
        manifest, summary = inspect_dataset_cached(config['dataset_manifest'])
        for key in ('pii_review_approved', 'near_duplicate_split_review_approved'):
            if manifest.get(key) is not True:
                blockers.append(f'dataset {key} required')
    if config.get('checkpoint_revision') != 'f2aae511e44e2086b1204bc4ddec6ac6c9651332':
        blockers.append('unreviewed entropy checkpoint revision')
    if not Path(config['model_path'], 'model.safetensors').is_file():
        blockers.append('local converted checkpoint unavailable')
    for key in POSITIVE_INTEGERS:
        if type(config.get(key)) is not int or config[key] < 1:
            blockers.append(f'positive {key} required')
    if type(config.get('sequence_length')) is int and not 1024 <= config['sequence_length'] <= 8192:
        blockers.append('sequence_length must stay within 1024..8192 (model positions)')
    if config.get('attention_backend') not in ('eager', 'sdpa', 'flex_attention'):
        blockers.append('attention_backend must be eager, sdpa or flex_attention')
    for key in ('lr', 'clip_norm'):
        if not isinstance(config.get(key), (int, float)) or not math.isfinite(config[key]) or config[key] <= 0:
            blockers.append(f'positive finite {key} required')
    for key in ('min_lr_ratio', 'decay_fraction'):
        if not isinstance(config.get(key), (int, float)) or not 0 < config[key] <= 1:
            blockers.append(f'{key} must be in (0, 1]')
    if not isinstance(config.get('plateau_min_delta'), (int, float)) or not config['plateau_min_delta'] >= 0:
        blockers.append('nonnegative plateau_min_delta required')
    for key in ('warmup_steps', 'seed'):
        if type(config.get(key)) is not int or config[key] < 0:
            blockers.append(f'nonnegative integer {key} required')
    if (not isinstance(config.get('weight_decay'), (int, float)) or
            not math.isfinite(config['weight_decay']) or config['weight_decay'] < 0):
        blockers.append('nonnegative finite weight_decay required')
    if not blockers and config['max_steps'] <= config['warmup_steps'] + config['min_decay_steps']:
        blockers.append('max_steps must exceed warmup_steps + min_decay_steps')
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
    model = load_patcher(config['model_path'], config['attention_backend']).to('cuda').train()
    context = model.config.original_spec['entropy_sliding_window']
    names = [name for name, _ in model.named_parameters()]
    master = [parameter.detach().float().clone().requires_grad_(True) for parameter in model.parameters()]
    optimizer = torch.optim.AdamW(master, lr=config['lr'], betas=(.9, .95), weight_decay=config['weight_decay'])
    checkpoint_reserve = sum(weight.numel() for weight in master) * 4 * 4 + 67108864
    identity = {'config': config, 'manifest_sha256': file_sha256(config['dataset_manifest']),
                'source_sha256': {str(path.relative_to(ROOT)): file_sha256(path)
                                  for path in [Path(__file__), ROOT / 'blt_hf/entropy_data.py',
                                               ROOT / 'blt_hf/training.py', ROOT / 'blt_hf/model.py',
                                               ROOT / 'blt_hf/attention.py', ROOT / 'blt_hf/patching.py',
                                               ROOT / 'blt_hf/manifest.py', ROOT / 'blt_hf/data_adapter.py',
                                               *sorted((ROOT / 'blt_hf/patched').glob('*.py'))]},
                'weights_sha256': file_sha256(Path(config['model_path']) / 'model.safetensors'),
                'model_config_sha256': file_sha256(Path(config['model_path']) / 'config.json'),
                'sliding_window': context, 'precision': 'fp32 master weights and AdamW; bf16 forward/backward',
                'torch': torch.__version__, 'device': torch.cuda.get_device_name(),
                'transformers': __import__('transformers').__version__}
    signature = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    progress = {'step': 0, 'stream': None, 'exposed_bytes': 0, 'elapsed_seconds': 0., 'evaluations': [],
                'last_eval_step': 0, 'decay': None}
    if resume:
        progress = restore_state(resume, model, names, master, optimizer, signature)
    else:
        root.mkdir()
        (root / 'contract.json').write_text(json.dumps(identity, indent=2) + '\n')
        (root / 'trainable.json').write_text(json.dumps(
            {name: list(parameter.shape) for name, parameter in model.named_parameters()}, indent=2) + '\n')
    if (root / 'validation-final.json').exists():
        print(json.dumps({'status': 'already_finished', 'step': progress['step']}), flush=True)
        return 0
    lock = root / '.active'
    with lock.open('x'):
        pass
    stop = StopRequest()
    batches = None
    validation_path = check['dataset']['validation']['path']

    def record(name, report):
        # Overwrite: a crash may resume from an older checkpoint and repeat this deterministic evaluation.
        report.update(step=progress['step'], signature=signature)
        temporary = root / (name + '.partial')
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(root / name)
        print(json.dumps({'event': name, **report}), flush=True)

    try:
        stop.install()
        started = time.monotonic()
        elapsed_before = progress['elapsed_seconds']
        batches = Batches(check['dataset']['train']['path'], config, context, progress['stream'])
        invocation_steps, status = 0, None
        while status is None:
            progress['elapsed_seconds'] = elapsed_before + time.monotonic() - started
            step, decay = progress['step'], progress['decay']
            if decay is not None and step >= decay['start'] + decay['length']:
                status = 'finished'
            elif stop.requested:
                status = 'signal'
            elif progress['elapsed_seconds'] >= config['max_seconds']:
                status = 'max_seconds'
            elif stop_after_steps is not None and invocation_steps >= stop_after_steps:
                status = 'pilot'
            elif step and step % config['eval_every'] == 0 and progress['last_eval_step'] != step:
                begun = time.monotonic()
                try:
                    report = evaluate(model, validation_path, config, context, 'cuda', config['eval_documents'], stop)
                except InterruptedError:
                    status = 'signal'
                    continue
                report['seconds'] = time.monotonic() - begun
                progress['evaluations'].append([step, report['byte_bpb']])
                progress['last_eval_step'] = step
                if decay is None and step >= config['warmup_steps'] and plateaued(progress['evaluations'], config):
                    progress['decay'] = {'start': step, 'length': decay_length(step, config), 'reason': 'plateau'}
                record(f'validation-{step:08d}.json', {**report, 'decay': progress['decay']})
            elif (decay is None and step >= config['warmup_steps'] and
                  step + decay_length(step, config) >= config['max_steps']):
                progress['decay'] = {'start': step, 'length': config['max_steps'] - step, 'reason': 'max_steps'}
            else:
                waited = time.monotonic()
                tokens, keep, state = batches.get()
                waited = time.monotonic() - waited
                byte_count = int((keep & (tokens[:, 1:] >= 4)).sum())
                if progress['exposed_bytes'] + byte_count > config['max_train_bytes']:
                    status = 'max_train_bytes'
                    continue
                check_storage(root, config, checkpoint_reserve)
                lr = learning_rate(step, config, decay)
                optimizer.param_groups[0]['lr'] = lr
                torch.cuda.synchronize()
                step_start = time.monotonic()
                nll, norm = train_step(model, master, optimizer, tokens, keep, config['micro_batch'],
                                       config['clip_norm'], 'cuda')
                torch.cuda.synchronize()
                seconds = time.monotonic() - step_start
                progress.update(step=step + 1, stream=state, exposed_bytes=progress['exposed_bytes'] + byte_count,
                                elapsed_seconds=elapsed_before + time.monotonic() - started)
                invocation_steps += 1
                event = {'step': progress['step'], 'lr': lr, 'byte_bpb': nll / byte_count / math.log(2),
                         'gradient_norm': norm, 'step_seconds': seconds, 'data_wait_seconds': waited,
                         'training_bytes_per_second': byte_count / seconds, 'step_utf8_bytes': byte_count,
                         'trained_target_fraction': float(keep.mean()), 'exposed_bytes': progress['exposed_bytes'],
                         'epoch': state['epoch'], 'elapsed_seconds': progress['elapsed_seconds'],
                         'peak_allocated_bytes': torch.cuda.max_memory_allocated()}
                with (root / 'metrics.jsonl').open('a') as handle:
                    handle.write(json.dumps(event) + '\n')
                print(json.dumps(event), flush=True)
                if event['peak_allocated_bytes'] > config['max_gpu_memory_bytes']:
                    raise ValueError('GPU memory budget exceeded')
                if progress['step'] % config['save_every'] == 0:
                    check_storage(root, config, checkpoint_reserve)
                    save_rolling(root, names, master, optimizer, dict(progress), signature, config['keep_checkpoints'])
        check_storage(root, config, checkpoint_reserve)
        if status == 'finished':
            final = root / f"final-{progress['step']:08d}.pt"
            if not final.exists():
                save_state(final, names, master, optimizer, dict(progress), signature)
            try:
                report = evaluate(model, validation_path, config, context, 'cuda', stop=stop)
            except InterruptedError:
                save_rolling(root, names, master, optimizer, dict(progress), signature, config['keep_checkpoints'])
                print(json.dumps({'status': 'paused_signal', 'validation': 'final incomplete'}), flush=True)
                return 75
            record('validation-final.json', {**report, 'checkpoint': str(final), 'decay': progress['decay']})
            print(json.dumps({'status': 'finished', 'checkpoint': str(final)}), flush=True)
            return 0
        checkpoint = save_rolling(root, names, master, optimizer, dict(progress), signature, config['keep_checkpoints'])
        if status == 'pilot':
            begun = time.monotonic()
            try:
                report = evaluate(model, validation_path, config, context, 'cuda', config['eval_documents'], stop)
                report['seconds'] = time.monotonic() - begun
                record(f"pilot-validation-{progress['step']:08d}.json", report)
            except InterruptedError:
                status = 'signal'
        print(json.dumps({'status': status, 'checkpoint': str(checkpoint), 'step': progress['step']}), flush=True)
        return 75 if status == 'signal' else 0
    finally:
        if batches is not None:
            batches.close()
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