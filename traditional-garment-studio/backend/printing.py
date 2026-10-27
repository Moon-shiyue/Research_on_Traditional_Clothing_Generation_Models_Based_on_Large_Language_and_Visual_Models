"""Actual-size net patterns on overlapping A4 sheets; never a fitted preview."""
import copy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import threading
from xml.etree import ElementTree as ET

from svgpathtools import parse_path

from .body_layout import tag


VERSION='a4-net-v3'
CM=72/2.54
PAGE_CM=(21.,29.7)
PLOT_CM=(1.5,2.,18.,25.2)
OVERLAP_CM=.5
# Dimension text sits 1.3cm outside a net and also has its own glyph width.
# Keep it inside the source canvas before tile clipping/optional rotation.
PADDING_CM=3.
MAX_PAGES=600
_font_lock=threading.Lock()
_font=None


def _read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _count(length,window):
    return max(1,math.ceil((length-OVERLAP_CM-1e-9)/(window-OVERLAP_CM)))


def _members(folder):
    meta=_read(folder/'metadata.json')
    if meta['component']=='outfit':
        return [(folder/g['id'],g['id'],g['name']) for g in meta['garments']]
    return [(folder,'','')]


def _templates(folder):
    templates=[]
    for member,prefix,name in _members(folder):
        meta=_read(member/'metadata.json')
        geometry=_read(member/'pattern.json')
        if not meta.get('panel_measurements'):
            raise ValueError('这份旧纸样缺少裁片尺寸，请重新生成后打印。')
        table={r['panel_id']:r for r in meta['panel_measurements']}
        root=ET.parse(member/'pattern-dimensions.svg').getroot()
        groups=root.findall(tag('g'))
        names=sorted(geometry['panels'])
        if len(groups)!=len(names):
            raise ValueError('制版SVG与裁片清单不一致，不能生成打印文件。')
        gores={}
        for panel,group in zip(names,groups):
            group=copy.deepcopy(group)
            path=group.find(tag('path'))
            if path is None:
                raise ValueError('裁片缺少轮廓，不能生成打印文件。')
            x0,x1,y0,y1=parse_path(path.attrib['d']).bbox()
            row=table[panel]
            if abs(x1-x0-row['width_cm'])>1e-5 or abs(y1-y0-row['height_cm'])>1e-5:
                raise ValueError('打印轮廓与裁片尺寸不一致。')
            ident=(prefix+'__' if prefix else '')+panel
            item={'panel_id':ident,'panel_ids':[ident],'garment':name,'label':row['label'],
                  'width_cm':x1-x0,'height_cm':y1-y0,'cut_count':1,
                  '_group':group,'_bbox':(x0,x1,y0,y1)}
            # Only the documented six identical gores share a paper template.
            # Mamian panels retain their distinct construction/door markings.
            if meta['component']=='ruqun-skirt' and panel.startswith('ruqun_gore_'):
                # Position in the 3D arrangement does not change a cutting net.
                flat={k:v for k,v in geometry['panels'][panel].items() if k not in {'translation','rotation'}}
                visible=copy.deepcopy(group)
                visible.attrib.pop('transform',None)
                key=(json.dumps(flat,sort_keys=True),ET.tostring(visible,encoding='utf-8'))
                if key in gores:
                    old=gores[key]
                    old['panel_ids'].append(ident)
                    old['cut_count']+=1
                    continue
                gores[key]=item
            templates.append(item)
    return templates


