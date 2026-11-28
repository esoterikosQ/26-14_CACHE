"""Export the trained BODY_FULL weights of a trusted local checkpoint as BF16 safetensors with a hash manifest.

The export holds every trainable body tensor (all parameters outside the frozen patcher) as the FP32 master
weight cast to BF16, which is exactly the BF16 copy the model held after that optimizer step. Optimizer and RNG
state are dropped. The patcher is not exported: loading rebuilds the public model, swaps in the run's patcher
checkpoint (verified by its SHA-256) and threshold from the run contract, then overwrites the body tensors.
"""
import argparse
import hashlib
import json
from pathlib import Path

from .entropy_data import file_sha256


SCHEMA_VERSION = 1
BODY_FILE = 'body.safetensors'


def run_contract(run_dir):
    contract = json.loads((Path(run_dir) / 'contract.json').read_text())
    return contract, hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()


def export(run_dir, checkpoint, output):
    import torch
    from safetensors.torch import save_file

    run_dir, checkpoint, output = Path(run_dir).resolve(), Path(checkpoint).resolve(), Path(output)
    if output.exists():
        raise FileExistsError(output)
    if checkpoint.parent != run_dir:
        raise ValueError('Checkpoint must belong to the given run directory')
    digest = file_sha256(checkpoint)
    if checkpoint.with_suffix('.sha256').read_text().strip() != digest:
        raise ValueError('Checkpoint file hash mismatch')
    contract, signature = run_contract(run_dir)
    shapes = json.loads((run_dir / 'trainable.json').read_text())
    state = torch.load(checkpoint, map_location='cpu', mmap=True, weights_only=True)
    if state['signature'] != signature:
        raise ValueError('Checkpoint belongs to a different run contract')
    names = list(state['master'])
    if names != list(shapes) or hashlib.sha256('\n'.join(names).encode()).hexdigest() != contract['trainable_sha256']:
        raise ValueError('Checkpoint parameter names differ from the run')
    tensors = {}
    for name in names:
        weight = state['master'][name]
        if weight.dtype != torch.float32 or list(weight.shape) != shapes[name] or not torch.isfinite(weight).all():
            raise ValueError(f'Unexpected master tensor: {name}')
        tensors[name] = weight.to(torch.bfloat16).contiguous()
    output.mkdir(parents=True)
    body = output / BODY_FILE
    save_file(tensors, str(body))
    final = run_dir / 'validation-final.json'
    validation = json.loads(final.read_text()) if final.is_file() else None
    if validation is not None and Path(validation['checkpoint']).resolve() != checkpoint:
        validation = None
    report = {
        'schema_version': SCHEMA_VERSION, 'status': 'exported',
        'source_checkpoint': str(checkpoint), 'source_checkpoint_sha256': digest,
        'run_dir': str(run_dir), 'contract_sha256': file_sha256(run_dir / 'contract.json'),
        'signature': signature, 'contract': contract, 'progress': state['progress'],
        'validation_final': validation, 'shapes': shapes,
        'parameters': sum(value.numel() for value in tensors.values()), 'dtype': 'bfloat16',
        'conversion': 'FP32 master cast to BF16 (round to nearest even), the copy the model held after this step',
        'excluded': 'Optimizer and RNG state; the frozen patcher comes from contract.config.patcher',
        'body_file': BODY_FILE, 'body_sha256': file_sha256(body), 'body_bytes': body.stat().st_size,
    }
    with (output / 'export.json').open('x') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    return report


def load_exported_body(model_path, export_dir, patcher_checkpoint=None, backend='eager'):
    """Public base model plus the run's patcher and threshold, with every body tensor taken from the export."""
    import torch
    from safetensors.torch import load_file
    from .body_train import load_body

    model_path, export_dir = Path(model_path), Path(export_dir)
    manifest = json.loads((export_dir / 'export.json').read_text())
    if manifest.get('schema_version') != SCHEMA_VERSION or manifest.get('status') != 'exported':
        raise ValueError('Unexpected export manifest')
    contract = manifest['contract']
    if (file_sha256(model_path / 'model.safetensors') != contract['weights_sha256'] or
            file_sha256(model_path / 'config.json') != contract['model_config_sha256']):
        raise ValueError('Public base model differs from the trained run')
    body = export_dir / manifest['body_file']
    if file_sha256(body) != manifest['body_sha256']:
        raise ValueError('Exported body hash mismatch')
    patcher = dict(contract['config']['patcher'])
    if patcher['checkpoint'] is not None:
        if patcher_checkpoint is None:
            raise ValueError('The run used a trained patcher; pass its local checkpoint')
        patcher['checkpoint'] = str(patcher_checkpoint)
    model = load_body(model_path, patcher, backend)
    tensors = load_file(str(body), device='cpu')
    named = [(name, parameter) for name, parameter in model.named_parameters() if not name.startswith('model.patcher.')]
    if [name for name, _ in named] != list(manifest['shapes']) or set(tensors) != set(manifest['shapes']):
        raise ValueError('Exported names differ from the model body')
    with torch.no_grad():
        for name, parameter in named:
            value = tensors[name]
            if value.dtype != torch.bfloat16 or parameter.dtype != torch.bfloat16 or value.shape != parameter.shape:
                raise ValueError(f'Exported tensor mismatch: {name}')
            parameter.copy_(value)
    model.requires_grad_(False)
    return model.eval(), manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True, type=Path)
    parser.add_argument('--checkpoint', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    report = export(args.run_dir, args.checkpoint, args.output)
    summary = {key: report[key] for key in ('status', 'source_checkpoint_sha256', 'parameters', 'body_sha256',
                                            'body_bytes')}
    print(json.dumps({**summary, 'step': report['progress']['step'],
                      'validation_final_bpb': (report['validation_final'] or {}).get('byte_bpb')}), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
