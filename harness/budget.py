"""Hard spend cap for the whole project.

Every generation run records its cost to runs/BUDGET.json. Runs refuse to start
if the projected spend would breach the cap, and abort mid-run if actual spend
crosses it. The cap is a ceiling on TOTAL project spend, not per-run.

  python3 -m budget            # show the ledger
  python3 -m budget --set 100  # change the cap
"""
import json
import pathlib
import threading

LEDGER = pathlib.Path(__file__).resolve().parent.parent / "runs" / "BUDGET.json"
DEFAULT_CAP = 100.0

_lock = threading.Lock()


def _load():
    if LEDGER.exists():
        return json.loads(LEDGER.read_text())
    return {"cap_usd": DEFAULT_CAP, "runs": {}}


def _save(d):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(d, indent=2))


def spent():
    d = _load()
    return sum(d["runs"].values())


def cap():
    return _load()["cap_usd"]


def remaining():
    return cap() - spent()


def record(run_id, cost_usd):
    """Add (or overwrite) a run's cost. Thread-safe."""
    with _lock:
        d = _load()
        d["runs"][run_id] = round(float(cost_usd), 4)
        _save(d)
        return sum(d["runs"].values())


def set_cap(v):
    d = _load()
    d["cap_usd"] = float(v)
    _save(d)


class BudgetExceeded(RuntimeError):
    pass


def preflight(projected_usd, run_id):
    """Refuse to start a run that would breach the cap."""
    rem = remaining()
    print(f"[budget] cap ${cap():.2f} | spent ${spent():.2f} | remaining ${rem:.2f}")
    print(f"[budget] '{run_id}' projected ~${projected_usd:.2f}")
    if projected_usd > rem:
        raise BudgetExceeded(
            f"projected ${projected_usd:.2f} exceeds remaining ${rem:.2f}. "
            f"Reduce --samples/--models, or raise the cap with "
            f"`python3 -m budget --set N`."
        )
    if projected_usd > rem * 0.8:
        print(f"[budget] WARNING: this run uses "
              f"{projected_usd / rem:.0%} of remaining budget.")


class Guard:
    """Live spend tracker for a single run. Aborts when the cap is crossed."""

    def __init__(self, run_id):
        self.run_id = run_id
        self.run_cost = 0.0
        self.baseline = spent()
        self._lock = threading.Lock()
        self.tripped = False

    def add(self, cost_usd):
        if not cost_usd:
            return
        with self._lock:
            self.run_cost += cost_usd
            if self.baseline + self.run_cost > cap() and not self.tripped:
                self.tripped = True

    def check(self):
        if self.tripped:
            raise BudgetExceeded(
                f"HARD STOP: project spend hit the ${cap():.2f} cap "
                f"(this run: ${self.run_cost:.2f}). Partial outputs are kept."
            )

    def commit(self):
        return record(self.run_id, self.run_cost)


if __name__ == "__main__":
    import sys
    if "--set" in sys.argv:
        set_cap(sys.argv[sys.argv.index("--set") + 1])
    d = _load()
    print(f"cap:       ${d['cap_usd']:.2f}")
    print(f"spent:     ${spent():.2f}")
    print(f"remaining: ${remaining():.2f}")
    print("\nruns:")
    for k, v in sorted(d["runs"].items(), key=lambda kv: -kv[1]):
        print(f"  {k:<28} ${v:.4f}")
