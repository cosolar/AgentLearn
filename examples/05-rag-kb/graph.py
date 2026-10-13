"""graph.py —— 极简知识图谱与多跳检索（GraphRAG 的可运行内核）

对应 docs/05-RAG系统/01-RAG原理.md 的 5.5 GraphRAG：
    向量检索擅长「找相似段落」，图谱擅长「跨文档多跳推理」。
    本模块提供零依赖的图结构 + 多跳遍历，以及一个**规则版**三元组抽取器，
    使得整条链路可以离线跑通；生产可换成 LLM 抽取（见 agent.py）或 Neo4j。

依赖：仅标准库。
"""

from __future__ import annotations

import re
from collections import deque

# 规则版三元组模式：(主语) 由/受/属于/包含 (宾语)
# 实体字符类需包含书名号《》，否则「《政策》由X制定」这类句子无法匹配；
# 用 \s* 容忍中英文之间的空格（如 "Atlas 受《...》约束"）。
_ENT = r"[\u4e00-\u9fffA-Za-z0-9《》]+"
_RULES = [
    (re.compile(rf"({_ENT})\s*由\s*({_ENT})\s*负责"), "由...负责"),
    (re.compile(rf"({_ENT})\s*由\s*({_ENT})\s*制定"), "由...制定"),
    (re.compile(rf"({_ENT})\s*受\s*({_ENT}?)\s*约束"), "受...约束"),
    (re.compile(rf"({_ENT})\s*属于\s*({_ENT})"), "属于"),
    (re.compile(rf"({_ENT})\s*包含\s*({_ENT})"), "包含"),
]


def _clean(entity: str) -> str:
    """去掉实体两侧的书名号与空白。"""
    return entity.strip().strip("《》").strip()


def extract_triples_rule(text: str) -> list[tuple[str, str, str]]:
    """规则版三元组抽取（离线可用，用于教学与自检）。

    返回 [(主语, 关系, 宾语)]。生产环境应改用 LLM 抽取（见 agent.py 的 extract_triples_llm）。
    """
    triples: list[tuple[str, str, str]] = []
    for sentence in re.split(r"[。；;\n]", text):
        for pattern, relation in _RULES:
            m = pattern.search(sentence)
            if m:
                subj, obj = _clean(m.group(1)), _clean(m.group(2))
                if subj and obj:
                    triples.append((subj, relation, obj))
    return triples


class SimpleGraph:
    """极简知识图谱（内存版，支持多跳遍历）"""

    def __init__(self) -> None:
        self.edges: list[tuple[str, str, str]] = []

    def add(self, triples: list[tuple[str, str, str]]) -> None:
        self.edges.extend(triples)

    def entities(self) -> set[str]:
        out: set[str] = set()
        for s, _r, o in self.edges:
            out.add(s)
            out.add(o)
        return out

    def neighbors(self, entity: str) -> list[tuple[str, str]]:
        """返回该实体的所有一跳邻居 [(邻居, 关系)]（无向）。"""
        out = [(o, r) for s, r, o in self.edges if s == entity]
        out += [(s, r) for s, r, o in self.edges if o == entity]
        return out

    def multi_hop(self, entity: str, hops: int = 2) -> list[str]:
        """BFS：收集 hops 跳内可达的实体（含起点）。"""
        visited = {entity}
        queue: deque[tuple[str, int]] = deque([(entity, 0)])
        while queue:
            node, depth = queue.popleft()
            if depth >= hops:
                continue
            for neighbor, _rel in self.neighbors(node):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, depth + 1))
        return sorted(visited)

    def path(self, src: str, dst: str, max_hops: int = 3) -> list[tuple[str, str, str]]:
        """返回 src→dst 的一条最短路径（边列表），找不到返回 []。"""
        if src == dst:
            return []
        prev: dict[str, tuple[str, str] | None] = {src: None}
        queue: deque[str] = deque([src])
        while queue:
            node = queue.popleft()
            for neighbor, rel in self.neighbors(node):
                if neighbor in prev:
                    continue
                prev[neighbor] = (node, rel)
                if neighbor == dst:
                    return self._reconstruct(prev, dst)
                queue.append(neighbor)
        return []

    @staticmethod
    def _reconstruct(prev: dict, dst: str) -> list[tuple[str, str, str]]:
        edges: list[tuple[str, str, str]] = []
        cur = dst
        while prev.get(cur) is not None:
            parent, rel = prev[cur]
            edges.append((parent, rel, cur))
            cur = parent
        return list(reversed(edges))


def build_graph_from_docs(docs: list[dict], use_llm: bool = False, llm=None) -> SimpleGraph:
    """从文档列表构建图。

    use_llm=False（默认）：用规则抽取器，**离线可用**，适合教学与自检。
    use_llm=True：用 LLM 抽取（需要 API Key），覆盖面更广但更慢、更贵。
    """
    g = SimpleGraph()
    for d in docs:
        if use_llm:
            g.add(extract_triples_llm(d["text"], llm=llm))
        else:
            g.add(extract_triples_rule(d["text"]))
    return g


def extract_triples_llm(text: str, llm=None) -> list[tuple[str, str, str]]:
    """用 LLM 抽取 (主语, 关系, 宾语) 三元组（需要 API Key）。

    生产做法：分批 + 结构化输出（ToolStrategy / response_format）以保证 JSON 合法。
    这里用最小实现，并对返回值做容错（剥离代码围栏、解析失败即返回空）。
    """
    import json
    import os

    if llm is None:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=os.getenv("LLM_MODEL_NAME", "gpt-5.5"),
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL"),
            temperature=0,
        )

    prompt = (
        "从下面的文本中抽取实体关系三元组。\n"
        "严格输出 JSON 数组，每个元素为 [主语, 关系, 宾语]，不要输出任何解释。\n"
        "关系用简短短语（如「由...负责」「受...约束」「包含」）。\n\n"
        f"文本：\n{text}"
    )
    raw = str(llm.invoke(prompt).content).strip()
    # 容错：剥离 ```json ... ``` 代码围栏
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        if raw.endswith("```"):
            raw = raw[:-3]
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return []
    out: list[tuple[str, str, str]] = []
    for item in data:
        if isinstance(item, (list, tuple)) and len(item) == 3:
            s, r, o = (_clean(str(x)) for x in item)
            if s and r and o:
                out.append((s, r, o))
    return out
