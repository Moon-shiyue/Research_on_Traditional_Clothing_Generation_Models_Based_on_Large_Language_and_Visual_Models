"""Validate actual cutting curves and attachment lengths before exporting.

The contour test samples curves. It cannot certify physical fit or every
possible mathematical intersection between sample points.
"""
from collections import Counter
import math

import numpy as np

from .traditional_templates import curve_for, valid_outline


def validate_geometry(pattern, construction=None, assembly=None):
    paths={name:curve_for(pattern,name) for name in pattern.pattern['panels']}
    if not paths:
        raise ValueError('裁片为空，请调整组件或尺寸。')
    for name,path in paths.items():
        points=[]
        for segment in path:
            length=float(segment.length())
            if not math.isfinite(length) or length < 1e-7:
                raise ValueError('裁片含退化边，请调整尺寸：'+name)
            count=max(3,min(120,int(length)+3))
            points += [(segment.point(t).real,segment.point(t).imag)
                       for t in np.linspace(0,1,count,endpoint=False)]
        if not valid_outline(points):
            raise ValueError('裁片轮廓退化或自交，请调整尺寸：'+name)
    c=construction or {}
    folded=c.get('version')=='mamian-overlap-v2'
    if folded:
        mapping=c['fold_map']
        segments=list(zip(mapping,mapping[1:]))
        if (not segments or any(q[0]<=p[0] or abs((q[0]-p[0])-abs(q[1]-p[1]))>1e-6 for p,q in segments)
            or abs(sum(abs(q[1]-p[1]) for p,q in segments)-c['side_flat_width'])>1e-6
            or abs(mapping[-1][1]-mapping[0][1]-c['side_folded_width'])>1e-6):
            raise ValueError('马面裙褶位收量与平铺布宽不一致，请调整参数。')
    refs=Counter()
    max_error=0.
    folded_checked=0
    for pair in pattern.pattern.get('stitches',[]):
        lengths=[]
        for ref in pair[:2]:
            name,index=ref['panel'],ref['edge']
            if name not in paths or type(index) is not int or not 0<=index<len(paths[name]):
                raise ValueError('裁片缝合引用无效，请重新生成。')
            length=float(paths[name][index].length())
            if folded and name.startswith('mamian_width_') and index==1:
                if abs(length-c['side_flat_width'])>1e-6:
                    raise ValueError('马面裙褶区裁片宽度与折褶记录不一致。')
                length=c['side_folded_width']
                folded_checked+=1
            lengths.append(length)
            refs[(name,index)]+=1
        if len(lengths)!=2:
            raise ValueError('裁片缝合记录缺少一侧，请重新生成。')
        max_error=max(max_error,abs(lengths[0]-lengths[1]))
    if max_error>.02:
        raise ValueError(f'缝合边长不匹配（最大差{max_error:.3f}cm），请调整参数。')
    layered={(item['panel'],item['edge']):item['layers'] for item in (assembly or {}).get('layered_seams',[])}
    if folded:
        item=c['layered_seam']
        layered[(item['panel'],item['edge'])]=2
    duplicates={ref:count for ref,count in refs.items() if count>1}
    if any(layered.get(ref)!=count for ref,count in duplicates.items()):
        raise ValueError('检测到未经声明的多层缝合，请检查连接关系。')
    return {'sampled_outline_valid':True,'checked_panels':len(paths),
        'max_seam_length_difference_cm':max_error,'folded_seams_checked':folded_checked,
        'declared_layered_seams':len(duplicates),
        'scope':'sampled flat outlines and attachment lengths; not physical sewing or fit validation'}
