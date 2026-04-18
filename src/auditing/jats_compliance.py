"""
PaperForge — JATS PMC Compliance Auditor
22-rule validation for PubMed Central compatibility.
"""
import pathlib
import json
from typing import Dict, Any, Optional, List, Tuple


RULES = [
    # Required elements
    ("article_type",
     lambda e: e.get("article-type") is not None or _find(e, ".//article-type") is not None,
     "Missing <article-type>", "error"),

    ("front_element",
     lambda e: _find(e, ".//front") is not None,
     "Missing <front> element", "error"),

    ("article_title",
     lambda e: _find(e, ".//article-title") is not None and _text(_find(e, ".//article-title")),
     "Missing or empty <article-title>", "error"),

    # Contributors
    ("contributors",
     lambda e: len(e.findall(".//contrib[@contrib-type='author']")) > 0,
     "No author contributors found", "error"),

    ("author_names",
     lambda e: all(
         _find(c, "name/surname") is not None and _find(c, "name/given-names") is not None
         for c in e.findall(".//contrib[@contrib-type='author']")
     ),
     "At least one author missing surname or given-names", "warning"),

    ("author_orcid",
     lambda e: all(
         _find(c, ".//contrib-id[@contrib-id-type='orcid']") is not None
         for c in e.findall(".//contrib[@contrib-type='author']")
     ),
     "At least one author missing ORCID", "info"),

    # Identifiers
    ("doi",
     lambda e: any(
         _text(el) for el in e.findall(".//article-id[@pub-id-type='doi']")
     ),
     "DOI not supplied", "error"),

    # Journal metadata
    ("journal_title",
     lambda e: _find(e, ".//journal-title") is not None,
     "Missing <journal-title>", "warning"),

    ("issn",
     lambda e: _find(e, ".//issn") is not None,
     "Missing <issn>", "warning"),

    # Content
    ("abstract",
     lambda e: _find(e, ".//abstract") is not None,
     "Missing <abstract>", "error"),

    ("body",
     lambda e: _find(e, ".//body") is not None,
     "Missing <body> element", "error"),

    # References
    ("reference_list",
     lambda e: len(e.findall(".//ref")) > 0,
     "No references found", "warning"),

    ("structured_refs",
     lambda e: all(
         _find(r, ".//element-citation") is not None or _find(r, ".//mixed-citation") is not None
         for r in e.findall(".//ref")
     ),
     "At least one reference lacks structured citation", "warning"),

    ("ref_dois",
     lambda e: all(
         _find(r, ".//pub-id[@pub-id-type='doi']") is not None
         for r in e.findall(".//ref")[:10]  # Check first 10
     ),
     "Some references missing DOIs", "info"),

    # Figures
    ("figure_captions",
     lambda e: all(
         _find(f, ".//caption") is not None
         for f in e.findall(".//fig")
     ),
     "At least one figure missing caption", "warning"),

    ("figure_labels",
     lambda e: all(
         _find(f, "label") is not None
         for f in e.findall(".//fig")
     ),
     "At least one figure missing label", "info"),

    ("figure_alt_text",
     lambda e: all(
         _find(f, ".//alt-text") is not None or _find(f, ".//graphic") is not None
         for f in e.findall(".//fig")
     ),
     "At least one figure missing alt-text or graphic", "info"),

    # Tables
    ("table_labels",
     lambda e: all(
         _find(t, "label") is not None
         for t in e.findall(".//table-wrap")
     ),
     "At least one table missing label", "info"),

    # Permissions/Licensing
    ("permissions",
     lambda e: _find(e, ".//permissions") is not None,
     "Missing <permissions> element", "error"),

    ("copyright_statement",
     lambda e: _find(e, ".//copyright-statement") is not None or _find(e, ".//license") is not None,
     "Missing copyright or license information", "warning"),

    # Funding
    ("funding",
     lambda e: _find(e, ".//funding-group") is not None or _find(e, ".//funding-statement") is not None,
     "No funding information found", "info"),

    # Language
    ("language",
     lambda e: e.get("{http://www.w3.org/XML/1998/namespace}lang") is not None or
               e.get("lang") is not None or
               e.find(".//{'http://www.w3.org/1999/xhtml}lang']") is not None,
     "Missing xml:lang attribute", "warning"),
]


def _find(element, xpath):
    """Safe find that returns None on failure."""
    try:
        return element.find(xpath)
    except Exception:
        return None


def _text(element) -> str:
    """Extract text content safely."""
    if element is None:
        return ""
    try:
        return "".join(element.itertext()).strip()
    except Exception:
        return str(element).strip()


def validate_jats(xml_path: str, strict: bool = False) -> Dict[str, Any]:
    """
    Validate JATS XML against PMC compliance rules.
    
    Args:
        xml_path: Path to JATS XML file
        strict: If True, treat info-level as warnings
    
    Returns:
        Dict with errors, warnings, info, and overall status.
    """
    path = pathlib.Path(xml_path)
    if not path.exists():
        return {
            "passed": False,
            "errors": [{"code": "file_not_found", "msg": f"File not found: {xml_path}"}],
            "warnings": [], "info": []
        }

    try:
        import lxml.etree as ET
    except ImportError:
        # Fallback to stdlib
        import xml.etree.ElementTree as ET

    try:
        tree = ET.parse(str(path))
        root = tree.getroot()
    except ET.ParseError as e:
        return {
            "passed": False,
            "errors": [{"code": "xml_parse", "msg": f"XML parse error: {e}"}],
            "warnings": [], "info": []
        }

    errors = []
    warnings = []
    info = []

    for code, test_fn, message, severity in RULES:
        try:
            passed = test_fn(root)
        except Exception as e:
            passed = False
            message = f"{message} (exception: {e})"

        if not passed:
            entry = {"code": code, "msg": message}
            if severity == "error":
                errors.append(entry)
            elif severity == "warning":
                warnings.append(entry)
            elif severity == "info":
                if strict:
                    warnings.append(entry)
                else:
                    info.append(entry)

    # DTD validation (if xmllint available)
    dtd_result = _validate_dtd(path)
    if dtd_result:
        if dtd_result["valid"]:
            info.append({"code": "dtd_valid", "msg": "XML validates against DTD"})
        else:
            for err in dtd_result["errors"]:
                warnings.append({"code": "dtd_error", "msg": err})

    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "info": info,
        "total_checks": len(RULES),
        "score": max(0, 100 - len(errors) * 10 - len(warnings) * 3 - len(info) * 1),
    }


def _validate_dtd(path: pathlib.Path) -> Optional[Dict]:
    """Validate XML against DTD using xmllint if available."""
    try:
        import subprocess
        result = subprocess.run(
            ["xmllint", "--valid", "--noout", str(path)],
            capture_output=True, text=True, timeout=30
        )
        return {
            "valid": result.returncode == 0,
            "errors": [result.stderr] if result.returncode != 0 else []
        }
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def validate_from_string(xml_string: str, strict: bool = False) -> Dict[str, Any]:
    """Validate JATS XML from string."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write(xml_string)
        temp_path = f.name

    try:
        return validate_jats(temp_path, strict)
    finally:
        pathlib.Path(temp_path).unlink(missing_ok=True)
