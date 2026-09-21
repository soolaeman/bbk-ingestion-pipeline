"""
BBKitchen Fast Watermark & WebP Image Processing Engine.
Ports battle-tested resizing, logo watermarking, and WebP compression.
"""

import os
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent
LOGO_FILE = BASE_DIR / "logo.png"

# Default configuration
LOGO_SIZE_PERCENT = 0.50
LOGO_OPACITY = 200
MAX_SIDE = 1600
WEBP_QUALITY = 80

def process_watermark_and_webp(src_image_path, dest_webp_path, max_side=MAX_SIDE, quality=WEBP_QUALITY) -> bool:
    """
    Resizes image to max_side, applies logo.png watermark with transparency,
    and compresses directly to WebP format.
    """
    try:
        dest_path = Path(dest_webp_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        img = Image.open(src_image_path).convert("RGB")
        w, h = img.size

        # 1. Resize if larger than max_side
        scale = min(max_side / max(w, h), 1.0)
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            w, h = img.size

        # 2. Apply watermark logo if logo.png exists
        if LOGO_FILE.exists():
            logo_raw = Image.open(LOGO_FILE).convert("RGBA")
            target_w = int(w * LOGO_SIZE_PERCENT)
            logo_h = int(logo_raw.size[1] * (target_w / logo_raw.size[0]))
            logo = logo_raw.resize((target_w, logo_h), Image.LANCZOS)
            
            alpha = logo.getchannel("A").point(lambda i: int(i * LOGO_OPACITY / 255))
            logo.putalpha(alpha)
            
            img_rgba = img.convert("RGBA")
            x, y = (w - target_w) // 2, int(h * 0.03)  # Centered horizontally, top 3%
            img_rgba.paste(logo, (x, y), logo)
            img = img_rgba.convert("RGB")

        # 3. Save as optimized WebP
        img.save(dest_path, "WEBP", quality=quality, optimize=True, method=6)
        return True
    except Exception as e:
        print(f"[ERROR] Watermark & WebP conversion failed for {src_image_path}: {e}")
        return False

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        src = sys.argv[1]
        dst = sys.argv[2]
        success = process_watermark_and_webp(src, dst)
        print(f"Conversion {'SUCCESS' if success else 'FAILED'}: {dst}")
    else:
        print("Usage: python watermark_engine.py <src_image> <dest_webp>")
