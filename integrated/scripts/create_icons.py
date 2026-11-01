"""Reproducible ContextSwitch vector and antialiased Chrome icon sizes."""
from pathlib import Path
from PIL import Image, ImageDraw
root=Path(__file__).parents[1];out=root/'extension/icons';out.mkdir(parents=True,exist_ok=True)
svg='''<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128"><rect x="1" y="1" width="126" height="126" rx="29" fill="#14251b"/><g fill="none" stroke="#c1ef9b" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"><path d="M34 46h59L80 33"/><path d="m93 46-13 13"/><path d="M94 82H35l13 13"/><path d="M35 82 48 69"/></g></svg>'''
(out/'contextswitch.svg').write_text(svg)
scale=8;image=Image.new('RGBA',(128*scale,128*scale),(0,0,0,0));draw=ImageDraw.Draw(image)
draw.rounded_rectangle((scale,scale,127*scale,127*scale),radius=29*scale,fill='#14251b')
for points in (((34,46),(93,46),(80,33)),((93,46),(80,59)),((94,82),(35,82),(48,95)),((35,82),(48,69))):
    coords=[(x*scale,y*scale) for x,y in points];draw.line(coords,fill='#c1ef9b',width=10*scale,joint='curve')
    for x,y in coords:draw.ellipse((x-5*scale,y-5*scale,x+5*scale,y+5*scale),fill='#c1ef9b')
for size in (16,32,48,128):image.resize((size,size),Image.Resampling.LANCZOS).save(out/f'icon-{size}.png')
public=root/'frontend/public';public.mkdir(exist_ok=True);(public/'contextswitch.svg').write_text(svg)
print('Created SVG source and 16/32/48/128px PNG extension icons')
