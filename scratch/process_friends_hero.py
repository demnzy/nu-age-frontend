from PIL import Image, ImageFilter
import numpy as np
from collections import deque

input_path = r"C:\Users\Admin\.gemini\antigravity-ide\brain\9f0d952f-2526-44e0-a5c0-aba3dd8f6b63\friends_hero_icon_1789129111512.jpg"
output_path = r"c:\Users\Admin\Desktop\Code\NU-Front\assets\friends_hero.png"
preview_dark = r"C:\Users\Admin\.gemini\antigravity-ide\brain\9f0d952f-2526-44e0-a5c0-aba3dd8f6b63\friends_hero_preview_dark.png"

img = Image.open(input_path).convert("RGBA")
w, h = img.size
arr = np.array(img, dtype=np.float32)
rgb = arr[:, :, :3]

# The squircle itself has strong blue/cyan color:
# Cyan bottom: R~0..100, G~200..230, B~200..240
# Blue top: R~60..120, G~140..190, B~240..255
# White outside has: sat < 20 and lum > 210, OR even lum > 195 and sat < 15.
# Let's do a floodfill from outside where sat < 35 or (lum > 220 and sat < 50):

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
    # Outside background:
    # Notice the white rim has sat < 40 and lum > 210
    if lum > 230 and sat < 45:
        return True
    if lum > 210 and sat < 30:
        return True
    if lum > 190 and sat < 18:
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
# Erode mask slightly to eliminate outer glow halo
alpha_eroded = alpha_img.filter(ImageFilter.MinFilter(5))
# Smooth edges nicely
alpha_smooth = alpha_eroded.filter(ImageFilter.GaussianBlur(radius=1.2))

result = img.copy()
result.putalpha(alpha_smooth)

bbox = result.getbbox()
if bbox:
    margin = 8
    left = max(0, bbox[0] - margin)
    top = max(0, bbox[1] - margin)
    right = min(w, bbox[2] + margin)
    bottom = min(h, bbox[3] + margin)
    result = result.crop((left, top, right, bottom))

result.thumbnail((256, 256), Image.Resampling.LANCZOS)
result.save(output_path, "PNG")

# Render dark preview with dark surface color #252424 (matching NU-Front dark surface)
bg_dark = Image.new("RGBA", result.size, (37, 36, 36, 255))
bg_dark.alpha_composite(result)
bg_dark.save(preview_dark, "PNG")
print("Updated transparent hero icon and dark preview successfully.")
