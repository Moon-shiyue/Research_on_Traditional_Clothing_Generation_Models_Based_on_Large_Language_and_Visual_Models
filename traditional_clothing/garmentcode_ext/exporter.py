"""
传统服饰纸样导出器 — 生成专业排料图（SVG + PNG）

相比 GarmentCode 自带的 `_pattern.png`（3D 投影会重叠、英文标签压线），
本导出器提供：
  ① 紧凑排料布局（裁片互不重叠，间距可调）
  ② 中文裁片名 + 序号 + 数量
  ③ 布纹线（grain line，带箭头虚线）
  ④ 尺寸标注（宽 × 高 cm）
  ⑤ 缝合边标注（区分缝合边/净边，来自 edge.label）
  ⑥ 标题与统计信息（裁片数、面料面积）

用法：
    from traditional_ext.exporter import export_pattern
    export_pattern(pattern, 'out_dir', tag='明代袄裙', title='明代袄裙三件套')
"""
from __future__ import annotations

import os

# ── 关键：先让 cairo 找到 DLL ──
# PyGarment 自带 Windows 版 cairo 运行时（pygarment/pattern/cairo_dlls/），
# 但它只在 wrappers.py 被导入时才写入 PATH。这里显式添加，
# 使本模块可独立导入（否则 import cairosvg 会抛 "no library called cairo-2"）。
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DLL_DIR = os.path.join(_ROOT, 'pygarment', 'pattern', 'cairo_dlls')
if os.path.isdir(_DLL_DIR):
    os.environ['PATH'] = os.environ.get('PATH', '') + os.pathsep + _DLL_DIR

import cairosvg
import svgwrite

# ── 英文裁片名 → 中文（可按需扩充）──
NAME_MAP = {
    # 马面裙
    'mamian_front': '前马面片',
    'mamian_back': '后马面片',
    'mamian_left_side': '左侧褶裥片',
    'mamian_right_side': '右侧褶裥片',
    'mamian_waistband': '腰头片',
    # 袖型
    'pipa_sleeve_right': '右琵琶袖片',
    'pipa_sleeve_left': '左琵琶袖片',
    'wide_sleeve_right': '右广袖片',
    'wide_sleeve_left': '左广袖片',
    'narrow_sleeve_right': '右窄袖片',
    'narrow_sleeve_left': '左窄袖片',
    # 领型
    'stand_collar_right': '立领右片',
    'stand_collar_left': '立领左片',
    'cross_collar_left_front': '交领左前片',
    'cross_collar_right_front': '交领右前片',
    'cross_collar_back': '交领后领片',
    'round_collar': '圆领领片',
    'duijin_left_front': '对襟左前片',
    'duijin_right_front': '对襟右前片',
    # 下裳
    'ruqun_front': '襦裙前片',
    'ruqun_back': '襦裙后片',
    'ruqun_waistband': '襦裙腰头片',
    # 配饰
    'cloud_shoulder': '云肩片',
    'cloud_shoulder_layer_1': '云肩内层片',
    'cloud_shoulder_layer_2': '云肩中层片',
    'cloud_shoulder_layer_3': '云肩外层片',
    'cloud_shoulder_tassel': '云肩垂须条',
    'beizi_front': '褙子前片',
    'beizi_back': '褙子后片',
    'beizi_sleeve_left': '褙子左袖片',
    'beizi_sleeve_right': '褙子右袖片',
    'banbi_front': '半臂前片',
    'banbi_back': '半臂后片',
}

# ── 样式 ──
C_PANEL_FILL = '#f6d5d8'      # 裁片填充（淡粉）
C_PANEL_STROKE = '#b03a48'    # 裁片轮廓（深红）
C_GRAIN = '#7a7a7a'           # 布纹线（灰）
C_TEXT = '#1f1f1f'            # 主文字
C_SUB = '#666666'             # 次要文字
C_HEM = '#2f6fb5'             # 净边（下摆）标注色

PX_PER_CM = 4.0               # 输出像素密度
LABEL_ZONE = 14.0             # 每片上下预留（cm）：上方标签 5.2 + 下方尺寸 6.4
GAP = 6.0                     # 裁片间距（cm）
MAX_ROW_W = 132.0             # 每行最大宽度（cm）


def _bbox(verts):
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    return min(xs), min(ys), max(xs), max(ys)


def _area(verts):
    a = 0.0
    n = len(verts)
    for i in range(n):
        j = (i + 1) % n
        a += verts[i][0] * verts[j][1] - verts[j][0] * verts[i][1]
    return abs(a) / 2.0


