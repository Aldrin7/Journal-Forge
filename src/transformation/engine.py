"""
PaperForge — Transformation Engine
Normalizes AST, applies Lua filters, maps journal styles, formats citations.
"""
import json
import subprocess
import pathlib
import re
import gc
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class TransformResult:
    """Result of the transformation phase."""
    ast_json: str = ""
    normalized_equations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    style_map: Dict[str, Any] = field(default_factory=dict)
    applied_filters: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def normalize_math(latex: str) -> str:
    """
    Normalize mathematical LaTeX for consistent rendering.
    Fixes common issues: aligned environments, whitespace, symbol variants.
    """
    # Normalize whitespace
    latex = re.sub(r'\s+', ' ', latex).strip()

    # Fix aligned environments
    latex = re.sub(r'\\begin\{align\*?\}', r'\\begin{aligned}', latex)
    latex = re.sub(r'\\end\{align\*?\}', r'\\end{aligned}', latex)
    latex = re.sub(r'\\begin\{gather\*?\}', r'\\begin{gathered}', latex)
    latex = re.sub(r'\\end\{gather\*?\}', r'\\end{gathered}', latex)

    # Normalize math operators
    latex = re.sub(r'\\operatorname\{([^}]+)\}', r'\\\1', latex)

    # Fix double-dollar to single for inline contexts
    # (Pandoc handles this, but we normalize for safety)

    # Remove trailing backslashes
    latex = latex.rstrip('\\').strip()

    return latex


def load_style_map(journal: str, templates_dir: Optional[pathlib.Path] = None) -> Dict[str, Any]:
    """
    Load journal-specific style map from templates directory.
    """
    if templates_dir is None:
        templates_dir = pathlib.Path(__file__).parent.parent.parent / "templates"

    manifest_path = templates_dir / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
            if journal in manifest:
                style_path = templates_dir / manifest[journal].get("style_map", "")
                if style_path.exists():
                    with open(style_path) as sf:
                        return json.load(sf)

    # Fallback: load from journal subdirectory
    journal_dir = templates_dir / journal
    style_path = journal_dir / "style_map.json"
    if style_path.exists():
        with open(style_path) as f:
            return json.load(f)

    # Return default style map
    return get_default_style_map(journal)


