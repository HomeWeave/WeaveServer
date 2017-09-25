import pytest

from app.core.toposort import toposort

class TestToposort(object):
    def test_simple(self):
        graph = {
            "a": {"x", "y", "z"},
            "b": {"x", "a"},
            "x": {"y", "z"},
            "z": {"y"},
            "y": {}
        }
        order = toposort(graph)
        order = {x: order.index(x) for x in order}

        for name, deps in graph.items():
            assert all(order[name] > order[d] for d in deps)

    def test_unknown_deps(self):
        graph = {
            "a": {"x", "y", "z"},
            "b": {"x", "a"},
            "x": {"y", "z", "k"},
            "z": {"y"},
            "y": {}
        }
        order = toposort(graph)
        order = {x: order.index(x) for x in order}
        graph["x"] = {"y", "z"}
        for name, deps in graph.items():
            assert all(order[name] > order[d] for d in deps)

    def test_cycle(self):
        graph = {
            "a": {"x", "y", "z"},
            "b": {"x", "a"},
            "x": {"y", "z", "k"},
            "z": {"y"},
            "y": {"a"},
        }
        with pytest.raises(ValueError):
            toposort(graph)
