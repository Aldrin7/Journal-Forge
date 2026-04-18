"""
PaperForge — Visual SSIM Regression Auditor
Pixel-level PDF comparison using Structural Similarity Index.
Falls back to hash-based comparison when scikit-image is unavailable.
"""
import pathlib
import hashlib
import subprocess
import tempfile
import json
from typing import Dict, Any, Optional, List, Tuple


def pdf_to_images(pdf_path: str, output_dir: str,
                  dpi: int = 150) -> List[pathlib.Path]:
    """
    Convert PDF pages to PNG images.
    Uses pdftoppm (poppler-utils) if available, falls back to ImageMagick.
    """
    pdf = pathlib.Path(pdf_path)
    out = pathlib.Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    images = []

    # Try pdftoppm first (faster, lower memory)
    try:
        result = subprocess.run(
            ["pdftoppm", "-png", "-r", str(dpi),
             str(pdf), str(out / "page")],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            images = sorted(out.glob("page-*.png"))
            if images:
                return images
    except FileNotFoundError:
        pass

    # Try ImageMagick convert
    try:
        result = subprocess.run(
            ["convert", "-density", str(dpi), str(pdf),
             str(out / "page-%03d.png")],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            images = sorted(out.glob("page-*.png"))
            if images:
                return images
    except FileNotFoundError:
        pass

    return images


def compute_image_hash(image_path: pathlib.Path) -> str:
    """Compute perceptual hash of an image for quick comparison."""
    try:
        import hashlib
        data = image_path.read_bytes()
        return hashlib.sha256(data).hexdigest()
    except Exception:
        return ""


def compute_ssim(img1_path: str, img2_path: str) -> Optional[float]:
    """
    Compute Structural Similarity Index between two images.
    Returns SSIM score (0.0 to 1.0) or None if library unavailable.
    """
    try:
        from skimage.metrics import structural_similarity as ssim
        from PIL import Image
        import numpy as np

        img1 = np.array(Image.open(img1_path).convert('L'))
        img2 = np.array(Image.open(img2_path).convert('L'))

        # Resize to same dimensions if needed
        if img1.shape != img2.shape:
            min_h = min(img1.shape[0], img2.shape[0])
            min_w = min(img1.shape[1], img2.shape[1])
            img1 = img1[:min_h, :min_w]
            img2 = img2[:min_h, :min_w]

        return float(ssim(img1, img2))
    except ImportError:
        return None
    except Exception:
        return None


def visual_diff(generated_pdf: str, baseline_pdf: str,
                output_dir: Optional[str] = None,
                dpi: int = 150,
                ssim_threshold: float = 0.95) -> Dict[str, Any]:
    """
    Perform visual regression between generated and baseline PDFs.

    Args:
        generated_pdf: Path to the generated PDF
        baseline_pdf: Path to the baseline/reference PDF
        output_dir: Directory for diff images
        dpi: Resolution for PDF-to-image conversion
        ssim_threshold: Minimum SSIM score to pass

    Returns:
        Dict with diff results, scores, and page-level details.
    """
    gen_path = pathlib.Path(generated_pdf)
    base_path = pathlib.Path(baseline_pdf)

    if not gen_path.exists():
        return {"passed": False, "error": f"Generated PDF not found: {generated_pdf}"}
    if not base_path.exists():
        return {"passed": False, "error": f"Baseline PDF not found: {baseline_pdf}"}

    if output_dir is None:
        output_dir = str(pathlib.Path(generated_pdf).parent / "diff")
    out = pathlib.Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = pathlib.Path(tmpdir)

        # Convert both PDFs to images
        gen_pages = pdf_to_images(str(gen_path), str(tmp / "gen"), dpi)
        base_pages = pdf_to_images(str(base_path), str(tmp / "base"), dpi)

        if not gen_pages or not base_pages:
            return {
                "passed": False,
                "error": "Could not convert PDFs to images. "
                         "Install poppler-utils or imagemagick.",
                "gen_pages": len(gen_pages),
                "base_pages": len(base_pages),
            }

        # Compare pages
        page_results = []
        total_ssim = 0.0
        min_ssim = 1.0
        pages_compared = min(len(gen_pages), len(base_pages))
        has_ssim = False

        for i in range(pages_compared):
            gen_img = gen_pages[i]
            base_img = base_pages[i]

            # Compute SSIM
            ssim_score = compute_ssim(str(gen_img), str(base_img))

            if ssim_score is not None:
                has_ssim = True
                total_ssim += ssim_score
                min_ssim = min(min_ssim, ssim_score)
                passed = ssim_score >= ssim_threshold
            else:
                # Fallback: hash comparison
                gen_hash = compute_image_hash(gen_img)
                base_hash = compute_image_hash(base_img)
                ssim_score = 1.0 if gen_hash == base_hash else 0.0
                passed = gen_hash == base_hash

            page_results.append({
                "page": i + 1,
                "ssim": round(ssim_score, 4),
                "passed": passed,
                "gen_size": gen_img.stat().st_size,
                "base_size": base_img.stat().st_size,
            })

        # Page count mismatch
        page_count_diff = len(gen_pages) - len(base_pages)

        avg_ssim = total_ssim / pages_compared if pages_compared > 0 else 0.0
        all_passed = all(p["passed"] for p in page_results) and page_count_diff == 0

        return {
            "passed": all_passed,
            "avg_ssim": round(avg_ssim, 4),
            "min_ssim": round(min_ssim, 4) if has_ssim else None,
            "gen_pages": len(gen_pages),
            "base_pages": len(base_pages),
            "page_count_diff": page_count_diff,
            "pages_compared": pages_compared,
            "threshold": ssim_threshold,
            "method": "ssim" if has_ssim else "hash",
            "page_results": page_results,
        }


def visual_audit_report(diff_result: Dict[str, Any]) -> str:
    """Generate a human-readable visual audit report."""
    lines = [
        "# Visual Regression Audit Report",
        "",
    ]

    if diff_result.get("error"):
        lines.append(f"**Error:** {diff_result['error']}")
        return "\n".join(lines)

    status = "✅ PASSED" if diff_result["passed"] else "❌ FAILED"
    lines.append(f"**Status:** {status}")
    lines.append(f"**Method:** {diff_result.get('method', 'unknown').upper()}")
    lines.append(f"**Pages Compared:** {diff_result['pages_compared']}")
    lines.append(f"**Generated Pages:** {diff_result['gen_pages']}")
    lines.append(f"**Baseline Pages:** {diff_result['base_pages']}")

    if diff_result.get("avg_ssim") is not None:
        lines.append(f"**Average SSIM:** {diff_result['avg_ssim']:.4f}")
    if diff_result.get("min_ssim") is not None:
        lines.append(f"**Minimum SSIM:** {diff_result['min_ssim']:.4f}")
    lines.append(f"**Threshold:** {diff_result.get('threshold', 0.95)}")

    if diff_result.get("page_count_diff", 0) != 0:
        lines.append(f"\n⚠️ **Page count mismatch:** {diff_result['page_count_diff']} pages difference")

    lines.append("\n## Page Details\n")
    for pr in diff_result.get("page_results", []):
        status_icon = "✅" if pr["passed"] else "❌"
        lines.append(f"- {status_icon} Page {pr['page']}: SSIM={pr['ssim']:.4f}")

    return "\n".join(lines)
