import sys

from PIL import Image
import os
from typing import Optional

def generate_ico(input_png_path: str, output_ico_path: str, sizes: Optional[list] = None) -> None:
    """
    Generate a .ico file (Windows) from a PNG image.
    Uses Pillow to resize and save in ICO format.

    Args:
        input_png_path: Path to the source PNG image.
        output_ico_path: Path to the output .ico file.
        sizes: List of icon sizes to include (e.g., [(16,16), (32,32), ...]).
               Default: [(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)].
    """
    if sizes is None:
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

    img = Image.open(input_png_path)
    img.save(output_ico_path, format="ICO", sizes=sizes)
    print(f"✅ ICO file generated: {output_ico_path}")

def generate_icns(input_png_path: str, output_icns_path: str) -> None:
    """
    Generate a .icns file (macOS) from a PNG image.
    Uses Pillow to create the .icns bundle with multiple sizes.

    Args:
        input_png_path: Path to the source PNG image (ideally square, >= 1024x1024).
        output_icns_path: Path to the output .icns file.
    """
    img = Image.open(input_png_path)
    icns_images = []

    # Standard sizes for .icns (in pixels)
    icns_sizes = [
        (16, 16, 1),    # 16x16 (1x)
        (16, 16, 2),    # 16x16 (2x, Retina)
        (32, 32, 1),    # 32x32 (1x)
        (32, 32, 2),    # 32x32 (2x)
        (128, 128, 1),  # 128x128 (1x)
        (128, 128, 2),  # 128x128 (2x)
        (256, 256, 1),  # 256x256 (1x)
        (256, 256, 2),  # 256x256 (2x)
        (512, 512, 1),  # 512x512 (1x)
        (512, 512, 2),  # 512x512 (2x)
        (1024, 1024, 1), # 1024x1024 (1x)
    ]

    for width, height, scale in icns_sizes:
        resized_img = img.resize((width, height), Image.Resampling.LANCZOS)
        if resized_img.mode != "RGBA":
            resized_img = resized_img.convert("RGBA")
        icns_images.append((resized_img, scale))

    # img.save(output_icns_path, append_images=icns_images, format="ICNS", save_all=True)
    img.save(output_icns_path, format="ICNS")

    print(f"✅ ICNS file generated: {output_icns_path}")

def convert_icon(input_png_path: str, output_dir: Optional[str] = None) -> None:
    """
    Generate both .ico (Windows) and .icns (macOS) icons from a PNG image.

    Args:
        input_png_path: Path to the source PNG image.
        output_dir: Output directory (default: same as input).
    """
    if output_dir is None:
        output_dir = os.path.dirname(input_png_path) or "."

    base_name = os.path.splitext(os.path.basename(input_png_path))[0]
    ico_path = os.path.join(output_dir, f"{base_name}.ico")
    icns_path = os.path.join(output_dir, f"{base_name}.icns")

    generate_ico(input_png_path, ico_path)
    generate_icns(input_png_path, icns_path)

if __name__ == "__main__":
    input_png = sys.argv[1]  # Replace with your path
    convert_icon(input_png)