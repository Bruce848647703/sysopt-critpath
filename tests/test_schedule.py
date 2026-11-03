from __future__ import annotations

import pytest

from sysopt_critpath import Assignment, Graph, Schedule, ScheduleError, plan, validate


def make(nodes, edges=()):
    return Graph.from_dict(
        {"nodes": [{"id": t, "duration": d} for t, d in nodes], "edges": list(edges)}
    )


def test_single_worker_runs_everything_serially():
    graph = make([("a", 1), ("b", 2), ("c", 3)], [("a", "b"), ("b", "c")])

    schedule = plan(graph, 1)

    assert schedule.makespan == 6.0
    assert [a.task for a in schedule.assignments] == ["a", "b", "c"]
    assert schedule.speedup == pytest.approx(1.0)


def test_two_workers_remove_the_diamond_bottleneck():
    graph = make(
        [("a", 1), ("b", 2), ("c", 3), ("d", 1)],
        [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")],
    )

    schedule = plan(graph, 2)

    assert schedule.makespan == 5.0
    assert schedule.makespan == schedule.critical_path
    assert schedule.gap == 0.0
    validate(schedule, graph)


def test_independent_tasks_balance_across_workers():
    graph = make([(f"t{i}", 1) for i in range(4)])

    schedule = plan(graph, 2)

    assert schedule.makespan == 2.0
    assert schedule.lower_bound == 2.0
    assert schedule.utilization == pytest.approx(1.0)
    assert [len(v) for v in schedule.by_worker().values()] == [2, 2]


def test_more_workers_never_exceed_the_critical_path():
    graph = make([("a", 1), ("b", 2), ("c", 3)], [("a", "b"), ("b", "c")])

    schedule = plan(graph, 8)

    assert schedule.makespan == schedule.critical_path == 6.0


def test_schedule_is_deterministic():
    graph = make(
        [("build", 4), ("lint", 1), ("unit", 3), ("docs", 2), ("package", 2)],
        [("build", "unit"), ("build", "package"), ("unit", "package"), ("lint", "package")],
    )

    first = plan(graph, 2)
    second = plan(graph, 2)

    assert first.to_dict() == second.to_dict()


def test_validate_rejects_a_dependency_violation():
    graph = make([("a", 1), ("b", 1)], [("a", "b")])
    schedule = Schedule(
        worker_count=2,
        makespan=1.0,
        assignments=[
            Assignment("a", 0, 0.0, 1.0),
            Assignment("b", 1, 0.0, 1.0),
        ],
        critical_path=2.0,
        critical_path_tasks=["a", "b"],
        total_work=2.0,
    )

    with pytest.raises(ScheduleError, match="starts before"):
        validate(schedule, graph)


def test_rejects_zero_workers():
    graph = make([("a", 1)])

    with pytest.raises(ScheduleError, match="at least 1"):
        plan(graph, 0)


def test_empty_graph():
    graph = Graph.from_dict({"nodes": [{"id": "a", "duration": 1}]})
    graph.tasks.clear()
    graph.successors.clear()
    graph.predecessors.clear()

    schedule = plan(graph, 2)

    assert schedule.makespan == 0.0
    assert schedule.assignments == []