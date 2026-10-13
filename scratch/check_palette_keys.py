import re

with open('src/platform_admin_view.py', 'r', encoding='utf-8') as f:
    content = f.read()

keys = {'bg', 'surface', 'surface_variant', 'card_bg', 'border', 'border_subtle', 'text', 'text_muted', 'accent', 'accent_glow', 'primary', 'danger', 'danger_bg', 'warning', 'warning_bg', 'success', 'success_bg', 'info', 'info_bg', 'purple'}

lookups = re.findall(r'palette\[([\'\"][a-zA-Z0-9_]+[\'\"])\]', content)
missing = set()
for l in lookups:
    k = l.strip('\'"')
    if k not in keys:
        missing.add(k)

print('Missing palette keys found:', missing)
