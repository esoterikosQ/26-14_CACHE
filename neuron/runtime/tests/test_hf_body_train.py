import json
from pathlib import Path
import tempfile
import unittest

from blt_hf.body_train import ChunkStream, preflight, step_chunks

try:
    import numpy
    import torch
except ImportError:
    numpy = torch = None


def write_corpus(path, texts, prefix=''):
    path.write_text(''.join(json.dumps({'id': f'{prefix}{index}', 'source': 's', 'text': text}, ensure_ascii=False) + '\n'
                            for index, text in enumerate(texts)), encoding='utf-8')


def drain(stream):
    chunks, states = [], []
    while (ids := stream.next_chunk()) is not None:
        chunks.append(ids.tolist())
        states.append(dict(stream.state))
    stream.close()
    return chunks, states


TEXTS = ['가', 'abcdefghijk', '한국어 문장입니다.', 'xy', '0123456789']


@unittest.skipUnless(numpy is not None, 'NumPy required')
class ChunkContracts(unittest.TestCase):
    def test_every_byte_and_document_eos_is_a_target_once(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'train.jsonl'
            write_corpus(path, TEXTS)
            chunks, states = drain(ChunkStream(path, 5))
        self.assertTrue(all(chunk[0] == 1 and 2 <= len(chunk) <= 7 for chunk in chunks))
        targets = [value for chunk in chunks for value in chunk[1:]]
        expected = [value for text in TEXTS for value in [byte + 4 for byte in text.encode()] + [2]]
        self.assertEqual(targets, expected)
        self.assertEqual(states[-1]['documents'], len(TEXTS))
        self.assertTrue(all(chunk[-1] != 2 for chunk, state in zip(chunks, states) if state['chunk']))

    def test_resume_from_any_state_continues_identically(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'train.jsonl'
            write_corpus(path, TEXTS)
            chunks, states = drain(ChunkStream(path, 4))
            for index, state in enumerate(states):
                rest, _ = drain(ChunkStream(path, 4, state))
                self.assertEqual(rest, chunks[index + 1:])

    def test_document_limit_wrap_and_step_grouping(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'train.jsonl'
            write_corpus(path, TEXTS)
            limited, states = drain(ChunkStream(path, 4, max_documents=2))
            self.assertEqual(states[-1]['documents'], 2)
            self.assertEqual(sum(chunk.count(2) for chunk in limited), 2)
            stream = ChunkStream(path, 4, wrap=True)
            steps = [step_chunks(stream, 12) for _ in range(6)]
            self.assertEqual(stream.state['epoch'], 1)
            for chunks in steps:
                sizes = [int((numpy.asarray(ids[1:]) >= 4).sum()) for ids in chunks]
                self.assertGreaterEqual(sum(sizes), 12)
                self.assertLess(sum(sizes[:-1]), 12)
            stream.close()
            ended = ChunkStream(path, 4, {'epoch': 0, 'offset': path.stat().st_size, 'chunk': 0, 'documents': 5})
            self.assertIsNone(step_chunks(ended, 12))
            ended.close()

    def test_preflight_blocks_unapproved_or_malformed_configs(self):
        report = preflight({'model_path': '/nonexistent', 'patcher': {'checkpoint': 'relative.pt', 'sha256': 'x',
                                                                        'threshold': 0}, 'trainable': 'encoder',
                            'sequence_bytes': 16384, 'attention_backend': 'flex_attention'})
        self.assertFalse(report['training_ready'])
        text = '\n'.join(report['blockers'])
        for expected in ('training_authorized', 'trainable must be "all"', 'dataset_manifest missing',
                         'checkpoint unavailable', 'positive finite patcher threshold', 'absolute path',
                         'sequence_bytes above 8192', 'attention_backend', 'compile must be',
                         'gradient_checkpointing'):
            self.assertIn(expected, text)


def tiny_model(directory):
    from transformers import BltConfig
    from blt_hf.patched.modeling_blt import BltForCausalLM
    local = {'vocab_size': 260, 'cross_attn_k': 2, 'hidden_size_global': 128, 'hidden_size': 64,
             'num_attention_heads': 4, 'max_position_embeddings': 2048, 'intermediate_size': 128}
    config = BltConfig(
        vocab_size=260, max_position_embeddings=1024, patch_in_forward=True, patch_size=4, patching_mode='entropy',
        patching_threshold=1.335442066192627, patching_batch_size=1, max_patch_length=None, cross_attn_k=2,
        encoder_hash_byte_group_size=[3, 4, 5], encoder_hash_byte_group_vocab=101,
        encoder_hash_byte_group_nb_functions=1,
        patcher_config={'vocab_size': 260, 'hidden_size': 32, 'num_hidden_layers': 1, 'num_attention_heads': 2,
                        'max_position_embeddings': 2048, 'intermediate_size': 64},
        encoder_config={**local, 'cross_attn_all_layers': False, 'num_hidden_layers': 1},
        decoder_config={**local, 'cross_attn_all_layers': True, 'num_hidden_layers': 2},
        global_config={'hidden_size': 128, 'num_attention_heads': 4, 'num_hidden_layers': 2,
                       'max_position_embeddings': 1024, 'intermediate_size': 256},
        tie_word_embeddings=False, bos_token_id=1, eos_token_id=2, pad_token_id=3, use_cache=False)
    config.original_spec = {'local_attention_window_len': 512, 'local_attn_bias_type': 'local_block_causal',
                            'global_attn_bias_type': 'block_causal', 'entropy_attn_bias_type': 'local_block_causal',
                            'entropy_sliding_window': 512, 'eos_id': 2, 'patch_size': 4.5,
                            'patching_threshold': 1.335442066192627, 'patching_threshold_add': None,
                            'monotonicity': False, 'max_patch_length': None}
    torch.manual_seed(3)
    BltForCausalLM(config).to(torch.bfloat16).save_pretrained(directory)
    return Path(directory)


def body_config(directory, model_path, manifest, run_dir, **overrides):
    config = {'training_authorized': True, 'model_path': str(model_path), 'dataset_manifest': str(manifest),
              'run_dir': str(run_dir), 'patcher': {'checkpoint': None, 'sha256': None, 'threshold': 1.335442066192627},
              'trainable': 'all', 'attention_backend': 'fast', 'compile': False, 'gradient_checkpointing': False,
              'max_steps': 100, 'max_train_bytes': 10 ** 9, 'max_seconds': 3600, 'max_run_bytes': 10 ** 10,
              'max_gpu_memory_bytes': 8 * 1024 ** 3, 'min_free_disk_bytes': 1, 'sequence_bytes': 64,
              'step_bytes': 200, 'save_every': 2, 'keep_checkpoints': 2, 'threads': 2, 'seed': 1, 'lr': 1e-3,
              'warmup_steps': 1, 'min_lr_ratio': .1, 'weight_decay': .1, 'clip_norm': 1., 'eval_every': 2,
              'eval_documents': 5, 'final_eval_documents': 10, 'plateau_patience': 3, 'plateau_min_delta': .002,
              'decay_fraction': .1, 'min_decay_steps': 5}
    config.update(overrides)
    path = Path(directory) / f'config-{Path(run_dir).name}.json'
    path.write_text(json.dumps(config))
    return config


@unittest.skipUnless(torch is not None and torch.cuda.is_available(), 'Body training checks need CUDA')
class BodyTraining(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.model_path = tiny_model(root / 'model')
        data = root / 'data'
        data.mkdir()
        texts = [('한국어 학습 문장 ' * (index % 9 + 1)) + str(index) for index in range(200)]
        write_corpus(data / 'train.jsonl', texts[:180], 't')
        write_corpus(data / 'validation.jsonl', texts[180:], 'v')
        from blt_hf.entropy_data import file_sha256
        (data / 'manifest.json').write_text(json.dumps({
            'splits': {split: {'path': f'{split}.jsonl', 'sha256': file_sha256(data / f'{split}.jsonl')}
                       for split in ('train', 'validation')},
            'pii_review_approved': True, 'near_duplicate_split_review_approved': True}))
        self.manifest = data / 'manifest.json'
        self.root = root

    def tearDown(self):
        from blt_hf import fast_body
        fast_body.disable()
        self.directory.cleanup()

    def test_fast_path_matches_eager_logits_and_gradients_in_fp32(self):
        from blt_hf import fast_body
        from blt_hf.model import configured_model
        from blt_hf.patched.modeling_blt import BltForCausalLM
        torch.manual_seed(5)
        first = [1] + [byte + 4 for byte in '한국어 문장과 다른 문장 '.encode() * 40] + [2]
        second = [1] + [byte + 4 for byte in 'second document '.encode() * 30]
        results = {}
        for backend in ('eager', 'fast'):
            config = configured_model(self.model_path, attention_mode='osc',
                                      backend='eager' if backend == 'eager' else 'sdpa')
            config.patching_threshold = 2.0
            model = BltForCausalLM.from_pretrained(str(self.model_path), config=config, local_files_only=True,
                                                   dtype=torch.float32, device_map='cuda')
            if backend == 'fast':
                fast_body.enable(model)
            for name, ids in (('one', first), ('two', first + second)):
                tensor = torch.tensor([ids], device='cuda')
                logits = model(input_ids=tensor[:, :-1], use_cache=False).logits
                torch.nn.functional.cross_entropy(logits[0], tensor[0, 1:]).backward()
                results[backend, name] = (logits.detach(), {key: value.grad.clone() for key, value in
                                                            model.named_parameters() if value.grad is not None})
                model.zero_grad(set_to_none=True)
            fast_body.disable()
        for name in ('one', 'two'):
            (eager, eager_grads), (fast, fast_grads) = results['eager', name], results['fast', name]
            torch.testing.assert_close(fast, eager, rtol=1e-4, atol=1e-4)
            self.assertEqual(set(fast_grads), set(eager_grads))
            for key in eager_grads:
                torch.testing.assert_close(fast_grads[key], eager_grads[key], rtol=1e-3, atol=1e-5, msg=key)

    def test_step_updates_body_but_not_patcher_or_unseen_hash_rows(self):
        from blt_hf.body_train import (HASH_EMBEDDING, load_body, make_optimizer, set_training, step_chunks,
                                       train_step, trainable)
        config = body_config(self.root, self.model_path, self.manifest, self.root / 'run')
        model = load_body(self.model_path, config['patcher'], 'fast')
        set_training(model)
        named = trainable(model)
        names = [name for name, _ in named]
        self.assertFalse(any(name.startswith('model.patcher.') for name in names))
        parameters = [parameter for _, parameter in named]
        master = [parameter.detach().float().clone().requires_grad_(True) for parameter in parameters]
        optimizer = make_optimizer(names, master, config)
        self.assertEqual([group['weight_decay'] for group in optimizer.param_groups], [.1, 0.])
        self.assertEqual(len(optimizer.param_groups[1]['params']), 1)
        patcher = {name: parameter.detach().clone() for name, parameter in model.named_parameters()
                   if name.startswith('model.patcher.')}
        initial = [weight.detach().clone() for weight in master]
        stream = ChunkStream(self.root / 'data/train.jsonl', 64)
        nll, norm = train_step(model, parameters, master, optimizer, step_chunks(stream, 200), 1., 'cuda')
        stream.close()
        self.assertTrue(numpy.isfinite(nll) and numpy.isfinite(norm) and norm > 0)
        hash_index = names.index(HASH_EMBEDDING)
        touched = master[hash_index].grad.abs().sum(-1) > 0
        self.assertTrue(touched.any() and not touched.all())
        for index, (name, weight) in enumerate(zip(names, master)):
            if index == hash_index:
                self.assertTrue(torch.equal(weight[~touched], initial[index][~touched]))
                self.assertFalse(torch.equal(weight[touched], initial[index][touched]))
            else:
                self.assertFalse(torch.equal(weight, initial[index]), name)
            self.assertTrue(torch.equal(parameters[index], weight.detach().to(torch.bfloat16)), name)
        after = dict(model.named_parameters())
        for name, value in patcher.items():
            self.assertTrue(torch.equal(after[name], value), name)

    def test_pilot_resume_matches_uninterrupted_run(self):
        from blt_hf.body_train import run
        straight = self.root / 'straight'
        config = body_config(self.root, self.model_path, self.manifest, straight)
        self.assertEqual(run(config, stop_after_steps=4), 0)
        split = self.root / 'split'
        config = body_config(self.root, self.model_path, self.manifest, split)
        self.assertEqual(run(config, stop_after_steps=2), 0)
        self.assertEqual(run(config, resume=split / 'step-00000002.pt', stop_after_steps=2), 0)
        load = lambda root: [json.loads(line) for line in (root / 'metrics.jsonl').read_text().splitlines()]
        whole, parts = load(straight), load(split)
        self.assertEqual([event['step'] for event in parts], [1, 2, 3, 4])
        for left, right in zip(whole, parts):
            self.assertEqual(left['exposed_bytes'], right['exposed_bytes'])
            self.assertAlmostEqual(left['byte_bpb'], right['byte_bpb'], delta=.02)
        for root in (straight, split):
            self.assertTrue((root / 'validation-00000000.json').is_file())
            self.assertTrue((root / 'validation-00000004.json').is_file() or (root / 'validation-00000002.json').is_file())
            self.assertFalse((root / '.active').exists())
        trained = json.loads((straight / 'trainable.json').read_text())
        self.assertFalse(any(name.startswith('model.patcher.') for name in trained))


if __name__ == '__main__':
    unittest.main()
