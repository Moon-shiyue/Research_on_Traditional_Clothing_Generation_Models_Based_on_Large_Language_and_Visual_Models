"""
云肩 / 褙子 / 半臂 — pygarment 原生实现（配饰批次）

对应项目（traditional_clothing）中的三个配饰部件：
  garment_components/accessories/cloud_shoulder.py  云肩（明清，多层云头披肩）
  garment_components/accessories/beizi.py           褙子（宋/明，对襟长外衣）
  garment_components/accessories/banbi.py           半臂（唐/宋，连袖短外衣）

设计原则（与 collars_extra / sleeves_extra / skirts_extra / mamian_skirt 一致）：
  - 用 pyg.Panel + Edge / CurveEdge / EdgeSequence 表达几何
  - 参数全部从 design 参数树读取，并尽量归一化到体型
    （× body['_leg_length'] / ['shoulder_w'] / ['bust'] / ['neck_w'] / ['arm_length']），
    只有单位本身就是 cm 的量（领深、袖口宽、褶深等）才直接用数值
  - 组件内置形制自检 self.warnings（规则取自 validation/rules/__init__.py）
  - y 轴约定：**y 负方向 = 向下**（衣摆自肩线向下延伸为 -length）
  - 对外接口名一律英文小写 + 下划线

三个组件与项目原实现的差异（有意简化，见各自类 docstring）：
  云肩：原实现为「领座 + N 片独立云片」，本实现把每层做成**整环云头片**
        （背中开一道窄口以保持平面可展开），层数用 layers 参数控制，
        另出 1 片垂须条（对应原 petal 上的垂须）。
  褙子：对襟开口以「前中线窄缝」表达（缝止于下摆上方一小段连接条），
        使前身仍为单一合法多边形裁片；袖片独立裁剪（共 4 片）。
  半臂：袖与大身连裁（平裁连袖）——这是半臂最常见也最省料的裁剪法，
        因此只需前/后两片；交领右衽以「前中开襟 + 前领深」表达。
"""
from __future__ import annotations

import math

import pygarment as pyg


# ═══════════════════════════════════════════════════════════════
# 通用几何工具
# ═══════════════════════════════════════════════════════════════

def _polar(radius, angle):
    """极坐标 → 直角坐标（圆心在原点）。"""
    return [radius * math.cos(angle), radius * math.sin(angle)]


def _arc_edges(radius, a0, a1, label='arc', max_step=math.pi / 2.0):
    """把圆弧离散为若干 ≤90° 的三次贝塞尔段，返回 Edge 列表。

    相邻段共享顶点对象，因此可直接 append 进 EdgeSequence 并保持链式/闭环判定。

    NOTE: 这里不用 CircleEdge —— 接近整圈的圆弧（云肩层片）用 SVG arc
    （大弧标志 + 起止点很近）表示时数值不稳定；贝塞尔分段更可控。
    """
    sweep = a1 - a0
    n = max(1, int(math.ceil(abs(sweep) / max_step)))
    angles = [a0 + sweep * i / n for i in range(n + 1)]
    pts = [_polar(radius, a) for a in angles]

    edges = []
    for i in range(n):
        t0, t1 = angles[i], angles[i + 1]
        # 圆弧 → 三次贝塞尔的标准控制长度 k = 4/3 · tan(Δ/4) · r
        k = 4.0 / 3.0 * math.tan((t1 - t0) / 4.0) * radius
        p0, p3 = pts[i], pts[i + 1]
        c1 = [p0[0] - k * math.sin(t0), p0[1] + k * math.cos(t0)]
        c2 = [p3[0] + k * math.sin(t1), p3[1] - k * math.cos(t1)]
        edges.append(pyg.CurveEdge(p0, p3, control_points=[c1, c2],
                                   relative=False, label=label))
    return edges


# ═══════════════════════════════════════════════════════════════
# 云肩 Cloud Shoulder
# ═══════════════════════════════════════════════════════════════

