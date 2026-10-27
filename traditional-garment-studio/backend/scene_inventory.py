"""Full-photo accounting, independent of which templates can be generated."""


SCENE_FIELDS = {'observations', 'visible_garments', 'single_outfit', 'all_garments_accounted'}


def ambiguous_skirt(row):
    features=row.get('features',{})
    return (row.get('component') is None
            and not row.get('innerwear_candidates')
            and features.get('innerwear_front','unclear')=='unclear'
            and features.get('innerwear_closure','unclear')=='unclear'
            and isinstance(row.get('skirt_candidates'),list)
            and len(row['skirt_candidates'])==2
            and all(isinstance(c,str) for c in row['skirt_candidates'])
            and set(row['skirt_candidates'])=={'mamian-skirt','ruqun-skirt'}
            and features.get('length') in {'full','mid','short'}
            and features.get('hem_shape') in {'straight','moderate','wide'}
            and (features.get('flat_front') is None or features.get('side_pleats') is None)
            and all(features.get(key,'unclear')=='unclear' for key in
                    ['upper_front','sleeve_shape','sleeve_extent','neckwear_shape','waist_belt'])
            and features.get('cloud_layers') is None
            and features.get('cloud_coverage','unclear')=='unclear')


def valid_scene(result):
    if not isinstance(result, dict) or not SCENE_FIELDS <= set(result):
        return False
    inventory = result['visible_garments']
    rows = result['observations']
    return (type(result['single_outfit']) is bool
            and type(result['all_garments_accounted']) is bool
            and isinstance(inventory, list) and 0 < len(inventory) <= 8
            and all(isinstance(name, str) and 0 < len(name.strip()) <= 120 for name in inventory)
            and isinstance(rows, list) and len(rows) <= 6
            and all(isinstance(row, dict) and type(row.get('garment_index')) is int
                    and 0 <= row['garment_index'] < len(inventory) for row in rows))


def coverage_issue(result):
    if not valid_scene(result):
        return '未收到完整的整图衣物核对信息，请重新识别；不会将未核对的局部结果当成整套。'
    if not result['single_outfit']:
        return '图片包含不同人物或不同套服饰，无法确定本次要制作哪一套。请裁出一套完整服饰后重试；同款正反面可保留。'
    indices = [row['garment_index'] for row in result['observations']]
    missing = [name for i, name in enumerate(result['visible_garments']) if i not in indices]
    if missing or not result['all_garments_accounted'] or len(indices) != len(set(indices)):
        details = '尚未逐件确认：' + '、'.join(missing) + '。' if missing else ''
        return details + '整图衣物清单与逐件识别尚未对应完整，不会只输出其它部分。请补充无遮挡全身图或明确整套款式。'
    return ''
