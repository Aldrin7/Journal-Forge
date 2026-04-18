"""
PaperForge — JATS XML Ingestion Pipeline
Parses Journal Article Tag Suite XML documents.
"""
import json
import pathlib
import subprocess
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict


@dataclass
class JatsDocument:
    """Parsed JATS XML document."""
    title: str = ""
    authors: List[Dict[str, str]] = field(default_factory=list)
    abstract: str = ""
    keywords: List[str] = field(default_factory=list)
    doi: str = ""
    article_type: str = ""
    journal: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    year: str = ""
    sections: List[Dict[str, Any]] = field(default_factory=list)
    equations: List[str] = field(default_factory=list)
    figures: List[Dict] = field(default_factory=list)
    tables: List[Dict] = field(default_factory=list)
    references: List[Dict] = field(default_factory=list)
    raw_xml: str = ""
    pandoc_json: str = ""


def ingest_jats(file_path: str) -> JatsDocument:
    """
    Parse a JATS XML file into a structured document.
    """
    path = pathlib.Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"JATS XML file not found: {file_path}")

    source = path.read_text(encoding='utf-8', errors='replace')
    doc = JatsDocument(raw_xml=source)

    try:
        import lxml.etree as ET
        tree = ET.parse(str(path))
        root = tree.getroot()

        # Article type
        doc.article_type = root.get("article-type", "")

        # Front matter
        front = root.find(".//front")
        if front is not None:
            _parse_front(doc, front)

        # Body
        body = root.find(".//body")
        if body is not None:
            _parse_body(doc, body)

        # Back (references)
        back = root.find(".//back")
        if back is not None:
            _parse_back(doc, back)

    except ImportError:
        # Fallback to regex
        _parse_jats_regex(doc, source)

    # Also try Pandoc
    pandoc_result = _jats_to_pandoc_json(path)
    if pandoc_result:
        doc.pandoc_json = pandoc_result

    return doc


def _parse_front(doc: JatsDocument, front) -> None:
    """Parse JATS front matter."""
    # Article title
    title_el = front.find(".//article-title")
    if title_el is not None:
        doc.title = _el_text(title_el)

    # Authors
    for contrib in front.findall(".//contrib[@contrib-type='author']"):
        name_el = contrib.find("name")
        if name_el is not None:
            surname = _el_text(name_el.find("surname"))
            given = _el_text(name_el.find("given-names"))
            doc.authors.append({
                "surname": surname,
                "given_names": given,
                "full_name": f"{given} {surname}".strip()
            })

        # ORCID
        orcid_el = contrib.find(".//contrib-id[@contrib-id-type='orcid']")
        if orcid_el is not None and doc.authors:
            doc.authors[-1]["orcid"] = _el_text(orcid_el)

    # DOI
    doi_el = front.find(".//article-id[@pub-id-type='doi']")
    if doi_el is not None:
        doc.doi = _el_text(doi_el)

    # Journal
    journal_el = front.find(".//journal-title")
    if journal_el is not None:
        doc.journal = _el_text(journal_el)

    # Volume, issue, year
    vol_el = front.find(".//volume")
    if vol_el is not None:
        doc.volume = _el_text(vol_el)
    issue_el = front.find(".//issue")
    if issue_el is not None:
        doc.issue = _el_text(issue_el)
    year_el = front.find(".//pub-date/year")
    if year_el is not None:
        doc.year = _el_text(year_el)
    pages_el = front.find(".//fpage")
    if pages_el is not None:
        doc.pages = _el_text(pages_el)
        lpage_el = front.find(".//lpage")
        if lpage_el is not None:
            doc.pages += f"-{_el_text(lpage_el)}"

    # Abstract
    abstract_el = front.find(".//abstract")
    if abstract_el is not None:
        doc.abstract = _el_text(abstract_el)

    # Keywords
    for kw in front.findall(".//kwd"):
        kwd = _el_text(kw)
        if kwd:
            doc.keywords.append(kwd)