def print_plan(folder):
    """Cheap plan: cm geometry and sheet count, no PDF dependencies or writes."""
    folder=Path(folder)
    items=_templates(folder)
    page=2  # page one is a calibration/instruction sheet
    for item in items:
        width=item['width_cm']+2*PADDING_CM
        height=item['height_cm']+2*PADDING_CM
        normal=_count(width,PLOT_CM[2])*_count(height,PLOT_CM[3])
        rotated=_count(height,PLOT_CM[2])*_count(width,PLOT_CM[3])
        rotation=90 if rotated<normal else 0
        if rotation:width,height=height,width
        columns=_count(width,PLOT_CM[2]); rows=_count(height,PLOT_CM[3])
        item.update(columns=columns,rows=rows,pages=columns*rows,
                    rotation_degrees=rotation,
                    first_page=page,last_page=page+columns*rows-1,
                    paper_width_cm=width,paper_height_cm=height)
        page+=columns*rows
    if page-1>MAX_PAGES:
        raise ValueError('当前纸样的A4分幅超过600页，请缩小尺寸或分别导出组件。')
    meta=_read(folder/'metadata.json')
    panels=[{k:v for k,v in item.items() if not k.startswith('_')} for item in items]
    if sum(p['cut_count'] for p in panels)!=meta['panel_count']:
        raise ValueError('打印份数与实际裁片数量不一致。')
    return {'version':VERSION,'paper':'A4','page_width_cm':21.,'page_height_cm':29.7,
            'scale':1.,'units':'cm','plot_width_cm':PLOT_CM[2],'plot_height_cm':PLOT_CM[3],
            'overlap_cm':OVERLAP_CM,'page_count':page-1,'calibration_pages':1,
            'fabric_panel_count':meta['panel_count'],'paper_template_count':len(items),
            'seam_allowance_included':False,'panels':panels,
            'notes':['按100%或实际大小打印，关闭适应纸张。先检查首页10cm校准框。',
                     '净样不含缝份；仅同一裁片的相邻页按5mm重叠拼接。',
                     '同形裙幅只打印一套，按标明份数裁布；不同裁片之间不拼接。',
                     '部分纸样旋转90°以减少纸张，尺寸和原有标记保持不变。']}


def _font_choice():
    global _font
    with _font_lock:
        if _font is not None:
            return _font
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        candidates=[Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/msyh.ttc',
                    Path('/usr/share/fonts/truetype/noto/NotoSansSC-Regular.ttf')]
        for path in candidates:
            if path.is_file():
                try:
                    pdfmetrics.registerFont(TTFont('GarmentPrint',str(path),subfontIndex=0))
                    _font=('GarmentPrint',True)
                    return _font
                except (ValueError,KeyError,IOError):
                    continue
        _font=('Helvetica',False)
        return _font


def _cover(canvas,plan,body,font,chinese):
    def line(y,cn,en,size=11):
        canvas.setFont(font,size)
        canvas.drawString(1.6*CM,y*CM,cn if chinese else en)
    line(27.8,'传统服饰 A4 分幅净样','Traditional garment - A4 sewing nets',18)
    line(26.6,f'{plan["fabric_panel_count"]}片裁布 / {plan["paper_template_count"]}套纸样 / 共{plan["page_count"]}页',
         f'{plan["fabric_panel_count"]} fabric pieces / {plan["paper_template_count"]} templates / {plan["page_count"]} pages')
    line(25.5,f'人体参考：身高{body["height"]:.1f}cm，胸围{body["bust"]:.1f}cm，腰围{body["waist"]:.1f}cm',
         f'Body reference: height {body["height"]:.1f}cm / bust {body["bust"]:.1f}cm / waist {body["waist"]:.1f}cm',10)
    for y,cn,en in [
        (23.8,'1. 选择100%或实际大小，关闭“适应纸张”。','1. Print at 100% / Actual size. Disable Fit to page.'),
        (22.7,'2. 先量下方方框：横、竖均应为10cm。','2. Measure the calibration square: both sides must be 10cm.'),
        (21.6,'3. 按裁片编号及行列号拼接，同一裁片相邻页重叠5mm。','3. Join sheets of ONE template by row/column, with 5mm overlap.'),
        (20.5,'4. 对齐十字和图线，裁去页框外空白。不同裁片不要拼在一起。','4. Align crosses/lines and trim outside the frame. Do not join different pieces.'),
        (19.4,'5. 本文件是净样，不含缝份。另核工艺后再裁布。','5. These are net patterns, WITHOUT seam allowance. Check before cutting.'),
        (18.3,'6. 标明“裁布6片”的同形裙幅，只需打印一套后重复裁布。','6. If a template says Cut 6, print it once and cut six fabric pieces.')]:
        line(y,cn,en,9.5)
    line(16.7,'10cm × 10cm 校准框','10cm x 10cm calibration square',12)
    canvas.setLineWidth(.7)
    canvas.rect(2*CM,5*CM,10*CM,10*CM,stroke=1,fill=0)
    canvas.setFont(font,10)
    canvas.drawCentredString(7*CM,4.4*CM,'10 cm')
    canvas.saveState(); canvas.translate(1.4*CM,10*CM); canvas.rotate(90)
    canvas.drawCentredString(0,0,'10 cm'); canvas.restoreState()
    line(2.8,'首页不用拼接。页码与裁片范围见后续每页页眉。','This guide sheet is not a pattern tile. Tile IDs appear on every sheet.',9)
    line(1.7,'二维基础款；未做实体试缝或合体性验证。','2D basic templates; not a physical sewing or fit certification.',9)