def get_default_style_map(journal: str) -> Dict[str, Any]:
    """Get built-in default style maps for known journals."""
    defaults = {
        "ieee": {
            "name": "IEEE",
            "class": "IEEEtran",
            "font": "Times New Roman",
            "font_size": "10pt",
            "columns": 2,
            "margins": {"top": "0.75in", "bottom": "1in", "left": "0.75in", "right": "0.75in"},
            "title_style": {"font_size": "24pt", "bold": True, "center": True},
            "abstract_style": {"font_size": "9pt", "italic": True, "label": "Abstract—"},
            "heading_styles": {
                "1": {"font_size": "10pt", "bold": True, "uppercase": True},
                "2": {"font_size": "10pt", "italic": True},
                "3": {"font_size": "10pt"},
            },
            "reference_style": "numbered",
            "citation_format": "[n]",
            "equation_style": {"numbered": True, "position": "right"},
            "table_style": {"caption_position": "top", "font_size": "8pt"},
            "figure_style": {"caption_position": "bottom"},
            "csl": "ieee.csl",
        },
        "springer": {
            "name": "Springer Nature",
            "class": "sn-jnl",
            "font": "Times New Roman",
            "font_size": "10pt",
            "columns": 1,
            "margins": {"top": "2.5cm", "bottom": "2.5cm", "left": "2.5cm", "right": "2.5cm"},
            "title_style": {"font_size": "17pt", "bold": True},
            "abstract_style": {"font_size": "9pt", "label": "Abstract "},
            "heading_styles": {
                "1": {"font_size": "12pt", "bold": True},
                "2": {"font_size": "11pt", "bold": True},
                "3": {"font_size": "10pt", "bold": True, "italic": True},
            },
            "reference_style": "numbered",
            "citation_format": "[n]",
            "csl": "springer-vancouver.csl",
        },
        "wiley": {
            "name": "Wiley",
            "class": "wiley-article",
            "font": "Times New Roman",
            "font_size": "10pt",
            "columns": 2,
            "margins": {"top": "2cm", "bottom": "2cm", "left": "2cm", "right": "2cm"},
            "title_style": {"font_size": "16pt", "bold": True},
            "abstract_style": {"font_size": "9pt", "label": "Abstract "},
            "heading_styles": {
                "1": {"font_size": "12pt", "bold": True},
                "2": {"font_size": "11pt", "bold": True, "italic": True},
                "3": {"font_size": "10pt", "bold": True},
            },
            "reference_style": "numbered",
            "citation_format": "[n]",
            "csl": "wiley-vancouver.csl",
        },
        "elsevier": {
            "name": "Elsevier",
            "class": "elsarticle",
            "font": "Times New Roman",
            "font_size": "12pt",
            "columns": 1,
            "margins": {"top": "2.5cm", "bottom": "2.5cm", "left": "2.5cm", "right": "2.5cm"},
            "title_style": {"font_size": "24pt", "bold": True},
            "abstract_style": {"font_size": "10pt", "label": "Abstract "},
            "heading_styles": {
                "1": {"font_size": "12pt", "bold": True},
                "2": {"font_size": "11pt", "bold": True, "italic": True},
            },
            "reference_style": "numbered",
            "citation_format": "[n]",
            "csl": "elsevier-with-titles.csl",
        },
        "mdpi": {
            "name": "MDPI",
            "class": "mdpi",
            "font": "Times New Roman",
            "font_size": "10pt",
            "columns": 1,
            "margins": {"top": "2.5cm", "bottom": "2.5cm", "left": "2.5cm", "right": "2.5cm"},
            "title_style": {"font_size": "18pt", "bold": True},
            "abstract_style": {"font_size": "9pt", "label": "Abstract: "},
            "heading_styles": {
                "1": {"font_size": "14pt", "bold": True},
                "2": {"font_size": "12pt", "bold": True},
                "3": {"font_size": "11pt", "bold": True, "italic": True},
            },
            "reference_style": "numbered",
            "citation_format": "[n]",
            "csl": "mdpi.csl",
        },
        "nature": {
            "name": "Nature",
            "class": "nature",
            "font": "Times New Roman",
            "font_size": "10pt",
            "columns": 1,
            "margins": {"top": "2cm", "bottom": "2cm", "left": "2.5cm", "right": "2.5cm"},
            "title_style": {"font_size": "24pt", "bold": True, "sans-serif": True},
            "abstract_style": {"font_size": "9pt", "italic": True, "label": "Abstract "},
            "heading_styles": {
                "1": {"font_size": "13pt", "bold": True},
                "2": {"font_size": "11pt", "bold": True},
            },
            "reference_style": "numbered",
            "citation_format": "superscript",
            "csl": "nature.csl",
        },
        "acm": {
            "name": "ACM",
            "class": "acmart",
            "font": "Libertine",
            "font_size": "10pt",
            "columns": 2,
            "margins": {"top": "1in", "bottom": "1in", "left": "1in", "right": "1in"},
            "title_style": {"font_size": "24pt", "bold": True, "sans-serif": True},
            "abstract_style": {"font_size": "9pt", "label": "Abstract"},
            "heading_styles": {
                "1": {"font_size": "14pt", "bold": True},
                "2": {"font_size": "12pt", "bold": True},
                "3": {"font_size": "11pt", "bold": True},
            },
            "reference_style": "numbered",
            "citation_format": "[n]",
            "csl": "acm-sig-proceedings.csl",
        },
        "plos": {
            "name": "PLOS ONE",
            "class": "plos",
            "font": "Times New Roman",
            "font_size": "10pt",
            "columns": 1,
            "title_style": {"font_size": "22pt", "bold": True},
            "abstract_style": {"font_size": "9pt", "label": "Abstract"},
            "heading_styles": {
                "1": {"font_size": "13pt", "bold": True},
                "2": {"font_size": "11pt", "bold": True},
            },
            "reference_style": "numbered",
            "csl": "plos.csl",
        },
        "frontiers": {
            "name": "Frontiers",
            "class": "frontiers",
            "font": "Times New Roman",
            "font_size": "10pt",
            "columns": 1,
            "title_style": {"font_size": "18pt", "bold": True},
            "heading_styles": {
                "1": {"font_size": "13pt", "bold": True},
                "2": {"font_size": "11pt", "bold": True},
            },
            "reference_style": "numbered",
            "csl": "frontiers.csl",
        },
        "bmj": {
            "name": "BMJ",
            "class": "bmj",
            "font": "Arial",
            "font_size": "10pt",
            "columns": 1,
            "title_style": {"font_size": "20pt", "bold": True},
            "heading_styles": {
                "1": {"font_size": "12pt", "bold": True},
                "2": {"font_size": "11pt", "bold": True},
            },
            "reference_style": "numbered",
            "csl": "bmj.csl",
        },
        "acs": {
            "name": "ACS",
            "class": "achemso",
            "font": "Times New Roman",
            "font_size": "12pt",
            "columns": 1,
            "title_style": {"font_size": "16pt", "bold": True},
            "heading_styles": {
                "1": {"font_size": "12pt", "bold": True},
                "2": {"font_size": "11pt", "bold": True, "italic": True},
            },
            "reference_style": "numbered",
            "csl": "american-chemical-society.csl",
        },
        "taylor-francis": {
            "name": "Taylor & Francis",
            "class": "tufte-latex",
            "font": "Times New Roman",
            "font_size": "10pt",
            "columns": 1,
            "title_style": {"font_size": "18pt", "bold": True},
            "heading_styles": {
                "1": {"font_size": "13pt", "bold": True},
                "2": {"font_size": "11pt", "bold": True},
            },
            "reference_style": "numbered",
            "csl": "taylor-and-francis-chicago-author-date.csl",
        },
        "oxford": {
            "name": "Oxford University Press",
            "class": "oup-authoring-template",
            "font": "Times New Roman",
            "font_size": "10pt",
            "columns": 1,
            "title_style": {"font_size": "18pt", "bold": True},
            "heading_styles": {
                "1": {"font_size": "13pt", "bold": True},
                "2": {"font_size": "11pt", "bold": True},
            },
            "reference_style": "numbered",
            "csl": "oxford-university-press-note.csl",
        },
    }

    # Handle IEEE variants
    if journal.startswith("ieee"):
        base = defaults.get("ieee", {})
        base["name"] = f"IEEE — {journal.upper()}"
        return base

    return defaults.get(journal, defaults["ieee"])


