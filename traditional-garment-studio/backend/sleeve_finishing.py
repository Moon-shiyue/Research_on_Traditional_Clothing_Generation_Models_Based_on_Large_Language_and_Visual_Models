"""Application assembly cues for existing single-piece sleeve nets.

The sleeve root is left free for fitting to a separately drafted upper body.
No assumption is made about which full garment the sleeve belongs to.
"""
PAIRS={
    'pipa-sleeve':[('top_to_bulge','bottom_to_root'),('top_to_cuff','bottom_to_bulge')],
    'wide-sleeve':[('right_top','left_top'),('flare_r','flare_l')],
    'narrow-sleeve':[('right_top','left_top'),('right_low','left_low')],
}


def finish_sleeves(pattern,component):
    if component not in PAIRS:
        return []
    if pattern.pattern.get('stitches'):
        raise ValueError('袖片已有连接记录，不能重复添加袖底缝。')
    seams=[]
    marks=list(pattern.pattern.get('drafting_marks',[]))
    for name,panel in pattern.pattern['panels'].items():
        labels={edge['label']:index for index,edge in enumerate(panel['edges'])}
        for first,second in PAIRS[component]:
            seams.append([{'panel':name,'edge':labels[first]},
                          {'panel':name,'edge':labels[second]}])
        def midpoint(label):
            edge=panel['edges'][labels[label]]
            a,b=(panel['vertices'][index] for index in edge['endpoints'])
            return [(a[0]+b[0])/2,(a[1]+b[1])/2]
        marks.append({'panel':name,'kind':'fold','start':midpoint('armhole'),'end':midpoint('cuff')})
    pattern.pattern['stitches']=seams
    pattern.pattern['drafting_marks']=marks
    return ['左右袖片各沿中线对折，再缝合两段等长袖底边；袖口和袖根保持开口。',
            '当前只输出独立袖片，袖根需与目标衣身袖窿另行试配；折线不代表裁剪线。']
