from pathlib import Path
import os
import sys

STUDIO_ROOT = Path(__file__).resolve().parents[1]
GARMENT_ROOT = Path(os.environ.get('GARMENT_ROOT', STUDIO_ROOT.parent / 'garmentcode-traditional')).resolve()
sys.path.insert(0, str(GARMENT_ROOT))
MODEL_PATH = Path(os.environ.get('GARMENT_MODEL_PATH', GARMENT_ROOT / 'lmm_utils/Qwen/Qwen2-VL-2B-Instruct')).resolve()
ADAPTER_PATH = Path(os.environ.get('GARMENT_ADAPTER_PATH', GARMENT_ROOT / 'artifacts/server-results-20261006/runs/traditional-json-lora-v1')).resolve()
RUNTIME_ROOT = Path(os.environ.get('GARMENT_RUNTIME_DIR', STUDIO_ROOT / 'runtime')).resolve()
