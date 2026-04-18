"""
PaperForge — Tectonic PDF Engine
Rust-based LaTeX engine with on-demand package download.
Tiny disk footprint vs TeX Live; compiles PDFs in ≤ 2s.
"""
import subprocess
import pathlib
import tempfile
import shutil
import json
from typing import Dict, Any, Optional, List


# Minimal LaTeX preamble for paper compilation
MINIMAL_PREAMBLE = r"""\documentclass[10pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{hyperref}
\usepackage{cite}
\usepackage{geometry}
\geometry{margin=1in}
"""

IEEE_PREAMBLE = r"""\documentclass[10pt,conference]{IEEEtran}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{hyperref}
\usepackage{cite}
"""

SPRINGER_PREAMBLE = r"""\documentclass[sn-basic]{sn-jnl}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{hyperref}
"""

JOURNAL_PREAMBLES = {
    "ieee": IEEE_PREAMBLE,
    "springer": SPRINGER_PREAMBLE,
    "springer-lncs": r"\documentclass{llncs}" + "\n" + MINIMAL_PREAMBLE.split('\n', 1)[1],
}


def check_tectonic() -> bool:
    """Check if tectonic is available."""
    try:
        result = subprocess.run(
            ["tectonic", "--version"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def latex_to_pdf_tectonic(latex_source: str, output_path: str,
                          journal: str = "ieee",
                          timeout: int = 300) -> Dict[str, Any]:
    """
    Compile LaTeX source to PDF using Tectonic.
    
    Args:
        latex_source: LaTeX source code (or path to .tex file)
        output_path: Path for output PDF
        journal: Journal identifier for preamble selection
        timeout: Compilation timeout in seconds
    
    Returns:
        Dict with success status, output path, size, and error if any.
    """
    result = {
        "success": False,
        "output_path": "",
        "size_bytes": 0,
        "engine": "tectonic",
        "error": "",
        "warnings": [],
    }

    if not check_tectonic():
        result["error"] = "Tectonic not found. Install from: https://tectonic-typesetting.github.io/"
        result["warnings"].append("Falling back to Pandoc for PDF rendering")
        return result

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = pathlib.Path(tmpdir)

        # Determine if latex_source is a file path or source code
        source_path = pathlib.Path(latex_source)
        if source_path.exists() and source_path.suffix == '.tex':
            tex_path = tmp / source_path.name
            shutil.copy2(source_path, tex_path)
        else:
            # Wrap in preamble if needed
            source = latex_source
            if not source.strip().startswith(r'\documentclass'):
                preamble = JOURNAL_PREAMBLES.get(journal, MINIMAL_PREAMBLE)
                source = preamble + "\n\\begin{document}\n" + source + "\n\\end{document}\n"

            tex_path = tmp / "paper.tex"
            tex_path.write_text(source, encoding='utf-8')

        # Run Tectonic
        try:
            proc = subprocess.run(
                ["tectonic", "--outdir", str(tmp), str(tex_path)],
                capture_output=True, text=True, timeout=timeout,
                cwd=str(tmp)
            )

            pdf_path = tmp / tex_path.with_suffix('.pdf').name

            if proc.returncode == 0 and pdf_path.exists():
                out = pathlib.Path(output_path)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(pdf_path, out)

                result["success"] = True
                result["output_path"] = str(out.resolve())
                result["size_bytes"] = out.stat().st_size
            else:
                result["error"] = proc.stderr[:500] if proc.stderr else "Tectonic compilation failed"
                if proc.stdout:
                    result["warnings"].append(f"stdout: {proc.stdout[:200]}")

        except subprocess.TimeoutExpired:
            result["error"] = f"Tectonic timed out after {timeout}s"
        except Exception as e:
            result["error"] = str(e)

    return result


def render_latex_with_tectonic(tex_path: str, output_path: str,
                                journal: str = "ieee") -> Dict[str, Any]:
    """
    Render an existing .tex file to PDF using Tectonic.
    Falls back to Pandoc if Tectonic is unavailable.
    """
    result = latex_to_pdf_tectonic(tex_path, output_path, journal)

    if not result["success"]:
        # Fallback to Pandoc
        try:
            proc = subprocess.run(
                ["pandoc", tex_path, "-o", output_path,
                 "--pdf-engine=xelatex"],
                capture_output=True, text=True, timeout=300
            )
            if proc.returncode == 0 and pathlib.Path(output_path).exists():
                result["success"] = True
                result["output_path"] = str(pathlib.Path(output_path).resolve())
                result["size_bytes"] = pathlib.Path(output_path).stat().st_size
                result["engine"] = "pandoc-xelatex"
                result["error"] = ""
            else:
                result["error"] = f"Pandoc fallback also failed: {proc.stderr[:200]}"
        except Exception as e:
            result["error"] = f"All PDF engines failed: {e}"

    return result
