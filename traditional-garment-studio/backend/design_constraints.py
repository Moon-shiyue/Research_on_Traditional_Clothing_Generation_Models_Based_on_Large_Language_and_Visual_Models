"""Display bounds for the current body and other committed garment values.

The renderer remains authoritative. These limits prevent offering a side slit
that reaches above the armhole, or a pipa cuff wider than its sleeve root.
"""
import math
from .whole_catalog import WHOLE, SLEEVED


def constrain_controls(component, values, params, body):
    if component=='chest-wrap':
        coverage=values['front_coverage']['v'];tie=values['tie_length']['v'];bust=float(body['bust'])
        params['tie_length']['range'][0]=max(30.,math.ceil(((bust*(1-coverage))/2+15.)*10-1e-8)/10)
        params['front_coverage']['range'][0]=max(.55,1-2*(tie-15.)/bust)
        params['tie_length']['constraint_note']='需跨过后背未覆盖部分，并为每侧系结留15cm；下限随胸围和覆盖比例更新。'
        params['front_coverage']['constraint_note']=f'当前围前布净宽{bust*coverage:.1f}cm；按人体胸围乘覆盖比例计算，背后保持开敞。'
        return
    if component=='pibo':
        length=values['strip_length']['v'];width=values['strip_width']['v']
        params['strip_length']['range'][0]=max(params['strip_length']['range'][0],math.ceil(2.5*width*10-1e-8)/10)
        params['strip_width']['range'][1]=min(params['strip_width']['range'][1],math.floor(length/2.5*10+1e-8)/10)
        params['strip_length']['constraint_note']='净长至少为幅宽的2.5倍；四边工艺余量另加，尺寸不随人体自动缩放。'
        params['strip_width']['constraint_note']='这里只支持长条直幅；宽幅披肩不能以此款替代。'
        return
    if component not in WHOLE:return
    d={key:node['v'] for key,node in values.items()}
    leg=body['_leg_length'];length=d['length']*leg
    a=(max(16.,min(27.,body['armscye_depth']+2.)) if component=='bijia'
       else max(16.,min(25.,body['armscye_depth'])))

    def maximum(field,value,note):
        item=params[field]
        item['range'][1]=max(item['range'][0],min(item['range'][1],value))
        item['constraint_note']=note

    def minimum(field,value,note):
        item=params[field]
        item['range'][0]=min(item['range'][1],max(item['range'][0],value))
        item['constraint_note']=note

    slit_max=max(0.,math.floor((length-a-3.+1e-8)*10)/10)
    maximum('side_slit',slit_max,'侧衩上端至少低于袖窿3cm；上限随当前衣长和人体更新。')
    needed=max(a+(d['side_slit']+3. if d['side_slit'] else 3.),d['neck_depth_front']+3.)
    minimum('length',needed/leg,'最短衣长受当前领深、袖窿和侧衩限制；缩短前可先减小侧衩。')
    if component not in SLEEVED:return
    w=max(body['bust']*d['chest_ease']/4,body['hips']/4+1. if component.endswith('robe') else 0.)
    dropped=max(0.,w-body['shoulder_w']/2)
    minimum('sleeve_length',(dropped+d['cuff_band_height']+3.)/body['arm_length'],
            '袖长包含落肩和袖口条，须保留至少3cm袖身；下限随当前胸围与袖口条更新。')
    if component.startswith('cross'):
        maximum('overlap',math.floor((w-.1)*10)/10,'搭襟宽须小于当前半身宽，按当前人体和胸围松量限制。')
    if d['sleeve_type']==1:
        maximum('sleeve_cuff_width',math.floor((2*a-.1)*10)/10,
                '琵琶袖需要从袖根收向较小袖口；上限随当前人体袖窿更新。')
    elif d['sleeve_cuff_width']>=2*a:
        params['sleeve_type']['option_disabled']={1:True}
        params['sleeve_type']['constraint_note']=f'选择琵琶袖前，请先把袖口整围调到{2*a:.1f}cm以下。'
