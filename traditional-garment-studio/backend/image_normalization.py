"""Use one upright, white-backed RGB photo for saved references and vision."""
from PIL import Image, ImageOps


def upright_rgb(source):
    photo = ImageOps.exif_transpose(source)
    # Dropping alpha directly exposes hidden RGB (commonly black), unlike the
    # browser's white-backed canvas. This also handles palette PNG tRNS data.
    if 'A' in photo.getbands() or 'transparency' in photo.info:
        rgba = photo.convert('RGBA')
        background = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
        return Image.alpha_composite(background, rgba).convert('RGB')
    return photo.convert('RGB')
