**upscale_png.py usage**

**Setup**
pip install Pillow

**Commands**
# 2x upscale (default)
python upscale_png.py photo.png

# 4x upscale
python upscale_png.py photo.png --scale 4

# Resize to a specific width (keeps aspect ratio)
python upscale_png.py photo.png --width 1920

# Exact dimensions
python upscale_png.py photo.png --width 1920 --height 1080

# Custom output filename
python upscale_png.py photo.png --output result.png

