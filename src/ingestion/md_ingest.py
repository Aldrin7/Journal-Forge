"""
PaperForge — Markdown Ingestion Pipeline
Parses Markdown directly into Pandoc AST with figure resolution.
"""
import json
import subprocess
import pathlib
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict


@dataclass
class MarkdownDocument:
    """Parsed Markdown document."""
    title: str = ""
    authors: List[str] = field(default_factory=list)
    abstract: str = ""
    keywords: List[str] = field(default_factory=list)
    sections: List[Dict[str, Any]] = field(default_factory=list)
    elements: List[Dict[str, Any]] = field(default_factory=list)
    equations: List[str] = field(default_factory=list)
    figures: List[Dict] = field(default_factory=list)
    tables: List[Dict] = field(default_factory=list)
    references: List[Dict] = field(default_factory=list)
    raw_source: str = ""
    pandoc_json: str = ""
    yaml_frontmatter: Dict[str, Any] = field(default_factory=dict)


def ingest_markdown(file_path: str) -> MarkdownDocument:
    """
    Parse a Markdown file into a structured document.
    Extracts YAML frontmatter, resolves figures, converts to Pandoc AST.
    """
    path = pathlib.Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Markdown file not found: {file_path}")

    source = path.read_text(encoding='utf-8', errors='replace')
    doc = MarkdownDocument(raw_source=source)

    # Parse YAML frontmatter
    _extract_frontmatter(doc, source)

    # Try Pandoc for full AST
    pandoc_result = _md_to_pandoc_json(path)
    if pandoc_result:
        doc.pandoc_json = pandoc_result
        _parse_pandoc_json(doc, pandoc_result)
    else:
        # Fallback to regex
        _parse_markdown_regex(doc, source)

    # Resolve figure paths relative to markdown file
    _resolve_figures(doc, path.parent)

    return doc


def _extract_frontmatter(doc: MarkdownDocument, source: str) -> None:
    """Extract YAML frontmatter from markdown."""
    fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', source, re.DOTALL)
    if fm_match:
        try:
            import yaml
            fm = yaml.safe_load(fm_match.group(1))
            if isinstance(fm, dict):
                doc.yaml_frontmatter = fm
                doc.title = fm.get("title", "")
                authors = fm.get("authors", fm.get("author", ""))
                if isinstance(authors, str):
                    doc.authors = [a.strip() for a in authors.split(",")]
                elif isinstance(authors, list):
                    doc.authors = [str(a) for a in authors]
                keywords = fm.get("keywords", "")
                if isinstance(keywords, str):
                    doc.keywords = [k.strip() for k in keywords.split(",")]
                elif isinstance(keywords, list):
                    doc.keywords = [str(k) for k in keywords]
                doc.abstract = fm.get("abstract", "")
        except ImportError:
            # Simple key-value extraction without yaml
            for line in fm_match.group(1).split("\n"):
                if ":" in line:
                    key, _, val = line.partition(":")
                    key = key.strip().lower()
                    val = val.strip().strip('"').strip("'")
                    if key == "title":
                        doc.title = val
                    elif key == "author":
                        doc.authors = [a.strip() for a in val.split(",")]
                    elif key == "abstract":
                        doc.abstract = val
                    elif key == "keywords":
                        doc.keywords = [k.strip() for k in val.split(",")]


