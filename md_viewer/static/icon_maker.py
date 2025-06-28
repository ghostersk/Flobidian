from pathlib import Path
from PIL import Image
src_path = Path("notes_app.png")
dst_path = Path("favicon.ico")
with Image.open(src_path) as img:
    img = img.convert("RGBA")
    icon_sizes = [(32, 32), (128, 128), (256, 256)]
    resized_images = [img.resize(size, Image.LANCZOS) for size in icon_sizes]
    resized_images[0].save(dst_path, format='ICO', sizes=icon_sizes)