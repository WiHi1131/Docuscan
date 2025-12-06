# generate_test_pngs.py
# Run: python generate_test_pngs.py
# Requires: pip install pillow (if not already)

from PIL import Image, ImageDraw, ImageFont
import os

# Create output dir if needed
os.makedirs('test_pngs', exist_ok=True)

for i in range(1, 11):
    # Create a small 200x100 PNG
    img = Image.new('RGB', (200, 100), color='white')
    draw = ImageDraw.Draw(img)
    
    # Add text (use default font; fallback if no TTF)
    try:
        font = ImageFont.truetype('arial.ttf', 20)  # Windows/Mac common; or use ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    draw.text((10, 40), f"Test Doc {i}\nOCR Sample Text Line 2", fill='black', font=font)
    
    # Save as PNG
    filename = f'test_pngs/test{i}.png'
    img.save(filename, 'PNG', optimize=True)
    print(f"Generated: {filename} (~{os.path.getsize(filename)} bytes)")

print("Done! 10 PNGs ready in 'test_pngs/'.")