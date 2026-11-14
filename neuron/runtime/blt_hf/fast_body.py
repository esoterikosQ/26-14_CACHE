"""Opt-in fast path for training the BLT body; the same masks and sums, computed with less work.

- Local window/EOS, global block-causal and patch cross-attention masks become flex BlockMasks with the
  same visibility, so fully masked blocks are skipped instead of computed and discarded.
- The six hash n-gram lookups become one embedding call, so backward builds one dense gradient of the
  3B-row table instead of six that are then added.
- Optional in-place compile of every transformer and cross-attention layer.
"""
NAME = 'blt_flex'
PRIMES = [1000000007, 5915587277, 1500450271, 3267000013, 5754853343, 4093082899, 9576890767, 3628273133,
          2860486313, 5463458053, 3367900313]


def attention(module, query, key, value, attention_mask, **kwargs):
    from torch.nn.attention.flex_attention import BlockMask
    from transformers.integrations.flex_attention import flex_attention_forward
    from transformers.integrations.sdpa_attention import sdpa_attention_forward
    if isinstance(attention_mask, BlockMask):
        return flex_attention_forward(module, query, key, value, attention_mask, **kwargs)
    return sdpa_attention_forward(module, query, key, value, attention_mask, **kwargs)


def block_mask(mask_mod, batch, queries, keys, device):
    from torch.nn.attention.flex_attention import create_block_mask
    return create_block_mask(mask_mod, batch, None, queries, keys, device=device, _compile=True)


def local_mask(tokens, dtype, *, window=None, eos_id=2):
    from .attention import segment_ids
    if window is None:
        raise ValueError('Local block mask needs a window')
    segments = segment_ids(tokens, eos_id)

    def visible(batch, head, query, key):
        return (key <= query) & (query - key < window) & (segments[batch, query] == segments[batch, key])

    return block_mask(visible, tokens.shape[0], tokens.shape[1], tokens.shape[1], tokens.device)


def global_mask(tokens, patch_ids, num_patches, dtype, *, eos_id=2):
    """attention.global_block_mask: a patch holding EOS closes its segment."""
    from .attention import segment_ids
    patch_tokens = tokens.new_zeros((tokens.shape[0], num_patches))
    rows, cols = (tokens == eos_id).nonzero(as_tuple=True)
    patch_tokens[rows, patch_ids[rows, cols]] = eos_id
    segments = segment_ids(patch_tokens, eos_id)

    def visible(batch, head, query, key):
        return (key <= query) & (segments[batch, query] == segments[batch, key])

    return block_mask(visible, tokens.shape[0], num_patches, num_patches, tokens.device)


def cross_mask(patch_ids, num_patches, sequence_length, patches_as_queries=False, cross_attn_k=1, dtype=None):
    """_prepare_patch_cross_attention_mask: each of the k slots of a patch sees exactly that patch's bytes."""
    batch = patch_ids.shape[0]
    if patches_as_queries:
        def visible(index, head, query, key):
            return patch_ids[index, key] == query // cross_attn_k
        return block_mask(visible, batch, num_patches * cross_attn_k, sequence_length, patch_ids.device)

    def visible(index, head, query, key):
        return patch_ids[index, query] == key // cross_attn_k
    return block_mask(visible, batch, sequence_length, num_patches * cross_attn_k, patch_ids.device)


def hash_embeddings(tokens, local_encoder, table, functions, group_sizes, vocab):
    """compute_hash_embeddings with one lookup over all hash groups."""
    import torch
    from .patched.modeling_blt import byte_group_hash_function
    ids, index = [], 0
    for function in range(functions):
        prime = PRIMES[function % len(PRIMES)]
        for size in group_sizes:
            ids.append(byte_group_hash_function(tokens, size, prime, vocab) + index * vocab)
            index += 1
    return local_encoder.embed_tokens(tokens) + table(torch.stack(ids)).sum(0)


REPLACEMENTS = {'block_causal_mask': local_mask, 'global_block_mask': global_mask,
                '_prepare_patch_cross_attention_mask': cross_mask, 'compute_hash_embeddings': hash_embeddings}
ORIGINALS = {}


def enable(model):
    """Call after loading; replaces the modeling functions process-wide until disable()."""
    from transformers import AttentionInterface
    from transformers.masking_utils import AttentionMaskInterface, sdpa_mask
    from .patched import modeling_blt
    AttentionInterface.register(NAME, attention)
    AttentionMaskInterface.register(NAME, sdpa_mask)
    for name, replacement in REPLACEMENTS.items():
        ORIGINALS.setdefault(name, getattr(modeling_blt, name))
        setattr(modeling_blt, name, replacement)
    body = model.model
    for module in (body.local_encoder, body.local_decoder, body.global_transformer, body.patcher):
        module.config._attn_implementation = NAME


def disable():
    from .patched import modeling_blt
    for name, original in ORIGINALS.items():
        setattr(modeling_blt, name, original)


def compile_layers(model):
    """In-place compile keeps parameter names, so checkpoints match the uncompiled model."""
    import torch
    # One layer class serves hidden sizes 768/1024/2048 at many lengths.
    torch._dynamo.config.recompile_limit = 64
    torch._dynamo.config.accumulated_recompile_limit = 1024
    body = model.model
    for module in (*body.local_encoder.layers, *body.local_encoder.cross_attn_layers,
                   *body.global_transformer.layers, *body.local_decoder.layers,
                   *body.local_decoder.cross_attn_layers, *body.patcher.layers):
        module.compile()
