"""
Knowledge Repository。

封装知识图谱相关的数据操作。
"""

import logging
from typing import Optional

from core.knowledge_graph import KnowledgeGraph, KnowledgeNode, build_english_learning_graph

logger = logging.getLogger(__name__)


class KnowledgeRepository:
    """知识图谱数据访问层。"""

    def __init__(self) -> None:
        self._graph: Optional[KnowledgeGraph] = None

    @property
    def graph(self) -> KnowledgeGraph:
        """获取知识图谱（懒加载）。"""
        if self._graph is None:
            self._graph = build_english_learning_graph()
        return self._graph

    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        """获取知识点节点。"""
        return self.graph.nodes.get(node_id)

    def get_all_nodes(self) -> list[KnowledgeNode]:
        """获取所有知识点节点。"""
        return list(self.graph.nodes.values())

    def get_prerequisites(self, node_id: str) -> list[str]:
        """获取前置知识点。"""
        return self.graph.get_prerequisites(node_id)

    def get_successors(self, node_id: str) -> list[str]:
        """获取后继知识点。"""
        return self.graph.get_successors(node_id)

    def get_ready_nodes(self, mastered_ids: set[str]) -> list[str]:
        """获取当前可学习的知识点。"""
        return self.graph.get_ready_nodes(mastered_ids)

    def get_learning_path(self, target_id: str, mastered_ids: set[str]) -> list[str]:
        """获取到达目标知识点的学习路径。"""
        return self.graph.get_learning_path(target_id, mastered_ids)

    def topological_sort(self) -> list[str]:
        """拓扑排序。"""
        return self.graph.topological_sort()

    def get_graph_data(self) -> dict:
        """获取图谱数据（用于 API 返回）。"""
        return {
            "nodes": [
                {
                    "id": node.id,
                    "name": node.name,
                    "difficulty": node.difficulty,
                    "prerequisites": node.prerequisites,
                    "tags": node.tags,
                }
                for node in self.graph.nodes.values()
            ],
            "learning_order": self.graph.topological_sort(),
        }
