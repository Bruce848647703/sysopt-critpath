from __future__ import annotations

import pytest

from sysopt_critpath import Graph, GraphError


def make(nodes, edges=()):
    return Graph.from_dict(
        {"nodes": [{"id": t, "duration": d} for t, d in nodes], "edges": list(edges)}
    )


def test_builds_tasks_and_edges():
    graph = make([("a", 1), ("b", 2)], [("a", "b")])

    assert len(graph) == 2
    assert graph.successors["a"] == {"b"}
    assert graph.predecessors["b"] == {"a"}


def test_rejects_duplicate_ids():
    with pytest.raises(GraphError, match="duplicate task id"):
        make([("a", 1), ("a", 2)])


def test_rejects_unknown_edge_endpoints():
    with pytest.raises(GraphError, match="unknown task 'ghost'"):
        make([("a", 1)], [("a", "ghost")])


def test_rejects_self_edge():
    with pytest.raises(GraphError, match="cannot depend on itself"):
        make([("a", 1)], [("a", "a")])


def test_rejects_non_positive_duration():
    with pytest.raises(GraphError, match="positive duration"):
        make([("a", 0)])


def test_rejects_empty_nodes():
    with pytest.raises(GraphError, match="non-empty 'nodes'"):
        Graph.from_dict({"nodes": []})


def test_detects_cycle_and_names_it():
    with pytest.raises(GraphError, match="dependency cycle detected"):
        make([("a", 1), ("b", 1), ("c", 1)], [("a", "b"), ("b", "c"), ("c", "a")])


def test_topological_order_is_deterministic():
    graph = make([("c", 1), ("a", 1), ("b", 1)], [("a", "c"), ("b", "c")])

    assert graph.topological_order() == ["a", "b", "c"]


def test_critical_path_of_a_diamond():
    graph = make(
        [("a", 1), ("b", 2), ("c", 3), ("d", 1)],
        [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")],
    )

    length, path = graph.critical_path()

    assert length == 5.0
    assert path == ["a", "c", "d"]


def test_bottom_levels_include_the_task_itself():
    graph = make([("a", 1), ("b", 2), ("c", 3)], [("a", "b"), ("b", "c")])

    assert graph.bottom_levels() == {"a": 6.0, "b": 5.0, "c": 3.0}


def test_total_duration():
    graph = make([("a", 1.5), ("b", 2.5)])

    assert graph.total_duration() == 4.0