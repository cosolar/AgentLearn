"""smoke_test.py —— 离线自检（无需 API Key，不依赖第三方包）

只检验纯标准库的部分：文档加载、切分、父子块、BM25、RRF、知识图谱、离线检索。
运行：python smoke_test.py
"""

from __future__ import annotations

import sys

from bm25 import BM25, rrf_fuse, tokenize
from chunking import (build_parent_child, children_only, chunk_text,
                      parent_index, split_by_heading)
from config import DEFAULT, load_documents
from graph import build_graph_from_docs, extract_triples_rule
from graph_rag import GraphRAG
from retrieval import HybridRetriever

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"✅ {name}" + (f"  —— {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"❌ {name}  —— {detail}")


def main() -> int:
    docs = load_documents(DEFAULT)
    text = "\n".join(d["text"] for d in docs)

    # ① 文档加载
    check("① 文档加载：data/ 下至少 3 篇文档", len(docs) >= 3,
          f"实际 {len(docs)} 篇")

    # ② 按标题切分
    sections = split_by_heading(docs[0]["text"])
    check("② 标题切分：首篇至少 2 段", len(sections) >= 2,
          f"实际 {len(sections)} 段")

    # ③ 定长切分 + 重叠
    long_text = "甲" * 500
    chunks = chunk_text(long_text, size=220, overlap=40)
    check("③ 定长切分：500 字按 220/40 切出多块", len(chunks) >= 3,
          f"实际 {len(chunks)} 块")
    check("③ 重叠生效：相邻块共享 40 字",
          len(chunks) >= 2 and chunks[0][-40:] == chunks[1][:40])

    # ④ 父子块：每个子块都能找到父块
    all_chunks = []
    for d in docs:
        all_chunks.extend(build_parent_child(d["text"], d["source"]))
    parents = parent_index(all_chunks)
    kids = children_only(all_chunks)
    check("④ 父子块：存在父块与子块", len(parents) > 0 and len(kids) > 0,
          f"父 {len(parents)} / 子 {len(kids)}")
    check("④ 子块 parent_id 均能回溯到父块",
          all(c.parent_id in parents for c in kids))

    # ⑤ BM25 分词
    toks = tokenize("LangGraph 用 StateGraph 描述工作流")
    check("⑤ 分词：英文词 + 中文单字/bigram",
          "langgraph" in toks and "工作" in toks)

    # ⑥ BM25 检索命中
    bm = BM25().fit([{"source": c.chunk_id, "text": c.text} for c in kids])
    hits = bm.search("数据合规政策 由谁制定", k=5)
    hit_ids = [doc["source"] for _s, doc in hits]
    hit_sources = {next(c.source for c in kids if c.chunk_id == cid) for cid in hit_ids}
    check("⑥ BM25：命中 02-合规政策.md",
          "02-合规政策.md" in hit_sources, f"命中来源 {sorted(hit_sources)}")

    # ⑦ RRF 融合
    fused = rrf_fuse([["a", "b", "c"], ["c", "a", "d"]])
    check("⑦ RRF：融合两路且 c/a 得分靠前",
          fused[0][0] in ("a", "c") and len(fused) == 4,
          f"融合结果 {[i for i, _ in fused]}")

    # ⑧ 规则三元组抽取
    triples = extract_triples_rule("Atlas 受《数据合规政策》约束。")
    check("⑧ 三元组抽取：得到 (Atlas, 受...约束, 数据合规政策)",
          any(t[0] == "Atlas" and t[2] == "数据合规政策" for t in triples),
          f"实际 {triples}")

    # ⑨ 图谱多跳
    graph = build_graph_from_docs(docs)
    related = graph.multi_hop("Atlas", hops=2)
    check("⑨ 图谱 2 跳：从 Atlas 可达 法务部 / 集团信息安全总纲",
          "法务部" in related and "集团信息安全总纲" in related,
          f"实际 {related}")

    # ⑩ 图谱最短路径
    path = graph.path("Atlas", "法务部")
    check("⑩ 图谱路径：Atlas → 法务部 存在路径",
          len(path) >= 1, f"路径 {path}")

    # ⑪ 离线混合检索（无向量库，退化为 BM25）
    retriever = HybridRetriever.from_disk(DEFAULT, vectorstore=None)
    result = retriever.search("Atlas 由谁负责")
    check("⑪ 离线检索：返回非空结果并带来源",
          len(result) > 0 and all(h.source for h in result),
          f"命中 {[h.source for h in result]}")

    # ⑫ 父块回溯：返回的文本来自父块集合（而非子块）
    parent_texts = {c.text for c in parents.values()}
    check("⑫ 父块回溯：结果文本来自父块集合",
          len(result) > 0 and all(h.text in parent_texts for h in result))

    # ---------- GraphRAG 完整链路（离线部分）----------
    rag = GraphRAG()
    ents = rag.find_entities("Atlas 受什么约束，由谁制定？")
    check("⑬ GraphRAG：从问题中识别出实体 Atlas", "Atlas" in ents,
          f"实际 {ents}")

    expanded = rag.expand(["Atlas"], hops=2)
    check("⑭ GraphRAG：2 跳扩展可达 法务部", "法务部" in expanded,
          f"实际 {expanded}")

    ctx = rag.collect_context(expanded)
    check("⑮ GraphRAG：取证片段带来源标注",
          "[01-公司与产品.md]" in ctx or "[02-合规政策.md]" in ctx)

    desc = rag.describe("Atlas")
    check("⑯ GraphRAG：子图描述含关系边", "Atlas" in desc and "--" in desc)

    print("-" * 60)
    print(f"通过 {PASS}/{PASS + FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
