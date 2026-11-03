# sysopt-critpath

Plan a build/test dependency graph onto a fixed number of parallel workers and see
where the wall-clock time actually goes.

Most CI speed-ups fail because the critical path, not the total work, sets the
floor. This tool makes that floor explicit: it computes the critical path, the
theoretical lower bound for `N` workers, and a deterministic list schedule that
you can compare against what your pipeline currently does.

```text
$ sysopt-critpath examples/build-graph.json -j 4
tasks:         13
workers:       4
total work:    66.00s
critical path: 41.00s  (fetch-deps -> gen-code -> compile-core -> compile-plugins -> unit-plugins -> package -> e2e -> publish)
makespan:      41.00s
speedup:       1.61x
utilization:   40.2%
lower bound:   41.00s
gap:           0.0%
```

## Install

```bash
pip install -e .
# or run without installing
PYTHONPATH=src python -m sysopt_critpath.cli examples/build-graph.json -j 4
```

## Graph format

```json
{
  "nodes": [
    {"id": "compile-core", "duration": 12},
    {"id": "unit-core", "duration": 8}
  ],
  "edges": [["compile-core", "unit-core"]]
}
```

- `duration` is in any consistent unit (seconds by default) and must be positive.
- Edges point from a prerequisite to the task that depends on it.
- Node ids must be unique; cycles are rejected with the offending cycle in the
  error message.

## Usage

```bash
# schedule on 4 workers
sysopt-critpath examples/build-graph.json -j 4

# machine-readable output
sysopt-critpath examples/build-graph.json -j 4 --format json

# validate only and report the critical path
sysopt-critpath examples/build-graph.json --check

# read from stdin
cat graph.json | sysopt-critpath - -j 8
```

Exit codes: `0` success, `2` invalid graph or schedule.

## What the numbers mean

| Field | Meaning |
| --- | --- |
| `total work` | Sum of all task durations (serial execution time). |
| `critical path` | Longest dependency chain; no schedule can beat it. |
| `makespan` | Finish time of the produced schedule. |
| `lower bound` | `max(critical_path, total_work / workers)`. |
| `gap` | How far the schedule is above that bound. |
| `utilization` | Fraction of worker time spent running tasks. |

## Algorithm

Tasks are scheduled with the classic critical-path priority rule: at every step
the ready task with the largest **bottom level** (longest remaining path to a
sink) is placed on the worker that frees up first. Ties are broken by task id,
so the same input always produces the same schedule. Every schedule is validated
against the graph (precedence and worker exclusivity) before it is returned.

The scheduler assumes identical workers and no resource limits beyond worker
count. That keeps the model honest: if the schedule still leaves a large gap,
the graph is the problem, not the machine count.

## Development

```bash
pip install -e ".[dev]"
ruff check .
pytest -q
```

## License

MIT