class CloudLayerPanel(pyg.Panel):
    """云肩层片 — 整环云头波浪片（背中开一道窄口，保证平面可展开）。

    形制：内圈为领口弧（半径 = inner_r），外圈为 petal_count 个云头：
      瓣尖半径 r_tip = inner_r + petal_len
      瓣谷半径 r_valley = r_tip - scallop_depth × petal_len
    每瓣用**两段二次贝塞尔**（瓣谷 → 瓣尖 → 瓣谷）表达，瓣尖是显式顶点
    （云头尖），因此裁片的顶点包围盒 = 真实外形包围盒，排料不会重叠。

    闭环顺序（y 负方向 = 向下，与其它部件一致）：
      内圈弧(a0→a1) → 背中切口(a1, 内→外) → 云头(a1→a0，逐瓣)
      → 背中切口(a0, 外→内，回到起点)
    """

    def __init__(self, name, inner_r, petal_len, petal_count,
                 scallop_depth, back_gap_deg=6.0):
        super().__init__(name)
        self.inner_r = inner_r
        self.petal_len = petal_len
        self.tip_r = inner_r + petal_len
        self.petal_count = int(petal_count)

        gap = math.radians(back_gap_deg)
        a0 = math.pi / 2.0 + gap / 2.0                 # 背中切口一侧
        a1 = a0 + 2.0 * math.pi - gap                  # 绕一圈回到切口另一侧

        r_tip = self.tip_r
        r_v = r_tip - scallop_depth * petal_len        # 瓣谷
        r_c = r_v + 1.2 * (r_tip - r_v)                # 云头鼓起控制半径（径向）

        # 1) 内圈弧：a0 → a1
        inner = _arc_edges(inner_r, a0, a1, label='neckline')
        self.edges.append(inner)

        # 2) 云头波浪：a0 → a1，每瓣「瓣谷 → 瓣尖 → 瓣谷」两段二次贝塞尔
        step = (a1 - a0) / self.petal_count
        half = step / 2.0
        valleys = [_polar(r_v, a0 + i * step) for i in range(self.petal_count + 1)]
        petals = []
        for i in range(self.petal_count):
            am = a0 + i * step + half                       # 瓣尖方向
            tip = _polar(r_tip, am)
            c_left = _polar(r_c, am - half / 2.0)
            c_right = _polar(r_c, am + half / 2.0)
            petals.append(pyg.CurveEdge(valleys[i], tip,
                                        control_points=[c_left],
                                        relative=False, label='scallop'))
            petals.append(pyg.CurveEdge(tip, valleys[i + 1],
                                        control_points=[c_right],
                                        relative=False, label='scallop'))

        # 3) 背中切口（内 a1 → 外 a1）
        self.edges.append(pyg.Edge(inner[-1].end, valleys[-1], label='back_cut_a'))

        # 4) 云头反向走回 a0（逐段翻转方向，顶点对象保持共享）
        for e in reversed(petals):
            e.reverse()
            self.edges.append(e)

        # 5) 背中切口（外 a0 → 内 a0 == 首边起点）
        self.edges.append(pyg.Edge(valleys[0], inner[0].start, label='back_cut_b'))
        self.edges.close_loop()                        # 已是闭环 → no-op

        n_inner = len(inner)
        self.inner_edges = self.edges[0:n_inner]
        self.cut_a = self.edges[n_inner]
        self.petal_edges = self.edges[n_inner + 1:-1]      # 2×petal_count 段
        self.cut_b = self.edges[-1]

        self.interfaces = {
            # 内圈：接领口 / 立领
            'neckline': pyg.Interface(self, self.inner_edges),
            # 外圈云头：接垂须条
            'outer': pyg.Interface.from_multiple(
                *[pyg.Interface(self, self.petal_edges[i])
                  for i in range(len(self.petal_edges))]),
            # 背中切口两侧（缝合后成环）
            'cut_a': pyg.Interface(self, self.cut_a),
            'cut_b': pyg.Interface(self, self.cut_b),
        }


class CloudTasselPanel(pyg.Panel):
    """云肩垂须片 — 最外层云头外缘的流苏条。

    长度 = 最外层外缘周长（缝合时被收拢到各云头之间），宽 = 垂须长。
    """

    def __init__(self, name, length, height):
        super().__init__(name)
        self.edges.append(pyg.Edge([0.0, 0.0], [length, 0.0], label='top'))
        self.edges.append(pyg.Edge([length, 0.0], [length, -height], label='right'))
        self.edges.append(pyg.Edge([length, -height], [0.0, -height], label='bottom'))
        self.edges.close_loop()

        self.interfaces = {
            'top': pyg.Interface(self, self.edges[0]),        # 接云头外缘
            'bottom': pyg.Interface(self, self.edges[2]),     # 垂须末端（净边）
            'left': pyg.Interface(self, self.edges[3]),
            'right': pyg.Interface(self, self.edges[1]),
        }


