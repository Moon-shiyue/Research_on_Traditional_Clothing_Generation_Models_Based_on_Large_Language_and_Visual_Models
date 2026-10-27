"""Lazy native Qwen2-VL inference; image requests actually use image pixels."""
import json
import threading

from .settings import MODEL_PATH, ADAPTER_PATH
from training.common import digest
from training.runtime import load_model, tokenizer_from, prompt_hash
from training.infer import generate_predictions
from training.schema import extract_json
from .cloud_vision import CloudVision


class ModelUnavailable(RuntimeError):
    pass


class NativeModel:
    def __init__(self):
        self.lock = threading.RLock()
        self.model = None
        self.processor = None
        self.tokenizer = None
        self.cloud_vision = CloudVision()

    def _load(self):
        if self.model is not None:
            return
        import torch
        if not torch.cuda.is_available():
            raise ModelUnavailable('本地自由文字模型需要可用的 NVIDIA GPU；明确组件和数值可直接生成纸样。')
        if not (ADAPTER_PATH / 'run_manifest.json').is_file():
            raise ModelUnavailable('尚未配置已训练模型，请先配置适配器目录。')
        manifest = json.loads((ADAPTER_PATH / 'run_manifest.json').read_text(encoding='utf-8'))
        if (manifest['status'] != 'complete' or manifest['system_prompt_sha256'] != prompt_hash()
                or manifest['model_config_sha256'] != digest(MODEL_PATH / 'config.json')
                or manifest['tokenizer_sha256'] != digest(MODEL_PATH / 'tokenizer.json')
                or manifest['adapter_file_sha256'] != digest(ADAPTER_PATH / 'adapter_model.safetensors')):
            raise ModelUnavailable('模型文件校验不一致，请检查基座与适配器版本。')
        from transformers import AutoProcessor
        tokenizer = tokenizer_from(MODEL_PATH)
        processor = AutoProcessor.from_pretrained(
            str(MODEL_PATH), local_files_only=True,
            min_pixels=128 * 28 * 28, max_pixels=384 * 28 * 28)
        model = load_model(MODEL_PATH, ADAPTER_PATH)
        model.eval()
        model.generation_config.temperature = 1.0
        model.generation_config.top_p = 1.0
        model.generation_config.top_k = 50
        self.tokenizer, self.processor, self.model = tokenizer, processor, model

    def text(self, text):
        with self.lock:
            self._load()
            predictions = generate_predictions(self.model, self.tokenizer, [{'id': 'request', 'prompt': text}])
            return extract_json(predictions[0]['prediction'])

    def image(self, image_path, components):
        return self.cloud_vision.image(image_path,components)

    def image_outfit(self, image_path, components):
        return self.cloud_vision.image(image_path,components,outfit=True)

    def image_local(self, image_path, components):
        with self.lock:
            self._load()
            import torch
            from PIL import Image, ImageOps
            with Image.open(image_path) as source:
                image = ImageOps.exif_transpose(source).convert('RGB')
                image.thumbnail((1024, 1024))
            prompt = (
                '描述图片中人物所穿的上衣和下装，说明颜色和款式。不要编造看不到的服饰。')
            messages = [{'role': 'user', 'content': [{'type': 'image'}, {'type': 'text', 'text': prompt}]}]
            chat = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = self.processor(text=[chat], images=[image], padding=True, return_tensors='pt')
            inputs = {key: value.to(next(self.model.parameters()).device) for key, value in inputs.items()}
            # The v1 adapter was trained on text JSON only. Keep the base visual
            # recognition behavior for classification, then generate code safely.
            flags = torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32
            try:
                torch.backends.cuda.matmul.allow_tf32 = True
                torch.backends.cudnn.allow_tf32 = True
                with self.model.disable_adapter(), torch.inference_mode():
                    # Bypass the text-only PEFT generation wrapper for pixels.
                    output = self.model.get_base_model().generate(**inputs, do_sample=False, max_new_tokens=200)
                    description = self.processor.batch_decode(output[:, inputs['input_ids'].shape[1]:], skip_special_tokens=True)[0]
                    # A separate caption avoids biasing visual observation toward
                    # a particular traditional skirt before examining the image.
                    if not any(word in description for word in ['传统', '汉服', '马面', '襦裙', '褙子', '云肩', '琵琶袖']):
                        return {'component': None, 'reason': '图片观察：' + description[:350] + '\n暂未确认传统组件，请补充要制作的组件名称。'}
                    classification = (
                        '检查图片中服装的可见结构，选择一个可制作的组件。有裙装时优先分析裙装。'
                        '马面裙需要同时看到中部平整裙门和两侧成组褶裥；襦裙下裳是其它可确认的传统展开长裙。'
                        '不要因为红色、花纹或出现汉服文字就判断为马面裙。现代裤装不属于裙装。'
                        '看不清或不能区分时component=null，不要默认选择襦裙。候选：'
                        + '、'.join(components.values())
                        + '。component必须写中文候选名称，不写英文代码。仅返回JSON：{"component":中文候选名称或null,"flat_front":true或false或null,'
                          '"side_pleats":true或false或null,"length":"full/mid/short/unclear",'
                          '"evidence":"简述可见结构，不猜隐藏结构"}。')
                    # Look at the pixels again: a generic caption may omit the
                    # very skirt-door/pleat evidence that distinguishes styles.
                    chat = self.processor.apply_chat_template(
                        [{'role':'user','content':[{'type':'image'},{'type':'text','text':classification}]}],
                        tokenize=False, add_generation_prompt=True)
                    detail = self.processor(text=[chat], images=[image], padding=True, return_tensors='pt')
                    detail = {key:value.to(next(self.model.parameters()).device) for key,value in detail.items()}
                    output = self.model.get_base_model().generate(**detail, do_sample=False, max_new_tokens=180)
                    text = self.processor.batch_decode(output[:,detail['input_ids'].shape[1]:], skip_special_tokens=True)[0]
            finally:
                torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32 = flags
            result = extract_json(text)
            if result and result.get('component') in components.values():
                result['component'] = next(key for key,value in components.items() if value == result['component'])
            if not result or result.get('component') not in components:
                return {'component': None, 'reason': '图片中的传统组件暂时无法可靠确认，请补充组件名称。'}
            if result['component'] == 'mamian-skirt' and not (
                    result.get('flat_front') is True and result.get('side_pleats') is True):
                return {'component': None, 'reason': '尚未同时确认裙门与侧褶，请补充清晰的裙装正面图。'}
            if result['component']=='ruqun-skirt' and result.get('flat_front') is True and result.get('side_pleats') is True:
                return {'component':None,'reason':'图片结构特征与款式判断不一致，请明确裙装名称；本次不自动套用襦裙模板。'}
            return {'component': result['component'], 'reason': '图片观察：' + description[:350]
                    + '\n结构依据：' + str(result.get('evidence', ''))[:200],
                    'features': {key:result.get(key) for key in ['flat_front','side_pleats','length']}}
