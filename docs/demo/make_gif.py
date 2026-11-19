import json, sys
from PIL import Image
frames = json.load(open(sys.argv[1]))
out = sys.argv[2]
W = int(sys.argv[3])
imgs, durs = [], []
for fr in frames:
    im = Image.open(fr["f"]).convert("RGB")
    h = round(im.height * W / im.width)
    im = im.resize((W, h), Image.LANCZOS)
    imgs.append(im.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
    durs.append(fr["ms"])
imgs[0].save(out, save_all=True, append_images=imgs[1:], duration=durs, loop=0, optimize=True, disposal=1)
print(out, sum(durs) / 1000, "s")