# ── 裁片显示顺序（按形制逻辑，而非装箱顺序）──
SEQ_HINTS = ['front', 'back', 'left', 'right', 'waistband',
             'collar', 'cuff', 'sleeve', 'skirt', 'side']


def _seq_key(name):
    """按形制逻辑给出排序权重（前→后→左→右→腰头→…）。"""
    for i, hint in enumerate(SEQ_HINTS):
        if hint in name:
            return i
    return len(SEQ_HINTS)


def _rel_to_abs(start, end, rel):
    """把「边局部坐标系」的相对控制点转成裁片绝对坐标。

    与 pygarment.pattern.utils.rel_to_abs_2d 一致：
      rel[0] 沿边方向的比例，rel[1] 垂直方向的比例（符号表示左右弯曲）。
    """
    ex, ey = end[0] - start[0], end[1] - start[1]
    px, py = -ey, ex                      # 边的垂直方向
    return (start[0] + rel[0] * ex + rel[1] * px,
            start[1] + rel[0] * ey + rel[1] * py)


def _panel_path(verts, edges, T, dx, dy):
    """构建裁片的 SVG path 字符串（支持三次/二次贝塞尔曲线边）。

    GarmentCode 序列化时把曲线存为 edge['curvature']：
      {'type': 'cubic', 'params': [[x1,y1],[x2,y2]]}   （相对边长归一化）
    """
    def tp(v):
        return T(v[0] + dx, v[1] + dy)

    if not edges:
        pts = [tp(v) for v in verts]
        return 'M ' + ' L '.join(f'{x:.2f},{y:.2f}' for x, y in pts) + ' Z'

    cmds = []
    for i, e in enumerate(edges):
        i0, i1 = e['endpoints']
        v0 = (verts[i0][0] + dx, verts[i0][1] + dy)
        v1 = (verts[i1][0] + dx, verts[i1][1] + dy)
        p0, p1 = T(*v0), T(*v1)
        if i == 0:
            cmds.append(f'M {p0[0]:.2f},{p0[1]:.2f}')

        curv = e.get('curvature') or {}
        ctype = curv.get('type')
        params = curv.get('params') or []
        if ctype == 'cubic' and len(params) >= 2:
            c1 = T(*_rel_to_abs(v0, v1, params[0]))
            c2 = T(*_rel_to_abs(v0, v1, params[1]))
            cmds.append(f'C {c1[0]:.2f},{c1[1]:.2f} '
                        f'{c2[0]:.2f},{c2[1]:.2f} '
                        f'{p1[0]:.2f},{p1[1]:.2f}')
        elif ctype == 'quadratic' and len(params) >= 1:
            c1 = T(*_rel_to_abs(v0, v1, params[0]))
            cmds.append(f'Q {c1[0]:.2f},{c1[1]:.2f} {p1[0]:.2f},{p1[1]:.2f}')
        else:
            cmds.append(f'L {p1[0]:.2f},{p1[1]:.2f}')
    cmds.append('Z')
    return ' '.join(cmds)


def _layout(panels):
    """首次适应装箱：按形制顺序（前→后→左→右→腰头）依次放入首个装得下的行。

    保持形制顺序 = 编号顺序 = 阅读顺序（左→右、上→下），便于查找裁片。
    返回 [(panel_name, dx, dy), ...] 与画布尺寸 (total_w, total_h)。
    """
    items = sorted(panels, key=lambda kv: _seq_key(kv[0]))

    rows = []          # [{'used': float, 'h': float, 'items': [(name, x_in_row, x0, y0)]}]
    for name, info in items:
        x0, y0, x1, y1 = info['bbox']
        w, h = x1 - x0, y1 - y0
        # 标签区高度自适应：小裁片不必留出大裁片那么宽的标注空间
        lz = max(9.0, min(LABEL_ZONE, h * 0.35 + 7.0))
        cw, ch = w + GAP, h + lz + GAP
        for r in rows:
            if r['used'] + cw <= MAX_ROW_W:
                r['items'].append((name, r['used'], x0, y0))
                r['used'] += cw
                r['h'] = max(r['h'], ch)
                break
        else:
            rows.append({'used': cw, 'h': ch,
                         'items': [(name, 0.0, x0, y0)]})

    placed = []
    y = 0.0
    for r in rows:
        for name, dx, x0, y0 in r['items']:
            placed.append((name, dx - x0, y - y0))
        y += r['h']

    total_w = max(r['used'] for r in rows) - GAP
    total_h = y - GAP
    return placed, total_w, total_h


