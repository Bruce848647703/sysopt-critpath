"""Command line entry point for sysopt-critpath."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .graph import Graph, GraphError
from .scheduler import Schedule, ScheduleError, plan


def _load(path: str) -> dict:
    try:
        text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"error: cannot read {path}: {exc}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("error: graph must be a JSON object")
    return payload


def _render_text(schedule: Schedule) -> str:
    lines = [
        f"tasks:         {len(schedule.assignments)}",
        f"workers:       {schedule.worker_count}",
        f"total work:    {schedule.total_work:.2f}s",
        f"critical path: {schedule.critical_path:.2f}s  "
        f"({' -> '.join(schedule.critical_path_tasks)})",
        f"makespan:      {schedule.makespan:.2f}s",
        f"speedup:       {schedule.speedup:.2f}x",
        f"utilization:   {schedule.utilization:.1%}",
        f"lower bound:   {schedule.lower_bound:.2f}s",
        f"gap:           {schedule.gap:.1%}",
        "",
        "worker timelines:",
    ]
    for worker, items in schedule.by_worker().items():
        lines.append(f"  worker {worker}:")
        if not items:
            lines.append("    (idle)")
            continue
        for item in items:
            lines.append(
                f"    {item.start:8.2f} -> {item.end:8.2f}  {item.task} "
                f"({item.end - item.start:.2f}s)"
            )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sysopt-critpath",
        description="Plan a build dependency graph onto parallel workers.",
    )
    parser.add_argument("graph", help="path to the JSON graph, or '-' for stdin")
    parser.add_argument(
        "-j",
        "--workers",
        type=int,
        default=4,
        help="number of identical workers (default: 4)",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format (default: text)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="only validate the graph and report its critical path",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        graph = Graph.from_dict(_load(args.graph))
    except GraphError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.check:
        critical_path, tasks = graph.critical_path()
        payload = {
            "tasks": len(graph),
            "total_work": round(graph.total_duration(), 6),
            "critical_path": round(critical_path, 6),
            "critical_path_tasks": tasks,
        }
        if args.format == "json":
            print(json.dumps(payload, indent=2))
        else:
            print(
                f"ok: {len(graph)} tasks, {graph.total_duration():.2f}s total, "
                f"critical path {critical_path:.2f}s ({' -> '.join(tasks)})"
            )
        return 0

    try:
        schedule = plan(graph, args.workers)
    except (GraphError, ScheduleError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(schedule.to_dict(), indent=2))
    else:
        print(_render_text(schedule))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())