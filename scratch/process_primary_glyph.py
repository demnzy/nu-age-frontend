from PIL import Image, ImageFilter
import numpy as np
from collections import deque

input_path = r"C:\Users\Admin\.gemini\antigravity-ide\brain\9f0d952f-2526-44e0-a5c0-aba3dd8f6b63\primary_friends_glyph_1789129686736.jpg"
output_path = r"c:\Users\Admin\Desktop\Code\NU-Front\assets\friends_hero.png"
preview_dark = r"C:\Users\Admin\.gemini\antigravity-ide\brain\9f0d952f-2526-44e0-a5c0-aba3dd8f6b63\friends_hero_primary_dark.png"
preview_light = r"C:\Users\Admin\.gemini\antigravity-ide\brain\9f0d952f-2526-44e0-a5c0-aba3dd8f6b63\friends_hero_primary_light.png"

img = Image.open(input_path).convert("RGBA")
w, h = img.size
arr = np.array(img, dtype=np.float32)
rgb = arr[:, :, :3]

# Outer floodfill
visited = np.zeros((h, w), dtype=bool)
queue = deque()

for x in range(w):
    queue.append((x, 0))
    queue.append((x, h - 1))
    visited[0, x] = True
    visited[h - 1, x] = True

for y in range(h):
    queue.append((0, y))
    queue.append((w - 1, y))
    visited[y, 0] = True
    visited[y, w - 1] = True

def is_bg(x, y):
    p = rgb[y, x]
    lum = np.mean(p)
    sat = np.max(p) - np.min(p)
    # The green glyph has high green dominance: G > R + 30 or G > B + 30
    is_green = (p[1] > p[0] + 25) and (p[1] > p[2] + 25) and p[1] > 60
    if is_green:
        return False
    # White / light grey background:
    if lum > 220:
        return True
    if lum > 190 and sat < 25:
        return True
    return False

while queue:
    x, y = queue.popleft()
    for nx, ny in [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]:
        if 0 <= nx < w and 0 <= ny < h and not visited[ny, nx]:
            if is_bg(nx, ny):
                visited[ny, nx] = True
                queue.append((nx, ny))

alpha = np.ones((h, w), dtype=np.uint8) * 255
alpha[visited] = 0

alpha_img = Image.fromarray(alpha, mode='L')
# Erode slightly to eliminate light fringes
alpha_eroded = alpha_img.filter(ImageFilter.MinFilter(3))
alpha_smooth = alpha_eroded.filter(ImageFilter.GaussianBlur(radius=1.2))

result = img.copy()
result.putalpha(alpha_smooth)

bbox = result.getbbox()
if bbox:
    margin = 12
    left = max(0, bbox[0] - margin)
    top = max(0, bbox[1] - margin)
    right = min(w, bbox[2] + margin)
    bottom = min(h, bbox[3] + margin)
    result = result.crop((left, top, right, bottom))

# Resize nicely
result.thumbnail((256, 256), Image.Resampling.LANCZOS)
result.save(output_path, "PNG")
print(f"Saved primary glyph to {output_path}")

# Dark preview
bg_dark = Image.new("RGBA", result.size, (37, 36, 36, 255))
bg_dark.alpha_composite(result)
bg_dark.save(preview_dark, "PNG")

# Light preview
bg_light = Image.new("RGBA", result.size, (250, 250, 250, 255))
bg_light.alpha_composite(result)
bg_light.save(preview_light, "PNG")
print("Previews saved!")
