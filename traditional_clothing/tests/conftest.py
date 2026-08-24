"""
pytest 共享配置 — 确保项目根目录可导入。
运行方式（在项目根目录）：
    python -m pytest tests/ -v
"""
import os
import sys

# 项目根目录（garment_components/、validation/ 的父目录）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