def export_pattern(pattern, out_dir, tag='', title='', px_per_cm=PX_PER_CM,
                   show_size=True, show_grain=True, show_edges=False):
    """导出专业排料图。

    Args:
        pattern:   component.assembly() 返回的 VisPattern
        out_dir:   输出目录
        tag:       文件名标签
        title:     图标题
        show_size: 显示尺寸标注
        show_grain: 显示布纹线
        show_edges: 显示每条边的标签（调试用）

    Returns:
        (svg_path, png_path, stats)
    """
    os.makedirs(out_dir, exist_ok=True)
    base = (pattern.name or 'pattern') + (f'_{tag}' if tag else '')
    svg_path = os.path.join(out_dir, base + '_paper.svg')
    png_path = os.path.join(out_dir, base + '_paper.png')

    # ── 收集裁片 ──
    # 统一 y 轴约定：组件内部用「y 负方向 = 向下」（与 GarmentCode 一致），
    # 导出时翻转 y，使 y=0（裁片起点，如袖根/腰口）显示在**上方**。
    panels = []
    for name in pattern.panel_order():
        p = pattern.pattern['panels'].get(name)
        if not p or not p.get('vertices'):
            continue
        verts = [[v[0], -v[1]] for v in p['vertices']]     # ⭐ 垂直翻转
        panels.append((name, {'verts': verts,
                              'bbox': _bbox(verts),
                              'edges': p.get('edges', []),
                              'area': _area(p['vertices'])}))
    if not panels:
        raise ValueError('纸样为空，无裁片可导出')

    placed, total_w, total_h = _layout(panels)

    # ── 画布（cm → px）──
    M = 18.0                      # 页边距（cm）
    HEADER = 24.0                 # 顶部标题区高度（cm）
    canvas_w_cm = total_w + 2 * M
    canvas_h_cm = total_h + 2 * M + HEADER
    # 自适应分辨率：小纸样也保证足够像素，避免图片过于局促
    k = max(px_per_cm, 900.0 / max(canvas_w_cm, 1.0))
    k = min(k, 12.0)
    W, H = canvas_w_cm * k, canvas_h_cm * k
    dwg = svgwrite.Drawing(svg_path, size=(f'{W:.0f}px', f'{H:.0f}px'))
    dwg.viewbox(0, 0, W, H)
    dwg.add(dwg.rect(insert=(0, 0), size=(W, H), fill='#ffffff'))

    def T(x_cm, y_cm):
        """cm 坐标 → px 坐标。

        布局后裁片 y ∈ [0, total_h]，y 越大越靠下（与 SVG 一致）；
        顶部预留 HEADER cm 给标题区（y ∈ [-HEADER, 0]）。
        """
        return ((M + x_cm) * k, (M + HEADER + y_cm) * k)

    font = 'Microsoft YaHei, SimHei, Arial, sans-serif'

    def _fit_font_cm(text, avail_cm, max_cm):
        """按可用宽度限制字号（cm）。

        宽度估算：中日韩文字与中文标点（U+2000 以上）按 1.0 em，
        ASCII 按 0.6 em；再乘 0.92 安全系数。
        """
        wide = sum(1.0 if ord(c) > 0x2000 else 0.6 for c in text)
        return min(max_cm, avail_cm * 0.92 / max(wide, 1.0))

    # 可用宽度：标题起点 x=0 cm（像素 M）到画布右边缘
    avail = total_w + M - 4.0

    # ── 标题 ──
    if title:
        tsize = _fit_font_cm(title, avail, 5.6)
        tx, ty = T(0, -16.0)
        dwg.add(dwg.text(title, insert=(tx, ty), fill=C_TEXT,
                         font_size=f'{tsize * k:.0f}px',
                         font_family=font, font_weight='bold'))
    # 副标题（统计）
    total_area = sum(info['area'] for _, info in panels)
    sub = (f'裁片 {len(panels)} 片 | '
           f'面料总面积 {total_area:.0f} cm2 ({total_area / 10000:.3f} m2) | '
           f'单位 cm | 比例 1:1')
    ssize = _fit_font_cm(sub, avail, 2.7)
    tx, ty = T(0, -10.0)
    dwg.add(dwg.text(sub, insert=(tx, ty), fill=C_SUB,
                     font_size=f'{ssize * k:.0f}px', font_family=font))

    # ── 逐片绘制 ──
    lookup = dict(panels)
    # 编号按形制逻辑（前→后→左→右→腰头），而非装箱顺序
    seq = {n: i + 1 for i, n in enumerate(
        sorted((n for n, _ in panels), key=_seq_key))}
    for name, dx, dy in placed:
        info = lookup[name]
        verts = [(v[0] + dx, v[1] + dy) for v in info['verts']]
        x0, y0, x1, y1 = _bbox(verts)      # y0=顶边(小值), y1=底边(大值)
        w, h = x1 - x0, y1 - y0

        pts_path = _panel_path(info['verts'], info['edges'], T, dx, dy)
        dwg.add(dwg.path(d=pts_path, fill=C_PANEL_FILL,
                         stroke=C_PANEL_STROKE, stroke_width=1.6,
                         stroke_linejoin='round'))

        # 布纹线（沿高度方向的带箭头虚线）
        if show_grain and h > 8:
            cx = (x0 + x1) / 2
            gy0, gy1 = y0 + h * 0.12, y0 + h * 0.88
            p1, p2 = T(cx, gy0), T(cx, gy1)     # p1 在上，p2 在下
            dwg.add(dwg.line(start=p1, end=p2, stroke=C_GRAIN,
                             stroke_width=1.0, stroke_dasharray='7,5'))
            for pt, sgn in ((p1, 1), (p2, -1)):   # sgn=1 → 箭头朝上
                dwg.add(dwg.polygon(
                    points=[(pt[0], pt[1]),
                            (pt[0] - 4, pt[1] + sgn * 11),
                            (pt[0] + 4, pt[1] + sgn * 11)],
                    fill=C_GRAIN))

        # 裁片名 + 序号（裁片上方，字号受裁片宽度限制以免压到相邻裁片）
        cname = NAME_MAP.get(name, name)
        label_txt = f'{seq[name]}. {cname} x1'
        lw = sum(1.0 if ord(c) > 0x2000 else 0.6 for c in label_txt)
        lsize = min(3.4, (w + GAP * 0.9) * 0.96 / max(lw, 1.0))
        tx, ty = T(x0, y0 - 5.2)
        dwg.add(dwg.text(label_txt, insert=(tx, ty),
                         fill=C_TEXT, font_size=f'{lsize * k:.0f}px',
                         font_family=font, font_weight='bold'))
        # 内部名（小字，便于追溯；同样限制宽度）
        nw = sum(1.0 if ord(c) > 0x2000 else 0.6 for c in name)
        nsize = min(2.1, (w + GAP * 0.9) * 0.96 / max(nw, 1.0))
        tx2, ty2 = T(x0, y0 - 2.0)
        dwg.add(dwg.text(name, insert=(tx2, ty2), fill=C_SUB,
                         font_size=f'{nsize * k:.0f}px', font_family=font))

        # 尺寸标注（裁片下方）
        if show_size:
            tx3, ty3 = T(x0, y1 + 3.2)
            dwg.add(dwg.text(f'{w:.1f} x {h:.1f}', insert=(tx3, ty3),
                             fill=C_SUB, font_size=f'{2.6 * k:.0f}px',
                             font_family=font))
            dwg.add(dwg.text(f'{info["area"]:.0f} cm2',
                             insert=(tx3, ty3 + 3.2 * k),
                             fill=C_SUB, font_size=f'{2.4 * k:.0f}px',
                             font_family=font))

        # 边标签（可选）
        if show_edges:
            for e in info['edges']:
                lbl = e.get('label', '')
                if not lbl:
                    continue
                i0, i1 = e['endpoints']
                v0 = (info['verts'][i0][0] + dx, info['verts'][i0][1] + dy)
                v1 = (info['verts'][i1][0] + dx, info['verts'][i1][1] + dy)
                mx, my = (v0[0] + v1[0]) / 2, (v0[1] + v1[1]) / 2
                px, py = T(mx, my)
                dwg.add(dwg.text(lbl, insert=(px + 2, py), fill=C_HEM,
                                 font_size=f'{2.0 * k:.0f}px',
                                 font_family=font))

    dwg.save(pretty=True)
    cairosvg.svg2png(url=svg_path, write_to=png_path, dpi=2.54 * k)

    stats = {'panels': len(panels), 'area_cm2': total_area,
             'canvas_cm': (total_w, total_h)}
    return svg_path, png_path, stats
