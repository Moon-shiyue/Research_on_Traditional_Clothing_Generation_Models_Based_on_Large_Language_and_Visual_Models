"""traditional_ext — 传统服饰 GarmentCode 扩展模块

用 pygarment 原生 API 实现传统服饰部件，并把传统服饰参数挂进
GarmentCode 的参数树（可被 caption / 多模态模型控制）。

模块：
  params.py        caption → 参数树映射（对应 D2GC 的 caption2yaml）
  mamian_skirt.py  马面裙组件（马面 + 褶裥侧片 + 腰头）
  demo.py          完整链路演示
"""
