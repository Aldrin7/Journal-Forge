"""
PaperForge — Memory Guard
Sub-process isolation and memory management for heavy operations.
Keeps RSS below 3 GB ceiling.

Per spec:
  @contextmanager
  def isolate(cmd):
      proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      yield proc
      proc.wait(); gc.collect()

The MemoryGuard class wraps this into a phase-level context manager
with RSS tracking, checkpoints, and automatic ceiling enforcement.
"""
import subprocess
import gc
import os
import sys
import json
import time
import pathlib
from contextlib import contextmanager
from typing import List, Optional, Dict, Any

# ── Constants ──────────────────────────────────────────────────────

MEMORY_CEILING_MB = 3000   # 3 GB hard limit
MEMORY_WARNING_MB = 2400   # 80% warning threshold


# ── RSS Measurement ────────────────────────────────────────────────

def get_rss_mb() -> float:
    """Get current process RSS in MB. Uses psutil or /proc/self/status."""
    try:
        import psutil
        return psutil.Process().memory_info().rss / (1024 * 1024)
    except ImportError:
        pass
    # Linux fallback
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except (FileNotFoundError, PermissionError):
        pass
    # macOS fallback
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except Exception:
        pass
    return 0.0


# ── Garbage Collection ─────────────────────────────────────────────

def force_gc() -> Dict[str, int]:
    """Force garbage collection and return stats."""
    before = get_rss_mb()
    collected = gc.collect()
    after = get_rss_mb()
    return {
        "before_mb": round(before, 1),
        "after_mb": round(after, 1),
        "freed_mb": round(before - after, 1),
        "objects_collected": collected,
    }


def check_memory_ceiling() -> bool:
    """Check if we're under the memory ceiling. Raises MemoryError if not."""
    rss = get_rss_mb()
    if rss > MEMORY_CEILING_MB:
        raise MemoryError(
            f"RSS {rss:.0f} MB exceeds {MEMORY_CEILING_MB} MB ceiling"
        )
    if rss > MEMORY_WARNING_MB:
        print(f"[memory] WARNING: RSS {rss:.0f} MB / {MEMORY_CEILING_MB} MB")
    return rss < MEMORY_CEILING_MB


# ── Subprocess Isolation (per spec) ────────────────────────────────

@contextmanager
def isolate(cmd: List[str], timeout: int = 300,
            cwd: Optional[str] = None,
            env: Optional[Dict[str, str]] = None):
    """
    Run a heavy operation in an isolated subprocess.
    Forces gc.collect() after completion to reclaim memory.

    Usage:
        with isolate(["pandoc", "-f", "latex", "-t", "json", "paper.tex"]) as proc:
            stdout, stderr = proc.communicate()
    """
    check_memory_ceiling()
    full_env = {**os.environ}
    if env:
        full_env.update(env)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        env=full_env,
    )
    try:
        yield proc
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise TimeoutError(
            f"Subprocess timed out after {timeout}s: {' '.join(cmd)}"
        )
    finally:
        # Force GC to reclaim memory from subprocess buffers
        gc_stats = force_gc()
        if gc_stats["freed_mb"] > 10:
            print(f"[memory] Recovered {gc_stats['freed_mb']} MB after subprocess")


@contextmanager
def isolate_subprocess(cmd: List[str], timeout: int = 300,
                       cwd: Optional[str] = None,
                       env: Optional[Dict[str, str]] = None):
    """Alias for isolate() — backward compatibility."""
    with isolate(cmd, timeout=timeout, cwd=cwd, env=env) as proc:
        yield proc


def run_isolated(cmd: List[str], input_data: Optional[bytes] = None,
                 timeout: int = 300,
                 cwd: Optional[str] = None) -> subprocess.CompletedProcess:
    """
    Convenience: run subprocess with memory guard + auto-GC.
    Returns CompletedProcess with stdout/stderr.
    """
    check_memory_ceiling()
    result = subprocess.run(
        cmd,
        input=input_data,
        capture_output=True,
        timeout=timeout,
        cwd=cwd,
    )
    force_gc()
    return result


# ── Phase-Level Memory Guard ───────────────────────────────────────

class MemoryGuard:
    """
    Context manager that monitors memory throughout a pipeline phase.
    Logs RSS at start/end, forces GC at checkpoints, enforces ceiling.

    Usage:
        with MemoryGuard("ingestion") as mg:
            doc = ingest(input_file)
            mg.checkpoint("document_parsed")
            # ... heavy work ...
            mg.checkpoint("tables_extracted")
    """

    def __init__(self, phase_name: str = "unknown"):
        self.phase_name = phase_name
        self.start_rss = 0.0
        self.peak_rss = 0.0
        self.checkpoints: List[Dict[str, Any]] = []

    def __enter__(self):
        self.start_rss = get_rss_mb()
        self.peak_rss = self.start_rss
        print(
            f"[memory] Phase '{self.phase_name}' started — "
            f"RSS: {self.start_rss:.0f} MB"
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        gc_stats = force_gc()
        final_rss = get_rss_mb()
        print(
            f"[memory] Phase '{self.phase_name}' ended — "
            f"Peak: {self.peak_rss:.0f} MB, "
            f"Final: {final_rss:.0f} MB, "
            f"Freed: {gc_stats['freed_mb']:.0f} MB"
        )
        return False  # don't suppress exceptions

    def checkpoint(self, label: str) -> None:
        """Record RSS at a logical checkpoint. Raises if ceiling breached."""
        rss = get_rss_mb()
        self.peak_rss = max(self.peak_rss, rss)
        self.checkpoints.append({"label": label, "rss_mb": round(rss, 1)})
        check_memory_ceiling()

    def gc_if_needed(self, threshold_mb: float = 2000) -> None:
        """Force GC if RSS exceeds threshold."""
        if get_rss_mb() > threshold_mb:
            force_gc()

    def get_report(self) -> Dict[str, Any]:
        return {
            "phase": self.phase_name,
            "start_rss_mb": round(self.start_rss, 1),
            "peak_rss_mb": round(self.peak_rss, 1),
            "current_rss_mb": round(get_rss_mb(), 1),
            "checkpoints": self.checkpoints,
        }
