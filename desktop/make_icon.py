"""Render the studio's simple geometric mark as Windows application assets."""
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parent
image = Image.new('RGBA', (256, 256), (18, 18, 21, 255))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((2, 2, 253, 253), radius=48, fill='#17171b')
draw.polygon([(50, 70), (200, 40), (200, 185), (50, 215)], fill='#ff963f')
draw.polygon([(89, 93), (168, 77), (168, 99), (113, 110), (113, 129), (158, 120), (158, 142), (113, 151), (113, 177), (89, 182)], fill='#20180f')
image.save(root / 'icon.png')
image.save(root / 'icon.ico', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
