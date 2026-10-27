"""Local FastAPI service for traditional component sewing-pattern generation."""
import asyncio
import copy
import hashlib
import io
import json
import logging
import random
import shutil
import threading
import time
import uuid
from typing import Optional, Literal
from urllib.parse import quote

from fastapi import FastAPI, BackgroundTasks, File, Header, UploadFile, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, SecretStr
from PIL import Image, UnidentifiedImageError
from .image_normalization import upright_rgb
from .text_scope import requested_local_kinds

from .settings import RUNTIME_ROOT
from .engine import PaperEngine
from .patterns import body_from, generate_pattern
from training.schema import validate_patch, form_errors
from .cloud_vision import VisionError
from .exporting import build_archive, build_outfit_archive
from .printing import print_plan, export_print_pdf
from .session_restore import (restore_last_design, restore_saved_design, remember_design, recent_designs,
    restore_body_draft, save_body_draft)
from .design_integrity import VERSION as INTEGRITY_VERSION, seal_design, verify_design
from .outfits import (PAIRS, interpret_outfit, interpret_outfit_image, interpret_outfit_scene, generate_outfit,
    parameter_response as outfit_parameters, common_contexts, GROUPS)


class ParseInput(BaseModel):
    text: str = Field('', max_length=4000)
    image: Optional[str] = None
    mode: str = 'auto'
    scope: Literal['component','outfit'] = 'outfit'
    image_proposal_id: Optional[str] = Field(None,max_length=64)
    opening_choice: Optional[Literal['right','center']] = None
    skirt_choice: Optional[Literal['mamian-skirt','ruqun-skirt']] = None
    innerwear_choice: Optional[Literal['chest-wrap']] = None
    request_id: Optional[str] = Field(None,max_length=64)


class ChangeInput(BaseModel):
    path: list[str]
    value: object
    unit: Literal['native', 'cm'] = 'native'


class PrintInput(BaseModel):
    pattern_url: Optional[str] = Field(None,max_length=1000)


class RestoreInput(BaseModel):
    design_id: str = Field(min_length=32,max_length=32)


class VisionConfigInput(BaseModel):
    base_url: str = Field(max_length=500)
    model: str = Field(max_length=150)
    api_key: SecretStr = SecretStr('')
    protocol: str = 'responses'


class PlanLoginInput(BaseModel):
    account_id: Optional[str] = Field(None, max_length=100)


class VisionSourceInput(BaseModel):
    source: str = Field(max_length=30)


class PlanModelInput(BaseModel):
    model: str = Field(max_length=150)


class ApiError(Exception):
    def __init__(self, code, message, status=400):
        self.code, self.message, self.status = code, message, status