class CloudShoulder(pyg.Component):
    """云肩 — 明清礼服/婚服的标志性肩部配饰。

    参数来源（design['cloud-shoulder']）：
      layers          层数（1~3）
      petal_count     每层云头数（4/6/8）
      petal_length    单瓣径向长（× body['shoulder_w']）
      neck_opening    领口半径系数（× body['neck_w']/2）
      scallop_depth   云头凹入比（瓣谷 = 瓣尖 − depth×petal_length）
      layer_overlap   层间叠压比（外层内圈内缩 (1−overlap)×petal_length）
      tassel_length   垂须长（cm，0 = 无垂须）
      back_gap        背中切口角度（°，平面展开用）

    形制自检（对应 validation/rules）：
      - 云片数宜为偶数且 ≥ 4（对称）
      - 外径需盖住肩宽
      - 领口周长需 ≥ 估算颈围（否则戴不进）
      - 层数不宜超过 3
    """

    def __init__(self, body, design, tag=''):
        super().__init__(f'CloudShoulder{"_" + tag if tag else ""}')
        self.body = body
        self.design = design
        d = design['cloud-shoulder']

        # ── 参数（归一化到体型）──
        layers = int(d['layers']['v'])
        petal_count = int(d['petal_count']['v'])
        petal_len = float(d['petal_length']['v']) * body['shoulder_w']
        neck_r = float(d['neck_opening']['v']) * body['neck_w'] / 2.0
        scallop = float(d['scallop_depth']['v'])
        overlap = float(d['layer_overlap']['v'])
        tassel_len = float(d['tassel_length']['v'])
        back_gap = float(d['back_gap']['v'])

        # ── 派生 ──
        layers = max(1, min(4, layers))
        petal_count = max(4, min(12, petal_count))
        scallop = max(0.1, min(0.8, scallop))
        overlap = max(0.0, min(0.85, overlap))

        self.layers = layers
        self.petal_count = petal_count
        self.petal_len = petal_len
        self.neck_r = neck_r
        self.tassel_len = tassel_len

        # ── 形制自检 ──
        self.warnings = []
        outer_r = neck_r + petal_len * (1.0 + (layers - 1) * (1.0 - overlap))
        self.outer_r = outer_r
        neck_circ_open = 2.0 * math.pi * neck_r
        neck_circ_body = body['neck_w'] * 2.15          # 颈围估算（≈ 领宽 × 2.15）

        if petal_count % 2 != 0:
            self.warnings.append(
                f'云头数 {petal_count} 为奇数，传统云肩以偶数对称排列为常（4/6/8）')
        if petal_count < 4:
            self.warnings.append(f'云片数过少（{petal_count}），建议至少 4 片')
        if layers > 3:
            self.warnings.append(f'云肩层数 {layers} 过多（常见 1~3 层）')
        if 2.0 * outer_r < body['shoulder_w']:
            self.warnings.append(
                f'云肩外径 {2 * outer_r:.1f}cm 小于肩宽 {body["shoulder_w"]:.1f}cm，'
                f'盖不住肩（形制不足）')
        if 2.0 * outer_r > 1.8 * body['shoulder_w']:
            self.warnings.append(
                f'云肩外径 {2 * outer_r:.1f}cm 过大（> 1.8×肩宽），已接近披风尺寸')
        if neck_circ_open < neck_circ_body:
            self.warnings.append(
                f'领口周长 {neck_circ_open:.1f}cm 小于估算颈围 {neck_circ_body:.1f}cm，'
                f'无法穿戴（应增大 neck_opening）')
        if neck_circ_open > 1.4 * neck_circ_body:
            self.warnings.append(
                f'领口周长 {neck_circ_open:.1f}cm 偏大（> 1.4×颈围），云肩易滑落')
        if tassel_len > 0 and tassel_len > petal_len:
            self.warnings.append(
                f'垂须长 {tassel_len:.1f}cm 超过单瓣径向长 {petal_len:.1f}cm，比例失衡')
        if back_gap > 15.0:
            self.warnings.append(f'背中切口 {back_gap:.1f}° 过大，成环后可见缺口')

        # ── 裁片：每层一片（cloud_shoulder_layer_1 ...）──
        self.layer_panels = []
        for i in range(layers):
            r_in = neck_r + i * petal_len * (1.0 - overlap)
            panel = CloudLayerPanel(
                f'cloud_shoulder_layer_{i + 1}', r_in, petal_len,
                petal_count, scallop, back_gap)
            setattr(self, f'layer_{i + 1}', panel)      # 让 pyg.Component 收集到
            self.layer_panels.append(panel)

        # ── 裁片：垂须条 ──
        self.tassel = None
        if tassel_len > 0.5:
            outer_len = float(
                self.layer_panels[-1].interfaces['outer'].projecting_lengths().sum())
            self.tassel = CloudTasselPanel('cloud_shoulder_tassel',
                                           outer_len, tassel_len)

        # ── 缝合 ──
        rules = []
        for p in self.layer_panels:
            rules.append((p.interfaces['cut_a'], p.interfaces['cut_b']))   # 成环
        if self.tassel is not None:
            rules.append((self.tassel.interfaces['top'],
                          self.layer_panels[-1].interfaces['outer']))
        self.stitching_rules = _safe_stitches(self, rules)

        # ── 对外接口 ──
        self.interfaces = {
            # 最内层领口（接衣身领线或立领）
            'neckline': pyg.Interface.from_multiple(
                self.layer_panels[0].interfaces['neckline']),
            # 最外层云头外缘
            'outer': pyg.Interface.from_multiple(
                self.layer_panels[-1].interfaces['outer']),
        }

    def summary(self):
        d = self.design['cloud-shoulder']
        tassel = f'垂须 {d["tassel_length"]["v"]}cm' if self.tassel else '无垂须'
        return (f'云肩 | {self.layers} 层 × {self.petal_count} 云头 | '
                f'瓣长 {self.petal_len:.1f}cm | 外径 {2 * self.outer_r:.1f}cm | '
                f'领口周长 {2 * math.pi * self.neck_r:.1f}cm | {tassel}')


# ═══════════════════════════════════════════════════════════════
# 褙子 Beizi
# ═══════════════════════════════════════════════════════════════

class BeiziBackPanel(pyg.Panel):
    """褙子后身片 — 后领窝 + 落肩袖窿 + 侧高开衩 + 平下摆。

    整幅后身（−half_w → +half_w），左右严格对称。
    闭环：左肩 → 左袖窿 → 左侧缝 → 左开衩 → 下摆 → 右开衩 → 右侧缝
          → 右袖窿 → 右肩 → 后领窝 → (回到左肩)
    """

    def __init__(self, name, half_w, half_sh, neck_half, depth_back,
                 armhole_depth, length, slit):
        super().__init__(name)
        L, ahd = length, armhole_depth
        nl, nr = [-neck_half, 0.0], [neck_half, 0.0]
        sl, sr = [-half_sh, 0.0], [half_sh, 0.0]
        al, ar = [-half_w, -ahd], [half_w, -ahd]
        bl, br = [-half_w, -(L - slit)], [half_w, -(L - slit)]
        hl, hr = [-half_w, -L], [half_w, -L]

        self.edges.append(pyg.Edge(nl, sl, label='shoulder_l'))
        self.edges.append(pyg.CurveEdge(
            sl, al,
            control_points=[[-(half_sh + 3.0), -ahd * 0.35],
                            [-half_w, -ahd * 0.65]],
            relative=False, label='armhole_l'))
        self.edges.append(pyg.Edge(al, bl, label='side_l'))
        self.edges.append(pyg.Edge(bl, hl, label='slit_l'))
        self.edges.append(pyg.Edge(hl, hr, label='hem'))
        self.edges.append(pyg.Edge(hr, br, label='slit_r'))
        self.edges.append(pyg.Edge(br, ar, label='side_r'))
        self.edges.append(pyg.CurveEdge(
            ar, sr,
            control_points=[[half_w, -ahd * 0.65],
                            [half_sh + 3.0, -ahd * 0.35]],
            relative=False, label='armhole_r'))
        self.edges.append(pyg.Edge(sr, nr, label='shoulder_r'))
        # 后领窝：控制点 y = −2×领深 → 曲线中点恰好落在 −领深
        self.edges.append(pyg.CurveEdge(nr, nl,
                                        control_points=[[0.0, -2.0 * depth_back]],
                                        relative=False, label='neckline'))
        self.edges.close_loop()

        self.interfaces = {
            'neckline': pyg.Interface(self, self.edges[9]),
            'shoulder_l': pyg.Interface(self, self.edges[0]),
            'shoulder_r': pyg.Interface(self, self.edges[8]),
            'armhole_l': pyg.Interface(self, self.edges[1]),
            'armhole_r': pyg.Interface(self, self.edges[7]),
            'side_l': pyg.Interface(self, self.edges[2]),
            'side_r': pyg.Interface(self, self.edges[6]),
            'slit_l': pyg.Interface(self, self.edges[3]),
            'slit_r': pyg.Interface(self, self.edges[5]),
            'hem': pyg.Interface(self, self.edges[4]),
        }


