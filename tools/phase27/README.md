# Phase 2.7 isolated parser evaluation

These CPU-only images keep Docling and PaddleOCR/PP-StructureV3 out of Accord's API and worker images while they are benchmark candidates. Each command emits provider-neutral JSON and processes mounted local files only.

```powershell
docker build -f tools/phase27/Dockerfile.docling -t accord-phase27-docling .
docker build -f tools/phase27/Dockerfile.paddle -t accord-phase27-paddle .
docker run --rm -v "${PWD}:/work:ro" accord-phase27-docling /work/benchmark-data/documents/example.pdf
docker run --rm -v "${PWD}:/work:ro" accord-phase27-paddle /work/benchmark-data/documents/example.png
```
