"""
纸样导出工具 — 输出不重叠的平铺预览图

背景：
  GarmentCode 默认输出的 `*_pattern.png/svg` 是按 **3D 定位投影**的
  （`get_svg(flat=False)`），前后层面板会互相重叠 —— 它主要用于
  查看装配关系，不适合直接看裁剪形状。

  本模块用 `get_svg(flat=True)` 导出**排料图式**的平铺预览
  （面板横向依次排开，互不重叠），并同时生成便于查看的 PNG。
"""
from __future__ import annotations

import os

import cairosvg


def save_flat_preview(pattern, out_dir, tag='', px_per_unit=3, margin=8):
    """导出平铺（不重叠）的纸样预览：SVG + PNG。

    Args:
        pattern:      VisPattern 对象（component.assembly() 的返回值）
        out_dir:      输出目录
        tag:          文件名后缀标签
        px_per_unit:  每厘米对应像素数（3 表示 3px = 1cm）
        margin:       面板间距（cm）

    Returns:
        (svg_path, png_path, panel_count)
    """
    os.makedirs(out_dir, exist_ok=True)
    name = pattern.name + (f'_{tag}' if tag else '')
    svg_path = os.path.join(out_dir, f'{name}_flat.svg')
    png_path = os.path.join(out_dir, f'{name}_flat.png')

    dwg = pattern.get_svg(
        svg_path,
        with_text=True,       # 标注裁片名
        view_ids=False,       # 不标注顶点/边编号（更清爽）
        flat=True,            # ⭐ 关键：平铺排开，不重叠
        fill_panels=True,     # 填充颜色便于辨识
        margin=margin,
    )
    dwg.save(pretty=True)
    cairosvg.svg2png(url=svg_path, write_to=png_path,
                     dpi=2.54 * px_per_unit)

    return svg_path, png_path, len(pattern.panel_order())


def save_all(pattern, out_dir, tag='', with_printable=True):
    """一次性导出全套：标准图 + 平铺预览 + 可打印 PDF。"""
    results = {}

    # 标准序列化（含 printable PDF）
    from pathlib import Path
    log_dir = pattern.serialize(
        Path(out_dir), tag=f'_{tag}' if tag else '',
        to_subfolder=True, with_3d=False, with_text=True,
        view_ids=False, with_printable=with_printable,
    )
    results['log_dir'] = log_dir

    # 平铺预览
    svg, png, n = save_flat_preview(pattern, log_dir, tag='')
    results['flat_svg'] = svg
    results['flat_png'] = png
    results['panel_count'] = n

    return results