class BeiziFrontPanel(pyg.Panel):
    """褙子前身片 — 对襟直领 + 前中开襟 + 两侧高开衩。

    对襟形态：前中线开一道宽 front_w 的窄缝（门襟线），缝一直开到下摆上方
    `tab` 处，由一小段连接条收尾 —— 这样前身仍是**单一合法多边形**（一个
    倒 U 形），裁剪时沿门襟线剪开即成两片对襟前襟。这是本项目对“对襟一片
    还是两片”的简化表达（真实裁剪为两片完全相同的襟片，各自镜像裁剪）。

    闭环：左前领弧 → 门襟左边 → 门襟下端连接条 → 门襟右边 → 右前领弧
          → 右肩 → 右袖窿 → 右侧缝 → 右开衩 → 下摆 → 左开衩 → 左侧缝
          → 左袖窿 → 左肩 → (回到左前领弧)
    """

    def __init__(self, name, half_w, half_sh, neck_half, depth_front,
                 armhole_depth, length, slit, front_w, tab):
        super().__init__(name)
        L, ahd, gw = length, armhole_depth, front_w
        nl, nr = [-neck_half, 0.0], [neck_half, 0.0]
        sl, sr = [-half_sh, 0.0], [half_sh, 0.0]
        al, ar = [-half_w, -ahd], [half_w, -ahd]
        bl, br = [-half_w, -(L - slit)], [half_w, -(L - slit)]
        hl, hr = [-half_w, -L], [half_w, -L]
        # 门襟：上端 = 前领深，下端 = 下摆上方 tab 处
        nt_l, nt_r = [-gw / 2.0, -depth_front], [gw / 2.0, -depth_front]
        nb_l, nb_r = [-gw / 2.0, -(L - tab)], [gw / 2.0, -(L - tab)]

        # 前领弧：控制点 y = −0.6×领深（前领比后领深，且向外张开）
        self.edges.append(pyg.CurveEdge(
            nl, nt_l,
            control_points=[[-neck_half * 0.55, -depth_front * 0.6]],
            relative=False, label='neckline_l'))
        self.edges.append(pyg.Edge(nt_l, nb_l, label='center_front_l'))
        self.edges.append(pyg.Edge(nb_l, nb_r, label='center_front_tab'))
        self.edges.append(pyg.Edge(nb_r, nt_r, label='center_front_r'))
        self.edges.append(pyg.CurveEdge(
            nt_r, nr,
            control_points=[[neck_half * 0.55, -depth_front * 0.6]],
            relative=False, label='neckline_r'))
        self.edges.append(pyg.Edge(nr, sr, label='shoulder_r'))
        self.edges.append(pyg.CurveEdge(
            sr, ar,
            control_points=[[half_sh + 3.0, -ahd * 0.35],
                            [half_w, -ahd * 0.65]],
            relative=False, label='armhole_r'))
        self.edges.append(pyg.Edge(ar, br, label='side_r'))
        self.edges.append(pyg.Edge(br, hr, label='slit_r'))
        self.edges.append(pyg.Edge(hr, hl, label='hem'))
        self.edges.append(pyg.Edge(hl, bl, label='slit_l'))
        self.edges.append(pyg.Edge(bl, al, label='side_l'))
        self.edges.append(pyg.CurveEdge(
            al, sl,
            control_points=[[-half_w, -ahd * 0.65],
                            [-(half_sh + 3.0), -ahd * 0.35]],
            relative=False, label='armhole_l'))
        self.edges.append(pyg.Edge(sl, nl, label='shoulder_l'))
        self.edges.close_loop()

        self.interfaces = {
            'neckline_l': pyg.Interface(self, self.edges[0]),
            'neckline_r': pyg.Interface(self, self.edges[4]),
            'center_front_l': pyg.Interface(self, self.edges[1]),
            'center_front_r': pyg.Interface(self, self.edges[3]),
            'center_front_tab': pyg.Interface(self, self.edges[2]),
            'shoulder_l': pyg.Interface(self, self.edges[13]),
            'shoulder_r': pyg.Interface(self, self.edges[5]),
            'armhole_l': pyg.Interface(self, self.edges[12]),
            'armhole_r': pyg.Interface(self, self.edges[6]),
            'side_l': pyg.Interface(self, self.edges[11]),
            'side_r': pyg.Interface(self, self.edges[7]),
            'slit_l': pyg.Interface(self, self.edges[10]),
            'slit_r': pyg.Interface(self, self.edges[8]),
            'hem': pyg.Interface(self, self.edges[9]),
        }


class BeiziSleevePanel(pyg.Panel):
    """褙子袖片 — 直身微收袖口 + 弧袖山（右袖；左袖由 mirror() 得到）。"""

    def __init__(self, name, length, root_w, cuff_w, cap_h):
        super().__init__(name)
        root_l, root_r = [-root_w / 2.0, 0.0], [root_w / 2.0, 0.0]
        cuff_l, cuff_r = [-cuff_w / 2.0, -length], [cuff_w / 2.0, -length]

        self.edges.append(pyg.Edge(root_r, cuff_r, label='outer'))
        self.edges.append(pyg.Edge(cuff_r, cuff_l, label='cuff'))
        self.edges.append(pyg.Edge(cuff_l, root_l, label='inner'))
        # 袖山：向 +y（上）隆起，与衣身袖窿的圆弧走向一致
        self.edges.append(pyg.CurveEdge(
            root_l, root_r,
            control_points=[[-root_w * 0.25, cap_h], [root_w * 0.25, cap_h]],
            relative=False, label='armhole'))
        self.edges.close_loop()

        self.interfaces = {
            'armhole': pyg.Interface(self, self.edges[3]),
            'cuff': pyg.Interface(self, self.edges[1]),
            'outer': pyg.Interface(self, self.edges[0]),
            'inner': pyg.Interface(self, self.edges[2]),
        }


