"""
PaperForge — Template Manager
Downloads and manages journal templates from official sources.
"""
import json
import pathlib
import subprocess
import zipfile
import shutil
from typing import Dict, Any, Optional, List


# Official template download URLs
TEMPLATE_URLS = {
    "ieee": {
        "name": "IEEE Transactions / Conferences",
        "url": "https://github.com/latextemplates/ieee-enhanced/archive/refs/heads/main.zip",
        "class": "IEEEtran",
        "csl": "ieee.csl",
    },
    "springer": {
        "name": "Springer Nature",
        "url": "https://www.springernature.com/de/authors/campaigns/latex-author-support/see-where-our-services-will-take-you/18782940",
        "download_url": "https://resource-cms.springernature.com/springer-cms/rest/v1/content/20566272/data/v7",
        "class": "sn-jnl",
        "csl": "springer-vancouver.csl",
    },
    "springer-lncs": {
        "name": "Springer LNCS (Lecture Notes)",
        "url": "https://github.com/latextemplates/LNCS/archive/refs/heads/main.zip",
        "class": "llncs",
        "csl": "springer-vancouver.csl",
    },
    "wiley": {
        "name": "Wiley",
        "url": "https://authors.wiley.com/asset/WileyDesign.zip",
        "class": "wiley-article",
        "csl": "wiley-vancouver.csl",
    },
    "wiley-njd": {
        "name": "Wiley New Journal Design",
        "url": "https://authorservices.wiley.com/asset/WileyNJDv5_Template.zip",
        "class": "wileyNJDv5",
        "csl": "wiley-vancouver.csl",
    },
    "elsevier": {
        "name": "Elsevier",
        "url": "https://mirrors.ctan.org/macros/latex/contrib/elsarticle.tar.gz",
        "class": "elsarticle",
        "csl": "elsevier-with-titles.csl",
    },
    "mdpi": {
        "name": "MDPI",
        "url": "https://github.com/metaphori/Template-LaTeX-MDPI/archive/refs/heads/master.zip",
        "class": "mdpi",
        "csl": "mdpi.csl",
    },
    "nature": {
        "name": "Nature",
        "url": "https://ctan.org/pkg/nature",
        "class": "nature",
        "csl": "nature.csl",
    },
    "acm": {
        "name": "ACM",
        "url": "https://github.com/latextemplates/ACM/archive/refs/heads/main.zip",
        "class": "acmart",
        "csl": "acm-sig-proceedings.csl",
    },
    "plos": {
        "name": "PLOS ONE",
        "url": "https://journals.plos.org/plosone/s/latex",
        "class": "plos",
        "csl": "plos.csl",
    },
    "frontiers": {
        "name": "Frontiers",
        "url": "https://www.frontiersin.org/design/zip/FT-Article-Template-LaTeX.zip",
        "class": "frontiers",
        "csl": "frontiers.csl",
    },
    "bmj": {
        "name": "BMJ",
        "url": "https://www.bmj.com/sites/default/files/attachments/bmj-author-guidelines.pdf",
        "class": "bmj",
        "csl": "bmj.csl",
    },
    "acs": {
        "name": "American Chemical Society",
        "url": "https://mirrors.ctan.org/macros/latex/contrib/achemso.tar.gz",
        "class": "achemso",
        "csl": "american-chemical-society.csl",
    },
    "taylor-francis": {
        "name": "Taylor & Francis",
        "url": "https://authorservices.taylorandfrancis.com/publishing-your-research/making-your-submission/latex-template/",
        "class": "tufte-latex",
        "csl": "taylor-and-francis-chicago-author-date.csl",
    },
    "oxford": {
        "name": "Oxford University Press",
        "url": "https://academic.oup.com/pages/authoring-journals/latex",
        "class": "oup-authoring-template",
        "csl": "oxford-university-press-note.csl",
    },
    "ieee-access": {
        "name": "IEEE Access",
        "url": "https://github.com/latextemplates/IEEE-access/archive/refs/heads/main.zip",
        "class": "IEEEtran",
        "csl": "ieee.csl",
    },
    "ieee-conference": {
        "name": "IEEE Conference",
        "url": "https://github.com/latextemplates/IEEE-Conference/archive/refs/heads/main.zip",
        "class": "IEEEtran",
        "csl": "ieee.csl",
    },
    # IEEE Transactions variants
    "ieee-tnn": {"name": "IEEE TNNLS", "class": "IEEEtran", "csl": "ieee.csl"},
    "ieee-tcom": {"name": "IEEE TCOM", "class": "IEEEtran", "csl": "ieee.csl"},
    "ieee-tc": {"name": "IEEE TC", "class": "IEEEtran", "csl": "ieee.csl"},
    "ieee-tsp": {"name": "IEEE TSP", "class": "IEEEtran", "csl": "ieee.csl"},
    "ieee-tkde": {"name": "IEEE TKDE", "class": "IEEEtran", "csl": "ieee.csl"},
    "ieee-tpami": {"name": "IEEE TPAMI", "class": "IEEEtran", "csl": "ieee.csl"},
    "ieee-tvt": {"name": "IEEE TVT", "class": "IEEEtran", "csl": "ieee.csl"},
    "ieee-spl": {"name": "IEEE SPL", "class": "IEEEtran", "csl": "ieee.csl"},
    "ieee-sensors": {"name": "IEEE Sensors", "class": "IEEEtran", "csl": "ieee.csl"},
    "ieee-tai": {"name": "IEEE TAI", "class": "IEEEtran", "csl": "ieee.csl"},
    "ieee-tmi": {"name": "IEEE TMI", "class": "IEEEtran", "csl": "ieee.csl"},
    "ieee-tr": {"name": "IEEE TR", "class": "IEEEtran", "csl": "ieee.csl"},
    "ieee-tse": {"name": "IEEE TSE", "class": "IEEEtran", "csl": "ieee.csl"},
    "ieee-tmm": {"name": "IEEE TMM", "class": "IEEEtran", "csl": "ieee.csl"},
    "ieee-jsac": {"name": "IEEE JSAC", "class": "IEEEtran", "csl": "ieee.csl"},
    "ieee-letter": {"name": "IEEE Letters", "class": "IEEEtran", "csl": "ieee.csl"},
    # MDPI variants
    "mdpi-sensors": {"name": "MDPI Sensors", "class": "mdpi", "csl": "mdpi.csl"},
    "mdpi-molecules": {"name": "MDPI Molecules", "class": "mdpi", "csl": "mdpi.csl"},
    "mdpi-electronics": {"name": "MDPI Electronics", "class": "mdpi", "csl": "mdpi.csl"},
    # Elsevier variants
    "elsevier-nuclear": {"name": "Elsevier Nuclear", "class": "elsarticle", "csl": "elsevier-with-titles.csl"},
    "elsevier-cviu": {"name": "Elsevier CVIU", "class": "elsarticle", "csl": "elsevier-with-titles.csl"},
    "elsevier-jocs": {"name": "Elsevier JOCS", "class": "elsarticle", "csl": "elsevier-with-titles.csl"},
    # Wiley variants
    "wiley-advanced": {"name": "Wiley Advanced", "class": "wiley-article", "csl": "wiley-vancouver.csl"},
    "wiley-chem": {"name": "Wiley Chemistry", "class": "wiley-article", "csl": "wiley-vancouver.csl"},
    "wiley-energy": {"name": "Wiley Energy", "class": "wiley-article", "csl": "wiley-vancouver.csl"},
    # Springer variants
    "springer-lnai": {"name": "Springer LNAI", "class": "llncs", "csl": "springer-vancouver.csl"},
    "springer-ifip": {"name": "Springer IFIP", "class": "llncs", "csl": "springer-vancouver.csl"},
}