def _parse_body(doc: JatsDocument, body) -> None:
    """Parse JATS body sections."""
    for sec in body.findall(".//sec"):
        title_el = sec.find("title")
        title = _el_text(title_el) if title_el is not None else ""
        content = _el_text(sec, exclude_tags=["title"])
        doc.sections.append({
            "title": title,
            "content": content
        })

    # Equations (disp-formula)
    for eq in body.findall(".//disp-formula"):
        tex_math = eq.find(".//tex-math")
        if tex_math is not None:
            doc.equations.append(_el_text(tex_math))
        else:
            doc.equations.append(_el_text(eq))

    # Figures
    for fig in body.findall(".//fig"):
        caption_el = fig.find(".//caption")
        label_el = fig.find("label")
        graphic_el = fig.find(".//graphic")
        doc.figures.append({
            "id": fig.get("id", ""),
            "label": _el_text(label_el) if label_el is not None else "",
            "caption": _el_text(caption_el) if caption_el is not None else "",
            "href": graphic_el.get("xlink:href", "") if graphic_el is not None else ""
        })

    # Tables
    for table in body.findall(".//table-wrap"):
        caption_el = table.find(".//caption")
        label_el = table.find("label")
        table_el = table.find(".//table")
        rows = []
        if table_el is not None:
            for tr in table_el.findall(".//tr"):
                row = [_el_text(td) for td in tr.findall(".//td")]
                if not row:
                    row = [_el_text(th) for th in tr.findall(".//th")]
                rows.append(row)
        doc.tables.append({
            "id": table.get("id", ""),
            "label": _el_text(label_el) if label_el is not None else "",
            "caption": _el_text(caption_el) if caption_el is not None else "",
            "rows": rows
        })


def _parse_back(doc: JatsDocument, back) -> None:
    """Parse JATS back matter (references)."""
    for ref in back.findall(".//ref"):
        ref_id = ref.get("id", "")
        citation = ref.find(".//element-citation") or ref.find(".//mixed-citation")
        if citation is not None:
            ref_data = {"id": ref_id}

            # Article title
            art_title = citation.find(".//article-title")
            if art_title is not None:
                ref_data["title"] = _el_text(art_title)

            # Authors
            authors = []
            for author in citation.findall(".//name"):
                surname = _el_text(author.find("surname"))
                given = _el_text(author.find("given-names"))
                authors.append(f"{surname} {given}")
            ref_data["authors"] = authors

            # Journal/source
            source_el = citation.find(".//source")
            if source_el is not None:
                ref_data["journal"] = _el_text(source_el)

            # Year
            year_el = citation.find(".//year")
            if year_el is not None:
                ref_data["year"] = _el_text(year_el)

            # DOI
            doi_el = citation.find(".//pub-id[@pub-id-type='doi']")
            if doi_el is not None:
                ref_data["doi"] = _el_text(doi_el)

            doc.references.append(ref_data)


def _el_text(element, exclude_tags=None) -> str:
    """Extract all text content from an element."""
    if element is None:
        return ""
    if hasattr(element, 'itertext'):
        if exclude_tags:
            return "".join(
                t for t in element.itertext()
                if not any(t == getattr(el, 'text', '') for el in element.findall('.//' + '|'.join(exclude_tags)))
            )
        return "".join(element.itertext()).strip()
    return str(element).strip()


def _parse_jats_regex(doc: JatsDocument, source: str) -> None:
    """Fallback regex-based JATS parsing."""
    import re

    # Title
    m = re.search(r'<article-title>(.*?)</article-title>', source, re.DOTALL)
    if m:
        doc.title = re.sub(r'<[^>]+>', '', m.group(1)).strip()

    # DOI
    m = re.search(r'<article-id[^>]*pub-id-type="doi"[^>]*>(.*?)</article-id>', source)
    if m:
        doc.doi = m.group(1).strip()

    # Article type
    m = re.search(r'<article\s+.*?article-type="([^"]*)"', source)
    if m:
        doc.article_type = m.group(1)

    # Abstract
    m = re.search(r'<abstract>(.*?)</abstract>', source, re.DOTALL)
    if m:
        doc.abstract = re.sub(r'<[^>]+>', '', m.group(1)).strip()

    # Keywords
    for m in re.finditer(r'<kwd>(.*?)</kwd>', source):
        doc.keywords.append(re.sub(r'<[^>]+>', '', m.group(1)).strip())


def _jats_to_pandoc_json(path: pathlib.Path) -> Optional[str]:
    """Convert JATS to Pandoc JSON AST."""
    try:
        result = subprocess.run(
            ["pandoc", str(path), "-f", "jats", "-t", "json"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def jats_to_dict(doc: JatsDocument) -> Dict:
    """Serialize JatsDocument to dict."""
    return {
        "title": doc.title,
        "authors": doc.authors,
        "abstract": doc.abstract,
        "keywords": doc.keywords,
        "doi": doc.doi,
        "article_type": doc.article_type,
        "journal": doc.journal,
        "volume": doc.volume,
        "issue": doc.issue,
        "pages": doc.pages,
        "year": doc.year,
        "sections": doc.sections,
        "equations": doc.equations,
        "figures": doc.figures,
        "tables": doc.tables,
        "references": doc.references,
    }
