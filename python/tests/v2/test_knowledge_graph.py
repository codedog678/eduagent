"""测试知识图谱扩展。"""

import pytest
from core.knowledge_graph import build_english_learning_graph


def test_english_graph_node_count():
    """测试英语知识图谱节点数量。"""
    graph = build_english_learning_graph()
    assert len(graph.nodes) >= 15  # 至少15个知识点


def test_english_graph_coverage():
    """测试英语知识图谱覆盖范围。"""
    graph = build_english_learning_graph()

    # 检查各个维度的覆盖
    vocabulary_nodes = [n for n in graph.nodes.values() if "词汇" in n.tags]
    grammar_nodes = [n for n in graph.nodes.values() if "语法" in n.tags]
    reading_nodes = [n for n in graph.nodes.values() if "阅读" in n.tags]
    writing_nodes = [n for n in graph.nodes.values() if "写作" in n.tags]
    listening_nodes = [n for n in graph.nodes.values() if "听力" in n.tags]
    speaking_nodes = [n for n in graph.nodes.values() if "口语" in n.tags]

    assert len(vocabulary_nodes) >= 3
    assert len(grammar_nodes) >= 3
    assert len(reading_nodes) >= 3
    assert len(writing_nodes) >= 3
    assert len(listening_nodes) >= 2
    assert len(speaking_nodes) >= 2


def test_english_graph_prerequisites():
    """测试英语知识图谱前置知识关系。"""
    graph = build_english_learning_graph()

    # 检查一些关键的前置关系
    assert "vocab_basic" in graph.nodes
    assert "vocab_intermediate" in graph.nodes
    assert "vocab_basic" in graph.nodes["vocab_intermediate"].prerequisites

    assert "grammar_tenses" in graph.nodes
    assert "vocab_basic" in graph.nodes["grammar_tenses"].prerequisites


def test_english_graph_topological_sort():
    """测试英语知识图谱拓扑排序。"""
    graph = build_english_learning_graph()
    order = graph.topological_sort()

    # 验证拓扑排序的正确性
    for i, node_id in enumerate(order):
        node = graph.nodes[node_id]
        for prereq_id in node.prerequisites:
            prereq_index = order.index(prereq_id)
            assert prereq_index < i, f"{prereq_id} should come before {node_id}"


def test_english_graph_ready_nodes():
    """测试获取可学习节点。"""
    graph = build_english_learning_graph()

    # 初始状态下，没有前置要求的节点应该可学习
    ready = graph.get_ready_nodes(set())
    assert len(ready) > 0

    # 检查没有前置要求的节点
    for node_id in ready:
        node = graph.nodes[node_id]
        assert len(node.prerequisites) == 0


def test_english_graph_learning_path():
    """测试学习路径生成。"""
    graph = build_english_learning_graph()

    # 从零开始学习某个高级知识点
    path = graph.get_learning_path("vocab_advanced", set())
    assert "vocab_basic" in path
    assert "vocab_intermediate" in path
    assert "vocab_advanced" in path
