from PIL import Image, ImageFilter
import numpy as np

img = Image.open(r"c:\Users\Admin\Desktop\Code\NU-Front\assets\friends_hero.png").convert("RGBA")
arr = np.array(img)
rgb = arr[:, :, :3]
alpha = arr[:, :, 3]

# Pixels that are green:
# G channel is higher than R and B
is_green = (rgb[:, :, 1].astype(int) > rgb[:, :, 0].astype(int) + 12) & \
           (rgb[:, :, 1].astype(int) > rgb[:, :, 2].astype(int) + 12) & \
           (rgb[:, :, 1] > 40)

# Also keep highlights on the green surface (where lum > 200 but surrounded by green)
# Any isolated grey at the very bottom:
height, width = arr.shape[:2]
for y in range(int(height * 0.85), height):
    for x in range(width):
        if not is_green[y, x]:
            alpha[y, x] = 0

arr[:, :, 3] = alpha
result = Image.fromarray(arr)

# Smooth edges
alpha_channel = Image.fromarray(arr[:, :, 3], mode='L')
alpha_smooth = alpha_channel.filter(ImageFilter.GaussianBlur(radius=0.8))
result.putalpha(alpha_smooth)

bbox = result.getbbox()
if bbox:
    result = result.crop(bbox)

result.save(r"c:\Users\Admin\Desktop\Code\NU-Front\assets\friends_hero.png", "PNG")

# Update dark preview
bg_dark = Image.new("RGBA", result.size, (37, 36, 36, 255))
bg_dark.alpha_composite(result)
bg_dark.save(r"C:\Users\Admin\.gemini\antigravity-ide\brain\9f0d952f-2526-44e0-a5c0-aba3dd8f6b63\friends_hero_primary_dark.png", "PNG")
print("Cleaned bottom shadow!")
