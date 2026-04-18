"""
PaperForge — Semantic Audit
Validates document structure, citations, metadata, and bibliography.
"""
import json
import re
import pathlib
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class AuditResult:
    """Result of a semantic audit."""
    passed: bool = True
    errors: List[Dict[str, str]] = field(default_factory=list)
    warnings: List[Dict[str, str]] = field(default_factory=list)
    info: List[Dict[str, str]] = field(default_factory=list)
    score: float = 100.0


def audit_citations(ast_json: str) -> AuditResult:
    """
    Validate that all citations in the AST resolve to bibliography entries.
    """
    result = AuditResult()

    try:
        ast = json.loads(ast_json)
    except json.JSONDecodeError:
        result.passed = False
        result.errors.append({
            "code": "ast_parse",
            "msg": "Could not parse AST JSON"
        })
        return result

    # Collect all citation keys
    citation_keys = set()
    bibliography_keys = set()

    def walk(node, in_bib=False):
        if isinstance(node, dict):
            if node.get("t") == "Cite":
                citations = node.get("c", [[], []])[0]
                if isinstance(citations, list):
                    for cite in citations:
                        if isinstance(cite, dict):
                            citation_keys.add(cite.get("citationId", ""))
            if node.get("t") == "Div" and "references" in node.get("c", [{}, []])[0].get("classes", []):
                in_bib = True
            if in_bib and node.get("t") == "Div":
                attrs = node.get("c", [{}, []])[0]
                if isinstance(attrs, dict) and "id" in attrs:
                    bibliography_keys.add(attrs["id"])
            for v in node.values():
                walk(v, in_bib)
        elif isinstance(node, list):
            for item in node:
                walk(item, in_bib)

    walk(ast)

    # Check for unresolved citations
    unresolved = citation_keys - bibliography_keys
    for key in unresolved:
        result.errors.append({
            "code": "unresolved_citation",
            "msg": f"Citation key '{key}' not found in bibliography"
        })

    # Check for unused bibliography entries
    unused = bibliography_keys - citation_keys
    for key in unused:
        result.warnings.append({
            "code": "unused_bib_entry",
            "msg": f"Bibliography entry '{key}' is never cited"
        })

    if result.errors:
        result.passed = False
        result.score = max(0, 100 - len(result.errors) * 10 - len(result.warnings) * 2)

    result.info.append({
        "code": "citation_stats",
        "msg": f"Found {len(citation_keys)} citations, {len(bibliography_keys)} bibliography entries, {len(unresolved)} unresolved"
    })

    return result


def audit_metadata(ast_json: str) -> AuditResult:
    """
    Validate document metadata completeness.
    """
    result = AuditResult()

    try:
        ast = json.loads(ast_json)
    except json.JSONDecodeError:
        result.passed = False
        result.errors.append({"code": "ast_parse", "msg": "Cannot parse AST"})
        return result

    meta = ast.get("meta", {})

    # Required fields
    required = ["title", "author"]
    for field in required:
        if field not in meta:
            result.errors.append({
                "code": f"missing_{field}",
                "msg": f"Required metadata field '{field}' is missing"
            })

    # Recommended fields
    recommended = ["abstract", "keywords", "date"]
    for field in recommended:
        if field not in meta:
            result.warnings.append({
                "code": f"missing_{field}",
                "msg": f"Recommended metadata field '{field}' is missing"
            })

    # Validate title
    if "title" in meta:
        title_text = _meta_to_text(meta["title"])
        if len(title_text) < 5:
            result.warnings.append({
                "code": "short_title",
                "msg": f"Title is very short: '{title_text}'"
            })

    # Validate authors
    if "author" in meta:
        authors = _meta_to_list(meta["author"])
        if not authors or all(not a.strip() for a in authors):
            result.errors.append({
                "code": "empty_authors",
                "msg": "Author list is empty"
            })

    if result.errors:
        result.passed = False
        result.score = max(0, 100 - len(result.errors) * 15 - len(result.warnings) * 5)

    return result


