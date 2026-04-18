"""
PaperForge — Session Heartbeat
Generates structured session summaries at 85% of wall-time limit.
Enables exact context recovery across ephemeral sessions.
"""
import time
import json
import pathlib
import threading
import datetime
from typing import Optional, List, Dict, Any


class SessionHeartbeat:
    """
    Monitors session wall-time and generates a structured summary
    at 85% of the limit, ensuring the agent can resume context on reboot.
    """

    def __init__(self, run_id: str, max_minutes: int = 45,
                 checkpoint_dir: Optional[pathlib.Path] = None):
        self.run_id = run_id
        self.max_minutes = max_minutes
        self.start_time = time.time()
        self.deadline = self.start_time + max_minutes * 60 * 0.85  # 85%
        self.checkpoint_dir = checkpoint_dir or pathlib.Path("checkpoints")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.summary_path = self.checkpoint_dir / f"summary_{run_id}.json"
        self.summary_md_path = self.checkpoint_dir / f"summary_{run_id}.md"

        # Mutable state updated by the pipeline
        self.metrics: Dict[str, Any] = {
            "pages_rendered": 0,
            "equations_extracted": 0,
            "tables_processed": 0,
            "figures_processed": 0,
            "citations_resolved": 0,
            "bytes_written": 0,
        }
        self.blockers: List[str] = []
        self.warnings: List[str] = []
        self.completed_steps: List[str] = []
        self.current_step: str = "init"
        self.next_step: Optional[str] = None
        self.journal: Optional[str] = None
        self.input_file: Optional[str] = None
        self.output_format: Optional[str] = None

        self._timer: Optional[threading.Timer] = None
        self._triggered = False

    def start(self) -> None:
        """Start the heartbeat timer."""
        delay = max(0, self.deadline - time.time())
        self._timer = threading.Timer(delay, self._write_summary)
        self._timer.daemon = True
        self._timer.start()

    def stop(self) -> None:
        """Stop the heartbeat timer."""
        if self._timer:
            self._timer.cancel()

    def update(self, **kwargs) -> None:
        """Update pipeline state metrics."""
        for k, v in kwargs.items():
            if k in self.metrics:
                self.metrics[k] = v
            elif k == "blocker":
                self.blockers.append(v)
            elif k == "warning":
                self.warnings.append(v)
            elif k == "completed_step":
                self.completed_steps.append(v)
            elif k == "current_step":
                self.current_step = v
            elif k == "next_step":
                self.next_step = v

    def add_blocker(self, msg: str) -> None:
        self.blockers.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def complete_step(self, step: str) -> None:
        if step not in self.completed_steps:
            self.completed_steps.append(step)

    def _write_summary(self) -> None:
        """Generate both JSON and Markdown summaries."""
        if self._triggered:
            return
        self._triggered = True

        elapsed = time.time() - self.start_time
        remaining = max(0, self.max_minutes * 60 - elapsed)

        summary = {
            "run_id": self.run_id,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "elapsed_minutes": round(elapsed / 60, 1),
            "remaining_minutes": round(remaining / 60, 1),
            "journal": self.journal,
            "input_file": self.input_file,
            "output_format": self.output_format,
            "metrics": self.metrics,
            "completed_steps": self.completed_steps,
            "current_step": self.current_step,
            "next_step": self.next_step or "unknown",
            "blockers": self.blockers,
            "warnings": self.warnings,
        }

        # Write JSON
        self.summary_path.write_text(json.dumps(summary, indent=2))

        # Write Markdown (human-readable)
        md = self._to_markdown(summary)
        self.summary_md_path.write_text(md)

        print(f"[heartbeat] Summary written → {self.summary_path}")
        print(f"[heartbeat] Remaining time: {remaining / 60:.1f} min")

    def _to_markdown(self, s: dict) -> str:
        lines = [
            f"# Session Summary — {s['run_id']}",
            f"**Generated:** {s['timestamp']}",
            f"**Elapsed:** {s['elapsed_minutes']} min | **Remaining:** {s['remaining_minutes']} min",
            "",
            f"## Pipeline State",
            f"- **Journal:** {s['journal'] or 'N/A'}",
            f"- **Input:** {s['input_file'] or 'N/A'}",
            f"- **Output Format:** {s['output_format'] or 'N/A'}",
            f"- **Current Step:** {s['current_step']}",
            f"- **Next Step:** {s['next_step']}",
            "",
            "## Metrics",
        ]
        for k, v in s["metrics"].items():
            lines.append(f"- **{k}:** {v}")

        lines.append("\n## Completed Steps")
        for step in s["completed_steps"]:
            lines.append(f"- ✅ {step}")

        if s["blockers"]:
            lines.append("\n## ⚠️ Blockers")
            for b in s["blockers"]:
                lines.append(f"- {b}")

        if s["warnings"]:
            lines.append("\n## Warnings")
            for w in s["warnings"]:
                lines.append(f"- {w}")

        lines.append("\n## Resume Instructions")
        lines.append(f"Run `python3 pipeline/translator.py --resume {s['run_id']}` to continue from step: **{s['next_step']}**")

        return "\n".join(lines)

    def get_time_remaining(self) -> float:
        """Return remaining seconds."""
        return max(0, self.max_minutes * 60 - (time.time() - self.start_time))

    def is_critical(self) -> bool:
        """True if less than 15% time remaining."""
        return self.get_time_remaining() < self.max_minutes * 60 * 0.15
