"""
知识图谱 -- 管理知识点之间的依赖关系。

知识图谱是一个 DAG（有向无环图），用于：
1. 确定学习顺序（拓扑排序）
2. 检查前置知识是否达标
3. 推荐下一个可学习的知识点

面试要点：
- DAG拓扑排序算法（Kahn's / DFS）
- 前置知识检查的重要性
- 知识图谱 vs 知识树：图更灵活，一个节点可有多个前置
"""

import logging
from collections import deque

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class KnowledgeNode(BaseModel):
    """知识点节点。"""

    id: str
    name: str
    subject: str = "math"  # 学科
    difficulty: float = 0.5  # 难度 0-1
    description: str = ""
    prerequisites: list[str] = Field(default_factory=list)  # 前置知识点ID列表
    tags: list[str] = Field(default_factory=list)


class KnowledgeGraph:
    """
    知识图谱（DAG），管理知识点依赖关系。

    示例（初中数学）：
        加法 → 乘法 → 一元一次方程 → 二元一次方程组
                    → 因式分解 → 一元二次方程
    """

    def __init__(self) -> None:
        self.nodes: dict[str, KnowledgeNode] = {}
        self._adjacency: dict[str, list[str]] = {}  # node_id -> 后继节点列表
        self._reverse_adj: dict[str, list[str]] = {}  # node_id -> 前置节点列表

    def add_node(self, node: KnowledgeNode) -> None:
        """添加知识点。"""
        self.nodes[node.id] = node
        if node.id not in self._adjacency:
            self._adjacency[node.id] = []
        if node.id not in self._reverse_adj:
            self._reverse_adj[node.id] = []

        for prereq_id in node.prerequisites:
            if prereq_id not in self._adjacency:
                self._adjacency[prereq_id] = []
            self._adjacency[prereq_id].append(node.id)
            self._reverse_adj[node.id].append(prereq_id)

    def get_prerequisites(self, node_id: str) -> list[str]:
        """获取直接前置知识点。"""
        return self._reverse_adj.get(node_id, [])

    def get_successors(self, node_id: str) -> list[str]:
        """获取直接后继知识点。"""
        return self._adjacency.get(node_id, [])

    def get_all_prerequisites(self, node_id: str) -> set[str]:
        """获取所有前置知识点（递归）。"""
        visited: set[str] = set()
        queue = deque(self.get_prerequisites(node_id))
        while queue:
            pid = queue.popleft()
            if pid not in visited:
                visited.add(pid)
                queue.extend(self.get_prerequisites(pid))
        return visited

    def topological_sort(self) -> list[str]:
        """
        拓扑排序 -- Kahn算法。

        返回知识点的学习顺序：确保前置知识排在前面。
        面试常考：BFS版拓扑排序 vs DFS版，时间复杂度O(V+E)。
        """
        in_degree: dict[str, int] = {nid: 0 for nid in self.nodes}
        for nid in self.nodes:
            for succ in self._adjacency.get(nid, []):
                if succ in in_degree:
                    in_degree[succ] += 1

        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        result: list[str] = []

        while queue:
            nid = queue.popleft()
            result.append(nid)
            for succ in self._adjacency.get(nid, []):
                if succ in in_degree:
                    in_degree[succ] -= 1
                    if in_degree[succ] == 0:
                        queue.append(succ)

        if len(result) != len(self.nodes):
            logger.warning("Knowledge graph contains a cycle! Partial sort returned.")

        return result

    def get_ready_nodes(self, mastered_ids: set[str]) -> list[str]:
        """
        获取当前可以学习的知识点：前置知识全部掌握，但自己还未掌握。

        这是 Curriculum Agent 推荐下一个知识点的核心逻辑。
        """
        ready = []
        for nid, node in self.nodes.items():
            if nid in mastered_ids:
                continue
            prereqs = set(node.prerequisites)
            if prereqs.issubset(mastered_ids):
                ready.append(nid)
        return sorted(ready, key=lambda nid: self.nodes[nid].difficulty)

    def get_learning_path(self, target_id: str, mastered_ids: set[str]) -> list[str]:
        """
        生成到达目标知识点的最短学习路径。

        从target_id反向遍历，找出所有未掌握的前置知识，按拓扑序排列。
        """
        needed = self.get_all_prerequisites(target_id) - mastered_ids
        if target_id not in mastered_ids:
            needed.add(target_id)

        full_order = self.topological_sort()
        return [nid for nid in full_order if nid in needed]