def audit_structure(ast_json: str) -> AuditResult:
    """
    Validate document structure (sections, headings hierarchy).
    """
    result = AuditResult()

    try:
        ast = json.loads(ast_json)
    except json.JSONDecodeError:
        result.passed = False
        result.errors.append({"code": "ast_parse", "msg": "Cannot parse AST"})
        return result

    blocks = ast.get("blocks", [])

    if not blocks:
        result.errors.append({
            "code": "empty_document",
            "msg": "Document has no content blocks"
        })
        result.passed = False
        return result

    # Check heading hierarchy
    prev_level = 0
    heading_count = 0
    has_body_text = False

    for block in blocks:
        t = block.get("t", "")
        if t == "Header":
            heading_count += 1
            level = block.get("c", [1])[0]
            if level > prev_level + 1 and prev_level > 0:
                result.warnings.append({
                    "code": "heading_skip",
                    "msg": f"Heading level jumped from {prev_level} to {level}"
                })
            prev_level = level
        elif t in ("Para", "CodeBlock", "Table", "Figure"):
            has_body_text = True

    if heading_count == 0:
        result.warnings.append({
            "code": "no_headings",
            "msg": "Document has no section headings"
        })

    if not has_body_text:
        result.warnings.append({
            "code": "no_body_text",
            "msg": "Document has no body text (only headings?)"
        })

    if result.errors:
        result.passed = False

    return result


def audit_math(ast_json: str) -> AuditResult:
    """
    Validate mathematical content (properly formatted equations).
    """
    result = AuditResult()

    try:
        ast = json.loads(ast_json)
    except json.JSONDecodeError:
        result.passed = False
        result.errors.append({"code": "ast_parse", "msg": "Cannot parse AST"})
        return result

    math_count = 0
    empty_math = 0

    def walk(node):
        nonlocal math_count, empty_math
        if isinstance(node, dict):
            if node.get("t") == "Math":
                math_count += 1
                c = node.get("c", ["", ""])
                if isinstance(c, list) and len(c) >= 2:
                    if not c[1].strip():
                        empty_math += 1
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(ast)

    if empty_math > 0:
        result.warnings.append({
            "code": "empty_equations",
            "msg": f"{empty_math} out of {math_count} equations are empty"
        })

    result.info.append({
        "code": "math_stats",
        "msg": f"Found {math_count} mathematical expressions"
    })

    return result


def audit_figures(ast_json: str) -> AuditResult:
    """Validate figures have captions and accessible alt text."""
    result = AuditResult()

    try:
        ast = json.loads(ast_json)
    except json.JSONDecodeError:
        result.passed = False
        return result

    figure_count = 0
    uncaptioned = 0

    def walk(node):
        nonlocal figure_count, uncaptioned
        if isinstance(node, dict):
            if node.get("t") == "Image":
                figure_count += 1
                c = node.get("c", [])
                if isinstance(c, list) and len(c) >= 2:
                    caption = c[1]  # caption is second element
                    if not caption or (isinstance(caption, list) and len(caption) == 0):
                        uncaptioned += 1
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(ast)

    if uncaptioned > 0:
        result.warnings.append({
            "code": "uncaptioned_figures",
            "msg": f"{uncaptioned} out of {figure_count} figures lack captions"
        })

    result.info.append({
        "code": "figure_stats",
        "msg": f"Found {figure_count} figures"
    })

    return result


def full_audit(ast_json: str) -> Dict[str, AuditResult]:
    """Run all semantic audits."""
    return {
        "citations": audit_citations(ast_json),
        "metadata": audit_metadata(ast_json),
        "structure": audit_structure(ast_json),
        "math": audit_math(ast_json),
        "figures": audit_figures(ast_json),
    }


def audit_report(audits: Dict[str, AuditResult]) -> Dict[str, Any]:
    """Generate a combined audit report."""
    total_errors = 0
    total_warnings = 0
    all_passed = True
    min_score = 100.0

    for name, result in audits.items():
        total_errors += len(result.errors)
        total_warnings += len(result.warnings)
        if not result.passed:
            all_passed = False
        min_score = min(min_score, result.score)

    return {
        "passed": all_passed,
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "score": min_score,
        "audits": {
            name: {
                "passed": r.passed,
                "errors": r.errors,
                "warnings": r.warnings,
                "info": r.info,
                "score": r.score,
            }
            for name, r in audits.items()
        }
    }


def _meta_to_text(meta_val: dict) -> str:
    if meta_val.get("t") == "MetaString":
        return meta_val.get("c", "")
    if meta_val.get("t") == "MetaInlines":
        return "".join(
            i.get("c", "") if i.get("t") == "Str" else " "
            for i in meta_val.get("c", [])
        )
    return ""


def _meta_to_list(meta_val: dict) -> List[str]:
    if meta_val.get("t") == "MetaList":
        return [_meta_to_text(item) for item in meta_val.get("c", [])]
    if meta_val.get("t") == "MetaInlines":
        text = _meta_to_text(meta_val)
        return [a.strip() for a in text.split(",")]
    return []