class Beizi(pyg.Component):
    """褙子 — 宋/明对襟长外衣（无扣敞开、两侧高开衩、直领）。

    参数来源（design['beizi']）：
      length            衣长（× body['_leg_length']）
      chest_ease        胸围松量比（× body['bust']，决定衣身宽）
      shoulder_ease     肩宽松量比（× body['shoulder_w']）
      neck_depth_front  前领深（cm）  neck_depth_back 后领深（cm）
      armhole_depth     袖窿深系数（× body['shoulder_w']）
      slit_height       开衩高比例（× 衣长）
      front_opening_width / front_opening_stop  对襟门襟缝宽 / 缝止位置
      sleeve_length     袖长（× body['arm_length']）
      sleeve_root_width / sleeve_cuff_width / sleeve_cap_height  袖肥/袖口/袖山高（cm）

    形制自检（对应 validation/rules 与项目原 beizi.validate）：
      衣长 80~140cm、肩宽 32~48cm、平铺胸宽 45~75cm、开衩高 25~80cm、
      袖长 45~85cm；开衩高不得超过衣长的 85%；前领深应大于后领深。
    """

    def __init__(self, body, design, tag=''):
        super().__init__(f'Beizi{"_" + tag if tag else ""}')
        self.body = body
        self.design = design
        d = design['beizi']

        # ── 参数 ──
        length = float(d['length']['v']) * body['_leg_length']
        chest_ease = float(d['chest_ease']['v'])
        shoulder_ease = float(d['shoulder_ease']['v'])
        depth_front = float(d['neck_depth_front']['v'])
        depth_back = float(d['neck_depth_back']['v'])
        ahd = float(d['armhole_depth']['v']) * body['shoulder_w']
        slit = float(d['slit_height']['v']) * length
        front_w = float(d['front_opening_width']['v'])
        tab = float(d['front_opening_stop']['v']) * length
        sleeve_len = float(d['sleeve_length']['v']) * body['arm_length']
        root_w = float(d['sleeve_root_width']['v'])
        cuff_w = float(d['sleeve_cuff_width']['v'])
        cap_h = float(d['sleeve_cap_height']['v'])

        # ── 派生几何 ──
        half_w = body['bust'] * chest_ease / 4.0        # 前后片半宽
        neck_half = body['neck_w'] / 2.0
        half_sh = max(body['shoulder_w'] * shoulder_ease / 2.0, neck_half + 3.0)
        # 保证侧缝有长度（开衩不能吃掉整个侧缝）
        side_len = (length - slit) - ahd
        if side_len < 5.0:
            slit = max(0.0, length - ahd - 5.0)
            side_len = 5.0
        tab = max(1.0, min(tab, 0.2 * length))          # 门襟下端连接条

        self.length_cm = length
        self.half_w = half_w
        self.shoulder_w = 2.0 * half_sh
        self.chest_flat = 2.0 * half_w
        self.slit_cm = slit
        self.side_len = side_len
        self.sleeve_len = sleeve_len

        # ── 形制自检 ──
        self.warnings = []
        if not 80.0 <= length <= 140.0:
            self.warnings.append(
                f'衣长 {length:.1f}cm 超出褙子推荐范围 [80, 140]cm')
        if not 32.0 <= 2.0 * half_sh <= 48.0:
            self.warnings.append(
                f'肩宽 {2 * half_sh:.1f}cm 超出推荐范围 [32, 48]cm')
        if not 45.0 <= 2.0 * half_w <= 75.0:
            self.warnings.append(
                f'平铺胸宽 {2 * half_w:.1f}cm 超出推荐范围 [45, 75]cm')
        if not 25.0 <= slit <= 80.0:
            self.warnings.append(
                f'开衩高 {slit:.1f}cm 超出推荐范围 [25, 80]cm'
                f'（褙子形制要求两侧高开衩）')
        elif slit < 0.25 * length:
            self.warnings.append(
                f'开衩高 {slit:.1f}cm < 1/4 衣长（{0.25 * length:.1f}cm），'
                f'高开衩特征不明显')
        if slit > 0.85 * length:
            self.warnings.append(
                f'开衩高 {slit:.1f}cm 超过衣长 {length:.1f}cm 的 85%，裁片结构不稳')
        if not 45.0 <= sleeve_len <= 85.0:
            self.warnings.append(
                f'袖长 {sleeve_len:.1f}cm 超出推荐范围 [45, 85]cm')
        if depth_front <= depth_back:
            self.warnings.append(
                f'前领深 {depth_front:.1f}cm 应大于后领深 {depth_back:.1f}cm'
                f'（形制要求领口前深后浅）')
        if cuff_w > root_w:
            self.warnings.append(
                f'袖口宽 {cuff_w:.1f}cm > 袖肥 {root_w:.1f}cm，褙子直袖不宜外展')
        if side_len <= 8.0:
            self.warnings.append(
                f'侧缝仅 {side_len:.1f}cm（袖窿深 {ahd:.1f}cm 与开衩高 {slit:.1f}cm 挤压），'
                f'结构不稳')

        # ── 裁片 ──
        self.front = BeiziFrontPanel('beizi_front', half_w, half_sh, neck_half,
                                     depth_front, ahd, length, slit, front_w, tab)
        self.back = BeiziBackPanel('beizi_back', half_w, half_sh, neck_half,
                                   depth_back, ahd, length, slit)
        self.sleeve_right = BeiziSleevePanel('beizi_sleeve_right', sleeve_len,
                                             root_w, cuff_w, cap_h)
        self.sleeve_left = BeiziSleevePanel('beizi_sleeve_left', sleeve_len,
                                            root_w, cuff_w, cap_h).mirror()

        # 袖窿 = 前袖窿 + 后袖窿（两段同向相连，袖山缝到整个袖窿圈上）
        armhole_r = pyg.Interface.from_multiple(self.front.interfaces['armhole_r'],
                                                self.back.interfaces['armhole_r'])
        armhole_l = pyg.Interface.from_multiple(self.front.interfaces['armhole_l'],
                                                self.back.interfaces['armhole_l'])

        rules = [
            # 肩缝
            (self.front.interfaces['shoulder_r'], self.back.interfaces['shoulder_r']),
            (self.front.interfaces['shoulder_l'], self.back.interfaces['shoulder_l']),
            # 侧缝（开衩以下不缝 = 开衩）
            (self.front.interfaces['side_r'], self.back.interfaces['side_r']),
            (self.front.interfaces['side_l'], self.back.interfaces['side_l']),
            # 袖山 ↔ 袖窿
            (self.sleeve_right.interfaces['armhole'], armhole_r),
            (self.sleeve_left.interfaces['armhole'], armhole_l),
        ]
        self.stitching_rules = _safe_stitches(self, rules)

        # ── 对外接口 ──
        self.interfaces = {
            'neckline': pyg.Interface.from_multiple(
                self.front.interfaces['neckline_l'],
                self.back.interfaces['neckline'],
                self.front.interfaces['neckline_r']),
            # 对襟门襟（敞开，不缝合）
            'center_front': pyg.Interface.from_multiple(
                self.front.interfaces['center_front_l'],
                self.front.interfaces['center_front_r']),
            'hem': pyg.Interface.from_multiple(
                self.front.interfaces['hem'], self.back.interfaces['hem']),
            'cuff_r': pyg.Interface.from_multiple(self.sleeve_right.interfaces['cuff']),
            'cuff_l': pyg.Interface.from_multiple(self.sleeve_left.interfaces['cuff']),
        }

    def summary(self):
        d = self.design['beizi']
        return (f'褙子（对襟直领）| 衣长 {d["length"]["v"]:.2f}×腿长 = {self.length_cm:.1f}cm | '
                f'平铺胸宽 {self.chest_flat:.1f}cm | 肩宽 {self.shoulder_w:.1f}cm | '
                f'开衩高 {self.slit_cm:.1f}cm | 袖长 {self.sleeve_len:.1f}cm')