def create_app(engine=None, runtime=None):
    service = engine or PaperEngine()
    root = runtime or RUNTIME_ROOT
    plan = getattr(getattr(service.model,'cloud_vision',None),'plan',None)
    if plan and (plan.directory.resolve() == root.resolve() or root.resolve() in plan.directory.resolve().parents):
        raise RuntimeError('登录凭据目录不能位于静态文件目录内。')
    root.mkdir(parents=True, exist_ok=True)
    for directory in ['uploads', 'patterns']:
        (root / directory).mkdir(exist_ok=True)
    app = FastAPI(title='传统服饰制版服务', version='0.3.0')
    app.mount('/static', StaticFiles(directory=str(root)), name='static')
    sessions, tasks = {}, {}
    lock = threading.RLock()

    @app.exception_handler(ApiError)
    async def api_error(request, error):
        return JSONResponse({'error': {'code': error.code, 'message': error.message}}, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        return JSONResponse({'error':{'code':'invalid_request','message':'请求格式不正确，请检查输入、图片和参数。'}},status_code=422)

    def session(sid):
        try:
            sid = str(uuid.UUID(sid or ''))
        except ValueError:
            raise ApiError('session_required', '请刷新页面建立会话。')
        with lock:
            now = time.monotonic()
            for key in list(sessions):
                if not sessions[key]['busy'] and now - sessions[key]['seen'] > 7200:
                    sessions.pop(key)
                    for ident in [k for k,v in tasks.items() if v['session'] == key]:
                        tasks.pop(ident)
            if sid not in sessions:
                body = {k:v for k,v in body_from().params.items() if not k.startswith('_')}
                sessions[sid] = {'id':sid,'patch':service.defaults('mamian-skirt'),'body':body,
                    'pattern':None,'folder':None,'busy':False,'seen':now,'sources':{},'defaults':[],
                    'absolute_lengths_cm':{}, 'body_sources':{}, 'image_proposal':None, 'outfit':None}
                sessions[sid]['parse_requests']={}
                saved=restore_last_design(service,root,sid)
                if saved:
                    sessions[sid].update(saved)
                else:
                    draft=restore_body_draft(root,sid)
                    if draft:
                        sessions[sid].update(draft)
            state = sessions[sid]
            state['seen'] = now
            return state

    def available(state):
        if state['busy']:
            raise ApiError('task_conflict', '正在生成纸样，请等待本次任务完成。', 409)

    def design_response(state):
        return (outfit_parameters(service,state['outfit'],state['body']) if state['outfit']
                else service.parameter_response(state['patch'],state['body']))

    def history_summary(saved):
        details=[]
        members=saved['outfit'] or [{'component':saved['pattern']['component'],'patch':saved['patch']}]
        for member in members:
            component=member['component'];values=member['patch'][component]
            if 'length' in values:
                label='裙长' if component.endswith('skirt') else '袖长' if component.endswith('sleeve') else '衣长'
                cm=values['length']['v']*service.length_reference(component,'length',saved['body'])
                details.append(f'{label}{cm:.1f}cm')
            elif component=='chest-wrap':
                details.append(f'围前净高{values["panel_height"]["v"]:g}cm')
            elif component=='pibo':
                details.append(f'披帛长{values["strip_length"]["v"]:g}cm/幅宽{values["strip_width"]["v"]:g}cm')
            elif component=='cloud-shoulder':
                details.append(f'{values["layers"]["v"]:g}层/{values["petal_count"]["v"]:g}云头')
            else:
                field,label={'stand-collar':('collar_height','领高'),'round-collar':('front_depth','前领深'),
                    'cross-collar':('collar_depth','领深'),'duijin-collar':('front_width','前襟宽')}[component]
                details.append(f'{label}{values[field]["v"]:g}cm')
        details.extend([f'身高{saved["body"]["height"]:g}cm',f'腰围{saved["body"]["waist"]:g}cm'])
        return ' · '.join(details)

    def links(metadata, folder):
        base='/static/'+folder.relative_to(root).as_posix()+'/'
        for key,name in {'svg_url':'pattern.svg','dimension_svg_url':'pattern-dimensions.svg',
                'body_layout_svg_url':'body-layout.svg','body_layout_dimension_svg_url':'body-layout-dimensions.svg',
                'preview_svg_url':'preview.svg','preview_dimension_svg_url':'preview-dimensions.svg',
                'cutting_svg_url':'cutting.svg','style_svg_url':'style.svg','structure_svg_url':'structure.svg',
                'pleat_detail_svg_url':'pleat-detail.svg','cutting_a_svg_url':'cutting-a.svg',
                'cutting_b_svg_url':'cutting-b.svg','cutting_waistband_svg_url':'cutting-waistband.svg'}.items():
            if (folder/name).is_file():
                metadata[key]=base+name

    def discard_failed_folder(folder):
        target=folder.resolve()
        boundary=(root/'patterns').resolve()
        if target != boundary and target.is_relative_to(boundary) and target.is_dir():
            shutil.rmtree(target)

    keep_reference = object()

    def attach_reference(state, metadata, folder, source):
        # A committed design owns a copy, so upload expiry cannot change its reference.
        # Only internal, session-owned paths enter here; no URL or client path is accepted.
        if source is keep_reference:
            source = state['folder']/'reference.jpg' if (
                state['folder'] and (state['pattern'] or {}).get('reference_image_url')) else None
            if source and not source.is_file():
                source = None  # A missing optional picture must not block dimension edits.
        if source is None:
            return
        if not source.is_file():
            raise ValueError('参考图已失效，请重新上传图片后识别。')
        target = folder/'reference.jpg'
        shutil.copyfile(source,target)
        metadata['reference_image_url'] = '/static/'+target.relative_to(root).as_posix()
        metadata['reference_image_sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()

    def save_metadata(metadata,folder):
        metadata['integrity_version']=INTEGRITY_VERSION
        try:
            (folder/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
            seal_design(folder)
        except Exception:
            discard_failed_folder(folder)
            raise

    def render_outfit(state, garments, body, body_sources=None, reference=keep_reference):
        # Validate every member before creating files or committing session data.
        garments=copy.deepcopy(garments)
        for g in garments:
            errors=validate_patch(g['patch'],service.schema) or form_errors(g['patch'],service.template)
            if errors:
                raise ApiError('invalid_parameters',service.parameter_error_message(errors,g['patch'],body),422)
            g['patch']=service.preserve_absolute_lengths(g['patch'],body,g['absolute_lengths_cm'],g['sources'])
            errors=validate_patch(g['patch'],service.schema) or form_errors(g['patch'],service.template)
            if errors:
                raise ApiError('invalid_parameters',service.parameter_error_message(errors,g['patch'],body),422)
        ident=uuid.uuid4().hex
        folder=root/'patterns'/state['id']/ident
        try:
            metadata=generate_outfit(garments,service.template,body,folder)
            attach_reference(state,metadata,folder,reference)
        except ValueError as error:
            discard_failed_folder(folder)
            raise ApiError('invalid_geometry',str(error),422)
        except Exception:
            discard_failed_folder(folder)
            raise
        sources={k:v for g in garments for k,v in g['sources'].items()}
        defaults=list(dict.fromkeys(k for g in garments for k in g['default_fields']))
        absolute={k:v for g in garments for k,v in g['absolute_lengths_cm'].items()}
        body_sources=copy.deepcopy(state['body_sources'] if body_sources is None else body_sources)
        metadata.update(parameter_sources=sources,default_fields=defaults,absolute_lengths_cm=absolute,
            body_parameter_sources=body_sources,updated_at=time.strftime('%Y-%m-%dT%H:%M:%S'))
        links(metadata,folder)
        for member in metadata['garments']:
            child=folder/member['id']
            child_meta=json.loads((child/'metadata.json').read_text(encoding='utf-8'))
            links(child_meta,child)
            child_meta['body_parameter_sources']=body_sources
            (child/'metadata.json').write_text(json.dumps(child_meta,ensure_ascii=False,indent=2),encoding='utf-8')
            member.update({key:value for key,value in child_meta.items() if key.endswith('_url')})
        save_metadata(metadata,folder)
        remember_design(root,state['id'],folder)
        with lock:
            state.update(outfit=copy.deepcopy(garments),patch=copy.deepcopy(garments[0]['patch']),
                body=copy.deepcopy(body),pattern=metadata,folder=folder,sources=sources,defaults=defaults,
                absolute_lengths_cm=absolute,body_sources=body_sources)
        return metadata

    def render(state, patch, body, sources=None, defaults=None, absolute_lengths=None, body_sources=None,
               reference=keep_reference):
        errors = validate_patch(patch, service.schema)
        if not errors:
            errors = form_errors(patch, service.template)
        if errors:
            raise ApiError('invalid_parameters',service.parameter_error_message(errors,patch,body),422)
        patch=service.preserve_absolute_lengths(patch,body,absolute_lengths or {},sources)
        errors=validate_patch(patch,service.schema) or form_errors(patch,service.template)
        if errors:
            raise ApiError('invalid_parameters',service.parameter_error_message(errors,patch,body),422)
        ident = uuid.uuid4().hex
        folder = root / 'patterns' / state['id'] / ident
        try:
            metadata = generate_pattern(patch, service.template, body, folder)
            attach_reference(state,metadata,folder,reference)
        except ValueError as error:
            discard_failed_folder(folder)
            raise ApiError('invalid_geometry', str(error), 422)
        except Exception:
            discard_failed_folder(folder)
            raise
        metadata.pop('body_values')
        body_sources=copy.deepcopy(state['body_sources'] if body_sources is None else body_sources)
        metadata.update({'svg_url':f'/static/patterns/{state["id"]}/{ident}/pattern.svg',
                         'dimension_svg_url':f'/static/patterns/{state["id"]}/{ident}/pattern-dimensions.svg',
                         'updated_at':time.strftime('%Y-%m-%dT%H:%M:%S'),
                         'default_fields':defaults or [],'parameter_sources':sources or {},
                         'absolute_lengths_cm':copy.deepcopy(absolute_lengths or {}),
                         'body_parameter_sources':body_sources})
        if (folder/'structure.svg').is_file():
            metadata['structure_svg_url'] = f'/static/patterns/{state["id"]}/{ident}/structure.svg'
        for key,name in {'body_layout_svg_url':'body-layout.svg','body_layout_dimension_svg_url':'body-layout-dimensions.svg',
                         'preview_svg_url':'preview.svg','preview_dimension_svg_url':'preview-dimensions.svg',
                         'cutting_svg_url':'cutting.svg', 'style_svg_url':'style.svg',
                         'pleat_detail_svg_url':'pleat-detail.svg', 'cutting_a_svg_url':'cutting-a.svg',
                         'cutting_b_svg_url':'cutting-b.svg', 'cutting_waistband_svg_url':'cutting-waistband.svg'}.items():
            if (folder/name).is_file():
                metadata[key] = f'/static/patterns/{state["id"]}/{ident}/{name}'
        save_metadata(metadata,folder)
        remember_design(root,state['id'],folder)
        with lock:
            state.update({'patch':copy.deepcopy(patch),'body':copy.deepcopy(body),'pattern':metadata,'folder':folder,
                          'sources':sources or {},'defaults':defaults or [],
                          'absolute_lengths_cm':copy.deepcopy(absolute_lengths or {}), 'body_sources':body_sources,
                          'outfit':None})
        return metadata

    def public_task(task):
        return {key:copy.deepcopy(task.get(key)) for key in ['task_id','status','stage','progress','result','error']}

    def execute(ident, text, image_path, proposal=None, scope='outfit'):
        task = tasks[ident]
        state = sessions[task['session']]
        try:
            with lock:
                task.update(status='running', stage='parsing', progress=15)
                body = copy.deepcopy(state['body'])
            if image_path and scope=='outfit' and not requested_local_kinds(text):
                outfit_intent=interpret_outfit_image(service,text,image_path,body)
            elif proposal and proposal.get('outfit'):
                visuals={o['component']:o for o in proposal['observations'] if o.get('component')}
                if proposal.get('scene'):
                    # Confirm one item, then keep asking about every remaining
                    # bounded choice before generating the entire saved scene.
                    checked=interpret_outfit_scene(service,text,proposal['scene'],body)
                    if checked.get('suggested_outfit') and not any(checked.get(k) for k in
                            ['opening_choices','skirt_choices','innerwear_choices']):
                        outfit_intent=interpret_outfit(service,checked['suggested_text'],body,visuals)
                    else:outfit_intent=checked
                else:outfit_intent=interpret_outfit(service,text,body,visuals)
            else:
                outfit_intent=interpret_outfit(service,text,body) if not image_path else None
            intent = outfit_intent if outfit_intent is not None else service.interpret(text, image_path, body, proposal)
            if intent['status']=='ready' and proposal and proposal.get('opening_choice'):
                chosen=proposal['opening_choice_component']
                for member in intent.get('garments') or [intent]:
                    if member['component']==chosen:
                        member['sources'][chosen+'.opening_type']='user_confirmation'
                        member['note']=(member.get('note','')+' 开襟位置由用户选择；本图遮挡，未从图片确认。').strip()
            if intent['status'] == 'needs_input':
                result = intent
                with lock:
                    if state['pattern']:
                        result['pattern']=copy.deepcopy(state['pattern'])
                        result['reply']+='\n本次尚未生成，保留上一次有效纸样。'
                    pending_reference=image_path or (proposal or {}).get('reference_path')
                    if pending_reference and intent.get('suggested_outfit'):
                        proposal_id=uuid.uuid4().hex
                        state['image_proposal']={'id':proposal_id,'outfit':True,
                            'suggested_text':intent['suggested_text'],
                            'reference_path':pending_reference,
                            'observations':copy.deepcopy(intent['outfit_observations'])}
                        if intent.get('outfit_scene'):
                            state['image_proposal']['scene']=copy.deepcopy(intent['outfit_scene'])
                        if intent.get('skirt_choices'):
                            state['image_proposal'].update(skirt_choices=copy.deepcopy(intent['skirt_choices']),
                                                          skirt_choice_index=intent['skirt_choice_index'])
                        if intent.get('innerwear_choices'):
                            state['image_proposal'].update(innerwear_choices=copy.deepcopy(intent['innerwear_choices']),
                                                          innerwear_choice_index=intent['innerwear_choice_index'])
                        result['image_proposal_id']=proposal_id
                    elif image_path and intent.get('suggested_component'):
                        proposal_id=uuid.uuid4().hex
                        state['image_proposal']={'id':proposal_id,'component':intent['suggested_component'],
                            'reference_path':image_path,
                            'features':copy.deepcopy(intent.get('visible_features',{})),
                            'default_lengths_cm':copy.deepcopy(intent.get('image_default_lengths_cm',{}))}
                        result['image_proposal_id']=proposal_id
                    if state.get('image_proposal') and intent.get('opening_choices'):
                        state['image_proposal'].update(opening_choice_component=intent['opening_choice_component'],
                                                      opening_choices=copy.deepcopy(intent['opening_choices']))
            else:
                with lock:
                    task.update(stage='pattern', progress=75)
                body=intent.get('body_values',body)
                body_sources=dict(state['body_sources'],**{key:'text' for key in intent.get('supplied_body_fields',[])})
                component = intent['component']
                # New text starts a new design; only confirmed image input carries a reference.
                reference = image_path or (proposal or {}).get('reference_path')
                if intent.get('garments'):
                    pattern=render_outfit(state,intent['garments'],body,body_sources,reference=reference)
                    names=[service.names[g['component']] for g in intent['garments']]
                    reply='已生成'+'＋'.join(names)+f'，共{len(names)}件独立衣物，共用当前人体尺寸。左侧为整套二维定位，右侧为全部净样。'
                    reply+='\n各件分别缝制；未指定参数已标为默认值，朝代与场合在本组基础款的共同范围内选择。'
                    if proposal and proposal.get('opening_choice'):
                        reply+='\n开襟位置已按你的选择制作；该细节未由图片确认。'
                    if any(g.get('component_source')=='user_confirmation' and g['component'].endswith('skirt') for g in intent['garments']):
                        reply+='\n下裙款式已按你的选择制作；该细节未由图片确认。'
                    if any(g.get('component_source')=='user_confirmation' and g['component']=='chest-wrap' for g in intent['garments']):
                        reply+='\n内搭采用你选择的直幅后背系带基础款，背面结构未由图片确认。'
                else:
                    pattern = render(state, intent['patch'], body, intent['sources'], intent['default_fields'],
                        intent.get('absolute_lengths_cm', {}),body_sources,reference=reference)
                    names=[service.names[component]]
                    reply = intent['note'] + '\n已生成' + service.names[component] + '的真实裁片。'
                if not intent.get('garments') and intent['default_fields']:
                    reply += '\n未指定的参数采用默认值，已在纸样下方标出；可在设计参数和人体尺寸面板调整。'
                if not intent.get('garments') and any(v == 'model' for v in intent['sources'].values()):
                    reply += '\n部分参数由模型推断，请检查设计参数。'
                result = {'status':'generated','reply':reply.strip(),'pattern':pattern,
                    'design_params':design_response(state)['params'],
                    'body_params':{'body_id':'mean_female','available_bodies':['mean_female'],
                        'params':body_from(body).params,'parameter_sources':body_sources},
                    'design_list':names, 'rag_sources':[]}
            with lock:
                task.update(status='done',stage='rendering',progress=100,result=result)
        except ApiError as error:
            with lock:
                result=service.clarify(error.message)
                if state['pattern']:
                    result['pattern']=copy.deepcopy(state['pattern'])
                    result['reply']+='\n本次尚未生成，保留上一次有效纸样。'
                task.update(status='done',progress=100,result=result)
        except Exception:
            logging.exception('Pattern task failed: %s', ident)
            with lock:
                task.update(status='failed', error={'code':'generation_failed','message':'生成未完成，请检查输入或重新选择组件；已有文件已保留。'})
        finally:
            with lock:
                state['busy'] = False

    @app.get('/api/v1/health')
    def health():
        return {'status':'ok','components':service.names,'model_loaded':bool(getattr(service.model,'model',None)),
                'outfits':[{'components':list(pair),'names':[service.names[c] for c in pair]} for pair in PAIRS],
                'ensembles':[{'components':list(group),'names':[service.names[c] for c in group]} for group in GROUPS]}

    def vision_client():
        client = getattr(service.model,'cloud_vision',None)
        if client is None:
            raise ApiError('vision_not_available','当前服务未提供云端视觉设置。',503)
        return client

    @app.get('/api/v1/vision/config')
    def get_vision_config():
        return vision_client().status()

    @app.put('/api/v1/vision/config')
    def configure_vision(payload: VisionConfigInput, x_session_id: Optional[str] = Header(None)):
        session(x_session_id)
        try:
            return vision_client().configure(payload.base_url,payload.model,
                payload.api_key.get_secret_value(),payload.protocol)
        except VisionError as error:
            raise ApiError('invalid_vision_config',str(error),422)

    @app.delete('/api/v1/vision/config')
    def clear_vision_config(x_session_id: Optional[str] = Header(None)):
        session(x_session_id)
        return vision_client().clear()

    def local_plan(request, sid):
        session(sid)
        if not request.client or request.client.host not in {'127.0.0.1','::1'}:
            raise ApiError('local_login_only','套餐登录仅支持本机访问。',403)
        return vision_client().plan

    @app.exception_handler(VisionError)
    async def vision_error(request, error):
        return JSONResponse({'error':{'code':'vision_plan_error','message':str(error)}},status_code=400)

    @app.put('/api/v1/vision/source')
    def vision_source(payload: VisionSourceInput, request: Request, x_session_id: Optional[str] = Header(None)):
        local_plan(request,x_session_id)
        return vision_client().select_source(payload.source)

    @app.get('/api/v1/vision/chatgpt')
    def plan_status(request: Request, x_session_id: Optional[str] = Header(None)):
        return local_plan(request,x_session_id).status()

    @app.post('/api/v1/vision/chatgpt/login')
    def plan_login(payload: PlanLoginInput, request: Request, x_session_id: Optional[str] = Header(None)):
        return local_plan(request,x_session_id).start(payload.account_id)

    @app.delete('/api/v1/vision/chatgpt/login')
    def cancel_plan_login(request: Request, x_session_id: Optional[str] = Header(None)):
        return local_plan(request,x_session_id).cancel()

    @app.delete('/api/v1/vision/chatgpt')
    def plan_sign_out(request: Request, x_session_id: Optional[str] = Header(None)):
        return local_plan(request,x_session_id).sign_out()

    @app.get('/api/v1/vision/chatgpt/models')
    def plan_models(request: Request, x_session_id: Optional[str] = Header(None)):
        return {'models':local_plan(request,x_session_id).models()}

    @app.put('/api/v1/vision/chatgpt/model')
    def plan_model(payload: PlanModelInput, request: Request, x_session_id: Optional[str] = Header(None)):
        state = local_plan(request,x_session_id).select_model(payload.model)
        vision_client().select_source('chatgpt_plan')
        return state

    @app.post('/api/v1/upload/image')
    async def upload(file: UploadFile = File(...), x_session_id: Optional[str] = Header(None)):
        state = session(x_session_id)
        content = await file.read(8 * 1024 * 1024 + 1)
        await file.close()
        if len(content) > 8 * 1024 * 1024:
            raise ApiError('image_too_large','图片应小于8MB，请压缩后重试。',413)
        try:
            with Image.open(io.BytesIO(content)) as source:
                if source.width * source.height > 20_000_000:
                    raise ApiError('image_too_large','图片像素过大，请缩小后重试。',413)
                image = upright_rgb(source)
                image.thumbnail((1600,1600))
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise ApiError('invalid_image','无法读取这张图片，请选择PNG、JPEG或WebP图片。')
        ident = 'img_' + uuid.uuid4().hex
        directory = root/'uploads'/state['id']
        directory.mkdir(parents=True,exist_ok=True)
        image.save(directory/(ident+'.jpg'), quality=92)
        return {'image_id':ident,'url':f'/static/uploads/{state["id"]}/{ident}.jpg'}

    @app.post('/api/v1/parse', status_code=202)
    def parse(payload: ParseInput, background: BackgroundTasks, x_session_id: Optional[str] = Header(None)):
        state = session(x_session_id)
        text = payload.text.strip()
        if not text and not payload.image:
            raise ApiError('empty_input','请输入文字或上传图片。')
        image_path = None
        with lock:
            fingerprint=None
            if payload.request_id is not None:
                import re
                if not re.fullmatch(r'[A-Za-z0-9_-]{16,64}',payload.request_id):
                    raise ApiError('invalid_request_id','本次请求标识无效，请重新发送。',422)
                fingerprint=hashlib.sha256(json.dumps({
                    'text':text,'image':payload.image,'mode':payload.mode,'scope':payload.scope,
                    'image_proposal_id':payload.image_proposal_id,'opening_choice':payload.opening_choice,
                    'skirt_choice':payload.skirt_choice,'innerwear_choice':payload.innerwear_choice,
                },sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()
                previous=state['parse_requests'].get(payload.request_id)
                if previous:
                    if previous['fingerprint']!=fingerprint:
                        raise ApiError('request_id_conflict','重试内容已变化，请作为新请求重新发送。',409)
                    if previous['task_id'] in tasks:
                        return {'task_id':previous['task_id'],'mode':previous['mode']}
            if payload.image:
                if not re_image_id(payload.image):
                    raise ApiError('invalid_image_reference','请先上传图片，再发起生成。')
                image_path = root/'uploads'/state['id']/(payload.image+'.jpg')
                if not image_path.is_file():
                    raise ApiError('image_not_found','这张图片不属于当前会话，请重新上传。')
            available(state)
            proposal=None
            if payload.image_proposal_id:
                proposal=state.get('image_proposal')
                matches=(proposal and (text==proposal['suggested_text'] if proposal.get('outfit')
                    else service.find_components(text)==[proposal['component']]))
                if (not proposal or proposal['id']!=payload.image_proposal_id or image_path or not matches):
                    raise ApiError('invalid_image_proposal','图片建议已失效或与组件不同，请重新上传图片或直接输入组件。',422)
                proposal=copy.deepcopy(proposal)
                if proposal.get('innerwear_choices'):
                    if payload.innerwear_choice not in {c['id'] for c in proposal['innerwear_choices']}:
                        raise ApiError('innerwear_choice_required','内搭背面未确认，请选择本次基础款或补充图片。',422)
                    if payload.skirt_choice is not None or payload.opening_choice is not None:
                        raise ApiError('invalid_innerwear_choice','本步先选择内搭，再确认其它待选细节。',422)
                    for visual in proposal['observations']:
                        if visual['garment_index']==proposal['innerwear_choice_index']:
                            visual.update(component='chest-wrap',component_source='user_confirmation',innerwear_candidates=[])
                            visual.setdefault('features',{}).update(innerwear_front='straight-top',innerwear_closure='tie-back')
                    proposal['scene']['observations']=copy.deepcopy(proposal['observations'])
                    proposal['innerwear_choice']='chest-wrap'
                    if 'chest-wrap' not in service.find_components(text):text+=('；' if text else '')+service.names['chest-wrap']
                elif payload.innerwear_choice is not None:
                    raise ApiError('invalid_innerwear_choice','当前没有待选的内搭基础款，请重新识别。',422)
                if proposal.get('skirt_choices'):
                    allowed={item['id'] for item in proposal['skirt_choices']}
                    if payload.skirt_choice not in allowed:
                        raise ApiError('skirt_choice_required','下裙被遮挡，请先选择本次采用的下裙基础款。',422)
                    if payload.opening_choice is not None:
                        raise ApiError('invalid_opening_choice','本步请先选择下裙，再确认其它待选细节。',422)
                    component=payload.skirt_choice
                    for visual in proposal['observations']:
                        if visual['garment_index']==proposal['skirt_choice_index']:
                            visual.update(component=component,component_source='user_confirmation',skirt_candidates=[])
                            visual.setdefault('features',{}).update(flat_front=component=='mamian-skirt',side_pleats=component=='mamian-skirt')
                    proposal['scene']['observations']=copy.deepcopy(proposal['observations'])
                    proposal['skirt_choice']=component
                    if component not in service.find_components(text):
                        text+=('；' if text else '')+service.names[component]
                elif payload.skirt_choice is not None:
                    raise ApiError('invalid_skirt_choice','当前图片没有待选择的下裙款式，请重新识别。',422)
                if proposal.get('opening_choices'):
                    if payload.opening_choice is None:
                        raise ApiError('opening_choice_required','前襟被遮挡，请先选择对襟闭合或右侧斜开襟。',422)
                    component=proposal['opening_choice_component']
                    value=int(payload.opening_choice=='center')
                    try:
                        supplied=service.supplied_fields(text,component,body_from(state['body']))
                    except ValueError as error:
                        raise ApiError('invalid_parameters',str(error),422)
                    if component+'.opening_type' in supplied and supplied[component+'.opening_type']!=value:
                        raise ApiError('opening_choice_conflict','文字开襟要求与所选按钮不同，请统一后重试。',422)
                    visuals=proposal['observations'] if proposal.get('outfit') else [proposal]
                    for visual in visuals:
                        if visual['component']==component:
                            visual.setdefault('features',{}).update(upper_front='closed',front_opening=payload.opening_choice)
                            visual['opening_source']='user_confirmation'
                    if proposal.get('scene'):
                        proposal['scene']['observations']=copy.deepcopy(proposal['observations'])
                    proposal['opening_choice']=payload.opening_choice
                elif payload.opening_choice is not None:
                    raise ApiError('invalid_opening_choice','当前图片没有待确认的开襟选项，请重新识别。',422)
            elif payload.opening_choice is not None or payload.skirt_choice is not None or payload.innerwear_choice is not None:
                raise ApiError('invalid_opening_choice','请先识别图片并选择本次图片的开襟选项。',422)
            state['image_proposal']=None
            state['busy'] = True
            ident = uuid.uuid4().hex
            tasks[ident] = {'session':state['id'],'task_id':ident,'status':'queued','stage':'queued',
                            'progress':5,'result':None,'error':None}
            if payload.request_id:
                state['parse_requests'][payload.request_id]={'fingerprint':fingerprint,'task_id':ident,
                    'mode':'picture_text' if image_path and text else ('picture' if image_path else 'text')}
                while len(state['parse_requests'])>64:
                    state['parse_requests'].pop(next(iter(state['parse_requests'])))
        background.add_task(execute,ident,text,image_path,proposal,payload.scope)
        return {'task_id':ident,'mode':'picture_text' if image_path and text else ('picture' if image_path else 'text')}

    @app.get('/api/v1/tasks/{ident}')
    def task_status(ident: str, x_session_id: Optional[str] = Header(None)):
        state = session(x_session_id)
        with lock:
            task = tasks.get(ident)
            if not task or task['session'] != state['id']:
                raise ApiError('task_not_found','任务不存在或不属于当前会话。',404)
            return public_task(task)

    @app.get('/api/v1/design/params')
    def design_params(x_session_id: Optional[str] = Header(None)):
        state = session(x_session_id)
        with lock:
            return design_response(state)

    @app.get('/api/v1/design/history')
    def design_history(x_session_id: Optional[str] = Header(None)):
        state=session(x_session_id)
        with lock:
            items=[]
            for saved in recent_designs(service,root,state['id']):
                meta=saved['pattern']
                names=([g['name'] for g in meta['garments']] if saved['outfit']
                    else [service.names[meta['component']]])
                items.append({'design_id':saved['folder'].name,'name':'＋'.join(names),
                    'panel_count':meta['panel_count'],'updated_at':meta['updated_at'],
                    'summary':history_summary(saved),
                    'current':state['folder']==saved['folder'],
                    'has_reference_image':bool(meta.get('reference_image_url'))})
            return {'items':items}

    @app.post('/api/v1/design/restore')
    def restore_design(payload: RestoreInput,x_session_id: Optional[str] = Header(None)):
        state=session(x_session_id)
        with lock:
            available(state)
            try:
                saved=restore_saved_design(service,root,state['id'],payload.design_id)
            except ValueError:
                raise ApiError('invalid_saved_design','这份纸样不存在、文件不完整或已不符合当前模板；当前纸样保持不变。',422)
            remember_design(root,state['id'],saved['folder'])
            state.update(saved,image_proposal=None)
            return {'status':'generated','reply':'已恢复所选纸样、款式参数和人体尺寸。',
                'pattern':copy.deepcopy(state['pattern']),'design_params':design_response(state)['params'],
                'body_params':{'body_id':'mean_female','available_bodies':['mean_female'],
                    'params':body_from(state['body']).params,
                    'parameter_sources':copy.deepcopy(state['body_sources'])},'design_list':[]}

    @app.put('/api/v1/design/params')
    def update_design(payload: ChangeInput, x_session_id: Optional[str] = Header(None)):
        state = session(x_session_id)
        with lock:
            available(state)
            if state['outfit']:
                garments=copy.deepcopy(state['outfit'])
                if len(payload.path)!=2:
                    raise ApiError('invalid_parameter','该参数不属于当前服饰组合。',422)
                section,key=payload.path
                selected=[g for g in garments if section in g['patch'] and key in g['patch'][section]]
                if not selected:
                    raise ApiError('invalid_parameter','该参数不属于当前服饰组合。',422)
                for g in selected:
                    path=section+'.'+key
                    if payload.unit=='cm':
                        from training.schema import finite_number
                        if not finite_number(payload.value):
                            raise ApiError('invalid_parameter','长度必须是有效厘米数。',422)
                        try:
                            reference=service.length_reference(section,key,state['body'])
                        except ValueError as error:
                            raise ApiError('invalid_parameter',str(error),422)
                        g['patch'][section][key]['v']=round(payload.value/reference,8)
                        g['absolute_lengths_cm'][path]=payload.value
                    else:
                        g['patch'][section][key]['v']=payload.value
                        g['absolute_lengths_cm'].pop(path,None)
                    g['sources'][path]='manual'
                    g['default_fields']=[v for v in g['default_fields'] if v!=path]
                return render_outfit(state,garments,state['body'])
            patch = copy.deepcopy(state['patch'])
            if len(payload.path) != 2 or payload.path[0] not in patch or payload.path[1] not in patch[payload.path[0]]:
                raise ApiError('invalid_parameter','该参数不属于当前组件。',422)
            section, key = payload.path
            absolute = dict(state['absolute_lengths_cm'])
            path = section + '.' + key
            if payload.unit == 'cm':
                from training.schema import finite_number
                if not finite_number(payload.value):
                    raise ApiError('invalid_parameter','长度必须是有效厘米数。',422)
                try:
                    reference = service.length_reference(section,key,state['body'])
                except ValueError as error:
                    raise ApiError('invalid_parameter',str(error),422)
                patch[section][key]['v'] = round(payload.value/reference, 8)
                absolute[path] = payload.value
            elif payload.unit == 'native':
                patch[section][key]['v'] = payload.value
                absolute.pop(path,None)
            else:
                raise ApiError('invalid_parameter','参数单位不受支持。',422)
            sources = dict(state['sources'], **{section+'.'+key:'manual'})
            defaults = [v for v in state['defaults'] if v != section+'.'+key]
            return render(state,patch,state['body'],sources,defaults,absolute)

    @app.get('/api/v1/body/params')
    def body_params(x_session_id: Optional[str] = Header(None)):
        state = session(x_session_id)
        return {'body_id':'mean_female','available_bodies':['mean_female'],
                'params':body_from(state['body']).params,'parameter_sources':copy.deepcopy(state['body_sources'])}

    @app.put('/api/v1/body/params')
    def update_body(payload: ChangeInput, x_session_id: Optional[str] = Header(None)):
        state = session(x_session_id)
        with lock:
            available(state)
            if len(payload.path)!=1 or payload.path[0] not in state['body']:
                raise ApiError('invalid_body_parameter','该人体参数不能直接修改。',422)
            body = dict(state['body'], **{payload.path[0]:payload.value})
            try:
                body_from(body)
            except ValueError as error:
                raise ApiError('invalid_body_parameter',str(error),422)
            sources=dict(state['body_sources'],**{payload.path[0]:'manual'})
            if state['pattern'] is None:
                # Preparing a body is not a request to make the default skirt.
                save_body_draft(root,state['id'],body,sources)
                state.update(body=copy.deepcopy(body),body_sources=sources)
                return {'svg_url':None,'panel_count':0,'stitch_count':0}
            if state['outfit']:
                garments=copy.deepcopy(state['outfit'])
                for g in garments:
                    g['patch']=service.preserve_absolute_lengths(g['patch'],body,g['absolute_lengths_cm'],g['sources'])
                return render_outfit(state,garments,body,sources)
            patch = service.preserve_absolute_lengths(state['patch'],body,state['absolute_lengths_cm'],state['sources'])
            return render(state,patch,body,state['sources'],state['defaults'],state['absolute_lengths_cm'],sources)

    @app.get('/api/v1/pattern')
    def get_pattern(x_session_id: Optional[str] = Header(None)):
        state = session(x_session_id)
        with lock:
            return copy.deepcopy(state['pattern']) or {'svg_url':None,'panel_count':0,'stitch_count':0}

    @app.post('/api/v1/design/default')
    def default_design(x_session_id: Optional[str] = Header(None)):
        state = session(x_session_id)
        with lock:
            available(state)
            if state['outfit']:
                garments=copy.deepcopy(state['outfit'])
                contexts=common_contexts(service,[g['component'] for g in garments])
                for g in garments:
                    g['patch']=service.defaults(g['component'])
                    for field,values in contexts.items():
                        g['patch']['traditional'][field]['v']=values[0]
                    g['sources']={s+'.'+k:'default' for s,fields in g['patch'].items() for k in fields}
                    g['default_fields']=list(g['sources'])
                    g['absolute_lengths_cm']={}
                    g.pop('note',None)
                render_outfit(state,garments,state['body'])
                return design_response(state)
            component = next(k for k in state['patch'] if k!='traditional')
            patch = service.defaults(component)
            defaults = [section+'.'+key for section,fields in patch.items() for key in fields]
            render(state,patch,state['body'],{key:'default' for key in defaults},defaults)
            return design_response(state)

    @app.post('/api/v1/design/random')
    def random_design(x_session_id: Optional[str] = Header(None)):
        state = session(x_session_id)
        with lock:
            available(state)
            if state['outfit']:
                for _ in range(100):
                    garments=copy.deepcopy(state['outfit'])
                    for g in garments:
                        for key,spec in service.schema['components'][g['component']]['fields'].items():
                            g['patch'][g['component']][key]['v']=random.choice(spec.get('random_values',spec['training_values']))
                        g['absolute_lengths_cm']={}
                        g.pop('note',None)
                        g['sources']={s+'.'+k:('random' if s==g['component'] else g['sources'].get(s+'.'+k,'default'))
                            for s,fields in g['patch'].items() for k in fields}
                        g['default_fields']=[k for k,v in g['sources'].items() if v=='default']
                    try:
                        render_outfit(state,garments,state['body'])
                    except ApiError as error:
                        if error.code in {'invalid_geometry','invalid_parameters'}:
                            continue
                        raise
                    return design_response(state)
                raise ApiError('random_failed','暂时无法生成有效组合，请恢复默认后重试。')
            component = next(k for k in state['patch'] if k!='traditional')
            for _ in range(100):
                patch = service.defaults(component)
                for key,spec in service.schema['components'][component]['fields'].items():
                    patch[component][key]['v'] = random.choice(spec.get('random_values',spec['training_values']))
                if not form_errors(patch,service.template):
                    sources = {section+'.'+key: ('random' if section==component else 'default')
                        for section,fields in patch.items() for key in fields}
                    defaults = [key for key,value in sources.items() if value=='default']
                    try:
                        render(state,patch,state['body'],sources,defaults)
                    except ApiError as error:
                        if error.code in {'invalid_geometry','invalid_parameters'}:
                            continue
                        raise
                    return design_response(state)
            raise ApiError('random_failed','暂时无法生成有效随机参数，请恢复默认后重试。')

    def ensure_current_files(state):
        try:
            verify_design(state['folder'],state['pattern'].get('integrity_version'))
        except (ValueError,OSError):
            raise ApiError('saved_design_changed','当前纸样文件已变化或不完整，请从最近纸样恢复另一份完整结果，或重新生成。',409)

    def archive_design(state):
        with lock:
            if not state['pattern'] or not state['folder']:
                raise ApiError('no_pattern','请先生成纸样。')
            ensure_current_files(state)
            if state['outfit']:
                buffer=build_outfit_archive(state['folder'])
            else:
                component=next(key for key in state['patch'] if key!='traditional')
                buffer = build_archive(state['folder'],service.names[component])
        return buffer

    def archive_name(state):
        components=([g['component'] for g in state['outfit']] if state['outfit']
                    else [state['pattern']['component']])
        names=['襦裙下裳' if c=='ruqun-skirt' else service.names[c] for c in components]
        return '二维纸样-'+'＋'.join(names)+'-'+state['folder'].name[:8]+'.zip'

    @app.post('/api/v1/download/link')
    def download_link(x_session_id: Optional[str] = Header(None)):
        state = session(x_session_id)
        with lock:
            buffer = archive_design(state)
            filename=archive_name(state)
            bundle = state['folder'] / filename
            bundle.write_bytes(buffer.getvalue())
            return {'url':'/static/' + bundle.relative_to(root).as_posix(), 'filename':filename}

    @app.get('/api/v1/download')
    def download(x_session_id: Optional[str] = Header(None)):
        state=session(x_session_id)
        with lock:
            buffer=archive_design(state)
            filename=archive_name(state)
        return StreamingResponse(buffer, media_type='application/zip', headers={
            'Content-Disposition':"attachment; filename=traditional-pattern.zip; filename*=UTF-8''"+quote(filename)})

    def printable(state):
        available(state)
        if not state['pattern'] or not state['folder']:
            raise ApiError('no_pattern','请先生成纸样。')
        ensure_current_files(state)
        return state['folder']

    @app.get('/api/v1/print/plan')
    def printing_plan(x_session_id: Optional[str] = Header(None)):
        state=session(x_session_id)
        with lock:
            folder=printable(state)
            try:
                return {**print_plan(folder),'pattern_url':state['pattern']['svg_url']}
            except ValueError as error:
                raise ApiError('print_invalid',str(error),422)

    @app.post('/api/v1/print/link')
    def printing_link(payload: Optional[PrintInput] = None, x_session_id: Optional[str] = Header(None)):
        state=session(x_session_id)
        with lock:
            folder=printable(state)
            pattern_url=state['pattern']['svg_url']
            if payload and payload.pattern_url and payload.pattern_url!=pattern_url:
                raise ApiError('print_changed','纸样已更新，请关闭后重新预览A4纸样。',409)
            state['busy']=True
        try:
            output,plan=export_print_pdf(folder)
            return {'url':'/static/'+output.relative_to(root).as_posix(),'filename':output.name,
                    'plan':plan,'pattern_url':pattern_url}
        except ImportError:
            raise ApiError('print_dependency','请安装后端requirements.txt中的PDF依赖后重试。',503)
        except ValueError as error:
            raise ApiError('print_invalid',str(error),422)
        finally:
            with lock:
                state['busy']=False

    @app.get('/api/v1/vocab')
    def vocab():
        return {'quick_tags':['明代褙子，衣长110cm；马面裙，裙长95cm，常服',
                              '唐代半臂，衣长50cm；襦裙，裙长95cm，常服',
                              '交领长袍，衣长130cm，袖长55cm','立领对襟上衣；马面裙，裙长95cm',
                              '交领上衣；襦裙，裙长95cm；双层云肩','圆领长袍，衣长130cm',
                              '交领上衣；圆领对襟比甲；襦裙，裙长95cm',
                                '交领上衣；襦裙，裙长95cm；披帛，披帛长300cm，幅宽30cm',
                              '明代马面裙，裙长95cm，常服'], 'components':service.names}

    app.state.engine, app.state.sessions, app.state.tasks = service,sessions,tasks
    return app


def re_image_id(value):
    import re
    return bool(re.fullmatch(r'img_[0-9a-f]{32}',value))


app = create_app()
