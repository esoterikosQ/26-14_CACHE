"""PATCHER arm: the frozen public BLT body with swapped entropy patchers and thresholds on Korean text.

Each patcher gets thresholds for the same mean bytes/patch targets from a random sample of the train
region that no compared checkpoint has read. Body BPB uses the first validation documents (the patcher
CPT evaluation sample) in nonoverlapping chunks with BOS per chunk; batch 1, eager, BF16, no cache.
"""
import argparse
import copy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import re
import time

from .entropy_data import MAX_RECORD_BYTES, documents, file_sha256, inspect_dataset_cached
from .patching import entropy_patch_lengths


BOS = 1
LN2 = math.log(2)
CONTRACT_KEYS = ('manifest_sha256', 'weights_sha256', 'model_config_sha256')


def chunk_ids(text, chunk_bytes):
    data = text.encode('utf-8', errors='strict')
    return [[BOS] + [value + 4 for value in data[offset:offset + chunk_bytes]]
            for offset in range(0, len(data), chunk_bytes)]


def sample_documents(path, start, target_bytes, seed, max_attempts=1_000_000):
    """Whole lines that follow uniform random byte offsets in [start, size); returns sorted (offset, text)."""
    path = Path(path)
    size = path.stat().st_size
    if not 0 <= start < size:
        raise ValueError('Calibration region is empty')
    generator = random.Random(seed)
    picked, total = {}, 0
    with path.open('rb') as handle:
        for _ in range(max_attempts):
            if total >= target_bytes:
                break
            handle.seek(generator.randrange(start, size))
            # The line holding the offset may have started before the region, so it is never used.
            if len(handle.readline(MAX_RECORD_BYTES + 1)) > MAX_RECORD_BYTES:
                continue
            offset = handle.tell()
            raw = handle.readline(MAX_RECORD_BYTES + 1)
            if not raw.endswith(b'\n') or offset in picked:
                continue
            text = json.loads(raw.decode('utf-8'))['text']
            picked[offset] = text
            total += len(text.encode('utf-8'))
        else:
            raise ValueError('Calibration sample did not reach its byte target')
    return [(offset, picked[offset]) for offset in sorted(picked)]


def bf16_values():
    """Float value of every BF16 bit pattern (BF16 is the upper half of float32)."""
    import numpy as np
    return (np.arange(65536, dtype=np.uint32) << 16).view(np.float32)


def entropy_histogram(entropies):
    """Counts of BF16 entropy bit patterns at the threshold-compared positions 1..L-1."""
    import torch
    if entropies.dtype != torch.bfloat16 or entropies.ndim != 2 or entropies.shape[0] != 1:
        raise ValueError('Expected [1, L] BF16 entropies')
    values = entropies[0, 1:]
    if not torch.isfinite(values).all():
        raise ValueError('Nonfinite entropies')
    patterns = values.contiguous().view(torch.int16).to(torch.int32) & 0xFFFF
    return torch.bincount(patterns, minlength=65536)


def threshold_curve(counts, chunks, scored_bytes):
    """Distinct entropy values v and the mean bytes/patch when v is the threshold (boundary iff e > v).

    Each chunk has patches 0 and 1 plus one per boundary, and no max_patch_length splitting.
    """
    import numpy as np
    counts = np.asarray(counts, dtype=np.int64)
    present = counts > 0
    values, inverse = np.unique(bf16_values()[present], return_inverse=True)
    merged = np.zeros(len(values), dtype=np.int64)
    np.add.at(merged, inverse, counts[present])
    above = merged.sum() - np.cumsum(merged)
    return values, scored_bytes / (2 * chunks + above)


def select_threshold(counts, chunks, scored_bytes, target):
    import numpy as np
    values, means = threshold_curve(counts, chunks, scored_bytes)
    index = int(np.argmin(np.abs(means - target)))
    return float(values[index]), float(means[index])


def boundaries(lengths):
    """Patch starts at positions 2..L (the virtual next position included), as sorted numpy values."""
    import torch
    lengths = lengths[0]
    starts = torch.cumsum(lengths, 0) - lengths
    return starts[starts >= 2].cpu().numpy()


def length_quantiles(histogram, quantiles=(.5, .9, .99)):
    import numpy as np
    cumulative = np.cumsum(histogram)
    total = cumulative[-1]
    result = {f'p{round(q * 100)}': int(np.searchsorted(cumulative, q * total)) for q in quantiles}
    result['max'] = int(np.flatnonzero(histogram)[-1])
    return result


