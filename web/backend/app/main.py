"""
PaperForge — FastAPI Backend
Web API for the PaperForge document conversion system.
"""
import sys
import pathlib
import json
import uuid
import datetime
from typing import Optional, List

# Add project root
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, JSONResponse
    from pydantic import BaseModel
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

if FASTAPI_AVAILABLE:
    app = FastAPI(
        title="PaperForge",
        description="Universal Agentic Research-to-Journal Converter",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Models ──────────────────────────────────────────────────────

    class ConvertRequest(BaseModel):
        journal: str = "ieee"
        format: str = "docx"
        bibliography: Optional[str] = None

    class ConvertResponse(BaseModel):
        run_id: str
        status: str
        message: str
        outputs: dict = {}

    class JournalInfo(BaseModel):
        id: str
        name: str
        document_class: str
        csl: str
        installed: bool = False

    class TemplateModeRequest(BaseModel):
        title: str
        authors: List[str] = []
        abstract: str = ""
        keywords: List[str] = []
        sections: List[dict] = []
        equations: List[str] = []
        journal: str = "ieee"
        format: str = "docx"

    # ── Routes ──────────────────────────────────────────────────────

    @app.get("/")
    async def root():
        return {
            "name": "PaperForge",
            "version": "1.0.0",
            "description": "Universal Agentic Research-to-Journal Converter",
            "endpoints": [
                "/api/v1/journals",
                "/api/v1/convert",
                "/api/v1/template",
                "/api/v1/status/{run_id}",
            ]
        }

    @app.get("/api/v1/journals")
    async def list_journals():
        """List all available journal templates."""
        from src.templates.manager import TEMPLATE_URLS
        journals = []
        for key, info in sorted(TEMPLATE_URLS.items()):
            journals.append({
                "id": key,
                "name": info["name"],
                "document_class": info.get("class", "article"),
                "csl": info.get("csl", "ieee.csl"),
            })
        return {"journals": journals, "total": len(journals)}

    @app.post("/api/v1/convert", response_model=ConvertResponse)
    async def convert_document(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        journal: str = Form("ieee"),
        output_format: str = Form("docx"),
        bibliography: Optional[UploadFile] = File(None),
    ):
        """Convert an uploaded document to the target journal format."""
        from src.pipeline.translator import run_pipeline, generate_run_id

        # Save uploaded file
        run_id = generate_run_id()
        upload_dir = PROJECT_ROOT / "output" / run_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        input_path = upload_dir / file.filename
        with open(input_path, "wb") as f:
            content = await file.read()
            f.write(content)

        bib_path = None
        if bibliography:
            bib_path = upload_dir / bibliography.filename
            with open(bib_path, "wb") as f:
                bib_content = await bibliography.read()
                f.write(bib_content)

        # Run pipeline
        result = run_pipeline(
            input_file=str(input_path),
            journal=journal,
            output_format=output_format,
            output_dir=str(upload_dir),
            bibliography=str(bib_path) if bib_path else None,
            quiet=True,
        )

        return ConvertResponse(
            run_id=run_id,
            status="completed" if result["success"] else "failed",
            message="Conversion completed" if result["success"] else "; ".join(result["errors"]),
            outputs=result.get("outputs", {}),
        )

    @app.post("/api/v1/template", response_model=ConvertResponse)
    async def convert_from_template(req: TemplateModeRequest):
        """Generate a document from structured template data (universal template mode)."""
        from src.pipeline.translator import generate_run_id
        from src.export.exporter import export_document

        run_id = generate_run_id()
        output_dir = PROJECT_ROOT / "output" / run_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Build AST from template data
        blocks = []

        # Title
        if req.title:
            blocks.append({
                "t": "Header",
                "c": [1, ["title"], [{"t": "Str", "c": req.title}]]
            })

        # Abstract
        if req.abstract:
            blocks.append({
                "t": "Div",
                "c": [["abstract"], [
                    {"t": "Header", "c": [2, [], [{"t": "Str", "c": "Abstract"}]]},
                    {"t": "Para", "c": [{"t": "Str", "c": req.abstract}]}
                ]]
            })

        # Sections
        for section in req.sections:
            level = section.get("level", 1)
            title = section.get("title", "")
            content = section.get("content", "")

            if title:
                blocks.append({
                    "t": "Header",
                    "c": [level, ["section"], [{"t": "Str", "c": title}]]
                })
            if content:
                blocks.append({
                    "t": "Para",
                    "c": [{"t": "Str", "c": content}]
                })

        # Equations
        for eq in req.equations:
            blocks.append({
                "t": "Math",
                "c": ["DisplayMath", eq]
            })

        # Build AST
        meta = {}
        if req.title:
            meta["title"] = {"t": "MetaInlines", "c": [{"t": "Str", "c": req.title}]}
        if req.authors:
            meta["author"] = {
                "t": "MetaList",
                "c": [{"t": "MetaInlines", "c": [{"t": "Str", "c": a}]} for a in req.authors]
            }
        if req.abstract:
            meta["abstract"] = {"t": "MetaInlines", "c": [{"t": "Str", "c": req.abstract}]}

        ast = {
            "pandoc-api-version": [1, 23, 1],
            "meta": meta,
            "blocks": blocks
        }

        ast_json = json.dumps(ast)

        # Save AST
        ast_path = output_dir / "ast.json"
        ast_path.write_text(ast_json)

        # Export
        ext = "tex" if req.format == "latex" else req.format
        output_path = output_dir / f"paper.{ext}"

        export_result = export_document(
            ast_json, str(output_path), req.format,
            journal=req.journal,
        )

        outputs = {}
        if export_result.success:
            outputs[req.format] = {
                "path": export_result.output_path,
                "size_bytes": export_result.size_bytes,
            }

        return ConvertResponse(
            run_id=run_id,
            status="completed" if export_result.success else "failed",
            message="Template conversion completed" if export_result.success else export_result.error,
            outputs=outputs,
        )

    @app.get("/api/v1/status/{run_id}")
    async def get_status(run_id: str):
        """Get the status of a conversion run."""
        from src.orchestration.ledger import Ledger

        ledger = Ledger()
        steps = ledger.get_run_steps(run_id, "")
        checkpoint = ledger.get_latest_checkpoint(run_id)
        ledger.close()

        return {
            "run_id": run_id,
            "steps": steps,
            "latest_checkpoint": checkpoint,
        }

    @app.get("/api/v1/download/{run_id}/{filename}")
    async def download_output(run_id: str, filename: str):
        """Download an output file."""
        output_path = PROJECT_ROOT / "output" / run_id / filename
        if not output_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(str(output_path))

else:
    print("FastAPI not installed. Install with: pip install fastapi uvicorn python-multipart")
    print("Web API is disabled. Use CLI: python3 pipeline/translator.py")