# ═══════════════════════════════════════════════════════════════
# 半臂 Banbi
# ═══════════════════════════════════════════════════════════════

class BanbiBackPanel(pyg.Panel):
    """半臂后身片 — 连袖「T 形」裁片（袖与大身连裁），后领窝 + 平下摆。

    闭环：左肩(含左袖顶) → 左袖口 → 左袖底 → 左侧缝 → 下摆
          → 右侧缝 → 右袖底 → 右袖口 → 右肩(含右袖顶) → 后领窝 → (回到左肩)

    连袖结构：肩线自领口一直延伸到袖口外端（x = ±(half_w + ext)），
    袖底缘 = 水平线（y = −sleeve_width），与前后片的对应边缝合即形成袖筒。
    """

    def __init__(self, name, half_w, neck_half, depth_back, sleeve_ext,
                 sleeve_width, length):
        super().__init__(name)
        x_out = half_w + sleeve_ext
        nl, nr = [-neck_half, 0.0], [neck_half, 0.0]
        al, ar = [-x_out, 0.0], [x_out, 0.0]
        bl, br = [-x_out, -sleeve_width], [x_out, -sleeve_width]
        cl, cr = [-half_w, -sleeve_width], [half_w, -sleeve_width]
        dl, dr = [-half_w, -length], [half_w, -length]

        self.edges.append(pyg.Edge(nl, al, label='shoulder_l'))
        self.edges.append(pyg.Edge(al, bl, label='cuff_l'))
        self.edges.append(pyg.Edge(bl, cl, label='sleeve_under_l'))
        self.edges.append(pyg.Edge(cl, dl, label='side_l'))
        self.edges.append(pyg.Edge(dl, dr, label='hem'))
        self.edges.append(pyg.Edge(dr, cr, label='side_r'))
        self.edges.append(pyg.Edge(cr, br, label='sleeve_under_r'))
        self.edges.append(pyg.Edge(br, ar, label='cuff_r'))
        self.edges.append(pyg.Edge(ar, nr, label='shoulder_r'))
        self.edges.append(pyg.CurveEdge(nr, nl,
                                        control_points=[[0.0, -2.0 * depth_back]],
                                        relative=False, label='neckline'))
        self.edges.close_loop()

        self.interfaces = {
            'neckline': pyg.Interface(self, self.edges[9]),
            'shoulder_l': pyg.Interface(self, self.edges[0]),
            'shoulder_r': pyg.Interface(self, self.edges[8]),
            'cuff_l': pyg.Interface(self, self.edges[1]),
            'cuff_r': pyg.Interface(self, self.edges[7]),
            'sleeve_under_l': pyg.Interface(self, self.edges[2]),
            'sleeve_under_r': pyg.Interface(self, self.edges[6]),
            'side_l': pyg.Interface(self, self.edges[3]),
            'side_r': pyg.Interface(self, self.edges[5]),
            'hem': pyg.Interface(self, self.edges[4]),
        }


