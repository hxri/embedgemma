#!/usr/bin/env bash
# One-time environment setup on big-machine. Run inside tmux; logs to ~/research/embedgemma/setup.log
set -euo pipefail
source ~/miniconda3/etc/profile.d/conda.sh
mkdir -p ~/research/embedgemma
cd ~/research/embedgemma
if ! conda env list | grep -q '^embedgemma '; then
  conda create -y -n embedgemma python=3.12
fi
conda activate embedgemma
python -m pip install -U pip
# default PyPI Linux wheels bundle CUDA (cu128+), which covers sm_120
pip install -U torch torchvision torchaudio torchcodec
pip install -U "sentence-transformers>=6.1.0" "transformers>=5.0.0" pillow soundfile datasets pyarrow accelerate numpy
python - <<'PY'
import torch, transformers, sentence_transformers
print("torch", torch.__version__, "cuda", torch.version.cuda, "archs", torch.cuda.get_arch_list())
print("gpu0", torch.cuda.get_device_name(0))
print("transformers", transformers.__version__, "sentence-transformers", sentence_transformers.__version__)
import torchcodec; print("torchcodec", torchcodec.__version__)
PY
echo "SETUP_DONE"
