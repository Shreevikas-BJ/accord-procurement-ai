"""Render corpus PDF pages into local QA contact sheets; no AI or DB access."""

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw
from pypdf import PdfReader

root = Path(__file__).resolve().parents[1] / "benchmark-data"
out = root / "previews" / "qa"
out.mkdir(parents=True, exist_ok=True)
pages = []
for path in sorted((root / "documents").glob("*.pdf")):
    reader = PdfReader(path)
    assert 1 <= len(reader.pages) <= 50
    subprocess.run(
        ["pdftoppm", "-scale-to", "1000", "-png", str(path), str(out / path.stem)],
        check=True,
        capture_output=True,
    )
    pages.extend(sorted(out.glob(path.stem + "-*.png")))
for offset in range(0, len(pages), 6):
    sheet = Image.new("RGB", (1200, 1500), "#ddd")
    draw = ImageDraw.Draw(sheet)
    for index, page in enumerate(pages[offset : offset + 6]):
        picture = Image.open(page).convert("RGB")
        picture.thumbnail((590, 455))
        x, y = (index % 2) * 600, (index // 2) * 500
        sheet.paste(picture, (x, y + 35))
        draw.text((x + 5, y + 5), page.name[:75], fill="black")
    sheet.save(out / f"contact-{offset // 6 + 1:02d}.png")
print(f"Rendered {len(pages)} PDF pages for visual QA")
