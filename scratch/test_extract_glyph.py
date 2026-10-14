from PIL import Image, ImageFilter
import numpy as np

img_path = r"C:\Users\Admin\.gemini\antigravity-ide\brain\9f0d952f-2526-44e0-a5c0-aba3dd8f6b63\friends_hero_icon_1789129111512.jpg"
preview_path = r"C:\Users\Admin\.gemini\antigravity-ide\brain\9f0d952f-2526-44e0-a5c0-aba3dd8f6b63\extracted_glyph_test.png"

img = Image.open(img_path).convert("RGBA")
arr = np.array(img, dtype=np.float32)
rgb = arr[:, :, :3]

# The avatar head, torso, plus sign are inside the center region:
# Let's check center: x between 200 and 850, y between 250 and 800
# Within this region, pixels that belong to the avatar glyph:
# They have low saturation (max(rgb) - min(rgb) < 40) and high luminance (mean(rgb) > 205)
sat = np.max(rgb, axis=-1) - np.min(rgb, axis=-1)
lum = np.mean(rgb, axis=-1)

# Mask for center region
h, w = img.size
y_indices, x_indices = np.indices((h, w))
center_mask = (x_indices > 200) & (x_indices < 850) & (y_indices > 220) & (y_indices < 780)

glyph_mask = center_mask & (sat < 40) & (lum > 200)

print(f"Total glyph pixels detected: {np.sum(glyph_mask)}")

# Create alpha from glyph_mask
alpha = np.zeros((h, w), dtype=np.uint8)
alpha[glyph_mask] = 255

alpha_img = Image.fromarray(alpha, mode='L')
# Smooth mask
alpha_smooth = alpha_img.filter(ImageFilter.GaussianBlur(radius=1.5))

result = img.copy()
result.putalpha(alpha_smooth)

# Crop to glyph bbox
bbox = result.getbbox()
if bbox:
    result = result.crop(bbox)

result.save(preview_path, "PNG")
print("Saved preview to", preview_path, "size:", result.size)