def paired_bootstrap(nll, utf8_bytes, pairs, replicates, seed):
    """Document-resampled BPB difference (a - b) for each config index pair; 95% percentile interval."""
    import numpy as np
    nll = np.asarray(nll, dtype=np.float64)
    utf8 = np.asarray(utf8_bytes, dtype=np.float64)
    generator = np.random.default_rng(seed)
    count = len(utf8)
    weights = np.stack([np.bincount(generator.integers(0, count, count), minlength=count)
                        for _ in range(replicates)]).astype(np.float64)
    sums = weights @ nll
    denominators = (weights @ utf8) * LN2
    results = []
    for a, b in pairs:
        samples = (sums[:, a] - sums[:, b]) / denominators
        low, high = np.quantile(samples, [.025, .975])
        results.append({'delta_bpb': float((nll[:, a].sum() - nll[:, b].sum()) / (utf8.sum() * LN2)),
                        'ci95': [float(low), float(high)]})
    return results


def checkpoint_patcher(base, path):
    """A copy of the public patcher holding a CPT checkpoint's FP32 master weights cast to BF16."""
    import torch
    path = Path(path)
    digest = file_sha256(path)
    if path.with_suffix('.sha256').read_text().strip() != digest:
        raise ValueError(f'Checkpoint hash mismatch: {path}')
    state = torch.load(path, map_location='cpu', weights_only=True)
    names = [name for name, _ in base.named_parameters()]
    if list(state['master']) != names:
        raise ValueError(f'Checkpoint parameter names differ: {path}')
    patcher = copy.deepcopy(base)
    patcher.load_state_dict({name: state['master'][name].to(torch.bfloat16) for name in names}, strict=True)
    return patcher.eval(), digest, state['progress']


def parse_patchers(values):
    patchers = {}
    for value in values:
        name, _, path = value.partition('=')
        if not re.fullmatch(r'[a-z0-9_-]+', name) or name == 'public' or name in patchers or not path:
            raise ValueError(f'Expected unique NAME=PATH (name not "public"): {value}')
        patchers[name] = Path(path)
    return patchers


