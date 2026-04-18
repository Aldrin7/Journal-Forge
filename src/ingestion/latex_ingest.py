"""
PaperForge — LaTeX Ingestion Pipeline
Uses Pandoc's native LaTeX reader for robust parsing.
Falls back to regex-based extraction when Pandoc unavailable.
"""
import json
import subprocess
import pathlib
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict


@dataclass
class LatexDocument:
    """Parsed LaTeX document."""
    title: str = ""
    authors: List[str] = field(default_factory=list)
    abstract: str = ""
    keywords: List[str] = field(default_factory=list)
    sections: List[Dict[str, Any]] = field(default_factory=list)
    equations: List[str] = field(default_factory=list)
    figures: List[Dict] = field(default_factory=list)
    tables: List[Dict] = field(default_factory=list)
    references: List[Dict] = field(default_factory=list)
    raw_source: str = ""
    pandoc_json: str = ""
    document_class: str = "article"
    packages: List[str] = field(default_factory=list)
    preamble: str = ""


def ingest_latex(file_path: str) -> LatexDocument:
    """
    Parse a LaTeX file into a structured document.
    Primary: Pandoc native LaTeX reader.
    Fallback: regex-based structural extraction.
    """
    path = pathlib.Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"LaTeX file not found: {file_path}")

    source = path.read_text(encoding='utf-8', errors='replace')
    doc = LatexDocument(raw_source=source)

    # Extract document class
    cls_match = re.search(r'\\documentclass(?:\[.*?\])?\{(\w+)\}', source)
    if cls_match:
        doc.document_class = cls_match.group(1)

    # Extract packages
    doc.packages = re.findall(r'\\usepackage(?:\[.*?\])?\{([^}]+)\}', source)

    # Try Pandoc first (most robust)
    pandoc_result = _latex_to_pandoc_json(path)
    if pandoc_result:
        doc.pandoc_json = pandoc_result
        _parse_pandoc_json(doc, pandoc_result)
    else:
        # Fallback to regex
        _parse_latex_regex(doc, source)

    # Resolve \input{} includes
    _resolve_includes(doc, path.parent, source)

    return doc