def _cross(canvas,x,y):
    canvas.line((x-.15)*CM,y*CM,(x+.15)*CM,y*CM)
    canvas.line(x*CM,(y-.15)*CM,x*CM,(y+.15)*CM)


def _tile_overlay(canvas,item,row,column,page,total,font,chinese):
    x,y,w,h=PLOT_CM
    canvas.setFont(font,11)
    title=' · '.join(filter(None,[item['garment'],item['label']])) if chinese else item['panel_id']
    canvas.drawString(x*CM,28.7*CM,title[:70])
    canvas.setFont(font,8.5)
    status=(f'第{row+1}行 / {column+1}列  ·  裁布{item["cut_count"]}片  ·  净样不含缝份'
            if chinese else f'Row {row+1} / Column {column+1}  |  Cut {item["cut_count"]}  |  No seam allowance')
    if item['rotation_degrees']:
        status+='  ·  旋转90°' if chinese else '  |  Rotated 90deg'
    canvas.drawString(x*CM,27.7*CM,status)
    canvas.setLineWidth(.45)
    canvas.rect(x*CM,y*CM,w*CM,h*CM,stroke=1,fill=0)
    canvas.setStrokeColorRGB(.4,.4,.4)
    if column>0:
        for dy in [.5,h-.5]:_cross(canvas,x+OVERLAP_CM/2,y+dy)
    if column+1<item['columns']:
        for dy in [.5,h-.5]:_cross(canvas,x+w-OVERLAP_CM/2,y+dy)
    if row>0:
        for dx in [.5,w-.5]:_cross(canvas,x+dx,y+h-OVERLAP_CM/2)
    if row+1<item['rows']:
        for dx in [.5,w-.5]:_cross(canvas,x+dx,y+OVERLAP_CM/2)
    canvas.setStrokeColorRGB(0,0,0)
    canvas.setFont(font,7)
    canvas.drawString(x*CM,1.35*CM,item['panel_id'])
    canvas.drawString(x*CM,.85*CM,f'R{row+1}C{column+1} / {item["rows"]}x{item["columns"]} | 100% | overlap 5mm')
    canvas.drawRightString((x+w)*CM,.85*CM,f'{page} / {total}')


def _panel_svg(item):
    x0,_,y0,y1=item['_bbox']
    width=item['paper_width_cm']; height=item['paper_height_cm']
    svg=ET.Element(tag('svg'),{'width':f'{width:.9f}cm','height':f'{height:.9f}cm',
                    'viewBox':f'0 0 {width:.9f} {height:.9f}'})
    group=copy.deepcopy(item['_group'])
    if item['rotation_degrees']:
        group.set('transform',f'matrix(0 1 -1 0 {PADDING_CM+y1:.9f} {PADDING_CM-x0:.9f})')
    else:
        group.set('transform',f'translate({PADDING_CM-x0:.9f},{PADDING_CM-y0:.9f})')
    for path in group.iter(tag('path')):
        path.set('fill','none'); path.set('stroke','#111111'); path.set('stroke-width','.025')
    svg.append(group)
    return ET.tostring(svg,encoding='utf-8')


