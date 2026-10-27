"""The photo seen in preview must match the bounded JPEG sent for recognition."""
import base64
import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid

import httpx
from fastapi.testclient import TestClient
from PIL import Image

from .app import create_app
from .chatgpt_plan import PlanSession
from .cloud_vision import CloudVision
from .engine import PaperEngine


def transparent_sample(mode):
    if mode == 'P':
        photo = Image.new('P', (120, 80), 0)
        photo.putpalette([0, 0, 0, 0, 80, 120] + [0] * 762)
        photo.info['transparency'] = 0
        for x in range(60, 120):
            for y in range(80):
                photo.putpixel((x, y), 1)
    else:
        photo = Image.new(mode, (120, 80), (0, 0) if mode == 'LA' else (0, 0, 0, 0))
        photo.paste((60, 255) if mode == 'LA' else (0, 80, 120, 255), (60, 0, 120, 80))
    return photo


class ImageNormalizationTests(unittest.TestCase):
    def test_phone_orientation_is_applied_once_and_semitransparency_is_blended(self):
        with tempfile.TemporaryDirectory() as folder:
            with TestClient(create_app(PaperEngine(model=object()), Path(folder))) as client:
                headers = {'X-Session-Id': str(uuid.uuid4())}
                phone = Image.new('RGB', (120, 80), (200, 30, 20))
                phone.paste((20, 40, 200), (60, 0, 120, 80))
                exif = phone.getexif(); exif[274] = 6
                raw = io.BytesIO(); phone.save(raw, format='JPEG', exif=exif)
                response = client.post('/api/v1/upload/image', headers=headers,
                    files={'file': ('phone.jpg', raw.getvalue(), 'image/jpeg')})
                self.assertEqual(response.status_code, 200)
                upright = Image.open(io.BytesIO(client.get(response.json()['url']).content))
                self.assertEqual(upright.size, (80, 120))
                self.assertNotIn(274, upright.getexif())
                self.assertGreater(upright.getpixel((40, 20))[0], 180)
                self.assertGreater(upright.getpixel((40, 100))[2], 180)
                translucent = Image.new('RGBA', (80, 80), (0, 80, 120, 128))
                raw = io.BytesIO(); translucent.save(raw, format='PNG')
                response = client.post('/api/v1/upload/image', headers=headers,
                    files={'file': ('sheer.png', raw.getvalue(), 'image/png')})
                saved = Image.open(io.BytesIO(client.get(response.json()['url']).content))
                self.assertTrue(all(abs(a-b) <= 3 for a,b in zip(saved.getpixel((40, 40)), (127, 167, 187))))

    def test_uploaded_transparent_photo_uses_white_paper_background_and_keeps_opaque_cloth(self):
        with tempfile.TemporaryDirectory() as folder:
            with TestClient(create_app(PaperEngine(model=object()), Path(folder))) as client:
                headers = {'X-Session-Id': str(uuid.uuid4())}
                for mode in ['RGBA', 'LA', 'P']:
                    with self.subTest(mode=mode):
                        raw = io.BytesIO()
                        transparent_sample(mode).save(raw, format='PNG')
                        response = client.post('/api/v1/upload/image', headers=headers,
                            files={'file': ('cutout.png', raw.getvalue(), 'image/png')})
                        self.assertEqual(response.status_code, 200, response.text)
                        saved = Image.open(io.BytesIO(client.get(response.json()['url']).content))
                        self.assertTrue(all(v >= 250 for v in saved.getpixel((15, 40))), saved.getpixel((15, 40)))
                        self.assertLess(max(saved.getpixel((100, 40))), 130)

    def test_direct_vision_input_composites_alpha_before_building_provider_payload(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            observed = dict(component=None, evidence='Controlled transport test', visible_garments=[],
                flat_front=None, side_pleats=None, length='unclear', hem_shape='unclear',
                tassels='unclear', sleeve_shape='unclear', upper_front='unclear', neckwear_shape='unclear', cloud_layers=None, waist_level='unclear', cuff_finish='unclear', front_opening='unclear', sleeve_extent='unclear', side_slits='unclear', waist_belt='unclear',
                uncertain=True)
            received = []

            def handle(request):
                payload = json.loads(request.content)
                encoded = payload['input'][0]['content'][1]['image_url'].split(',', 1)[1]
                received.append(Image.open(io.BytesIO(base64.b64decode(encoded))).copy())
                return httpx.Response(200, json={'output': [{'type': 'message', 'content': [
                    {'type': 'output_text', 'text': json.dumps(observed)}]}]})

            transport = httpx.MockTransport(handle)
            cloud = CloudVision(transport=transport, plan=PlanSession(folder/'isolated-login', transport=transport))
            cloud.configure('https://api.openai.com/v1', 'gpt-6.1-sol', 'test-only-key')
            for mode in ['RGBA', 'LA', 'P']:
                path = folder/(mode+'.png')
                transparent_sample(mode).save(path)
                cloud.image(path, {'cloud-shoulder': 'Cloud shoulder'})
            self.assertEqual(len(received), 3)
            for photo in received:
                self.assertTrue(all(v >= 250 for v in photo.getpixel((15, 40))))
                self.assertLess(max(photo.getpixel((100, 40))), 130)

