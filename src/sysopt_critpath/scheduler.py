"""List scheduling on identical workers with critical-path priorities."""

from __future__ import annotations

from dataclasses import dataclass, field
from heapq import heappop, heappush
from math import ceil
from typing import Any

from .graph import Graph


class ScheduleError(ValueError):
    """Raised when a schedule cannot be built or validated."""


@dataclass(frozen=True)
class Assignment:
    """One task placed on a worker."""

    task: str
    worker: int
    start: float
    end: float


@dataclass
class Schedule:
    """Result of planning a graph onto a fixed number of workers."""

    worker_count: int
    makespan: float
    assignments: list[Assignment] = field(default_factory=list)
    critical_path: float = 0.0
    critical_path_tasks: list[str] = field(default_factory=list)
    total_work: float = 0.0

    @property
    def utilization(self) -> float:
        """Fraction of available worker time spent on tasks."""
        capacity = self.worker_count * self.makespan
        return self.total_work / capacity if capacity else 0.0

    @property
    def speedup(self) -> float:
        """Serial time divided by makespan."""
        return self.total_work / self.makespan if self.makespan else 0.0

    @property
    def lower_bound(self) -> float:
        """Best possible makespan given the critical path and total work."""
        return max(self.critical_path, self.total_work / self.worker_count)

    @property
    def gap(self) -> float:
        """Relative gap between this makespan and the lower bound."""
        if self.lower_bound == 0:
            return 0.0
        return (self.makespan - self.lower_bound) / self.lower_bound

    def by_worker(self) -> dict[int, list[Assignment]]:
        grouped: dict[int, list[Assignment]] = {w: [] for w in range(self.worker_count)}
        for assignment in self.assignments:
            grouped[assignment.worker].append(assignment)
        for items in grouped.values():
            items.sort(key=lambda a: a.start)
        return grouped

    def to_dict(self) -> dict[str, Any]:
        return {
            "workers": self.worker_count,
            "makespan": round(self.makespan, 6),
            "critical_path": round(self.critical_path, 6),
            "critical_path_tasks": self.critical_path_tasks,
            "total_work": round(self.total_work, 6),
            "speedup": round(self.speedup, 6),
            "utilization": round(self.utilization, 6),
            "lower_bound": round(self.lower_bound, 6),
            "gap": round(self.gap, 6),
            "assignments": [
                {
                    "task": a.task,
                    "worker": a.worker,
                    "start": round(a.start, 6),
                    "end": round(a.end, 6),
                }
                for a in sorted(self.assignments, key=lambda a: (a.start, a.worker, a.task))
            ],
        }


def plan(graph: Graph, workers: int) -> Schedule:
    """Schedule every task on ``workers`` identical workers.

    Tasks are picked by descending bottom level (the longest path to a sink),
    which is the classic critical-path priority for list scheduling. Ties are
    broken by task id so the result is deterministic.
    """
    if workers < 1:
        raise ScheduleError("workers must be at least 1")

    order = graph.topological_order()
    if not order:
        return Schedule(worker_count=workers, makespan=0.0)

    bottom = graph.bottom_levels()
    indegree = {task_id: len(graph.predecessors[task_id]) for task_id in graph.tasks}
    ready: list[tuple[float, str]] = [
        (-bottom[task_id], task_id) for task_id in order if indegree[task_id] == 0
    ]
    ready.sort()
    ready_heap: list[tuple[float, str]] = []
    for item in ready:
        heappush(ready_heap, item)

    worker_free = [0.0] * workers
    finish: dict[str, float] = {}
    assignments: list[Assignment] = []

    while ready_heap:
        _, task_id = heappop(ready_heap)
        earliest = max((finish[p] for p in graph.predecessors[task_id]), default=0.0)
        worker = min(range(workers), key=lambda w: (worker_free[w], w))
        start = max(earliest, worker_free[worker])
        end = start + graph.tasks[task_id].duration
        worker_free[worker] = end
        finish[task_id] = end
        assignments.append(Assignment(task_id, worker, start, end))

        for successor in sorted(graph.successors[task_id]):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                heappush(ready_heap, (-bottom[successor], successor))

    if len(assignments) != len(graph.tasks):
        raise ScheduleError("internal error: not every task was scheduled")

    critical_path, critical_tasks = graph.critical_path()
    schedule = Schedule(
        worker_count=workers,
        makespan=max(finish.values()),
        assignments=assignments,
        critical_path=critical_path,
        critical_path_tasks=critical_tasks,
        total_work=graph.total_duration(),
    )
    validate(schedule, graph)
    return schedule


def validate(schedule: Schedule, graph: Graph) -> None:
    """Check precedence and worker exclusivity for a schedule."""
    placed = {a.task: a for a in schedule.assignments}
    if set(placed) != set(graph.tasks):
        raise ScheduleError("schedule does not cover every task")

    for task_id, assignment in placed.items():
        if assignment.start < 0 or assignment.end < assignment.start:
            raise ScheduleError(f"invalid time window for {task_id!r}")
        for pred in graph.predecessors[task_id]:
            if placed[pred].end > assignment.start + 1e-9:
                raise ScheduleError(f"{task_id!r} starts before {pred!r} finishes")

    for worker in range(schedule.worker_count):
        items = sorted(
            (a for a in schedule.assignments if a.worker == worker), key=lambda a: a.start
        )
        for previous, current in zip(items, items[1:], strict=False):
            if previous.end > current.start + 1e-9:
                raise ScheduleError(f"worker {worker} runs overlapping tasks")

    if ceil(schedule.makespan * 1e9) < ceil(schedule.lower_bound * 1e9):
        raise ScheduleError("makespan is below the theoretical lower bound")