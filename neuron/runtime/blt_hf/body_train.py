"""Opt-in single-GPU Korean continued pretraining of the whole public BLT body (BODY_FULL); default is preflight.

Every body parameter trains (local encoder/decoder, hash n-gram embeddings, global transformer, lm_head);
the entropy patcher and its threshold come from the config and stay frozen. One unpadded document chunk per
micro-batch (BOS + at most sequence_bytes bytes, EOS at the document end), so documents are never packed.
FP32 master weights and fused AdamW with BF16 forward/backward, hash embeddings without weight decay, and
the patcher CPT's warmup-stable-decay schedule whose decay starts when the validation sample plateaus.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import time

from .entropy_data import MAX_RECORD_BYTES, file_sha256, inspect_dataset_cached
from .entropy_train import (StopRequest, check_storage, decay_length, learning_rate, plateaued, save_rolling,
                            save_state)


ROOT = Path(__file__).resolve().parents[1]
BOS, EOS = 1, 2
HASH_EMBEDDING = 'model.encoder_hash_tok_embedding.weight'
POSITIVE_INTEGERS = ('sequence_bytes', 'step_bytes', 'save_every', 'keep_checkpoints', 'threads',
                     'min_free_disk_bytes', 'eval_every', 'eval_documents', 'final_eval_documents',
                     'plateau_patience', 'min_decay_steps')
BRANCH_KEYS = ('run_dir', 'max_steps', 'max_train_bytes', 'max_seconds', 'max_run_bytes', 'init_from')


class ChunkStream:
    """Document chunks: BOS + up to `size` bytes, plus EOS on the last chunk of a document.

    Every byte and each document EOS is a target exactly once. State is (epoch, byte offset of the
    current document line, next chunk index in it, completed documents).
    """

    def __init__(self, path, size, state=None, max_documents=None, wrap=False):
        if type(size) is not int or size < 1:
            raise ValueError('Positive chunk size required')
        self.path, self.size, self.max_documents, self.wrap = Path(path), size, max_documents, wrap
        self.state = dict(state or {'epoch': 0, 'offset': 0, 'chunk': 0, 'documents': 0})
        self._handle = self._cached = None

    def close(self):
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def _document(self):
        offset = self.state['offset']
        if self._cached is None or self._cached[0] != offset:
            if self._handle is None:
                self._handle = self.path.open('rb')
            self._handle.seek(offset)
            raw = self._handle.readline(MAX_RECORD_BYTES + 1)
            if not raw:
                return None
            if len(raw) > MAX_RECORD_BYTES:
                raise ValueError(f'Record exceeds 16MiB at byte {offset}: {self.path}')
            record = json.loads(raw.decode('utf-8'))
            if not isinstance(record, dict) or not isinstance(record.get('text'), str) or not record['text']:
                raise ValueError(f'Expected nonempty text at byte {offset}: {self.path}')
            self._cached = (offset, record['text'].encode('utf-8'), offset + len(raw))
        return self._cached

    def next_chunk(self):
        import numpy as np
        if self.max_documents is not None and self.state['chunk'] == 0 and self.state['documents'] >= self.max_documents:
            return None
        document = self._document()
        if document is None:
            if not self.wrap or self.state['offset'] == 0:
                return None
            self.state.update(epoch=self.state['epoch'] + 1, offset=0, chunk=0, documents=0)
            return self.next_chunk()
        _, data, next_offset = document
        start = self.state['chunk'] * self.size
        piece = np.frombuffer(data[start:start + self.size], dtype=np.uint8).astype(np.int64) + 4
        last = start + self.size >= len(data)
        ids = np.concatenate([[BOS], piece, [EOS] if last else []]).astype(np.int64)
        if last:
            self.state.update(offset=next_offset, chunk=0, documents=self.state['documents'] + 1)
        else:
            self.state['chunk'] += 1
        return ids


def step_chunks(stream, step_bytes):
    """Chunks until their byte targets reach step_bytes; None when the stream is exhausted."""
    chunks, total = [], 0
    while total < step_bytes and (ids := stream.next_chunk()) is not None:
        chunks.append(ids)
        total += int((ids[1:] >= 4).sum())
    return chunks or None


def set_training(model):
    model.train()
    model.model.patcher.eval()


def load_body(model_path, patcher, backend='sdpa'):
    """Public body in BF16 with the configured frozen patcher and threshold in the in-forward patching path.

    backend 'fast' loads with SDPA and then switches to fast_body's block-sparse masks and single hash lookup.
    """
    import torch
    from . import fast_body
    from .model import configured_model
    from .patched.modeling_blt import BltForCausalLM
    from .patcher_compare import checkpoint_patcher
    base = 'sdpa' if backend == 'fast' else backend
    config = configured_model(model_path, attention_mode='osc', backend=base)
    config.patching_threshold = float(patcher['threshold'])
    model, info = BltForCausalLM.from_pretrained(str(model_path), config=config, local_files_only=True,
                                                 dtype=torch.bfloat16, device_map='cuda',
                                                 attn_implementation=base, output_loading_info=True)
    if any(info.get(key) for key in ('missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs')):
        raise ValueError('Checkpoint does not strictly match model')
    if model.config.max_patch_length is not None or model.model.patcher is None:
        raise ValueError('Expected the in-forward entropy patcher without max_patch_length')
    if patcher['checkpoint'] is not None:
        loaded, digest, _ = checkpoint_patcher(model.model.patcher, patcher['checkpoint'])
        if digest != patcher['sha256']:
            raise ValueError('Patcher checkpoint differs from the configured sha256')
        model.model.patcher = loaded
    for parameter in model.model.patcher.parameters():
        parameter.requires_grad_(False)
    if model.model.config.patching_threshold != float(patcher['threshold']):
        raise ValueError('Patching threshold was not applied')
    if backend == 'fast':
        fast_body.enable(model)
    return model


def trainable(model):
    """BODY_FULL: every parameter outside the frozen patcher."""
    named = [(name, parameter) for name, parameter in model.named_parameters() if not name.startswith('model.patcher.')]
    for _, parameter in named:
        parameter.requires_grad_(True)
    if HASH_EMBEDDING not in dict(named):
        raise ValueError('Hash n-gram embedding not found')
    return named


def make_optimizer(names, master, config):
    import torch
    groups = [{'params': [weight for name, weight in zip(names, master) if name != HASH_EMBEDDING],
               'weight_decay': config['weight_decay']},
              {'params': [weight for name, weight in zip(names, master) if name == HASH_EMBEDDING],
               'weight_decay': 0.}]
    return torch.optim.AdamW(groups, lr=config['lr'], betas=(.9, .95), eps=1e-8, fused=True)


def chunk_losses(model, ids, device):
    import torch
    tensor = torch.from_numpy(ids).to(device)[None]
    logits = model(input_ids=tensor[:, :-1], use_cache=False).logits[0].float()
    targets = tensor[0, 1:]
    return torch.nn.functional.cross_entropy(logits, targets, reduction='none'), targets >= 4


def train_step(model, parameters, master, optimizer, chunks, clip_norm, device):
    """Mean loss over every target of the step; BF16 chunk grads accumulate into FP32 master grads."""
    import torch
    total = sum(len(ids) - 1 for ids in chunks)
    for weight in master:
        if weight.grad is None:
            weight.grad = torch.zeros_like(weight)
        else:
            weight.grad.zero_()
    body = torch.zeros((), device=device, dtype=torch.float64)
    for ids in chunks:
        losses, byte_mask = chunk_losses(model, ids, device)
        (losses.sum() / total).backward()
        body += losses[byte_mask].double().sum().detach()
        for weight, parameter in zip(master, parameters):
            if parameter.grad is None:
                raise ValueError('A trainable body parameter received no gradient')
            weight.grad.add_(parameter.grad)
            parameter.grad = None
    norm = torch.nn.utils.clip_grad_norm_(master, clip_norm, error_if_nonfinite=True)
    optimizer.step()
    with torch.no_grad():
        for weight, parameter in zip(master, parameters):
            parameter.copy_(weight)
    return float(body), float(norm)


def restore(path, parameters, names, master, optimizer, signature):
    """Unlike the patcher restore, copies only into the trainable list (model.parameters() includes the patcher)."""
    import torch
    path = Path(path)
    if path.with_suffix('.sha256').read_text().strip() != file_sha256(path):
        raise ValueError('Checkpoint file hash mismatch')
    state = torch.load(path, map_location='cpu', mmap=True, weights_only=False)
    if state['signature'] != signature:
        raise ValueError('Checkpoint contract mismatch')
    if list(state['master']) != list(names):
        raise ValueError('Checkpoint parameter names differ')
    with torch.no_grad():
        for weight, parameter, name in zip(master, parameters, names):
            weight.copy_(state['master'][name])
            parameter.copy_(weight)
    optimizer.load_state_dict(state['optimizer'])
    random.setstate(state['python_rng'])
    torch.set_rng_state(state['torch_rng'])
    if state['cuda_rng']:
        torch.cuda.set_rng_state_all(state['cuda_rng'])
    return state['progress']


def branch_from(config, identity, parameters, names, master, optimizer):
    """Continue another BODY_FULL run from a checkpoint without decayed updates, under new run limits.

    Weights, AdamW and RNG state, data position, elapsed time and the evaluation history used by the plateau
    rule carry over and any scheduled decay is dropped, so training proceeds as if the parent had been approved
    with these limits. Every other config key and the data/model identity must match the parent run.
    """
    import torch
    path = Path(config['init_from']['checkpoint'])
    digest = file_sha256(path)
    if digest != config['init_from']['sha256'] or path.with_suffix('.sha256').read_text().strip() != digest:
        raise ValueError('init_from checkpoint hash mismatch')
    parent = json.loads((path.parent / 'contract.json').read_text())
    state = torch.load(path, map_location='cpu', mmap=True, weights_only=True)
    if state['signature'] != hashlib.sha256(json.dumps(parent, sort_keys=True).encode()).hexdigest():
        raise ValueError('init_from checkpoint does not belong to its run contract')
    kept = lambda values: {key: value for key, value in values.items() if key not in BRANCH_KEYS}
    if kept(parent['config']) != kept(config):
        raise ValueError('init_from run config differs beyond the run limits')
    for key in ('manifest_sha256', 'weights_sha256', 'model_config_sha256', 'trainable_sha256'):
        if parent[key] != identity[key]:
            raise ValueError(f'init_from {key} differs')
    if list(state['master']) != list(names):
        raise ValueError('init_from parameter names differ')
    progress = dict(state['progress'])
    if progress['decay'] is not None and progress['decay']['start'] != progress['step']:
        raise ValueError('init_from checkpoint already contains decayed updates')
    with torch.no_grad():
        for weight, parameter, name in zip(master, parameters, names):
            weight.copy_(state['master'][name])
            parameter.copy_(weight)
    optimizer.load_state_dict(state['optimizer'])
    random.setstate(state['python_rng'])
    torch.set_rng_state(state['torch_rng'])
    if state['cuda_rng']:
        torch.cuda.set_rng_state_all(state['cuda_rng'])
    progress['decay'] = None
    return progress


def evaluate(model, path, size, documents, device, stop=None):
    import torch
    stream = ChunkStream(path, size, max_documents=documents)
    nll, count = torch.zeros((), device=device, dtype=torch.float64), 0
    model.eval()
    try:
        with torch.inference_mode():
            while (ids := stream.next_chunk()) is not None:
                if stop is not None and stop.requested:
                    raise InterruptedError('Validation interrupted by a stop request')
                losses, byte_mask = chunk_losses(model, ids, device)
                nll += losses[byte_mask].double().sum()
                count += int(byte_mask.sum())
    finally:
        set_training(model)
        stream.close()
    nll = float(nll)
    if not count or not math.isfinite(nll):
        raise ValueError('Invalid validation loss')
    return {'byte_bpb': nll / count / math.log(2), 'utf8_bytes': count, 'documents': stream.state['documents']}


def preflight(config):
    blockers, summary = [], None
    if config.get('training_authorized') is not True:
        blockers.append('training_authorized must be explicitly true after budget approval')
    for key in ('max_steps', 'max_train_bytes', 'max_seconds', 'max_run_bytes', 'max_gpu_memory_bytes'):
        if type(config.get(key)) is not int or config[key] < 1:
            blockers.append(f'positive approved {key} required')
    if config.get('trainable') != 'all':
        blockers.append('trainable must be "all" (BODY_FULL); module subsets are not implemented yet')
    if not config.get('dataset_manifest'):
        blockers.append('dataset_manifest missing')
    else:
        manifest, summary = inspect_dataset_cached(config['dataset_manifest'])
        for key in ('pii_review_approved', 'near_duplicate_split_review_approved'):
            if manifest.get(key) is not True:
                blockers.append(f'dataset {key} required')
    if not Path(config['model_path'], 'model.safetensors').is_file():
        blockers.append('local converted checkpoint unavailable')
    patcher = config.get('patcher')
    if not isinstance(patcher, dict) or set(patcher) != {'checkpoint', 'sha256', 'threshold'}:
        blockers.append('patcher needs checkpoint (null for public), sha256 and threshold')
    else:
        threshold = patcher['threshold']
        if not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or threshold <= 0:
            blockers.append('positive finite patcher threshold required')
        if patcher['checkpoint'] is None:
            if patcher['sha256'] is not None:
                blockers.append('public patcher takes sha256 null')
        elif not Path(patcher['checkpoint']).is_absolute() or not Path(patcher['checkpoint']).is_file():
            blockers.append('patcher checkpoint must be an existing absolute path')
        elif Path(patcher['checkpoint']).with_suffix('.sha256').read_text().strip() != patcher['sha256']:
            blockers.append('patcher sha256 differs from the checkpoint sidecar')
    branch = config.get('init_from')
    if branch is not None:
        if not isinstance(branch, dict) or set(branch) != {'checkpoint', 'sha256'}:
            blockers.append('init_from needs checkpoint and sha256')
        elif not Path(branch['checkpoint']).is_absolute() or not Path(branch['checkpoint']).is_file():
            blockers.append('init_from checkpoint must be an existing absolute path')
        elif Path(branch['checkpoint']).with_suffix('.sha256').read_text().strip() != branch['sha256']:
            blockers.append('init_from sha256 differs from the checkpoint sidecar')
    for key in POSITIVE_INTEGERS:
        if type(config.get(key)) is not int or config[key] < 1:
            blockers.append(f'positive {key} required')
    if type(config.get('sequence_bytes')) is int and config['sequence_bytes'] > 8192:
        blockers.append('sequence_bytes above 8192 can exceed 4096 global patch positions')
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
    if config.get('attention_backend') not in ('eager', 'sdpa', 'fast'):
        blockers.append('attention_backend must be eager, sdpa or fast')
    if config.get('compile') not in (True, False):
        blockers.append('compile must be true or false')
    if config.get('gradient_checkpointing') not in (True, False):
        blockers.append('gradient_checkpointing must be true or false')
    if not blockers and config['max_steps'] <= config['warmup_steps'] + config['min_decay_steps']:
        blockers.append('max_steps must exceed warmup_steps + min_decay_steps')
    return {'training_ready': not blockers, 'blockers': blockers, 'dataset': summary}


def run(config, resume=None, stop_after_steps=None, deadline=None):
    import torch
    check = preflight(config)
    if not check['training_ready']:
        raise ValueError(json.dumps(check['blockers']))
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
    model = load_body(config['model_path'], config['patcher'], config['attention_backend'])
    if config['compile']:
        from .fast_body import compile_layers
        compile_layers(model)
    if config['gradient_checkpointing']:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
    set_training(model)
    named = trainable(model)
    names = [name for name, _ in named]
    parameters = [parameter for _, parameter in named]
    master = [parameter.detach().float().clone().requires_grad_(True) for parameter in parameters]
    optimizer = make_optimizer(names, master, config)
    checkpoint_reserve = sum(weight.numel() for weight in master) * 4 * 3 + 67108864
    sources = [Path(__file__), ROOT / 'blt_hf/entropy_train.py', ROOT / 'blt_hf/entropy_data.py',
               ROOT / 'blt_hf/patcher_compare.py', ROOT / 'blt_hf/fast_body.py', ROOT / 'blt_hf/model.py',
               ROOT / 'blt_hf/attention.py',
               ROOT / 'blt_hf/patching.py', *sorted((ROOT / 'blt_hf/patched').glob('*.py'))]
    identity = {'config': config, 'manifest_sha256': file_sha256(config['dataset_manifest']),
                'source_sha256': {str(path.relative_to(ROOT)): file_sha256(path) for path in sources},
                'weights_sha256': file_sha256(Path(config['model_path']) / 'model.safetensors'),
                'model_config_sha256': file_sha256(Path(config['model_path']) / 'config.json'),
                'trainable_sha256': hashlib.sha256('\n'.join(names).encode()).hexdigest(),
                'precision': 'fp32 master weights and fused AdamW; bf16 forward/backward',
                'torch': torch.__version__, 'device': torch.cuda.get_device_name(),
                'transformers': __import__('transformers').__version__}
    signature = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    progress = {'step': 0, 'stream': None, 'exposed_bytes': 0, 'elapsed_seconds': 0., 'evaluations': [],
                'last_eval_step': None, 'decay': None}
    if resume:
        progress = restore(resume, parameters, names, master, optimizer, signature)
    else:
        if config.get('init_from') is not None:
            progress = branch_from(config, identity, parameters, names, master, optimizer)
        root.mkdir()
        (root / 'contract.json').write_text(json.dumps(identity, indent=2) + '\n')
        (root / 'trainable.json').write_text(json.dumps(
            {name: list(parameter.shape) for name, parameter in named}, indent=2) + '\n')
    if (root / 'validation-final.json').exists():
        print(json.dumps({'status': 'already_finished', 'step': progress['step']}), flush=True)
        return 0
    lock = root / '.active'
    with lock.open('x'):
        pass
    stop = StopRequest(deadline)
    validation_path = check['dataset']['validation']['path']
    stream = ChunkStream(check['dataset']['train']['path'], config['sequence_bytes'], progress['stream'], wrap=True)

    def record(name, report):
        report.update(step=progress['step'], signature=signature)
        temporary = root / (name + '.partial')
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(root / name)
        print(json.dumps({'event': name, **report}), flush=True)

    def save_predecay():
        path = root / f"predecay-{progress['step']:08d}.pt"
        if not path.exists():
            check_storage(root, config, checkpoint_reserve)
            save_state(path, names, master, optimizer, dict(progress), signature)

    try:
        stop.install()
        started = time.monotonic()
        elapsed_before = progress['elapsed_seconds']
        invocation_steps, status = 0, None
        while status is None:
            progress['elapsed_seconds'] = elapsed_before + time.monotonic() - started
            step, decay = progress['step'], progress['decay']
            if decay is not None and step >= decay['start'] + decay['length']:
                status = 'finished'
            elif stop.requested:
                status = 'signal' if stop.signaled else 'deadline'
            elif progress['elapsed_seconds'] >= config['max_seconds']:
                status = 'max_seconds'
            elif stop_after_steps is not None and invocation_steps >= stop_after_steps:
                status = 'pilot'
            elif step % config['eval_every'] == 0 and progress['last_eval_step'] != step:
                begun = time.monotonic()
                try:
                    report = evaluate(model, validation_path, config['sequence_bytes'], config['eval_documents'],
                                      'cuda', stop)
                except InterruptedError:
                    status = 'signal' if stop.signaled else 'deadline'
                    continue
                report['seconds'] = time.monotonic() - begun
                progress['evaluations'].append([step, report['byte_bpb']])
                progress['last_eval_step'] = step
                if decay is None and step >= config['warmup_steps'] and plateaued(progress['evaluations'], config):
                    progress['decay'] = {'start': step, 'length': decay_length(step, config), 'reason': 'plateau'}
                    save_predecay()
                record(f'validation-{step:08d}.json', {**report, 'decay': progress['decay']})
            elif (decay is None and step >= config['warmup_steps'] and
                  step + decay_length(step, config) >= config['max_steps']):
                progress['decay'] = {'start': step, 'length': config['max_steps'] - step, 'reason': 'max_steps'}
                save_predecay()
            else:
                before = dict(stream.state)
                chunks = step_chunks(stream, config['step_bytes'])
                if chunks is None:
                    raise ValueError('Training split produced no chunks')
                byte_count = sum(int((ids[1:] >= 4).sum()) for ids in chunks)
                if progress['exposed_bytes'] + byte_count > config['max_train_bytes']:
                    stream.state = before
                    status = 'max_train_bytes'
                    continue
                check_storage(root, config, checkpoint_reserve)
                lr = learning_rate(step, config, decay)
                for group in optimizer.param_groups:
                    group['lr'] = lr
                torch.cuda.synchronize()
                step_start = time.monotonic()
                nll, norm = train_step(model, parameters, master, optimizer, chunks, config['clip_norm'], 'cuda')
                torch.cuda.synchronize()
                seconds = time.monotonic() - step_start
                progress.update(step=step + 1, stream=dict(stream.state),
                                exposed_bytes=progress['exposed_bytes'] + byte_count,
                                elapsed_seconds=elapsed_before + time.monotonic() - started)
                invocation_steps += 1
                event = {'step': progress['step'], 'lr': lr, 'byte_bpb': nll / byte_count / math.log(2),
                         'gradient_norm': norm, 'step_seconds': seconds, 'chunks': len(chunks),
                         'training_bytes_per_second': byte_count / seconds, 'step_utf8_bytes': byte_count,
                         'exposed_bytes': progress['exposed_bytes'], 'epoch': stream.state['epoch'],
                         'elapsed_seconds': progress['elapsed_seconds'],
                         'peak_allocated_bytes': torch.cuda.max_memory_allocated()}
                with (root / 'metrics.jsonl').open('a') as handle:
                    handle.write(json.dumps(event) + '\n')
                if progress['step'] <= 20 or progress['step'] % 10 == 0:
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
                report = evaluate(model, validation_path, config['sequence_bytes'], config['final_eval_documents'],
                                  'cuda', stop)
            except InterruptedError:
                save_rolling(root, names, master, optimizer, dict(progress), signature, config['keep_checkpoints'])
                print(json.dumps({'status': 'paused_signal', 'validation': 'final incomplete'}), flush=True)
                return 75
            record('validation-final.json', {**report, 'checkpoint': str(final), 'decay': progress['decay']})
            print(json.dumps({'status': 'finished', 'checkpoint': str(final)}), flush=True)
            return 0
        checkpoint = save_rolling(root, names, master, optimizer, dict(progress), signature, config['keep_checkpoints'])
        print(json.dumps({'status': status, 'checkpoint': str(checkpoint), 'step': progress['step']}), flush=True)
        return 75 if status in ('signal', 'deadline') else 0
    finally:
        stream.close()
        stop.restore()
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--resume', help='Trusted local checkpoint only; torch pickle loading required')
    parser.add_argument('--stop-after-steps', type=int)
    parser.add_argument('--deadline-unix', type=float, help='Save and stop at this wall-clock time (job end minus margin)')
    parser.add_argument('--report', help='Fresh preflight report JSON; refuses to overwrite')
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    if args.execute:
        return run(config, args.resume, args.stop_after_steps, args.deadline_unix)
    report = preflight(config)
    print(json.dumps(report, indent=2))
    if args.report:
        with Path(args.report).open('x') as handle:
            handle.write(json.dumps(report, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
