"""
PaperForge — Memory Guard
Sub-process isolation and memory management for heavy operations.
Keeps RSS below 3 GB ceiling.
"""
import subprocess
import gc
import os
import sys
import json
import time
import pathlib
import resource
from contextlib import contextmanager
from typing import List, Optional, Dict, Any, Callable

MEMORY_CEILING_MB = 3000  # 3 GB hard limit
MEMORY_WARNING_MB = 2400  # 80% warning threshold


def get_rss_mb() -> float:
    """Get current process RSS in MB."""
    try:
        import psutil
        return psutil.Process().memory_info().rss / (1024 * 1024)
    except ImportError:
        # Fallback: read from /proc/self/status
        try:
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) / 1024
        except (FileNotFoundError, PermissionError):
            pass
    return 0.0


def force_gc() -> Dict[str, int]:
    """Force garbage collection and return stats."""
    before = get_rss_mb()
    collected = gc.collect()
    after = get_rss_mb()
    return {
        "before_mb": round(before, 1),
        "after_mb": round(after, 1),
        "freed_mb": round(before - after, 1),
        "objects_collected": collected
    }


def check_memory_ceiling() -> bool:
    """Check if we're under the memory ceiling. Returns True if OK."""
    rss = get_rss_mb()
    if rss > MEMORY_CEILING_MB:
        raise MemoryError(
            f"RSS {rss:.0f} MB exceeds {MEMORY_CEILING_MB} MB ceiling")
    if rss > MEMORY_WARNING_MB:
        print(f"[memory] WARNING: RSS {rss:.0f} MB / {MEMORY_CEILING_MB} MB")
    return rss < MEMORY_CEILING_MB


@contextmanager
def isolate_subprocess(cmd: List[str], timeout: int = 300,
                       cwd: Optional[str] = None,
                       env: Optional[Dict[str, str]] = None):
    """
    Run a heavy operation in an isolated subprocess.
    Forces GC after completion to reclaim memory.
    
    Usage:
        with isolate_subprocess(["pandoc", "-f", "latex", "-t", "json", "paper.tex"]) as proc:
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
        raise TimeoutError(f"Subprocess timed out after {timeout}s: {' '.join(cmd)}")
    finally:
        gc_stats = force_gc()
        if gc_stats["freed_mb"] > 10:
            print(f"[memory] Recovered {gc_stats['freed_mb']} MB after subprocess")


def run_isolated(cmd: List[str], input_data: Optional[bytes] = None,
                 timeout: int = 300, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
    """
    Convenience function: run subprocess with memory guard.
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
    gc_stats = force_gc()
    return result


class MemoryGuard:
    """
    Context manager that monitors memory throughout a pipeline phase.
    Logs warnings and forces GC at checkpoints.
    """

    def __init__(self, phase_name: str = "unknown"):
        self.phase_name = phase_name
        self.start_rss = 0.0
        self.peak_rss = 0.0
        self.checkpoints: List[Dict] = []

    def __enter__(self):
        self.start_rss = get_rss_mb()
        self.peak_rss = self.start_rss
        print(f"[memory] Phase '{self.phase_name}' started — RSS: {self.start_rss:.0f} MB")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        gc_stats = force_gc()
        final_rss = get_rss_mb()
        print(f"[memory] Phase '{self.phase_name}' ended — "
              f"Peak: {self.peak_rss:.0f} MB, Final: {final_rss:.0f} MB, "
              f"Freed: {gc_stats['freed_mb']:.0f} MB")
        return False

    def checkpoint(self, label: str) -> None:
        """Record a memory checkpoint within the phase."""
        rss = get_rss_mb()
        self.peak_rss = max(self.peak_rss, rss)
        self.checkpoints.append({"label": label, "rss_mb": round(rss, 1)})
        check_memory_ceiling()

    def gc_if_needed(self, threshold_mb: float = 2000) -> None:
        """Force GC if RSS exceeds threshold."""
        if get_rss_mb() > threshold_mb:
            force_gc()

    def get_report(self) -> Dict:
        return {
            "phase": self.phase_name,
            "start_rss_mb": round(self.start_rss, 1),
            "peak_rss_mb": round(self.peak_rss, 1),
            "current_rss_mb": round(get_rss_mb(), 1),
            "checkpoints": self.checkpoints,
        }
