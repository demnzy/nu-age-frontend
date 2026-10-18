import os
import urllib.request
import sys

FONTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "fonts"))
os.makedirs(FONTS_DIR, exist_ok=True)

FONTS = {
    "PlusJakartaSans-Variable.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/plusjakartasans/PlusJakartaSans%5Bwght%5D.ttf",
    "Outfit-Variable.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/outfit/Outfit%5Bwght%5D.ttf",
    "Lora-Variable.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/lora/Lora%5Bwght%5D.ttf",
    "SpaceGrotesk-Variable.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf",
    "FiraCode-Variable.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/firacode/FiraCode%5Bwght%5D.ttf",
    "Poppins-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-Regular.ttf",
}

def download_fonts():
    print(f"Downloading fonts into: {FONTS_DIR}")
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for filename, url in FONTS.items():
        dest = os.path.join(FONTS_DIR, filename)
        if os.path.exists(dest) and os.path.getsize(dest) > 10000:
            print(f"[SKIP] {filename} already exists ({os.path.getsize(dest)} bytes)")
            continue
            
        success = False
        for attempt in range(1, 4):
            print(f"[DOWNLOADING] {filename} (attempt {attempt}/3)...")
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = resp.read()
                    if len(data) < 5000:
                        print(f"[ERROR] {filename} download resulted in unusually small file ({len(data)} bytes)")
                        continue
                    with open(dest, "wb") as f:
                        f.write(data)
                    print(f"[SUCCESS] {filename} saved ({len(data)} bytes)")
                    success = True
                    break
            except Exception as ex:
                print(f"[RETRY] {filename} attempt {attempt} failed: {ex}")
                import time
                time.sleep(2)
        if not success:
            print(f"[FAILED PERMANENTLY] {filename}")

if __name__ == "__main__":
    download_fonts()
