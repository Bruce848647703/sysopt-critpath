from __future__ import annotations

import json

import pytest

from sysopt_critpath.cli import main

GRAPH = {
    "nodes": [
        {"id": "build", "duration": 4},
        {"id": "lint", "duration": 1},
        {"id": "unit", "duration": 3},
        {"id": "package", "duration": 2},
    ],
    "edges": [["build", "unit"], ["build", "package"], ["unit", "package"]],
}


def write_graph(tmp_path, payload) -> str:
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_plan_prints_a_text_report(tmp_path, capsys):
    code = main([write_graph(tmp_path, GRAPH), "--workers", "2"])

    output = capsys.readouterr().out
    assert code == 0
    assert "makespan:" in output
    assert "worker 0:" in output


def test_plan_emits_json(tmp_path, capsys):
    code = main([write_graph(tmp_path, GRAPH), "--workers", "2", "--format", "json"])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["workers"] == 2
    assert payload["makespan"] == 9.0
    assert len(payload["assignments"]) == 4


def test_check_reports_the_critical_path(tmp_path, capsys):
    code = main([write_graph(tmp_path, GRAPH), "--check"])

    output = capsys.readouterr().out
    assert code == 0
    assert "critical path" in output


def test_invalid_graph_exits_with_code_two(tmp_path, capsys):
    path = write_graph(
        tmp_path, {"nodes": [{"id": "a", "duration": 1}], "edges": [["a", "b"]]}
    )

    code = main([path])

    assert code == 2
    assert "unknown task" in capsys.readouterr().err


def test_missing_file_exits_with_a_message(tmp_path):
    with pytest.raises(SystemExit, match="cannot read"):
        main([str(tmp_path / "missing.json")])