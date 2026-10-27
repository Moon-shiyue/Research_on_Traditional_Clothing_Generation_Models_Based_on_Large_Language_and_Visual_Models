"""Open neckline facings with regular, non-overlapping cutting boundaries.

These adjustable engineering basics describe only collar/facing pieces. They
are not complete crossed/open-front garments or measured historical replicas.
"""
import math

def offset_strip(start, end, tip, width, normal_sign):
    """Constant-width band around a rounded two-line neckline.

    A circular fillet keeps both contours smooth and concentric. Its inner
    radius exceeds the band width, so a wide border cannot create an offset
    cusp. End caps are exactly ``width`` and join the rear facing at that size.
    """
    def xy(z):
        return [float(z.real),float(z.imag)]
    first,corner,last=complex(*start),complex(*end),complex(*tip)
    a,b=corner-first,last-corner
    if min(abs(a),abs(b)) < 1e-6:
        raise ValueError('前领延伸长度必须大于零。')
    u,v=a/abs(a),b/abs(b)
    turn=math.atan2((u.conjugate()*v).imag,(u.conjugate()*v).real)
    offset=normal_sign*1j*width
    if abs(turn) < 1e-5:
        return [xy(first),xy(last),xy(last+offset*v),xy(first+offset*u)],{},3
    radius=width+1.
    cut=radius*math.tan(abs(turn)/2)
    if cut >= .8*min(abs(a),abs(b)):
        raise ValueError('领缘宽度与领深、转角不相容，请减小领缘宽或增加领深。')
    enter,leave=corner-u*cut,corner+v*cut
    outside_radius=radius-normal_sign*(1 if turn>0 else -1)*width
    k=4/3*math.tan(abs(turn)/4)
    outside_enter,outside_leave=enter+offset*u,leave+offset*v
    points=[xy(first),xy(enter),xy(leave),xy(last),xy(last+offset*v),
            xy(outside_leave),xy(outside_enter),xy(first+offset*u)]
    controls={1:[xy(enter+u*k*radius),xy(leave-v*k*radius)],
              5:[xy(outside_leave-v*k*outside_radius),xy(outside_enter+u*k*outside_radius)]}
    return points,controls,len(points)-1


def cross_collar(body,design,piece,new_pattern,seam):
    d=design['cross-collar']
    half=float(body['neck_w'])/2+float(d['collar_width']['v'])*.15
    depth=float(d['collar_depth']['v'])
    angle=math.radians(float(d['cross_angle']['v'])/2)
    overlap=float(d['overlap_amount']['v'])
    border=float(d['border_width']['v'])
    back_depth=float(d['back_neck_depth']['v'])
    if min(half,depth,border,back_depth) <= 0:
        raise ValueError('交领尺寸必须为正数。')
    pattern=new_pattern('cross-collar')
    panels=pattern.pattern['panels']
    free=[]
    cap_refs=[]
    for side,sign,is_outer in [('left',1,True),('right',-1,False)]:
        neck=[0.,-depth*.35]
        extension=depth*.65+(overlap*.6 if is_outer else 0.)
        direction=complex(math.sin(angle),-math.cos(angle))
        tip=[extension*direction.real,neck[1]+extension*direction.imag]
        points,controls,cap=offset_strip([-half,0.],neck,tip,border,-1)
        name='cross_collar_'+side+'_front'
        panels[name]=piece([[sign*x,y] for x,y in points],
            {i:[[sign*x,y] for x,y in cs] for i,cs in controls.items()})
        cap_refs.append((name,cap))
        free += [{'panel':name,'edge':i,'reason':'free neckline or facing boundary'} for i in range(cap)]
    back='cross_collar_back'
    panels[back]=piece([[-half,0.],[half,0.],[half,border],[-half,border]],
        {0:[[-half*.5,-4*back_depth/3],[half*.5,-4*back_depth/3]],
         2:[[half*.5,border-4*back_depth/3],[-half*.5,border-4*back_depth/3]]})
    seam(pattern,cap_refs[0],(back,3))
    seam(pattern,cap_refs[1],(back,1))
    free += [{'panel':back,'edge':i,'reason':'free neckline or facing boundary'} for i in (0,2)]
    return pattern,{'version':'open-collar-facings-2026-10-21','component':'cross-collar',
        'variant':'crossed-front-neck-facing','variant_label':'交领右衽领贴基础款',
        'source_ids':[],'units':'cm','neck_half_width':half,'collar_depth':depth,
        'cross_angle_degrees':math.degrees(angle)*2,'overlap_parameter':overlap,
        'border_width':border,'free_edges':free,'simulation_supported':False,
        'notes':['当前仅输出交叉领贴及后领贴，不含左右交叠衣身、系带、袖片或整件上衣。',
            '内侧保持真实领口空区；左右前领末端一长一短，作为右衽交叠的定位示意。',
            '领贴短边均按领缘宽度配长，后领贴曲深为工程默认值；需按目标衣身领圈试配。',
            '偏移曲线为参数化基础款；未测量复原某件馆藏服饰，净样未加缝份。']}


def duijin_collar(body,design,piece,new_pattern):
    d=design['duijin-collar']
    front=float(d['front_width']['v'])
    depth=float(d['neck_depth']['v'])
    border=float(d['placket_width']['v'])
    height=float(d['placket_height']['v'])
    if min(front,depth,border,height) <= 0:
        raise ValueError('对襟领贴尺寸必须为正数。')
    pattern=new_pattern('duijin-collar')
    free=[]
    for side,sign in [('right',1),('left',-1)]:
        points,controls,cap=offset_strip([front,0.],[0.,-depth],[0.,-depth-height],border,1)
        name='duijin_'+side+'_front'
        pattern.pattern['panels'][name]=piece([[sign*x,y] for x,y in points],
            {i:[[sign*x,y] for x,y in cs] for i,cs in controls.items()})
        free += [{'panel':name,'edge':i,'reason':'separate open front facing'} for i in range(cap+1)]
    return pattern,{'version':'open-collar-facings-2026-10-21','component':'duijin-collar',
        'variant':'separate-open-front-facings','variant_label':'对襟前领贴基础款',
        'source_ids':[],'units':'cm','front_width':front,'neck_depth':depth,
        'placket_width':border,'placket_extension':height,'free_edges':free,'simulation_supported':False,
        'notes':['仅输出左右独立前领襟贴，不包含后领、衣身或整件上衣。',
            '两前襟保持分离，领口内侧留空；不把领口填成三角布片或将前襟缝死。',
            '门襟下延与肩端连接需按目标衣身配合；当前为无立起量的平面领贴净样。',
            '领襟外缘以法线偏移形成，不沿肩端重复折返；未复原某件馆藏服饰。']}