def get_available_journals() -> List[str]:
    """Return list of all available journal identifiers."""
    return sorted(TEMPLATE_URLS.keys())


def get_journal_info(journal: str) -> Dict[str, Any]:
    """Get info about a specific journal template."""
    return TEMPLATE_URLS.get(journal, {
        "name": journal.upper(),
        "class": "article",
        "csl": "ieee.csl",
    })


def download_template(journal: str, templates_dir: Optional[pathlib.Path] = None) -> bool:
    """
    Download a journal template from its official source.
    Returns True if successful.
    """
    if templates_dir is None:
        templates_dir = pathlib.Path(__file__).parent.parent / "templates"

    info = TEMPLATE_URLS.get(journal)
    if not info:
        print(f"[templates] Unknown journal: {journal}")
        return False

    url = info.get("download_url") or info.get("url")
    if not url:
        print(f"[templates] No download URL for {journal}")
        return False

    target_dir = templates_dir / journal
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Download
        print(f"[templates] Downloading {journal} from {url}...")
        result = subprocess.run(
            ["curl", "-sL", "-o", str(target_dir / "template.zip"), url],
            capture_output=True, text=True, timeout=120
        )

        if result.returncode != 0:
            # Try wget
            result = subprocess.run(
                ["wget", "-q", "-O", str(target_dir / "template.zip"), url],
                capture_output=True, text=True, timeout=120
            )

        # Extract
        zip_path = target_dir / "template.zip"
        if zip_path.exists() and zipfile.is_zipfile(str(zip_path)):
            with zipfile.ZipFile(str(zip_path), 'r') as zf:
                zf.extractall(str(target_dir))
            zip_path.unlink()
            print(f"[templates] {journal} template installed")
            return True
        else:
            print(f"[templates] Download failed or not a ZIP for {journal}")
            return False

    except Exception as e:
        print(f"[templates] Error downloading {journal}: {e}")
        return False


def generate_manifest(templates_dir: Optional[pathlib.Path] = None) -> Dict[str, Any]:
    """
    Generate a manifest.json of all available templates.
    """
    if templates_dir is None:
        templates_dir = pathlib.Path(__file__).parent.parent / "templates"

    manifest = {}
    for journal, info in TEMPLATE_URLS.items():
        journal_dir = templates_dir / journal
        manifest[journal] = {
            "name": info["name"],
            "class": info.get("class", "article"),
            "csl": info.get("csl", "ieee.csl"),
            "installed": journal_dir.exists() and any(journal_dir.iterdir()),
            "url": info.get("url", ""),
        }

    # Write manifest
    manifest_path = templates_dir / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    return manifest


def create_style_map(journal: str, templates_dir: Optional[pathlib.Path] = None) -> None:
    """
    Create a style_map.json for a journal if it doesn't exist.
    """
    if templates_dir is None:
        templates_dir = pathlib.Path(__file__).parent.parent / "templates"

    journal_dir = templates_dir / journal
    journal_dir.mkdir(parents=True, exist_ok=True)

    style_path = journal_dir / "style_map.json"
    if not style_path.exists():
        # Import default style map from transformation engine
        from src.transformation.engine import get_default_style_map
        style_map = get_default_style_map(journal)
        with open(style_path, 'w') as f:
            json.dump(style_map, f, indent=2)
        print(f"[templates] Created style map for {journal}")
