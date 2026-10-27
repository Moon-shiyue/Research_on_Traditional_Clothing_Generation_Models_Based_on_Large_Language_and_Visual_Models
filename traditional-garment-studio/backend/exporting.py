"""Self-contained sewing-pattern ZIP with file guidance and integrity hashes."""
import hashlib
import io
import json
from zipfile import ZipFile, ZIP_DEFLATED
from .panel_measurements import panel_label


REQUIRED=['pattern.svg','pattern-dimensions.svg','pattern.json','design.json','body.json','metadata.json']
OPTIONAL=['body-layout.svg','body-layout-dimensions.svg','body-layout.json',
    'preview-layout.json',
    'construction.json','assembly.json','structure.svg','cutting.json','cutting.svg','style.svg',
    'pleat-detail.svg','cutting-a.svg','cutting-b.svg','cutting-waistband.svg']


def build_outfit_archive(folder):
    metadata=json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
    files={name:(folder/name).read_bytes() for name in REQUIRED}
    for name in ['body-layout.svg','body-layout-dimensions.svg','body-layout.json']:
        files[name]=(folder/name).read_bytes()
    if (folder/'preview-layout.json').is_file():files['preview-layout.json']=(folder/'preview-layout.json').read_bytes()
    names=[];selection_notes=[]
    for garment in metadata['garments']:
        names.append(garment['name'])
        child_meta=json.loads((folder/garment['id']/'metadata.json').read_text(encoding='utf-8'))
        if child_meta.get('component_source')=='user_confirmation' and child_meta.get('selection_note'):
            selection_notes.append(garment['name']+'：'+child_meta['selection_note'])
        # Reuse each garment's exact drafting files, guidance and local hashes.
        with ZipFile(build_archive(folder/garment['id'],garment['name'])) as child:
            files.update({garment['id']+'/'+name:child.read(name) for name in child.namelist()})
    lines=['传统服饰组合 — '+'＋'.join(names), '',
        f'本次{len(names)}件衣物共用 body.json 中的人体参考尺寸，分别缝制，没有衣物之间的缝合边。',
        '根目录 pattern*.svg 为所有裁片的1:1厘米净样总览；每件独立文件在 '+ '、'.join(g['id']+'/' for g in metadata['garments'])+'。',
        'body-layout*.svg 左侧为整套二维定位示意，不能沿穿着示意裁布；右侧为全部净样。',
        '净样不含缝份；马面裙 lower/cutting*.svg 的裁剪线另含明示余量，按 lower/README.txt 核对，勿重复添加。',
        '按100%实际大小打印，先核对各件 pattern-dimensions.svg 的10cm校准线。',
        '每件的 assembly.json 或 construction.json 记录其独立结构和缝合说明。',
        '每件内部已进行平面轮廓与配缝检查；未进行布料仿真、实体试缝或合体性验证。',
        '一套基础款组合不等于任意历史服饰的精确复原。', '', '本次裁片清单：']
    lines += [f'- {g["name"]}：{g["panel_count"]}片，目录 {g["id"]}/' for g in metadata['garments']]
    if selection_notes:lines+=['','本次用户选款（不是图片确认的细节）：']+selection_notes
    if metadata.get('reference_image_url'):
        lines += ['', '本次参考图片不包含在此包；可在软件纸样区查看，后续尺寸编辑不代表图片重新识别。']
    files['README.txt']=('\n'.join(lines)+'\n').encode('utf-8')
    if 'user_confirmation' in metadata.get('parameter_sources',{}).values():
        files['README.txt']+='\n开襟位置由用户选择；参考图遮挡，未从图片确认。\n'.encode('utf-8')
    manifest={'version':'outfit-export-v1','component':'outfit','units':'cm','hash_algorithm':'sha256',
        'hash_scope':'uncompressed bytes; excludes this manifest',
        'garments':[{k:g[k] for k in ['id','component','name','panel_count']} for g in metadata['garments']],
        'files':{name:{'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()}
            for name,content in sorted(files.items())}}
    files['export-manifest.json']=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8')
    buffer=io.BytesIO()
    with ZipFile(buffer,'w',ZIP_DEFLATED) as archive:
        for name,content in files.items():
            archive.writestr(name,content)
    buffer.seek(0)
    return buffer


def build_archive(folder, component_name):
    files={name:(folder/name).read_bytes() for name in REQUIRED}
    files.update({name:(folder/name).read_bytes() for name in OPTIONAL if (folder/name).is_file()})
    metadata=json.loads(files['metadata.json'])
    body=json.loads(files['body.json'])
    instructions=[f'传统服饰二维纸样 — {component_name}', '',
        ('长度单位：cm（厘米）。本包包含所选整件基础衣物的全部裁片，不包含其它独立衣物。'
         if metadata.get('assembly',{}).get('whole_garment') else
         '长度单位：cm（厘米）。每次只输出一个组件，不代表图中整套服装。'),
        f'本次人体参考：身高 {body["height"]:g}cm，胸围 {body["bust"]:g}cm，腰围 {body["waist"]:g}cm，臀围 {body["hips"]:g}cm。', '',
        '用于制版：',
        '- pattern.svg：实际厘米尺寸的裁片净样。',
        '- pattern-dimensions.svg：同一净样，另标各边长度与每片宽×高。曲线标注为弧长；裁片平铺宽不等于成衣围度。',
        '- 净样未加缝份。按工艺加缝份、核对缝边与人体尺寸后再裁布。']
    if 'cutting.json' in files:
        instructions += ['- 马面裙 cutting-a.svg、cutting-b.svg、cutting-waistband.svg 为单片制版图；cutting.svg 为总览。',
            '- 这些精细制版图中的裁剪线已含明示的接腰、侧边和折边余量，具体数值见图和 cutting.json；不要再次重复添加。',
            '- 褶线、腰头对位和经向按图示核对；折后配缝长度与展开布长不同。']
    instructions += ['', '打印：',
        '- SVG 已写入厘米物理宽高。打印或导入矢量/CAD软件时选100%或实际大小，关闭适应纸张。',
        '- 先核对 pattern-dimensions.svg 中10cm校准线，再核对标注尺寸。屏幕缩放与背景网格不可当作尺子。',
        '- 在软件中点击“A4纸样”可另下载1:1分幅PDF，先预览纸张数量；每张5mm重叠，只拼接同一裁片。',
        '- A4 PDF为净样，不含缝份；即使另有含明示余量的cutting*.svg，也不要混用裁剪线。', '',
        '仅供示意：',
        '- body-layout*.svg：左侧人体二维定位、右侧净样对照。左侧可能折叠或投影，不能沿其轮廓裁布。',
        '- preview*.svg、style.svg、structure.svg、pleat-detail.svg：平铺、款式或结构说明，不替代制版净样。', '',
        '参数与追溯：',
        '- design.json 为款式参数，body.json 为人体参考，pattern.json 为裁片几何。',
        '- metadata.json 记录固定厘米长度、参数来源、默认字段和几何检查。',
        '- body_parameter_sources 记录人体尺寸来自文字或面板手动设置；未列字段沿用当前体型。人体围度不等同于成衣完成围度。',
        '- 图片样式建议的厘米默认值不是从照片测量所得；未指定的尺寸须在试样前核对。',
        '- export-manifest.json 记录本包其它文件的字节数与SHA256；哈希针对解压后的原文件。', '',
        '检查范围：采样的平面轮廓、有限坐标与缝边配长；未进行布料仿真、实体试缝或合体性验证。']
    constraints=metadata.get('absolute_lengths_cm',{})
    if 'user_confirmation' in metadata.get('parameter_sources',{}).values():
        instructions += ['', '开襟位置由用户选择；参考图遮挡，未从图片确认。']
    if metadata.get('reference_image_url'):
        instructions += ['', '本次参考图片不包含在此包；可在软件纸样区查看，后续尺寸编辑不代表图片重新识别。']
    if metadata.get('component_source')=='user_confirmation' and metadata.get('selection_note'):
        instructions += ['', '本次用户选款：'+metadata['selection_note']]
    if constraints:
        instructions += ['', '本次固定厘米长度（修改人体尺寸时仍保持）：']
        instructions += [f'- {path}: {cm:g}cm' for path,cm in sorted(constraints.items())]
    if 'assembly.json' in files:
        assembly=json.loads(files['assembly.json'])
        instructions += ['', '当前基础款裁布清单（仍为净样，另核缝份）：']
        for index,item in enumerate(assembly.get('cut_list',[])):
            grain=('斜裁包边条；裁前先试样核对' if item.get('grain')=='bias strip; test before cutting'
                   else '沿裁片中心纵向核对直丝' if item.get('grain')=='lengthwise grain through panel centre'
                   else '纹向需按面料与工艺复核')
            instructions.append(f'- {panel_label(item["panel"],index)} [{item["panel"]}]：裁布{item["quantity"]}片；{grain}。')
        if assembly.get('assembly_steps'):
            instructions += ['', '本款组装顺序（试样前核对，不代表实体试缝通过）：']
            instructions += [f'{index}. {step}' for index,step in enumerate(assembly['assembly_steps'],1)]
    files['README.txt']=('\n'.join(instructions)+'\n').encode('utf-8')
    manifest={'version':'pattern-export-v1','component':metadata['component'],'component_name':component_name,
        'units':'cm','hash_algorithm':'sha256','hash_scope':'uncompressed bytes; excludes this manifest',
        'files':{name:{'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()}
            for name,content in sorted(files.items())}}
    files['export-manifest.json']=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8')
    buffer=io.BytesIO()
    with ZipFile(buffer,'w',ZIP_DEFLATED) as archive:
        for name,content in files.items():
            archive.writestr(name,content)
    buffer.seek(0)
    return buffer
