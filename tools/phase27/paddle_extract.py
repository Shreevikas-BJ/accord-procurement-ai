"""Emit stable JSON from the local PP-StructureV3 pipeline."""

import json
import argparse
import time
from importlib.metadata import version

from bs4 import BeautifulSoup
from paddleocr import PPStructureV3


parser = argparse.ArgumentParser()
parser.add_argument("paths", nargs="+")
parser.add_argument("--output")
args = parser.parse_args()
pipeline = PPStructureV3(
    device="cpu",
    enable_mkldnn=False,
    use_doc_orientation_classify=True,
    use_doc_unwarping=False,
    use_textline_orientation=True,
    use_seal_recognition=False,
    use_table_recognition=True,
    use_formula_recognition=False,
    use_chart_recognition=False,
    use_region_detection=False,
)
documents = []
for path in args.paths:
    started = time.monotonic()
    pages = []
    for result in pipeline.predict(path):
        data = result.json if hasattr(result, "json") else result
        if isinstance(data, str):
            data = json.loads(data)
        data = data.get("res", data)
        tables = []
        blocks = []
        for block in data.get("parsing_res_list", []):
            if block.get("block_label") == "table":
                soup = BeautifulSoup(block.get("block_content", ""), "html.parser")
                tables.append(
                    {
                        "bbox": block.get("block_bbox"),
                        "rows": [[cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])] for row in soup.find_all("tr")],
                    }
                )
            else:
                blocks.append({key: block.get(key) for key in ("block_label", "block_content", "block_bbox", "block_order")})
        ocr = data.get("overall_ocr_res", {})
        pages.append({"width": data.get("width"), "height": data.get("height"), "tables": tables, "blocks": blocks, "ocr_text": ocr.get("rec_texts", []), "ocr_scores": ocr.get("rec_scores", [])})
    documents.append(
        {
            "path": path,
            "provider": "paddle_ppstructure_v3",
            "version": version("paddleocr"),
            "paddle_version": version("paddlepaddle"),
            "seconds": round(time.monotonic() - started, 4),
            "pages": pages,
        }
    )
payload = json.dumps({"documents": documents}, ensure_ascii=False, default=str)
if args.output:
    with open(args.output, "w", encoding="utf-8") as stream:
        stream.write(payload)
else:
    print(payload)
