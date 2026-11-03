"""Graph model and analysis for build dependency DAGs."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from heapq import heappop, heappush
from typing import Any


class GraphError(ValueError):
    """Raised when a dependency graph is malformed or cyclic."""


@dataclass(frozen=True)
class Task:
    """A single unit of work."""

    id: str
    duration: float

    def __post_init__(self) -> None:
        if not self.id:
            raise GraphError("task id must not be empty")
        if self.duration <= 0:
            raise GraphError(f"task {self.id!r} must have a positive duration")


@dataclass
class Graph:
    """Directed acyclic graph of tasks.

    Edges point from a prerequisite to the task that depends on it.
    """

    tasks: dict[str, Task] = field(default_factory=dict)
    successors: dict[str, set[str]] = field(default_factory=dict)
    predecessors: dict[str, set[str]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Graph:
        """Build a graph from the JSON-friendly mapping format."""
        if not isinstance(payload, dict):
            raise GraphError("graph must be a mapping")

        raw_nodes = payload.get("nodes")
        if not isinstance(raw_nodes, list) or not raw_nodes:
            raise GraphError("graph must contain a non-empty 'nodes' list")

        graph = cls()
        for node in raw_nodes:
            if not isinstance(node, dict):
                raise GraphError(f"node must be a mapping, got {type(node).__name__}")
            try:
                task_id = node["id"]
                duration = node["duration"]
            except KeyError as exc:
                raise GraphError(f"node is missing {exc.args[0]!r}") from exc
            if not isinstance(task_id, str):
                raise GraphError(f"node id must be a string, got {task_id!r}")
            if not isinstance(duration, (int, float)) or isinstance(duration, bool):
                raise GraphError(f"duration for {task_id!r} must be a number")
            if task_id in graph.tasks:
                raise GraphError(f"duplicate task id {task_id!r}")
            graph.tasks[task_id] = Task(task_id, float(duration))
            graph.successors[task_id] = set()
            graph.predecessors[task_id] = set()

        raw_edges = payload.get("edges", [])
        if not isinstance(raw_edges, list):
            raise GraphError("'edges' must be a list")
        for edge in raw_edges:
            if not isinstance(edge, (list, tuple)) or len(edge) != 2:
                raise GraphError(f"edge must be a [from, to] pair, got {edge!r}")
            source, target = edge
            if source not in graph.tasks:
                raise GraphError(f"edge references unknown task {source!r}")
            if target not in graph.tasks:
                raise GraphError(f"edge references unknown task {target!r}")
            if source == target:
                raise GraphError(f"task {source!r} cannot depend on itself")
            graph.successors[source].add(target)
            graph.predecessors[target].add(source)

        graph.topological_order()  # raises on cycles
        return graph

    def __len__(self) -> int:
        return len(self.tasks)

    def __iter__(self) -> Iterable[str]:
        return iter(self.tasks)

    def topological_order(self) -> list[str]:
        """Return a deterministic topological order, raising on cycles."""
        indegree = {task_id: len(self.predecessors[task_id]) for task_id in self.tasks}
        ready: list[str] = []
        for task_id, degree in indegree.items():
            if degree == 0:
                heappush(ready, task_id)

        order: list[str] = []
        while ready:
            task_id = heappop(ready)
            order.append(task_id)
            for successor in sorted(self.successors[task_id]):
                indegree[successor] -= 1
                if indegree[successor] == 0:
                    heappush(ready, successor)

        if len(order) != len(self.tasks):
            raise GraphError(f"dependency cycle detected: {' -> '.join(find_cycle(self))}")
        return order

    def critical_path(self) -> tuple[float, list[str]]:
        """Return the longest path by duration and the tasks on it."""
        order = self.topological_order()
        finish: dict[str, float] = {}
        previous: dict[str, str | None] = {}
        for task_id in order:
            best = 0.0
            best_pred: str | None = None
            for pred in self.predecessors[task_id]:
                if finish[pred] > best:
                    best = finish[pred]
                    best_pred = pred
            finish[task_id] = best + self.tasks[task_id].duration
            previous[task_id] = best_pred

        if not finish:
            return 0.0, []
        end_task = max(finish, key=lambda t: (finish[t], t))
        path: list[str] = []
        cursor: str | None = end_task
        while cursor is not None:
            path.append(cursor)
            cursor = previous[cursor]
        path.reverse()
        return finish[end_task], path

    def bottom_levels(self) -> dict[str, float]:
        """Longest remaining path from each task, including the task itself."""
        order = self.topological_order()
        levels: dict[str, float] = {}
        for task_id in reversed(order):
            tail = max((levels[s] for s in self.successors[task_id]), default=0.0)
            levels[task_id] = self.tasks[task_id].duration + tail
        return levels

    def total_duration(self) -> float:
        return sum(task.duration for task in self.tasks.values())


def find_cycle(graph: Graph) -> list[str]:
    """Return one dependency cycle, for error messages."""
    white, grey, black = 0, 1, 2
    colour = dict.fromkeys(graph.tasks, white)
    stack: list[str] = []
    position: dict[str, int] = {}

    def visit(task_id: str) -> list[str] | None:
        colour[task_id] = grey
        position[task_id] = len(stack)
        stack.append(task_id)
        for successor in sorted(graph.successors[task_id]):
            if colour[successor] == white:
                found = visit(successor)
                if found:
                    return found
            elif colour[successor] == grey:
                return stack[position[successor] :] + [successor]
        stack.pop()
        position.pop(task_id, None)
        colour[task_id] = black
        return None

    for task_id in sorted(graph.tasks):
        if colour[task_id] == white:
            found = visit(task_id)
            if found:
                return found
    return []