def _latex_to_pandoc_json(path: pathlib.Path) -> Optional[str]:
    """Convert LaTeX to Pandoc JSON AST using native reader."""
    try:
        result = subprocess.run(
            ["pandoc", str(path), "-f", "latex", "-t", "json",
             "--wrap=none", "--citeproc=false"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _parse_pandoc_json(doc: LatexDocument, json_str: str) -> None:
    """Extract structured data from Pandoc JSON AST."""
    try:
        ast = json.loads(json_str)

        # Extract metadata
        meta = ast.get("meta", {})

        if "title" in meta:
            doc.title = _extract_meta_text(meta["title"])
        if "author" in meta:
            doc.authors = _extract_meta_list(meta["author"])
        if "abstract" in meta:
            doc.abstract = _extract_meta_text(meta["abstract"])
        if "keywords" in meta:
            doc.keywords = _extract_meta_list(meta["keywords"])

        # Walk blocks for equations, figures, tables, sections
        blocks = ast.get("blocks", [])
        _walk_blocks(doc, blocks, level=0)

    except (json.JSONDecodeError, KeyError):
        pass


def _extract_meta_text(meta_val: dict) -> str:
    """Extract plain text from Pandoc meta value."""
    if meta_val.get("t") == "MetaString":
        return meta_val.get("c", "")
    if meta_val.get("t") == "MetaInlines":
        return "".join(_inline_to_text(i) for i in meta_val.get("c", []))
    return ""


def _extract_meta_list(meta_val: dict) -> List[str]:
    """Extract list of strings from Pandoc meta value."""
    if meta_val.get("t") == "MetaList":
        return [_extract_meta_text(item) for item in meta_val.get("c", [])]
    if meta_val.get("t") == "MetaInlines":
        text = "".join(_inline_to_text(i) for i in meta_val.get("c", []))
        return [a.strip() for a in text.split(",")]
    return []


def _inline_to_text(inline: dict) -> str:
    """Convert Pandoc inline element to text."""
    t = inline.get("t", "")
    if t == "Str":
        return inline.get("c", "")
    if t == "Space":
        return " "
    if t == "SoftBreak":
        return "\n"
    if t == "Math":
        return inline.get("c", [{}])[1] if isinstance(inline.get("c"), list) else ""
    if t == "Code":
        return inline.get("c", ["", ""])[1] if isinstance(inline.get("c"), list) else ""
    if t == "Emph":
        return "".join(_inline_to_text(i) for i in inline.get("c", []))
    if t == "Strong":
        return "".join(_inline_to_text(i) for i in inline.get("c", []))
    if t == "Link":
        return "".join(_inline_to_text(i) for i in inline.get("c", [[], []])[0])
    return ""


def _walk_blocks(doc: LatexDocument, blocks: list, level: int) -> None:
    """Recursively walk Pandoc AST blocks."""
    for block in blocks:
        t = block.get("t", "")

        if t == "Header":
            sec_level = block.get("c", [1])[0]
            sec_text = "".join(
                _inline_to_text(i) for i in block.get("c", [1, {}, []])[2]
            )
            doc.sections.append({
                "level": sec_level,
                "title": sec_text,
                "content": ""
            })

        elif t == "Math":
            math_type, latex = block.get("c", ["DisplayMath", ""])
            doc.equations.append(latex)

        elif t == "Para":
            for inline in block.get("c", []):
                if inline.get("t") == "Math":
                    math_content = inline.get("c", ["", ""])
                    if isinstance(math_content, list) and len(math_content) >= 2:
                        doc.equations.append(math_content[1])

        elif t == "Table":
            table_data = _extract_table_data(block)
            if table_data:
                doc.tables.append(table_data)

        elif t == "Figure":
            caption = _extract_caption(block)
            doc.figures.append({"caption": caption, "source": ""})

        elif t == "CodeBlock":
            code_text = block.get("c", [["", []], ""])[1]
            doc.sections.append({
                "level": 0,
                "title": "[Code Block]",
                "content": code_text
            })

        # Recurse into nested blocks
        if "c" in block and isinstance(block["c"], list):
            for item in block["c"]:
                if isinstance(item, list):
                    _walk_blocks(doc, item, level + 1)


def _extract_table_data(block: dict) -> Optional[Dict]:
    """Extract table data from Pandoc Table block."""
    try:
        c = block.get("c", [])
        if len(c) >= 5:
            caption = _extract_meta_text(c[0]) if isinstance(c[0], dict) else ""
            # Table body is in c[4]
            rows = []
            body = c[4] if len(c) > 4 else []
            if isinstance(body, list):
                for row_group in body:
                    if isinstance(row_group, dict):
                        for row in row_group.get("c", []):
                            if isinstance(row, list):
                                cells = []
                                for cell in row:
                                    cell_text = "".join(
                                        _inline_to_text(i)
                                        for i in (cell.get("c", [[], []])[1]
                                                  if isinstance(cell, dict) else [])
                                    )
                                    cells.append(cell_text)
                                rows.append(cells)
            return {"caption": caption, "rows": rows}
    except (IndexError, TypeError):
        pass
    return None


def _extract_caption(block: dict) -> str:
    """Extract figure caption from Figure block."""
    try:
        c = block.get("c", [])
        if c and isinstance(c[0], dict):
            return _extract_meta_text(c[0])
    except (IndexError, TypeError):
        pass
    return ""


def _parse_latex_regex(doc: LatexDocument, source: str) -> None:
    """
    Fallback: regex-based LaTeX structural extraction.
    Handles common patterns when Pandoc is unavailable.
    """
    # Title
    title_match = re.search(r'\\title\{([^}]+)\}', source)
    if title_match:
        doc.title = title_match.group(1).strip()

    # Authors
    author_match = re.search(r'\\author\{([^}]+)\}', source)
    if author_match:
        doc.authors = [a.strip() for a in author_match.group(1).split(r'\\')]

    # Abstract
    abstract_match = re.search(
        r'\\begin\{abstract\}(.*?)\\end\{abstract\}',
        source, re.DOTALL
    )
    if abstract_match:
        doc.abstract = abstract_match.group(1).strip()

    # Keywords
    kw_match = re.search(r'\\keywords?\{([^}]+)\}', source, re.IGNORECASE)
    if kw_match:
        doc.keywords = [k.strip() for k in kw_match.group(1).split(",")]

    # Sections
    for match in re.finditer(r'\\(section|subsection|subsubsection)\*?\{([^}]+)\}', source):
        level_map = {"section": 1, "subsection": 2, "subsubsection": 3}
        doc.sections.append({
            "level": level_map.get(match.group(1), 1),
            "title": match.group(2).strip(),
            "content": ""
        })

    # Equations (display math)
    for match in re.finditer(
        r'\\begin\{(equation|align|gather|multline|eqnarray)\*?\}(.*?)\\end\{\1\*?\}',
        source, re.DOTALL
    ):
        doc.equations.append(match.group(2).strip())

    # Inline math
    for match in re.finditer(r'(?<!\\)\$\$(.+?)\$\$', source, re.DOTALL):
        doc.equations.append(match.group(1).strip())

    # Figures
    for match in re.finditer(
        r'\\begin\{figure\}.*?\\caption\{([^}]+)\}.*?\\end\{figure\}',
        source, re.DOTALL
    ):
        doc.figures.append({"caption": match.group(1), "source": ""})

    # Tables
    for match in re.finditer(
        r'\\begin\{table\}.*?\\caption\{([^}]+)\}.*?\\end\{table\}',
        source, re.DOTALL
    ):
        doc.tables.append({"caption": match.group(1), "rows": []})

    # Bibliography references
    for match in re.finditer(r'\\bibitem\{([^}]+)\}', source):
        doc.references.append({"key": match.group(1), "text": ""})

    for match in re.finditer(r'\\bibliography\{([^}]+)\}', source):
        bib_files = match.group(1).split(",")
        for bf in bib_files:
            doc.references.append({"bib_file": bf.strip()})


def _resolve_includes(doc: LatexDocument, base_dir: pathlib.Path,
                      source: str) -> None:
    """Resolve \\input{} and \\include{} directives."""
    includes = re.findall(r'\\(?:input|include)\{([^}]+)\}', source)
    for inc in includes:
        inc_path = base_dir / inc
        if not inc_path.suffix:
            inc_path = inc_path.with_suffix('.tex')
        if inc_path.exists():
            inc_source = inc_path.read_text(encoding='utf-8', errors='replace')
            # Recursively parse included content
            _parse_latex_regex(doc, inc_source)


def latex_to_dict(doc: LatexDocument) -> Dict:
    """Serialize LatexDocument to dict."""
    return {
        "title": doc.title,
        "authors": doc.authors,
        "abstract": doc.abstract,
        "keywords": doc.keywords,
        "document_class": doc.document_class,
        "packages": doc.packages,
        "sections": doc.sections,
        "equations": doc.equations,
        "figures": doc.figures,
        "tables": doc.tables,
        "references": doc.references,
    }