class BanbiFrontPanel(pyg.Panel):
    """半臂前身片 — 连袖「T 形」裁片 + 交领式前中开襟。

    交领右衽以「前领深 + 前中开襟（门襟线）」表达：门襟缝自前领深点一直
    开到下摆上方 `tab` 处，由一小段连接条收尾，保证前身是单一合法多边形，
    裁剪时沿门襟线剪开即为左右两片襟片（右衽 = 左襟压右襟）。

    闭环：左前领弧 → 门襟左 → 门襟连接条 → 门襟右 → 右前领弧
          → 右肩(含右袖顶) → 右袖口 → 右袖底 → 右侧缝 → 下摆
          → 左侧缝 → 左袖底 → 左袖口 → 左肩 → (回到左前领弧)
    """

    def __init__(self, name, half_w, neck_half, depth_front, sleeve_ext,
                 sleeve_width, length, front_w, tab):
        super().__init__(name)
        gw = front_w
        x_out = half_w + sleeve_ext
        nl, nr = [-neck_half, 0.0], [neck_half, 0.0]
        al, ar = [-x_out, 0.0], [x_out, 0.0]
        bl, br = [-x_out, -sleeve_width], [x_out, -sleeve_width]
        cl, cr = [-half_w, -sleeve_width], [half_w, -sleeve_width]
        dl, dr = [-half_w, -length], [half_w, -length]
        nt_l, nt_r = [-gw / 2.0, -depth_front], [gw / 2.0, -depth_front]
        nb_l, nb_r = [-gw / 2.0, -(length - tab)], [gw / 2.0, -(length - tab)]

        self.edges.append(pyg.CurveEdge(
            nl, nt_l,
            control_points=[[-neck_half * 0.5, -depth_front * 0.6]],
            relative=False, label='neckline_l'))
        self.edges.append(pyg.Edge(nt_l, nb_l, label='center_front_l'))
        self.edges.append(pyg.Edge(nb_l, nb_r, label='center_front_tab'))
        self.edges.append(pyg.Edge(nb_r, nt_r, label='center_front_r'))
        self.edges.append(pyg.CurveEdge(
            nt_r, nr,
            control_points=[[neck_half * 0.5, -depth_front * 0.6]],
            relative=False, label='neckline_r'))
        self.edges.append(pyg.Edge(nr, ar, label='shoulder_r'))
        self.edges.append(pyg.Edge(ar, br, label='cuff_r'))
        self.edges.append(pyg.Edge(br, cr, label='sleeve_under_r'))
        self.edges.append(pyg.Edge(cr, dr, label='side_r'))
        self.edges.append(pyg.Edge(dr, dl, label='hem'))
        self.edges.append(pyg.Edge(dl, cl, label='side_l'))
        self.edges.append(pyg.Edge(cl, bl, label='sleeve_under_l'))
        self.edges.append(pyg.Edge(bl, al, label='cuff_l'))
        self.edges.append(pyg.Edge(al, nl, label='shoulder_l'))
        self.edges.close_loop()

        self.interfaces = {
            'neckline_l': pyg.Interface(self, self.edges[0]),
            'neckline_r': pyg.Interface(self, self.edges[4]),
            'center_front_l': pyg.Interface(self, self.edges[1]),
            'center_front_r': pyg.Interface(self, self.edges[3]),
            'center_front_tab': pyg.Interface(self, self.edges[2]),
            'shoulder_l': pyg.Interface(self, self.edges[13]),
            'shoulder_r': pyg.Interface(self, self.edges[5]),
            'cuff_l': pyg.Interface(self, self.edges[12]),
            'cuff_r': pyg.Interface(self, self.edges[6]),
            'sleeve_under_l': pyg.Interface(self, self.edges[11]),
            'sleeve_under_r': pyg.Interface(self, self.edges[7]),
            'side_l': pyg.Interface(self, self.edges[10]),
            'side_r': pyg.Interface(self, self.edges[8]),
            'hem': pyg.Interface(self, self.edges[9]),
        }


