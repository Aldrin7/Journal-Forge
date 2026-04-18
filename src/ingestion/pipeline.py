"""
PaperForge — Unified Ingestion Pipeline
Dispatches to format-specific parsers and normalizes output.
Supports: DOCX, LaTeX, Markdown, JATS XML, and Universal Template mode.
"""
import json
import pathlib
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field, asdict

from .docx_ingest import ingest_docx, docx_to_dict, DocxDocument
from .latex_ingest import ingest_latex, latex_to_dict, LatexDocument
from .md_ingest import ingest_markdown, markdown_to_dict, MarkdownDocument
from .jats_ingest import ingest_jats, jats_to_dict, JatsDocument


SUPPORTED_FORMATS = {
    ".docx": "docx",
    ".doc": "docx",
    ".tex": "latex",
    ".latex": "latex",
    ".md": "markdown",
    ".markdown": "markdown",
    ".rmd": "markdown",
    ".jats": "jats",
    ".xml": "jats",
    ".nxml": "jats",
}


@dataclass
class UnifiedDocument:
    """
    Normalized document representation regardless of input format.
    All ingestion parsers produce this as their final output.
    """
    title: str = ""
    authors: list = field(default_factory=list)
    abstract: str = ""
    keywords: list = field(default_factory=list)
    sections: list = field(default_factory=list)
    elements: list = field(default_factory=list)
    equations: list = field(default_factory=list)
    figures: list = field(default_factory=list)
    tables: list = field(default_factory=list)
    references: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    source_format: str = ""
    source_path: str = ""
    pandoc_json: str = ""
    raw_source: str = ""


def detect_format(file_path: str) -> str:
    """Detect document format from file extension."""
    path = pathlib.Path(file_path)
    ext = path.suffix.lower()
    fmt = SUPPORTED_FORMATS.get(ext)
    if fmt:
        return fmt

    # Try content-based detection
    try:
        content = path.read_text(encoding='utf-8', errors='replace')[:1000]
        if content.strip().startswith("<?xml") or "<article" in content:
            return "jats"
        if "\\documentclass" in content or "\\begin{" in content:
            return "latex"
        if content.strip().startswith("#") or "---" in content[:200]:
            return "markdown"
    except Exception:
        pass

    return "unknown"


def ingest(file_path: str, fmt: Optional[str] = None) -> UnifiedDocument:
    """
    Main ingestion entry point.
    Detects format and dispatches to the appropriate parser.
    Returns a UnifiedDocument.
    """
    path = pathlib.Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if fmt is None:
        fmt = detect_format(file_path)

    doc = UnifiedDocument(
        source_format=fmt,
        source_path=str(path.resolve()),
    )

    if fmt == "docx":
        parsed = ingest_docx(file_path)
        _merge_docx(doc, parsed)
    elif fmt == "latex":
        parsed = ingest_latex(file_path)
        _merge_latex(doc, parsed)
    elif fmt == "markdown":
        parsed = ingest_markdown(file_path)
        _merge_markdown(doc, parsed)
    elif fmt == "jats":
        parsed = ingest_jats(file_path)
        _merge_jats(doc, parsed)
    else:
        raise ValueError(f"Unsupported format: {fmt}")

    return doc


def _merge_docx(doc: UnifiedDocument, parsed: DocxDocument) -> None:
    doc.title = parsed.title
    doc.authors = parsed.authors
    doc.abstract = parsed.abstract
    doc.keywords = parsed.keywords
    doc.elements = [asdict(e) for e in parsed.elements]
    doc.equations = parsed.equations
    doc.figures = parsed.figures
    doc.tables = parsed.tables
    doc.references = parsed.references
    doc.raw_source = parsed.raw_xml


def _merge_latex(doc: UnifiedDocument, parsed: LatexDocument) -> None:
    doc.title = parsed.title
    doc.authors = parsed.authors
    doc.abstract = parsed.abstract
    doc.keywords = parsed.keywords
    doc.sections = parsed.sections
    doc.equations = parsed.equations
    doc.figures = parsed.figures
    doc.tables = parsed.tables
    doc.references = parsed.references
    doc.pandoc_json = parsed.pandoc_json
    doc.raw_source = parsed.raw_source
    doc.metadata = {
        "document_class": parsed.document_class,
        "packages": parsed.packages,
    }


def _merge_markdown(doc: UnifiedDocument, parsed: MarkdownDocument) -> None:
    doc.title = parsed.title
    doc.authors = parsed.authors
    doc.abstract = parsed.abstract
    doc.keywords = parsed.keywords
    doc.sections = parsed.sections
    doc.elements = parsed.elements
    doc.equations = parsed.equations
    doc.figures = parsed.figures
    doc.tables = parsed.tables
    doc.references = parsed.references
    doc.pandoc_json = parsed.pandoc_json
    doc.raw_source = parsed.raw_source
    doc.metadata = parsed.yaml_frontmatter


def _merge_jats(doc: UnifiedDocument, parsed: JatsDocument) -> None:
    doc.title = parsed.title
    doc.authors = [a.get("full_name", "") for a in parsed.authors]
    doc.abstract = parsed.abstract
    doc.keywords = parsed.keywords
    doc.sections = parsed.sections
    doc.equations = parsed.equations
    doc.figures = parsed.figures
    doc.tables = parsed.tables
    doc.references = parsed.references
    doc.pandoc_json = parsed.pandoc_json
    doc.raw_source = parsed.raw_source
    doc.metadata = {
        "doi": parsed.doi,
        "article_type": parsed.article_type,
        "journal": parsed.journal,
        "volume": parsed.volume,
        "issue": parsed.issue,
        "pages": parsed.pages,
        "year": parsed.year,
    }


def ingest_to_dict(file_path: str, fmt: Optional[str] = None) -> Dict:
    """Ingest and return as a plain dict."""
    doc = ingest(file_path, fmt)
    return {
        "title": doc.title,
        "authors": doc.authors,
        "abstract": doc.abstract,
        "keywords": doc.keywords,
        "sections": doc.sections,
        "elements": doc.elements,
        "equations": doc.equations,
        "figures": doc.figures,
        "tables": doc.tables,
        "references": doc.references,
        "metadata": doc.metadata,
        "source_format": doc.source_format,
        "source_path": doc.source_path,
    }
