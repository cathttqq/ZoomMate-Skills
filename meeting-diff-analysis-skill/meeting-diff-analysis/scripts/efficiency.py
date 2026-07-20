#!/usr/bin/env python3
"""Compute the meeting efficiency score for one or two occurrences.

Efficiency Score (E) = k * (T * R * P) / (M * (1 + Rt))

  T  = number of unique topics discussed
  R  = number of actionable results / decisions made
  P  = number of participants who actively spoke
  M  = total meeting duration in minutes
  Rt = number of repeated topics (also covered in the baseline occurrence)
  k  = optional normalization constant (default 1.0)

Usage examples
--------------
Single occurrence:
    python efficiency.py --T 6 --R 3 --P 5 --M 90 --Rt 1

Compare two occurrences (baseline vs current) in one call:
    python efficiency.py \\
        --baseline T=5,R=2,P=4,M=60,Rt=0 \\
        --current  T=6,R=3,P=5,M=90,Rt=1

The compare form prints both scores and the delta so the diff is deterministic.
"""

import argparse
import sys


def efficiency(T, R, P, M, Rt, k=1.0):
    """Return the efficiency score. Raises ValueError on invalid inputs."""
    for name, val in (("T", T), ("R", R), ("P", P), ("M", M), ("Rt", Rt)):
        if val < 0:
            raise ValueError(f"{name} must be >= 0 (got {val})")
    if M <= 0:
        raise ValueError(f"M (duration in minutes) must be > 0 (got {M})")
    return k * (T * R * P) / (M * (1 + Rt))


def _parse_occurrence(spec):
    """Parse 'T=6,R=3,P=5,M=90,Rt=1[,k=1]' into a kwargs dict."""
    out = {}
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"expected key=value, got '{part}'")
        key, _, raw = part.partition("=")
        key = key.strip()
        out[key] = float(raw) if key == "k" else int(raw)
    missing = {"T", "R", "P", "M", "Rt"} - out.keys()
    if missing:
        raise ValueError(f"missing inputs: {', '.join(sorted(missing))}")
    return out


def _fmt(kwargs, score):
    ins = ", ".join(f"{key}={kwargs[key]}" for key in ("T", "R", "P", "M", "Rt"))
    if kwargs.get("k", 1.0) != 1.0:
        ins += f", k={kwargs['k']}"
    return f"{ins}  ->  E = {score:.4f}"


def main(argv=None):
    p = argparse.ArgumentParser(description="Meeting efficiency score calculator.")
    p.add_argument("--baseline", help="baseline occurrence, e.g. T=5,R=2,P=4,M=60,Rt=0")
    p.add_argument("--current", help="current occurrence, e.g. T=6,R=3,P=5,M=90,Rt=1")
    p.add_argument("--T", type=int, help="unique topics discussed")
    p.add_argument("--R", type=int, help="actionable results / decisions")
    p.add_argument("--P", type=int, help="participants who actively spoke")
    p.add_argument("--M", type=int, help="total meeting duration in minutes")
    p.add_argument("--Rt", type=int, help="repeated topics vs. baseline")
    p.add_argument("--k", type=float, default=1.0, help="normalization constant (default 1.0)")
    args = p.parse_args(argv)

    try:
        if args.baseline or args.current:
            if not (args.baseline and args.current):
                p.error("compare mode needs both --baseline and --current")
            base = _parse_occurrence(args.baseline)
            curr = _parse_occurrence(args.current)
            e_base = efficiency(**base)
            e_curr = efficiency(**curr)
            delta = e_curr - e_base
            arrow = "up" if delta > 0 else "down" if delta < 0 else "flat"
            print(f"baseline: {_fmt(base, e_base)}")
            print(f"current : {_fmt(curr, e_curr)}")
            print(f"delta   : {delta:+.4f} ({arrow})")
        else:
            required = {"T": args.T, "R": args.R, "P": args.P, "M": args.M, "Rt": args.Rt}
            missing = [key for key, val in required.items() if val is None]
            if missing:
                p.error(f"provide {', '.join('--' + m for m in missing)} (or use --baseline/--current)")
            score = efficiency(args.T, args.R, args.P, args.M, args.Rt, args.k)
            print(_fmt({**required, "k": args.k}, score))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
