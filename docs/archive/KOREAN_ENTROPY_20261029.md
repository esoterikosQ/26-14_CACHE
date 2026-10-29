# Korean Entropy CPT Preparation

Archived history only. The paths below were mistakenly placed in the reference
project and are not current execution instructions. Use ../../command.md and
../../neuron/command.md. The original guide body is preserved below.

2026-10-29: preparation only. No corpus CPT or pretrained optimizer update
has been performed. Sejong is optional, not a prerequisite. Primary sources
are the user's requested NIKL corpora and pinned FineWeb2 Korean train data.
The user downloads and transfers NIKL material. Do not fetch it automatically.

## Installed Paths on Itcerdo

All paths below are relative to `/home/itcmaster/projects/phdq3`.

| Path | Purpose |
| --- | --- |
| `data/korean_cpt/incoming/nikl` | Original NIKL downloads, unchanged |
| `data/korean_cpt/incoming/fineweb2` | Separately approved FineWeb2 material |
| `data/korean_cpt/licenses` | Description files and signed use conditions |
| `data/korean_cpt/manifests` | Source identities and explicit split plans |
| `data/korean_cpt/prepared` | New versioned document JSONL datasets |
| `outputs/korean_entropy` | New run directories; never reuse an old run ID |
| `artifacts/korean_entropy` | Preparation diagnostics; no raw text in reports |

Use the existing `/home/itcmaster/miniconda3/envs/phdq_blt_hf/bin/python`.
No package installation or change to the GEC training environment was needed.

## After Data Arrival

1. Inventory originals and SHA256 hashes, read the actual descriptions and
   license/use period, inspect schemas, and review Korean PII/quality filters.
   Keep compressed originals intact. Extract only reviewed archive paths into
   a separate directory; the converter does not unpack archives.
2. Select whole documents and near-duplicate clusters for train/validation
   before chunking. Do not feed final test, body validation/test, or official
   FineWeb2 test into this pipeline. Review overlap with English replay and
   future body/count roles. No automatic 75/15/10 mix or 1GB/5GB budget.
3. Write an explicit source plan. The converter supports only the schemas
   below; a different real schema requires review, not recursive text scraping.

```json
{
  "files": [
    {"path": "../extracted/train-book.json", "source": "nikl-written-2025", "split": "train", "format": "nikl_paragraph"},
    {"path": "../extracted/heldout-dialogue.json", "source": "nikl-dialogue-2025", "split": "validation", "format": "nikl_utterance"}
  ]
}
```

NIKL input must have a `document` list with `id` and either `paragraph` or
`utterance` lists containing `form` strings. Forms are joined with LF, without
speaker/annotation metadata or Unicode normalization. This join is explicit
preprocessing, not byte-identical serialization of the original JSON file.
`jsonl` input instead requires `id`, `source`, `text` per document. FineWeb2
Parquet ingestion and its filtering/sampling remain a separate pending step;
this converter deliberately does not download or read the reserved test.

```bash
cd /home/itcmaster/projects/phdq3
PY=/home/itcmaster/miniconda3/envs/phdq_blt_hf/bin/python
$PY -m blt_hf.entropy_data --plan data/korean_cpt/manifests/source-plan.json --output data/korean_cpt/prepared/v001
$PY -m blt_hf.entropy_train --config plan/korean_entropy_preparation.json --check-model
```

Conversion refuses existing outputs, duplicate IDs/text, unsupported roles,
JSON records over 16MiB, and NIKL JSON files over 512MiB. Failures preserve
partial artifacts for inspection. Exact duplicate checks do not replace
near-duplicate review. All three dataset review approvals start false.
Dataset inspection retains document IDs/text hashes in RAM; measure memory
before using this preparation reader for a large web corpus.

## Training Gate and Semantics

`plan/korean_entropy_preparation.json` remains unauthorized with null training
budgets. Chunk size, accumulation and optimizer values are pilot proposals,
not an approved learning recipe. Copy to a new run-specific configuration,
set the dataset manifest, approve license/PII/near-duplicate reviews, decide
GPU/bytes/steps/time/storage budgets and validation size, then run preflight.
`--execute` additionally requires explicit training authorization. Neuron
access, transfers and job submission remain user-only.

The loader uses the existing converted checkpoint and strictly loads only
`model.patcher.*`: 99,512,064 BF16 parameters. Runtime identities bind source,
config, dataset and checkpoint hashes. No body model or cache training occurs.
Training uses one document chunk at a time, no padding/packing/cache, BOS at
each chunk reset and EOS only at the actual document end. UTF-8 bytes map to
IDs byte+4, BOS=1/EOS=2. Initial payloads are at most 512 bytes. CE is shifted
exactly once and normalized over accumulated targets including EOS; byte BPB
excludes EOS. Patching still uses predictive-distribution entropy, not observed
byte surprisal. Chunk resets must be matched by later online/offline checks.

Checkpoints include model, AdamW state, Python/Torch/CUDA RNG, epoch/cursor,
step, cumulative byte exposure and a SHA256 sidecar. LR is reconstructed from
the bound step/schedule. Resume accepts only trusted local pickle checkpoints
with the exact run signature. Existing outputs are not overwritten; an active
run lock must not be deleted while a process is running. GPU allocator budget,
disk reserve and per-run artifact checks apply; a time budget is checked
between steps and during validation, not a hard process kill timer. A final
checkpoint/one update may overrun a boundary, so reserve shutdown headroom.

## Verified and Still Pending

Itcerdo: seven CPU preparation tests and three existing schedule tests passed, including exact next loss/weights
after AdamW/RNG restore. Actual pretrained CPU strict load and synthetic
forward/backward passed with finite gradients in all 129 parameter tensors;
no pretrained optimizer step or checkpoint was produced. Preflight reports
`training_ready=false` until data and approvals are supplied.

Real corpus schema/extraction/near-duplicate and PII review, actual RTX5090
Adam-state/VRAM/warmed throughput, uninterrupted-vs-resumed GPU update,
baseline and adapted Korean/English validation, and train-only threshold
calibration are still pending. These checks are required before claiming
training readiness or adaptation quality. Never extrapolate CPU/5090 speed
to Neuron H200.