def _md_to_pandoc_json(path: pathlib.Path) -> Optional[str]:
    """Convert Markdown to Pandoc JSON AST."""
    try:
        result = subprocess.run(
            ["pandoc", str(path), "-f", "markdown", "-t", "json",
             "--wrap=none"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _parse_pandoc_json(doc: MarkdownDocument, json_str: str) -> None:
    """Extract structured data from Pandoc JSON AST."""
    try:
        ast = json.loads(json_str)

        # Extract metadata
        meta = ast.get("meta", {})
        if "title" in meta and not doc.title:
            doc.title = _extract_meta_text(meta["title"])
        if "author" in meta and not doc.authors:
            doc.authors = _extract_meta_list(meta["author"])
        if "abstract" in meta and not doc.abstract:
            doc.abstract = _extract_meta_text(meta["abstract"])
        if "keywords" in meta and not doc.keywords:
            doc.keywords = _extract_meta_list(meta["keywords"])

        # Walk blocks
        blocks = ast.get("blocks", [])
        _walk_md_blocks(doc, blocks)

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
    """Extract list from Pandoc meta value."""
    if meta_val.get("t") == "MetaList":
        return [_extract_meta_text(item) for item in meta_val.get("c", [])]
    if meta_val.get("t") == "MetaInlines":
        text = "".join(_inline_to_text(i) for i in meta_val.get("c", []))
        return [a.strip() for a in text.split(",")]
    return []


def _inline_to_text(inline: dict) -> str:
    """Convert Pandoc inline to text."""
    t = inline.get("t", "")
    if t == "Str":
        return inline.get("c", "")
    if t == "Space":
        return " "
    if t == "SoftBreak":
        return "\n"
    if t == "Math":
        c = inline.get("c", ["", ""])
        if isinstance(c, list) and len(c) >= 2:
            return c[1]
        return ""
    if t == "Code":
        c = inline.get("c", [["", []], ""])
        if isinstance(c, list) and len(c) >= 2:
            return c[1]
        return ""
    if t == "Emph" or t == "Strong":
        return "".join(_inline_to_text(i) for i in inline.get("c", []))
    if t == "Link":
        return "".join(_inline_to_text(i) for i in inline.get("c", [[], []])[0])
    if t == "Image":
        return "".join(_inline_to_text(i) for i in inline.get("c", [[], []])[0])
    if t == "Quoted":
        c = inline.get("c", [None, []])
        if isinstance(c, list) and len(c) >= 2:
            return '"' + "".join(_inline_to_text(i) for i in c[1]) + '"'
        return ""
    if t == "Cite":
        c = inline.get("c", [[], []])
        if isinstance(c, list) and len(c) >= 2:
            return "".join(_inline_to_text(i) for i in c[1])
        return ""
    return ""


def _walk_md_blocks(doc: MarkdownDocument, blocks: list) -> None:
    """Walk Pandoc AST blocks for Markdown."""
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
            doc.elements.append({
                "type": "heading",
                "level": sec_level,
                "text": sec_text
            })

        elif t == "Math":
            math_type, latex = block.get("c", ["DisplayMath", ""])
            doc.equations.append(latex)
            doc.elements.append({
                "type": "equation",
                "latex": latex
            })

        elif t == "Para":
            inlines = block.get("c", [])
            para_text = ""
            for inline in inlines:
                if inline.get("t") == "Math":
                    math_c = inline.get("c", ["", ""])
                    if isinstance(math_c, list) and len(math_c) >= 2:
                        doc.equations.append(math_c[1])
                elif inline.get("t") == "Image":
                    img_c = inline.get("c", [[], []])
                    url = img_c[1][0] if img_c[1] else ""
                    caption = "".join(
                        _inline_to_text(i) for i in img_c[0]
                    )
                    doc.figures.append({
                        "caption": caption,
                        "source": url
                    })
                para_text += _inline_to_text(inline)

            doc.elements.append({
                "type": "paragraph",
                "text": para_text
            })

        elif t == "CodeBlock":
            code_text = block.get("c", [["", []], ""])[1]
            doc.elements.append({
                "type": "code_block",
                "text": code_text
            })

        elif t == "Figure":
            # Pandoc 3.x wraps standalone images in Figure blocks
            c = block.get("c", [])
            caption = ""
            if len(c) >= 2 and isinstance(c[1], list):
                # Caption is in c[1]
                for item in c[1]:
                    if isinstance(item, dict):
                        caption += _inline_to_text(item)
            # Content is in c[2] — walk for Image elements
            if len(c) >= 3 and isinstance(c[2], list):
                for content_block in c[2]:
                    if isinstance(content_block, dict):
                        for inline in content_block.get("c", []):
                            if isinstance(inline, dict) and inline.get("t") == "Image":
                                img_c = inline.get("c", [[], []])
                                url = img_c[2][0] if len(img_c) >= 3 and img_c[2] else ""
                                img_caption = caption or "".join(
                                    _inline_to_text(i) for i in (img_c[1] if len(img_c) >= 2 else [])
                                )
                                doc.figures.append({
                                    "caption": img_caption,
                                    "source": url
                                })
                                doc.elements.append({
                                    "type": "figure",
                                    "caption": img_caption,
                                    "source": url
                                })

        elif t == "Table":
            table_caption = ""
            c = block.get("c", [])
            if c and isinstance(c[0], dict):
                table_caption = _extract_meta_text(c[0])
            doc.tables.append({
                "caption": table_caption,
                "rows": []
            })

        elif t == "BlockQuote":
            quote_text = "".join(
                _inline_to_text(i)
                for inner in block.get("c", [])
                for i in (inner.get("c", []) if isinstance(inner, dict) else [])
            )
            doc.elements.append({
                "type": "blockquote",
                "text": quote_text
            })


def _parse_markdown_regex(doc: MarkdownDocument, source: str) -> None:
    """Fallback regex-based markdown parsing."""
    # Title (first H1)
    title_match = re.search(r'^#\s+(.+)$', source, re.MULTILINE)
    if title_match and not doc.title:
        doc.title = title_match.group(1).strip()

    # All headings
    for match in re.finditer(r'^(#{1,6})\s+(.+)$', source, re.MULTILINE):
        level = len(match.group(1))
        doc.sections.append({
            "level": level,
            "title": match.group(2).strip(),
            "content": ""
        })

    # Equations (display math)
    for match in re.finditer(r'\$\$(.+?)\$\$', source, re.DOTALL):
        doc.equations.append(match.group(1).strip())

    # Inline equations
    for match in re.finditer(r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)', source):
        doc.equations.append(match.group(1).strip())

    # Images
    for match in re.finditer(r'!\[([^\]]*)\]\(([^)]+)\)', source):
        doc.figures.append({
            "caption": match.group(1),
            "source": match.group(2)
        })

    # Tables (pipe tables)
    table_pattern = re.compile(
        r'(\|.+\|)\n(\|[-:| ]+\|)\n((?:\|.+\|\n?)+)',
        re.MULTILINE
    )
    for match in table_pattern.finditer(source):
        header = [c.strip() for c in match.group(1).split("|")[1:-1]]
        rows = []
        for row_str in match.group(3).strip().split("\n"):
            row = [c.strip() for c in row_str.split("|")[1:-1]]
            rows.append(row)
        doc.tables.append({"header": header, "rows": rows})

    # References (cite keys)
    for match in re.finditer(r'\[@(\w+)\]', source):
        doc.references.append({"key": match.group(1)})


def _resolve_figures(doc: MarkdownDocument, base_dir: pathlib.Path) -> None:
    """Resolve relative figure paths to absolute."""
    for fig in doc.figures:
        src = fig.get("source", "")
        if src and not src.startswith(("http://", "https://", "/")):
            resolved = base_dir / src
            fig["resolved_path"] = str(resolved)
            fig["exists"] = resolved.exists()


def markdown_to_dict(doc: MarkdownDocument) -> Dict:
    """Serialize MarkdownDocument to dict."""
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
    }