def run(args):
    import numpy as np
    import torch
    import transformers
    from .model import configured_model
    from .patched.modeling_blt import BltForCausalLM

    output = Path(args.output)
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    checkpoints = parse_patchers(args.patcher)
    targets = [float(value) for value in args.targets.split(',')]
    if not targets or len(set(targets)) != len(targets) or min(targets) <= 1:
        raise ValueError('Distinct mean bytes/patch targets above 1 required')

    contracts = {name: json.loads((path.parent / 'contract.json').read_text()) for name, path in checkpoints.items()}
    first = next(iter(contracts.values()))
    for name, contract in contracts.items():
        if any(contract[key] != first[key] for key in CONTRACT_KEYS) or \
                contract['config']['model_path'] != first['config']['model_path'] or \
                contract['config']['dataset_manifest'] != first['config']['dataset_manifest']:
            raise ValueError(f'Run contract differs: {name}')
    manifest_path = Path(first['config']['dataset_manifest'])
    model_path = Path(first['config']['model_path'])
    if file_sha256(manifest_path) != first['manifest_sha256']:
        raise ValueError('Dataset manifest changed since training')
    if (file_sha256(model_path / 'model.safetensors') != first['weights_sha256'] or
            file_sha256(model_path / 'config.json') != first['model_config_sha256']):
        raise ValueError('Public model changed since training')
    _, splits = inspect_dataset_cached(manifest_path)
    train_path, validation_path = Path(splits['train']['path']), Path(splits['validation']['path'])

    torch.cuda.set_device(0)
    torch.backends.cuda.matmul.allow_tf32 = False
    config = configured_model(model_path, attention_mode='osc', backend='eager')
    model, info = BltForCausalLM.from_pretrained(str(model_path), config=config, local_files_only=True,
                                                 dtype=torch.bfloat16, device_map='cuda',
                                                 attn_implementation='eager', output_loading_info=True)
    if any(info.get(key) for key in ('missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs')):
        raise ValueError('Checkpoint does not strictly match model')
    model.eval()
    if model.config.max_patch_length is not None or model.model.patcher is None:
        raise ValueError('Expected the in-forward entropy patcher without max_patch_length')
    native = model.config.patching_threshold

    patchers = {'public': model.model.patcher}
    inputs = {'public': {'path': str(model_path / 'model.safetensors'), 'sha256': first['weights_sha256']}}
    unseen = 0
    for name, path in checkpoints.items():
        patcher, digest, progress = checkpoint_patcher(model.model.patcher, path)
        stream = progress['stream']
        if not stream or stream['epoch'] != 0:
            raise ValueError(f'Calibration needs first-epoch checkpoints: {name}')
        unseen = max(unseen, stream['offset'])
        patchers[name] = patcher
        inputs[name] = {'path': str(path), 'sha256': digest, 'step': progress['step'],
                        'exposed_bytes': progress['exposed_bytes'], 'stream': stream}
    code = Path(__file__).resolve().parent
    report = {
        'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'PATCHER arm: frozen public body, swapped patcher and threshold; Korean only',
        'inputs': {'manifest': str(manifest_path), 'manifest_sha256': first['manifest_sha256'],
                   'model_path': str(model_path), 'model_config_sha256': first['model_config_sha256'],
                   'patchers': inputs},
        'code_sha256': {name: file_sha256(code / name) for name in (
            'patcher_compare.py', 'patching.py', 'model.py', 'attention.py', 'patched/modeling_blt.py')},
        'runtime': {'torch': torch.__version__, 'transformers': transformers.__version__,
                    'gpu': torch.cuda.get_device_name(0), 'dtype': 'bfloat16', 'attention': 'osc',
                    'backend': 'eager', 'batch': 1, 'cache': False},
        'protocol': {
            'chunks': f'Nonoverlapping {args.chunk_bytes}-byte chunks, BOS per chunk, no EOS target; every byte scored',
            'bytes_per_patch': 'UTF-8 bytes / patches; patches = 2 + count(entropy[1:] > threshold) per chunk',
            'thresholds': 'BF16 entropy value nearest each target on the calibration sample; public@native keeps '
                          'the model config threshold',
            'calibration': 'Next whole train line after uniform random offsets beyond every compared stream offset',
            'evaluation': f'First {args.documents} validation documents; paired document bootstrap '
                          f'{args.replicates}x, seed {args.seed}'}}

    def save():
        temporary = output.with_suffix('.partial')
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(output)

    calibration = sample_documents(train_path, unseen, args.calibration_bytes, args.seed)
    counts = {name: torch.zeros(65536, dtype=torch.int64, device='cuda') for name in patchers}
    native_boundaries = dict.fromkeys(patchers, 0)
    chunks = scored = 0
    with torch.inference_mode():
        for _, text in calibration:
            for ids in chunk_ids(text, args.chunk_bytes):
                tensor = torch.tensor([ids], device='cuda')
                chunks += 1
                scored += len(ids) - 1
                for name, patcher in patchers.items():
                    entropies = patcher(input_ids=tensor, use_cache=False)[0]
                    counts[name] += entropy_histogram(entropies)
                    native_boundaries[name] += int((entropies[:, 1:] > native).sum())
    configs = [{'name': 'public@native', 'patcher': 'public', 'target': None, 'threshold': native}]
    summary = {}
    for name in patchers:
        histogram = counts[name].cpu().numpy()
        summary[name] = {'native_bytes_per_patch': scored / (2 * chunks + native_boundaries[name]), 'targets': {}}
        for target in targets:
            threshold, mean = select_threshold(histogram, chunks, scored, target)
            summary[name]['targets'][f'{target:g}'] = {'threshold': threshold, 'bytes_per_patch': mean}
    for target in targets:
        for name in patchers:
            configs.append({'name': f'{name}@{target:g}', 'patcher': name, 'target': target,
                            'threshold': summary[name]['targets'][f'{target:g}']['threshold']})
    report['calibration'] = {'train_path': str(train_path), 'region_start': unseen,
                             'train_file_bytes': train_path.stat().st_size, 'documents': len(calibration),
                             'chunks': chunks, 'utf8_bytes': scored, 'native_threshold': native,
                             'seconds': time.monotonic() - started, 'patchers': summary}
    report['configs'] = configs
    save()
    print(json.dumps({'event': 'calibration', **report['calibration']}), flush=True)

    histogram_size = args.chunk_bytes + 3
    histograms = [np.zeros(histogram_size, dtype=np.int64) for _ in configs]
    patch_counts = [0] * len(configs)
    most_patches = [0] * len(configs)
    body_seconds = [0.] * len(configs)
    patcher_nll = dict.fromkeys(patchers, 0.)
    pairs = [(a, b) for a in range(1, len(configs)) for b in range(1, a)
             if configs[a]['target'] == configs[b]['target']]
    agreement = {pair: [0, 0, 0] for pair in pairs}
    sources, nll, utf8_bytes, records = {}, [], [], []
    controls = 0
    evaluation_started = time.monotonic()
    with torch.inference_mode():
        for index, record in enumerate(documents(validation_path)):
            if index == args.documents:
                break
            row = [0.] * len(configs)
            for ids in chunk_ids(record['text'], args.chunk_bytes):
                tensor = torch.tensor([ids], device='cuda')
                expected = tensor[0, 1:]
                entropies = {}
                for name, patcher in patchers.items():
                    entropies[name], _, logits = patcher(input_ids=tensor, use_cache=False)
                    patcher_nll[name] += float(torch.nn.functional.cross_entropy(
                        logits[0, :-1].float(), expected, reduction='sum'))
                starts = {}
                for position, setting in enumerate(configs):
                    lengths = entropy_patch_lengths(entropies[setting['patcher']], setting['threshold'])
                    torch.cuda.synchronize()
                    begun = time.monotonic()
                    logits = model(input_ids=tensor, patch_lengths=lengths, use_cache=False).logits
                    loss = float(torch.nn.functional.cross_entropy(logits[0, :-1].float(), expected, reduction='sum'))
                    body_seconds[position] += time.monotonic() - begun
                    if not math.isfinite(loss):
                        raise ValueError(f'Nonfinite loss: {setting["name"]}')
                    if position == 0 and controls < args.controls:
                        if not torch.equal(model(input_ids=tensor, use_cache=False).logits, logits):
                            raise ValueError('External native patching differs from the in-model patcher path')
                        controls += 1
                    row[position] += loss
                    values = lengths[0].cpu().numpy()
                    histograms[position] += np.bincount(values, minlength=histogram_size)
                    patch_counts[position] += len(values)
                    most_patches[position] = max(most_patches[position], len(values))
                    if position:
                        starts[position] = boundaries(lengths)
                for (a, b), totals in agreement.items():
                    totals[0] += np.intersect1d(starts[a], starts[b], assume_unique=True).size
                    totals[1] += starts[a].size
                    totals[2] += starts[b].size
            size = len(record['text'].encode('utf-8'))
            nll.append(row)
            utf8_bytes.append(size)
            records.append({'id': record['id'], 'source': record['source'], 'utf8_bytes': size, 'nll_nats': row})
            totals = sources.setdefault(record['source'], [0, [0.] * len(configs)])
            totals[0] += size
            totals[1] = [left + right for left, right in zip(totals[1], row)]
            if (index + 1) % 100 == 0:
                total = sum(utf8_bytes) * LN2
                print(json.dumps({'event': 'progress', 'documents': index + 1,
                                  'seconds': round(time.monotonic() - evaluation_started, 1),
                                  'bpb': {setting['name']: round(sum(values[i] for values in nll) / total, 4)
                                          for i, setting in enumerate(configs)}}), flush=True)
    if controls < 1:
        raise ValueError('No in-model control chunk was evaluated')

    nll_array = np.asarray(nll)
    total = float(sum(utf8_bytes))
    results = []
    for position, setting in enumerate(configs):
        results.append({**setting, 'bpb': float(nll_array[:, position].sum() / (total * LN2)),
                        'bpb_by_source': {source: values[1][position] / (values[0] * LN2)
                                          for source, values in sorted(sources.items())},
                        'bytes_per_patch': total / patch_counts[position], 'patches': patch_counts[position],
                        'patch_length': length_quantiles(histograms[position]),
                        'max_patches_per_chunk': most_patches[position],
                        'body_seconds': body_seconds[position]})
    comparisons = [(position, 0) for position in range(1, len(configs))] + pairs
    for (a, b), result in zip(comparisons, paired_bootstrap(nll_array, utf8_bytes, comparisons,
                                                             args.replicates, args.seed)):
        result.update(a=configs[a]['name'], b=configs[b]['name'])
        report.setdefault('comparisons', []).append(result)
    report.update(
        status='completed', finished_at_utc=datetime.now(timezone.utc).isoformat(),
        evaluation={'validation_path': str(validation_path), 'documents': len(utf8_bytes), 'utf8_bytes': int(total),
                    'documents_by_source': {source: values[0] for source, values in sorted(sources.items())},
                    'in_model_controls_passed': controls, 'seconds': time.monotonic() - evaluation_started},
        results=results,
        patcher_bpb={name: value / (total * LN2) for name, value in patcher_nll.items()},
        boundary_agreement=[{'a': configs[a]['name'], 'b': configs[b]['name'], 'shared': shared,
                             'a_boundaries': left, 'b_boundaries': right, 'f1': 2 * shared / (left + right)}
                            for (a, b), (shared, left, right) in agreement.items()])
    report['documents'] = records
    save()
    print(json.dumps({key: value for key, value in report.items() if key != 'documents'}), flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--patcher', action='append', required=True, help='NAME=PATH of a final CPT checkpoint')
    parser.add_argument('--targets', default='4,4.5,6,8', help='Mean UTF-8 bytes/patch targets')
    parser.add_argument('--chunk-bytes', type=int, default=2047)
    parser.add_argument('--calibration-bytes', type=int, default=20_000_000)
    parser.add_argument('--documents', type=int, default=5000)
    parser.add_argument('--controls', type=int, default=3, help='Chunks checked against the in-model patcher path')
    parser.add_argument('--replicates', type=int, default=2000)
    parser.add_argument('--seed', type=int, default=20261114)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if min(args.chunk_bytes, args.calibration_bytes, args.documents, args.replicates) < 1 or args.controls < 1:
        parser.error('Positive sizes required')
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