def apply_lua_filters(ast_json: str, journal: str,
                      filters_dir: Optional[pathlib.Path] = None) -> str:
    """
    Apply Pandoc Lua filters to the AST.
    """
    if filters_dir is None:
        filters_dir = pathlib.Path(__file__).parent.parent.parent / "filters"

    filter_files = [
        filters_dir / "fonts-and-alignment.lua",
        filters_dir / f"{journal}.lua",
    ]

    for filter_path in filter_files:
        if filter_path.exists():
            try:
                result = subprocess.run(
                    ["pandoc", "-f", "json", "-t", "json",
                     f"--lua-filter={filter_path}"],
                    input=ast_json,
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0 and result.stdout.strip():
                    ast_json = result.stdout
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

    return ast_json


def format_citations(ast_json: str, journal: str,
                     csl_dir: Optional[pathlib.Path] = None) -> str:
    """
    Format citations using CSL engine via Pandoc.
    """
    style_map = get_default_style_map(journal)
    csl_file = style_map.get("csl", "ieee.csl")

    if csl_dir is None:
        csl_dir = pathlib.Path(__file__).parent.parent.parent / "data" / "csl-styles"

    csl_path = csl_dir / csl_file
    csl_args = []
    if csl_path.exists():
        csl_args = [f"--csl={csl_path}"]

    try:
        result = subprocess.run(
            ["pandoc", "-f", "json", "-t", "json", "--citeproc"] + csl_args,
            input=ast_json,
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return ast_json


def transform(ast_json: str, journal: str,
              templates_dir: Optional[pathlib.Path] = None) -> TransformResult:
    """
    Main transformation pipeline:
    1. Normalize math
    2. Apply Lua filters
    3. Load and apply journal style map
    4. Format citations
    """
    result = TransformResult()

    # Load style map
    result.style_map = load_style_map(journal, templates_dir)

    # Normalize equations in AST
    try:
        ast = json.loads(ast_json)
        equations = _extract_and_normalize_equations(ast)
        result.normalized_equations = equations
        ast_json = json.dumps(ast)
    except json.JSONDecodeError:
        result.warnings.append("Could not parse AST JSON for equation normalization")

    # Apply Lua filters
    ast_json = apply_lua_filters(ast_json, journal)
    result.applied_filters.append("fonts-and-alignment.lua")
    result.applied_filters.append(f"{journal}.lua")

    # Format citations
    ast_json = format_citations(ast_json, journal)

    result.ast_json = ast_json

    # Extract metadata
    try:
        ast = json.loads(ast_json)
        result.metadata = ast.get("meta", {})
    except json.JSONDecodeError:
        pass

    gc.collect()
    return result


def _extract_and_normalize_equations(ast: dict) -> List[str]:
    """Walk AST and normalize all math content."""
    equations = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("t") == "Math":
                c = node.get("c", ["", ""])
                if isinstance(c, list) and len(c) >= 2:
                    normalized = normalize_math(c[1])
                    node["c"][1] = normalized
                    equations.append(normalized)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(ast)
    return equations
