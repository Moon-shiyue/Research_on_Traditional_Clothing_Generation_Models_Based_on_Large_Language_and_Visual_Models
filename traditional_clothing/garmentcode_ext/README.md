# GarmentCode 扩展模块（传统服饰领域适配）

本目录是把**传统服饰领域知识**接入 GarmentCode/pygarment 引擎的扩展实现，
对应技术路线 A（零训练路线）的组件层与数据层。

> 这些文件在开发时位于 `GarmentCode/traditional_ext/`（GarmentCode 仓库内），
> 此处为项目侧备份。使用时请复制回 GarmentCode 仓库：
>
> ```bash
> # 1. 获取 GarmentCode
> git clone https://github.com/maria-korosteleva/GarmentCode.git
> cd GarmentCode && pip install -e . && python test_garmentcode.py   # 验证环境
> # 2. 复制本目录到 GarmentCode/traditional_ext/
> # 3. 复制 traditional.yaml 到 GarmentCode/assets/design_params/
> # 4. 运行演示
> python traditional_ext/demo_aoqun.py      # 明代袄裙三件套
> python traditional_ext/build_dataset.py   # 构建微调数据集
> ```

## 📦 文件说明

| 文件 | 作用 |
|------|------|
| `traditional.yaml` | ⭐ **扩展参数树**：在 GarmentCode 官方参数树上新增 `traditional`（形制元信息）与 12 个组件的参数节点，range 采用「语义标签: 数值」形式便于 LMM 输出标签 |
| `params.py` | ⭐ **caption → 参数树映射**（复刻 D2GC 的 `caption2yaml`）：把 `mamian-skirt__mamian_width__wide` 这类路径标签解析为参数值 |
| **组件（pygarment 原生实现）** | |
| `mamian_skirt.py` | 马面裙（前/后马面 + 左/右褶裥侧片 + 腰头，**褶裥用 `Interface(ruffle=)` 表达**） |
| `collars.py` | 立领 |
| `collars_extra.py` | 交领（右衽三片式）/ 圆领 / 对襟 |
| `sleeves.py` | 琵琶袖（贝塞尔曲线琵琶形轮廓） |
| `sleeves_extra.py` | 广袖 / 窄袖 |
| `skirts_extra.py` | 襦裙（梯形裙片 + 腰头系带） |
| `accessories.py` | 云肩（整环云头片）/ 褙子（对襟开衩长外衣）/ 半臂（平裁连袖） |
| **工具** | |
| `exporter.py` | ⭐ **专业纸样导出器**：中文标签 + 布纹线 + 尺寸/面积标注 + 首次适应装箱排版 + **贝塞尔曲线渲染**（解析 `edge['curvature']`） |
| `export.py` | 平铺预览导出（`get_svg(flat=True)`，解决官方 `_pattern.png` 裁片重叠问题） |
| `build_dataset.py` | ⭐ **数据集构建**：枚举合法参数 → 真实生成纸样验证 → 生成说明/caption/配置/代码 |
| `demo.py` / `demo_aoqun.py` | 演示脚本 |

## 🎯 12 个组件（全部完成）

| 类别 | 组件 | pygarment 类 | 裁片数 |
|------|------|-------------|--------|
| 领型 | 交领（右衽） | `CrossCollar` | 3 |
| 领型 | 圆领 | `RoundCollar` | 1 |
| 领型 | 立领 | `StandCollar` | 2 |
| 领型 | 对襟 | `DuijinCollar` | 2 |
| 袖型 | 广袖 | `WideSleeve` | 2 |
| 袖型 | 窄袖 | `NarrowSleeve` | 2 |
| 袖型 | 琵琶袖 | `PipaSleeve` | 2 |
| 下裳 | 襦裙 | `RuqunSkirt` | 3 |
| 下裳 | 马面裙 | `MamianSkirt` | 5 |
| 配饰 | 云肩 | `CloudShoulder` | 2–3 |
| 配饰 | 褙子 | `Beizi` | 4 |
| 配饰 | 半臂 | `Banbi` | 2 |

## 🔑 关键技术点

### 1. 褶裥用 `ruffle` 表达（重要简化）
GarmentCode 的 `Interface(panel, edge, ruffle=比值)` 用「展开宽/收拢宽」表达褶裥，
**无需手工计算每个褶位的坐标**（对比自研实现里的 `internal_lines` 逐褶标记）：

```python
top=pyg.Interface(self, self.edges[0], ruffle=ruffle).reverse(True)
```

### 2. 参数必须归一化
```python
length = design['mamian-skirt']['length']['v'] * body['_leg_length']   # 0.85 × 82.3 = 69.9cm
```
这是参数树能适配不同体型、也是 LMM 能通过 caption 控制的前提。

### 3. 贝塞尔曲线边的写法与渲染
```python
pyg.CurveEdge(start, end,
    control_points=[[cx1, cy1], [cx2, cy2]],   # 1 个=二次，2 个=三次
    relative=False, label='neckline')
```
导出纸样时曲线存在 `edge['curvature'] = {'type': 'cubic', 'params': [[...]]}`（**相对边长归一化**），
`exporter.py` 实现 `rel_to_abs_2d` 等价转换后转成 SVG `C` 命令，曲线才平滑。

### 4. y 轴约定
组件内部统一 **`y 负方向 = 向下`**（与 GarmentCode 官方组件一致），
`exporter.py` 导出时翻转 y，使裁片起点（袖根/腰口）显示在上方。

## ⚙️ 环境依赖

- Python 3.13（Anaconda）+ `pygarment`（`pip install -e .` 安装 GarmentCode 本体）
- 额外依赖：`svgpathtools`、`svgwrite`、`scipy`、`psutil`、`CairoSVG`
- **cairo DLL 问题**：pygarment 自带 Windows 版 cairo 运行时（`pygarment/pattern/cairo_dlls/`），
  但它只在 `wrappers.py` 被导入时写入 PATH。`exporter.py` 顶部显式添加该目录，
  否则 `import cairosvg` 会抛 `OSError: no library called "cairo-2"`。

## 📊 数据集产出

`build_dataset.py` 产出 **2,140 条**微调样本（12 组件 × 参数枚举 × 形制上下文），
每条含：中文制版说明（3 句式）× caption（D2GC 路径标签）× 设计配置 × 目标代码 × 纸样统计，
**100% 可执行**（真实调用 `assembly()` 验证过）。

数据集位于 `../data/annotations/traditional_design_dataset.jsonl`，
数据卡见 `../data/annotations/README_traditional_design_dataset.md`。

## 📚 参考

- [GarmentCode](https://github.com/maria-korosteleva/GarmentCode)（SIGGRAPH Asia 2023）— 参数化纸样 DSL 与 pygarment 引擎
- [Design2GarmentCode](https://style3d.github.io/design2garmentcode/)（CVPR 2025, arXiv:2412.08603）— 微调数据构造方法（§3.2.1 Program Learning）与双 Agent 架构
