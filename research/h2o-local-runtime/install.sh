#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
command -v uv >/dev/null
uv venv --python 3.12 .venv
UV_CONCURRENT_DOWNLOADS=2 uv pip install --python .venv/bin/python -r requirements.lock --extra-index-url https://wheels.vllm.ai/0.30.0/cu129 --extra-index-url https://download.pytorch.org/whl/cu129 --index-strategy unsafe-best-match
# Low-concurrency download; model and tools are pinned to the same immutable commit.
HF_XET_NUM_CONCURRENT_RANGE_GETS=2 .venv/bin/hf download h2oai/h2o-lightning-4b model.safetensors label_rows.lightning config.json generation_config.json tokenizer.json tokenizer_config.json chat_template.jinja preprocessor_config.json video_preprocessor_config.json merges.txt vocab.json h2o_lightning_shim.py pooled_readout.py card_common.py assets.py box.py serve_config.json serve.sh README.md LICENSE --revision e5c86b7564de9574fc48e759c226e50819d079ec --local-dir model --max-workers 1