def build_sample_math_graph() -> KnowledgeGraph:
    """构建示例数学知识图谱（初中数学部分知识点）。"""
    graph = KnowledgeGraph()

    nodes = [
        KnowledgeNode(id="arithmetic", name="四则运算", difficulty=0.1, tags=["基础"]),
        KnowledgeNode(id="fractions", name="分数运算", difficulty=0.2, prerequisites=["arithmetic"], tags=["基础"]),
        KnowledgeNode(id="negative_numbers", name="负数", difficulty=0.15, prerequisites=["arithmetic"], tags=["基础"]),
        KnowledgeNode(id="algebraic_expr", name="代数式", difficulty=0.3, prerequisites=["arithmetic", "negative_numbers"], tags=["代数"]),
        KnowledgeNode(id="linear_eq_1", name="一元一次方程", difficulty=0.35, prerequisites=["algebraic_expr"], tags=["方程"]),
        KnowledgeNode(id="linear_eq_2", name="二元一次方程组", difficulty=0.45, prerequisites=["linear_eq_1"], tags=["方程"]),
        KnowledgeNode(id="factoring", name="因式分解", difficulty=0.4, prerequisites=["algebraic_expr"], tags=["代数"]),
        KnowledgeNode(id="quadratic_eq", name="一元二次方程", difficulty=0.55, prerequisites=["factoring", "linear_eq_1"], tags=["方程"]),
        KnowledgeNode(id="quadratic_func", name="二次函数", difficulty=0.6, prerequisites=["quadratic_eq"], tags=["函数"]),
        KnowledgeNode(id="inequality", name="不等式", difficulty=0.4, prerequisites=["linear_eq_1"], tags=["不等式"]),
        KnowledgeNode(id="coordinate", name="平面直角坐标系", difficulty=0.3, prerequisites=["negative_numbers"], tags=["几何"]),
        KnowledgeNode(id="linear_func", name="一次函数", difficulty=0.45, prerequisites=["linear_eq_1", "coordinate"], tags=["函数"]),
        KnowledgeNode(id="pythagorean", name="勾股定理", difficulty=0.35, prerequisites=["arithmetic"], tags=["几何"]),
        KnowledgeNode(id="similar_triangle", name="相似三角形", difficulty=0.5, prerequisites=["pythagorean", "fractions"], tags=["几何"]),
        KnowledgeNode(id="trig_basic", name="三角函数基础", difficulty=0.55, prerequisites=["pythagorean", "fractions"], tags=["三角"]),
        KnowledgeNode(id="probability", name="概率初步", difficulty=0.4, prerequisites=["fractions"], tags=["统计"]),
        KnowledgeNode(id="statistics", name="数据统计", difficulty=0.35, prerequisites=["arithmetic", "fractions"], tags=["统计"]),
        KnowledgeNode(id="sequence", name="数列", difficulty=0.5, prerequisites=["algebraic_expr"], tags=["代数"]),
        KnowledgeNode(id="sets", name="集合", difficulty=0.25, prerequisites=["arithmetic"], tags=["基础"]),
        KnowledgeNode(id="logic", name="简易逻辑", difficulty=0.3, prerequisites=["sets"], tags=["基础"]),
    ]

    for node in nodes:
        graph.add_node(node)

    logger.info("Sample math knowledge graph built with %d nodes", len(nodes))
    return graph


