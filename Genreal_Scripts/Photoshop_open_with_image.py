import os
import glob
import subprocess

def get_base_dir():
    while True:
        base_dir = input("Enter the full path to your base image folder (e.g., D:\\Raj\\Porterlyons\\Embrald_Edit): ").strip()
        if os.path.isdir(base_dir):
            return base_dir
        print("⚠️ That folder does not exist. Please try again.")

base_dir = get_base_dir()
# Supported image extensions
exts = ('*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.webp', '*.gif')

# Find all image files in all subfolders
image_files = []
for ext in exts:
    image_files.extend(glob.glob(os.path.join(base_dir, '**', ext), recursive=True))

if not image_files:
    print("No images found in the provided directory and its subfolders.")
    exit()

print(f"Found {len(image_files)} image files. Opening each in Photoshop 2020 (like right-click > Open with)...")

photoshop_path = r'C:\Program Files\Adobe\Adobe Photoshop 2020\Photoshop.exe'

for idx, img_path in enumerate(image_files, 1):
    # Launch Photoshop as if doing "Open With" on each file
    try:
        subprocess.Popen([photoshop_path, img_path])
        print(f"[{idx}/{len(image_files)}] Opened {img_path}")
        # Optionally: add a short delay to avoid opening too rapidly!
        # time.sleep(0.2)
    except Exception as e:
        print(f"Failed to open {img_path}: {e}")

print("All images launched in Photoshop. You may close each after editing as desired.")
