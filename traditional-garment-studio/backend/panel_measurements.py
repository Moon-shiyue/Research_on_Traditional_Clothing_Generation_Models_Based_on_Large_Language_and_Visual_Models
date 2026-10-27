"""Human-readable net-piece bounds from the same curves used in SVG export."""
import re


def panel_label(name,index):
    if name=='chest_wrap_front':return '抹胸围前布'
    if name.startswith('chest_wrap_tie_'):return '抹胸后背系带'+name.rsplit('_',1)[1]
    if name=='pibo_strip':return '披帛整幅'
    known={'mamian_width_a':'裙身 A（含褶区）','mamian_width_b':'裙身 B（含褶区）',
        'mamian_waistband':'马面裙腰头及系带','ruqun_waistband':'下裙腰头',
        'ruqun_tie_left':'下裙左系带','ruqun_tie_right':'下裙右系带',
        'cloud_neck_binding':'云肩领口包边','cross_collar_back':'交领后领贴'}
    if name in known:
        return known[name]
    match=re.fullmatch(r'ruqun_gore_(\d+)',name)
    if match:
        return '下裙第'+str(int(match[1]))+'幅'
    match=re.fullmatch(r'cloud_layer_(\d+)',name)
    if match:
        return '云肩第'+str(int(match[1]))+'层'
    from .whole_catalog import NAMES
    for prefix,title in [('beizi','褙子'),('banbi','半臂')]+list(NAMES.items()):
        if name.startswith(prefix+'_'):
            part=name[len(prefix)+1:]
            translated={'back':'后身','front_left':'左前身','front_right':'右前身',
                'sleeve_left':'左袖','sleeve_right':'右袖','neck_front_facing':'领襟贴边',
                'tie_left':'左系带','tie_right':'右系带','neck_binding':'领片',
                'under_neck_binding':'内搭襟领片','opening_facing':'斜襟贴边',
                'belt':'腰带',
                'cuff_left':'左袖口条','cuff_right':'右袖口条',
                'placket_left':'左门襟贴','placket_right':'右门襟贴',
                'armhole_binding_left':'左袖窿包边条','armhole_binding_right':'右袖窿包边条',
                **{'tie_'+str(i):'系带'+str(i) for i in range(1,5)}}.get(part)
            if translated:
                return title+translated
    for prefix,title in [('stand_collar','立领'),('round_collar','圆领'),
        ('cross_collar','交领'),('duijin','对襟领'),('wide_sleeve','广袖'),
        ('narrow_sleeve','窄袖'),('pipa_sleeve','琵琶袖')]:
        if name.startswith(prefix+'_'):
            part=name[len(prefix)+1:]
            if part in {'left','left_front','right','right_front'}:
                return title+('左片' if part.startswith('left') else '右片')
    return '裁片'+str(index+1)


def measure_panels(pattern):
    rows=[]
    for index,name in enumerate(sorted(pattern.pattern['panels'])):
        curve=pattern._draw_a_panel(name,apply_transform=False,fill=False)[0]
        x0,x1,y0,y1=curve.bbox()
        rows.append({'panel_id':name,'label':panel_label(name,index),
            'width_cm':round(float(x1-x0),8),'height_cm':round(float(y1-y0),8),'units':'cm'})
    return rows