def build_english_learning_graph() -> KnowledgeGraph:
    """
    构建英语学习知识图谱。

    包含7个维度：词汇、语法、阅读、写作、听力、口语、发音
    知识点之间有依赖关系，如：基础词汇 -> 高级词汇
    """
    graph = KnowledgeGraph()

    nodes = [
        # ── 词汇类（基础到高级） ──
        KnowledgeNode(
            id="vocab_basic",
            name="基础词汇",
            subject="english",
            difficulty=0.3,
            description="日常生活中最常用的300个英语单词",
            tags=["词汇", "基础"],
        ),
        KnowledgeNode(
            id="vocab_intermediate",
            name="中级词汇",
            subject="english",
            difficulty=0.5,
            description="学术和工作场景常用的500个单词",
            prerequisites=["vocab_basic"],
            tags=["词汇", "中级"],
        ),
        KnowledgeNode(
            id="vocab_advanced",
            name="高级词汇",
            subject="english",
            difficulty=0.7,
            description="GRE/托福级别的高级词汇",
            prerequisites=["vocab_intermediate"],
            tags=["词汇", "高级"],
        ),
        KnowledgeNode(
            id="vocab_academic",
            name="学术词汇",
            subject="english",
            difficulty=0.8,
            description="学术论文和专业文献中的词汇",
            prerequisites=["vocab_advanced"],
            tags=["词汇", "学术"],
        ),
        KnowledgeNode(
            id="vocab_idioms",
            name="习语与短语动词",
            subject="english",
            difficulty=0.65,
            description="常见英语习语和短语动词的含义与用法",
            prerequisites=["vocab_intermediate"],
            tags=["词汇", "实用"],
        ),

        # ── 语法类（从基础到复杂） ──
        KnowledgeNode(
            id="grammar_tenses",
            name="时态",
            subject="english",
            difficulty=0.4,
            description="英语12种时态的用法",
            prerequisites=["vocab_basic"],
            tags=["语法", "基础"],
        ),
        KnowledgeNode(
            id="grammar_passive",
            name="被动语态",
            subject="english",
            difficulty=0.5,
            description="被动语态的构成和使用场景",
            prerequisites=["grammar_tenses"],
            tags=["语法", "中级"],
        ),
        KnowledgeNode(
            id="grammar_conditionals",
            name="条件句",
            subject="english",
            difficulty=0.6,
            description="零条件句、第一/二/三条件句",
            prerequisites=["grammar_tenses"],
            tags=["语法", "中级"],
        ),
        KnowledgeNode(
            id="grammar_relative",
            name="定语从句",
            subject="english",
            difficulty=0.6,
            description="关系代词和关系副词引导的定语从句",
            prerequisites=["grammar_tenses", "vocab_intermediate"],
            tags=["语法", "高级"],
        ),
        KnowledgeNode(
            id="grammar_articles",
            name="冠词用法",
            subject="english",
            difficulty=0.45,
            description="a/an/the 的用法规则与例外",
            prerequisites=["vocab_basic"],
            tags=["语法", "基础"],
        ),
        KnowledgeNode(
            id="grammar_prepositions",
            name="介词搭配",
            subject="english",
            difficulty=0.5,
            description="常见介词搭配与固定用法",
            prerequisites=["vocab_basic"],
            tags=["语法", "中级"],
        ),

        # ── 阅读类 ──
        KnowledgeNode(
            id="reading_skimming",
            name="略读技巧",
            subject="english",
            difficulty=0.4,
            description="快速获取文章主旨的阅读技巧",
            prerequisites=["vocab_basic", "grammar_tenses"],
            tags=["阅读", "基础"],
        ),
        KnowledgeNode(
            id="reading_scanning",
            name="扫读技巧",
            subject="english",
            difficulty=0.4,
            description="快速定位特定信息的阅读技巧",
            prerequisites=["vocab_basic", "grammar_tenses"],
            tags=["阅读", "基础"],
        ),
        KnowledgeNode(
            id="reading_inference",
            name="推理判断",
            subject="english",
            difficulty=0.6,
            description="根据上下文推断词义和作者意图",
            prerequisites=["reading_skimming", "vocab_intermediate"],
            tags=["阅读", "高级"],
        ),
        KnowledgeNode(
            id="reading_main_idea",
            name="主旨大意",
            subject="english",
            difficulty=0.5,
            description="把握文章中心思想和段落大意",
            prerequisites=["reading_skimming"],
            tags=["阅读", "中级"],
        ),
        KnowledgeNode(
            id="reading_critical",
            name="批判性阅读",
            subject="english",
            difficulty=0.7,
            description="分析作者观点、论据和隐含意义",
            prerequisites=["reading_inference", "vocab_advanced"],
            tags=["阅读", "高级"],
        ),

        # ── 写作类 ──
        KnowledgeNode(
            id="writing_paragraph",
            name="段落写作",
            subject="english",
            difficulty=0.5,
            description="主题句、支撑句、结论句的写作",
            prerequisites=["grammar_tenses", "vocab_intermediate"],
            tags=["写作", "基础"],
        ),
        KnowledgeNode(
            id="writing_email",
            name="邮件写作",
            subject="english",
            difficulty=0.4,
            description="商务邮件和日常邮件的写作规范",
            prerequisites=["grammar_tenses", "vocab_basic"],
            tags=["写作", "实用"],
        ),
        KnowledgeNode(
            id="writing_essay",
            name="议论文写作",
            subject="english",
            difficulty=0.7,
            description="引言、正文、结论的结构化写作",
            prerequisites=["writing_paragraph", "grammar_relative"],
            tags=["写作", "高级"],
        ),
        KnowledgeNode(
            id="writing_summary",
            name="摘要写作",
            subject="english",
            difficulty=0.6,
            description="提取关键信息并简洁表达",
            prerequisites=["reading_main_idea", "writing_paragraph"],
            tags=["写作", "中级"],
        ),
        KnowledgeNode(
            id="writing_letter",
            name="书信写作",
            subject="english",
            difficulty=0.45,
            description="正式与非正式书信的格式和表达",
            prerequisites=["grammar_tenses", "vocab_intermediate"],
            tags=["写作", "实用"],
        ),
        KnowledgeNode(
            id="writing_report",
            name="报告写作",
            subject="english",
            difficulty=0.65,
            description="商务报告的结构、数据呈现和结论撰写",
            prerequisites=["writing_paragraph", "vocab_academic"],
            tags=["写作", "高级"],
        ),

        # ── 听力类 ──
        KnowledgeNode(
            id="listening_gist",
            name="听力主旨",
            subject="english",
            difficulty=0.4,
            description="听懂对话或讲座的主要内容",
            prerequisites=["vocab_basic", "grammar_tenses"],
            tags=["听力", "基础"],
        ),
        KnowledgeNode(
            id="listening_detail",
            name="听力细节",
            subject="english",
            difficulty=0.5,
            description="捕捉具体信息如时间、地点、数字",
            prerequisites=["listening_gist"],
            tags=["听力", "中级"],
        ),
        KnowledgeNode(
            id="listening_note",
            name="听力笔记",
            subject="english",
            difficulty=0.6,
            description="边听边记的笔记技巧",
            prerequisites=["listening_detail"],
            tags=["听力", "高级"],
        ),
        KnowledgeNode(
            id="listening_predict",
            name="听力预测",
            subject="english",
            difficulty=0.5,
            description="根据上下文预测说话者意图",
            prerequisites=["listening_gist", "reading_inference"],
            tags=["听力", "中级"],
        ),

        # ── 口语类 ──
        KnowledgeNode(
            id="speaking_pronunciation",
            name="发音基础",
            subject="english",
            difficulty=0.35,
            description="音标、重音、连读等发音规则",
            tags=["口语", "基础"],
        ),
        KnowledgeNode(
            id="speaking_conversation",
            name="日常对话",
            subject="english",
            difficulty=0.4,
            description="日常交际用语和对话技巧",
            prerequisites=["vocab_basic", "grammar_tenses"],
            tags=["口语", "基础"],
        ),
        KnowledgeNode(
            id="speaking_presentation",
            name="演讲表达",
            subject="english",
            difficulty=0.65,
            description="公众演讲的结构、语气和肢体语言",
            prerequisites=["speaking_conversation", "vocab_advanced"],
            tags=["口语", "高级"],
        ),
        KnowledgeNode(
            id="speaking_discussion",
            name="讨论辩论",
            subject="english",
            difficulty=0.6,
            description="表达观点、反驳和达成共识",
            prerequisites=["speaking_conversation", "grammar_conditionals"],
            tags=["口语", "中级"],
        ),
    ]

    for node in nodes:
        graph.add_node(node)

    logger.info("English learning knowledge graph built with %d nodes", len(nodes))
    return graph