class Banbi(pyg.Component):
    """半臂 — 唐/宋半袖短外衣（连袖裁剪，衣长至腰胯之间）。

    参数来源（design['banbi']）：
      length            衣长（× body['_leg_length']）
      chest_ease        胸围松量比（× body['bust']）
      shoulder_ease     肩宽松量比（× body['shoulder_w']）
      sleeve_length     半袖长（× body['arm_length']，自肩点量至袖口）
      sleeve_width      袖口宽/袖肥（cm，连袖裁片的袖筒宽度）
      neck_depth_front  前领深（cm）  neck_depth_back 后领深（cm）
      front_opening_width / front_opening_stop  门襟缝宽 / 缝止位置

    形制自检（对应 validation/rules 与项目原 banbi.validate）：
      衣长 40~70cm；半袖长 15~35cm 且不得超过衣长的 0.7 倍（半臂短袖特征）。
    """

    def __init__(self, body, design, tag=''):
        super().__init__(f'Banbi{"_" + tag if tag else ""}')
        self.body = body
        self.design = design
        d = design['banbi']

        # ── 参数 ──
        length = float(d['length']['v']) * body['_leg_length']
        chest_ease = float(d['chest_ease']['v'])
        shoulder_ease = float(d['shoulder_ease']['v'])
        sleeve_len = float(d['sleeve_length']['v']) * body['arm_length']
        sleeve_width = float(d['sleeve_width']['v'])
        depth_front = float(d['neck_depth_front']['v'])
        depth_back = float(d['neck_depth_back']['v'])
        front_w = float(d['front_opening_width']['v'])
        tab = float(d['front_opening_stop']['v']) * length

        # ── 派生几何 ──
        half_w = body['bust'] * chest_ease / 4.0
        neck_half = body['neck_w'] / 2.0
        half_sh = max(body['shoulder_w'] * shoulder_ease / 2.0, neck_half + 3.0)
        # 连袖：袖长自肩点量起，故袖片自衣身侧缝再向外伸 ext
        sleeve_ext = sleeve_len - max(0.0, half_w - half_sh)
        if sleeve_ext < 3.0:
            sleeve_ext = 3.0
            self.warnings_extra = [
                '袖长偏短：袖片自衣身侧缝外伸不足 3cm，已按最小外伸量 3cm 兜底']
        else:
            self.warnings_extra = []
        # 保证侧缝有长度
        if length - sleeve_width < 5.0:
            sleeve_width = max(5.0, length - 5.0)
        tab = max(1.0, min(tab, 0.2 * length))

        self.length_cm = length
        self.half_w = half_w
        self.chest_flat = 2.0 * half_w
        self.shoulder_w = 2.0 * half_sh
        self.sleeve_ext = sleeve_ext
        self.sleeve_width = sleeve_width
        # 实际半袖长（自肩点量至袖口）——袖片被兜底加长时以此为准
        self.sleeve_len_actual = (half_w - half_sh) + sleeve_ext
        self.side_len = length - sleeve_width

        # ── 形制自检 ──
        self.warnings = list(self.warnings_extra)
        if not 40.0 <= length <= 70.0:
            self.warnings.append(
                f'衣长 {length:.1f}cm 超出半臂推荐范围 [40, 70]cm'
                f'（半臂衣长通常在腰胯之间）')
        if not 15.0 <= self.sleeve_len_actual <= 35.0:
            self.warnings.append(
                f'半袖长 {self.sleeve_len_actual:.1f}cm 超出推荐范围 [15, 35]cm')
        if self.sleeve_len_actual >= 0.7 * length:
            self.warnings.append(
                f'半袖长 {self.sleeve_len_actual:.1f}cm 接近衣长 '
                f'{length:.1f}cm 的 0.7 倍，不符合半臂短袖特征')
        if self.sleeve_width < 14.0:
            self.warnings.append(
                f'袖口宽 {self.sleeve_width:.1f}cm 偏窄（< 14cm），'
                f'连袖袖筒过紧不便活动')
        if not 1.02 <= chest_ease <= 1.3:
            self.warnings.append(
                f'胸围松量比 {chest_ease:.2f} 不在常见区间 [1.02, 1.30]，'
                f'半臂多作外搭，需在襦衫之外留有富余')
        if depth_front <= depth_back:
            self.warnings.append(
                f'前领深 {depth_front:.1f}cm 应大于后领深 {depth_back:.1f}cm'
                f'（交领形制要求前领深）')
        if self.side_len <= 8.0:
            self.warnings.append(
                f'侧缝仅 {self.side_len:.1f}cm（袖肥 {self.sleeve_width:.1f}cm 挤压），'
                f'结构不稳')

        # ── 裁片（连袖，仅前后两片）──
        self.front = BanbiFrontPanel('banbi_front', half_w, neck_half, depth_front,
                                     sleeve_ext, sleeve_width, length, front_w, tab)
        self.back = BanbiBackPanel('banbi_back', half_w, neck_half, depth_back,
                                   sleeve_ext, sleeve_width, length)

        rules = [
            # 肩缝（含袖顶，连袖的一道通缝）
            (self.front.interfaces['shoulder_r'], self.back.interfaces['shoulder_r']),
            (self.front.interfaces['shoulder_l'], self.back.interfaces['shoulder_l']),
            # 侧缝
            (self.front.interfaces['side_r'], self.back.interfaces['side_r']),
            (self.front.interfaces['side_l'], self.back.interfaces['side_l']),
            # 袖底缝：缝合后形成短袖筒
            (self.front.interfaces['sleeve_under_r'],
             self.back.interfaces['sleeve_under_r']),
            (self.front.interfaces['sleeve_under_l'],
             self.back.interfaces['sleeve_under_l']),
        ]
        self.stitching_rules = _safe_stitches(self, rules)

        # ── 对外接口 ──
        self.interfaces = {
            'neckline': pyg.Interface.from_multiple(
                self.front.interfaces['neckline_l'],
                self.back.interfaces['neckline'],
                self.front.interfaces['neckline_r']),
            'center_front': pyg.Interface.from_multiple(
                self.front.interfaces['center_front_l'],
                self.front.interfaces['center_front_r']),
            'hem': pyg.Interface.from_multiple(
                self.front.interfaces['hem'], self.back.interfaces['hem']),
            'cuff_r': pyg.Interface.from_multiple(
                self.front.interfaces['cuff_r'], self.back.interfaces['cuff_r']),
            'cuff_l': pyg.Interface.from_multiple(
                self.front.interfaces['cuff_l'], self.back.interfaces['cuff_l']),
        }

    def summary(self):
        d = self.design['banbi']
        return (f'半臂（连袖短外衣）| 衣长 {d["length"]["v"]:.2f}×腿长 = '
                f'{self.length_cm:.1f}cm | 半袖长 {self.sleeve_len_actual:.1f}cm | '
                f'袖口宽 {self.sleeve_width:.1f}cm | 平铺胸宽 {self.chest_flat:.1f}cm | '
                f'通袖展宽 {2 * (self.half_w + self.sleeve_ext):.1f}cm')


# ═══════════════════════════════════════════════════════════════
# 工具
# ═══════════════════════════════════════════════════════════════

def _safe_stitches(comp, rules):
    """构建缝合规则；投影失败时降级为「无缝合」并把原因记进 warnings。

    pyg.Stitches 在构造时就会对齐两侧接口（必要时细分裁片边），若两侧
    长度/分段差异过大可能抛错。配饰仍能出纸样，故此处不让它中断组件构建。
    """
    try:
        return pyg.Stitches(*rules)
    except Exception as exc:                                   # noqa: BLE001
        comp.warnings.append(f'缝合规则构建失败，已降级为无缝合（{exc}）')
        return pyg.Stitches()
