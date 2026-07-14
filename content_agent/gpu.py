"""GPU discipline — content drafting is the LOWEST-priority tenant on the shared 8GB card.

Mirrors the markets-llm gpu_guard posture without importing its runtime (read-only sibling): on WDDM,
nvidia-smi reports per-process memory as [N/A], so the check is compute-PID-based. The card is "free for
drafting" when every compute PID belongs to ollama (an idle resident model is not contention — ollama
swaps internally). Anything else (quant, philosophy, an active markets run's non-ollama tooling) => yield.
Drafting is batchable and time-flexible: no preemption, no retry pressure — just don't start.
"""
from __future__ import annotations
import subprocess
import time

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_OLLAMA_NAMES = ("ollama", "ollama.exe", "ollama_llama_server", "ollama_llama_server.exe",
                 "ollama-runner", "ollama runner")


def _compute_pids() -> list[int]:
    try:
        r = subprocess.run(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=10, creationflags=_NO_WINDOW)
        return [int(x) for x in r.stdout.split() if x.strip().isdigit()]
    except Exception:
        return []


def _proc_name(pid: int) -> str:
    try:
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                           capture_output=True, text=True, timeout=10, creationflags=_NO_WINDOW)
        line = (r.stdout or "").strip().splitlines()
        return line[0].split('","')[0].strip('"').lower() if line else ""
    except Exception:
        return ""


def gpu_free_for_drafting() -> tuple[bool, str]:
    pids = _compute_pids()
    for pid in pids:
        name = _proc_name(pid)
        if name and not any(o in name for o in _OLLAMA_NAMES):
            return False, f"non-ollama GPU tenant: {name} (pid {pid})"
    return True, "free" if not pids else "only ollama resident"


def wait_for_gpu(attempts: int, sleep_seconds: int) -> bool:
    """Poll politely; give up quietly (the daily pass just tries again tomorrow)."""
    for i in range(attempts):
        ok, why = gpu_free_for_drafting()
        if ok:
            return True
        if i < attempts - 1:
            time.sleep(sleep_seconds)
    return False
