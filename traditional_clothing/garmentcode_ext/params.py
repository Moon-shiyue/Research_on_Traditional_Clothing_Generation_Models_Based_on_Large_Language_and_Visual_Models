"""
caption → 参数树映射

对应 Design2GarmentCode 中 DSL-GA 的 `caption2yaml()` 逻辑：
把 LMM 输出的 caption 列表应用到 GarmentCode 参数树上。

caption 格式：`节点路径__子路径__值标签`（用 `__` 分隔）
  例：`mamian-skirt__mamian_width__wide`
      → design['mamian-skirt']['mamian_width']['v'] = 35.0

其中 `wide` 是语义标签，需在参数节点的 `range` 里查到对应数值
（这正是 GarmentCode 参数树需要"文本值版本"的原因：
 让 LMM 输出人类可读的标签，而不是裸数值）。
"""
from __future__ import annotations


def _resolve_value(node: dict, raw: str):
    """把 caption 末段的值标签解析为实际值。

    - 类型还原：None/True/False/int
    - 标签映射：若 range 为 [{标签: 数值}, ...]，查表得数值
    """
    value = raw
    if raw == 'None':
        value = None
    elif raw == 'True':
        value = True
    elif raw == 'False':
        value = False
    elif raw.lstrip('-').isdigit():
        value = int(raw)
    else:
        try:
            value = float(raw)
        except ValueError:
            pass  # 保持字符串（语义标签）

    rng = node.get('range', [])
    if rng and isinstance(rng[0], dict):
        for entry in rng:
            if raw in entry:
                value = entry[raw]
                break
    return value


def caption2design(caption, design: dict, verbose: bool = True):
    """把 caption 列表应用到设计参数树。

    Args:
        caption: caption 列表，如 ['mamian-skirt__mamian_width__wide', ...]
        design:  参数树（即 yaml['design']）
        verbose: 是否打印应用过程

    Returns:
        (design, applied) — 修改后的参数树与应用记录 [(caption, 路径, 值), ...]
    """
    applied = []
    for item in caption:
        parts = item.split('__')
        node = design
        ok = True
        for i, key in enumerate(parts):
            if i == len(parts) - 1:
                if not isinstance(node, dict):
                    ok = False
                    break
                value = _resolve_value(node, key)
                node['v'] = value
                applied.append((item, '__'.join(parts[:-1]), value))
                if verbose:
                    print(f'    {item:<46} → {value}')
            else:
                if not isinstance(node, dict) or key not in node:
                    ok = False
                    break
                node = node[key]
        if not ok and verbose:
            print(f'    ⚠ 跳过（路径不存在）: {item}')
    return design, applied


def design_summary(design: dict, keys=('traditional', 'mamian-skirt')) -> str:
    """打印传统服饰相关参数摘要。"""
    lines = []
    for k in keys:
        if k not in design:
            continue
        node = design[k]
        vals = []
        for sub, subnode in node.items():
            if isinstance(subnode, dict) and 'v' in subnode:
                vals.append(f'{sub}={subnode["v"]}')
        lines.append(f'  {k}: ' + ', '.join(vals))
    return '\n'.join(lines)
