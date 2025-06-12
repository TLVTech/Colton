# Colton/core/watermark.py

from PIL import Image
from PIL.Image import Resampling
import io
import cairosvg
import os

def add_watermark(
    image_path: str,
    watermark_path: str,
    output_path: str,
    scale_factor: float = 0.4,
    padding: int = 60,
    opacity: float = 0.35
) -> str:
    """
    Load an image, overlay an SVG or raster watermark with the given opacity/scale, and save.
    Returns the path where the watermarked image was written.
    """
    try:
        base_image = Image.open(image_path)
        # Convert to RGBA if needed
        if base_image.format == 'WEBP' and base_image.mode != 'RGBA':
            base_image = base_image.convert('RGBA')
        elif base_image.mode != 'RGBA':
            base_image = base_image.convert('RGBA')

        # Load watermark (SVG->PNG if necessary)
        if watermark_path.lower().endswith('.svg'):
            svg_data = cairosvg.svg2png(url=watermark_path)
            watermark = Image.open(io.BytesIO(svg_data)).convert("RGBA")
        else:
            watermark = Image.open(watermark_path).convert("RGBA")

        # Resize watermark to width = scale_factor × base_image.width
        new_wm_width = int(base_image.width * scale_factor)
        new_wm_height = int(new_wm_width * watermark.height / watermark.width)
        watermark = watermark.resize((new_wm_width, new_wm_height), Resampling.LANCZOS)

        # Apply partial transparency
        watermark_with_opacity = Image.new('RGBA', watermark.size, (0, 0, 0, 0))
        for x in range(watermark.width):
            for y in range(watermark.height):
                r, g, b, a = watermark.getpixel((x, y))
                watermark_with_opacity.putpixel((x, y), (r, g, b, int(a * opacity)))

        # Compute bottom-left position
        pos = (padding, base_image.height - watermark_with_opacity.height - padding)

        # Composite onto a fresh RGBA canvas
        final_image = Image.new('RGBA', base_image.size, (0, 0, 0, 0))
        final_image.paste(base_image, (0, 0))
        final_image.paste(watermark_with_opacity, pos, watermark_with_opacity)

        # Save
        output_ext = os.path.splitext(output_path)[1].lower()
        if output_ext == '.webp':
            final_image.save(output_path, 'WEBP', lossless=True, quality=90)
        else:
            rgb_final = final_image.convert("RGB")
            rgb_final.save(output_path)

        return output_path

    except Exception as e:
        raise Exception(f"Error processing image: {e}")

def process_folder_watermark(
    input_folder: str,
    output_folder: str,
    watermark_path: str,
    scale_factor: float = 0.60,
    padding: int = 70,
    opacity: float = 0.35
) -> None:
    """
    Apply add_watermark(...) to every supported image in input_folder and write into output_folder.
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder, exist_ok=True)

    supported_formats = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp')
    for filename in os.listdir(input_folder):
        if filename.lower().endswith(supported_formats):
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, filename)
            try:
                add_watermark(input_path, watermark_path, output_path, scale_factor, padding, opacity)
                print(f"Processed watermark for: {filename}")
            except Exception as e:
                print(f"Error processing {filename}: {e}")
