"""Deterministic demo worker. This is explicitly NOT a Pi/OMP model substitute."""
from __future__ import annotations

import json
from pathlib import Path
import runpy
import sys


def main() -> int:
    role, output_name = sys.argv[1:]
    output = Path(output_name)
    task = json.loads((output / "handoff.json").read_text())["task"]
    findings = []
    if role == "implement":
        source = Path("billing.py")
        text = source.read_text()
        expected = "    return seconds // 60\n"
        if expected not in text:
            findings.append("The deterministic fixture recognizes only the seeded defect")
        else:
            source.write_text(text.replace(expected, "    return (seconds + 59) // 60\n", 1))
    elif role == "review":
        # Fresh process in a separate review worktree. Fixed independent examples
        # belong to the synthetic policy; no implementation formula is repeated.
        function = runpy.run_path("billing.py")["billed_minutes"]
        for seconds, oracle in [(0, 0), (1, 1), (59, 1), (60, 1), (61, 2), (120, 2)]:
            if function(seconds) != oracle:
                findings.append(f"Wrong charge for {seconds}")
        for invalid in [-1, True, 1.5, "60"]:
            try:
                function(invalid)
                findings.append(f"Accepted invalid duration {invalid!r}")
            except ValueError:
                pass
    else:
        raise ValueError("Unknown fixture role")
    result = {"status": "FAIL" if findings else "PASS", "role": role,
              "covered_ac": [a["id"] for a in task["acceptance"]] if role == "review" else [],
              "lenses": ["spec", "correctness", "tests"] if role == "review" else [],
              "findings": findings, "text": "Deterministic synthetic fixture; no live model call"}
    (output / "result.json").write_text(json.dumps(result) + "\n")
    print(json.dumps({"type": "result", **result}))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