def build_print_pdf(folder):
    """Source nets retain scale 1; optional 90-degree turns precede tile clipping."""
    import cairosvg
    from pypdf import PdfReader,PdfWriter,Transformation
    from pypdf.generic import RectangleObject
    from reportlab.pdfgen.canvas import Canvas
    folder=Path(folder)
    plan=print_plan(folder)
    items=_templates(folder)
    for item,public in zip(items,plan['panels']):item.update(public)
    font,chinese=_font_choice()
    overlays=io.BytesIO()
    canvas=Canvas(overlays,pagesize=(PAGE_CM[0]*CM,PAGE_CM[1]*CM),pageCompression=1)
    canvas.setTitle('Traditional garment - A4 net patterns 1:1')
    _cover(canvas,plan,_read(folder/'body.json'),font,chinese); canvas.showPage()
    tiles=[]
    page=2
    for item in items:
        for row in range(item['rows']):
            for column in range(item['columns']):
                _tile_overlay(canvas,item,row,column,page,plan['page_count'],font,chinese)
                canvas.showPage()
                tiles.append((item,row,column)); page+=1
    canvas.save()
    overlay_reader=PdfReader(overlays)
    writer=PdfWriter()
    writer.add_page(overlay_reader.pages[0])
    sources={}
    for index,(item,row,column) in enumerate(tiles,1):
        ident=item['panel_id']
        if ident not in sources:
            reader=PdfReader(io.BytesIO(cairosvg.svg2pdf(bytestring=_panel_svg(item))))
            sources[ident]=reader
        src=copy.copy(sources[ident].pages[0])
        left=column*(PLOT_CM[2]-OVERLAP_CM)
        bottom=item['paper_height_cm']-row*(PLOT_CM[3]-OVERLAP_CM)-PLOT_CM[3]
        src.cropbox=RectangleObject([left*CM,bottom*CM,(left+PLOT_CM[2])*CM,(bottom+PLOT_CM[3])*CM])
        page=writer.add_page(overlay_reader.pages[index])
        page.merge_transformed_page(src,Transformation().translate((PLOT_CM[0]-left)*CM,
                                      (PLOT_CM[1]-bottom)*CM),over=False,expand=False)
        if row==0 and column==0:
            writer.add_outline_item(ident,index)
    writer.add_metadata({'/Title':'Traditional garment - A4 net patterns 1:1',
                         '/Subject':'Actual size net patterns. No seam allowance. 5mm overlap.'})
    writer.compress_identical_objects(remove_duplicates=True,remove_unreferenced=True)
    output=io.BytesIO(); writer.write(output); output.seek(0)
    return output,plan


def export_print_pdf(folder):
    """Cache only a complete export whose inputs and output digest still agree."""
    folder=Path(folder)
    inputs=[Path(__file__),folder/'metadata.json',folder/'body.json']
    for member,_,_ in _members(folder):
        inputs.extend(member/name for name in ['metadata.json','pattern.json','pattern-dimensions.svg'])
    fingerprint=hashlib.sha256(b''.join(path.read_bytes() for path in inputs)).hexdigest()
    output=folder/'traditional-pattern-a4.pdf'
    receipt=folder/'print-a4.json'
    if output.is_file() and receipt.is_file():
        try:
            old=_read(receipt)
        except (ValueError,OSError):
            old={}
        if not isinstance(old,dict):old={}
        if old.get('input_sha256')==fingerprint and old.get('pdf_sha256')==hashlib.sha256(output.read_bytes()).hexdigest():
            if old.get('plan')==print_plan(folder):return output,old['plan']
    buffer,plan=build_print_pdf(folder)
    payload=buffer.getvalue()
    temp=output.with_suffix('.pdf.tmp')
    temp.write_bytes(payload)
    os.replace(temp,output)
    receipt.write_text(json.dumps({'input_sha256':fingerprint,'pdf_sha256':hashlib.sha256(payload).hexdigest(),
                                  'plan':plan},ensure_ascii=False,indent=2),encoding='utf-8')
    return output,plan
