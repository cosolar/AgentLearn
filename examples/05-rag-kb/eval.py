"""eval.py —— RAG 检索质量离线评测（无需 API Key）

对应 docs/05-RAG系统/06-RAG评估.md：
    用「黄金集（golden set）」把检索质量**程序化**地量化出来，
    而不是凭感觉说"好像检索得不错"。

核心指标（全部可离线计算）：
    - Hit@k            命中率：期望来源是否出现在前 k 条
    - MRR              平均倒数排名：首个正确结果排得越前越好
    - Source Recall    来源召回：期望来源被覆盖的比例
    - Keyword Coverage 关键词覆盖：期望关键词出现在检索上下文中的比例

生成侧指标（Faithfulness 等）需要 LLM 判定，见本文件的 judge_faithfulness_llm，
属于"补充手段"——教程主张**程序化判定优先**。

⚠️ 本示例语料只有 3 篇，指标接近满分是正常的：它验证的是**流水线正确**，
   而非**检索能力上限**。把 data/ 换成你的真实语料，数字才会有信息量。

运行：python eval.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from config import DEFAULT
from retrieval import HybridRetriever


@dataclass
class Case:
    question: str
    sources: list[str]        # 期望命中的来源文件
    keywords: list[str]       # 期望出现在检索上下文里的关键词


# ---- 黄金集：来自 data/ 的三篇示例文档 ----
GOLDEN: list[Case] = [
    Case("Atlas 产品由哪个区负责？", ["01-公司与产品.md"], ["华东区"]),
    Case("Borealis 由谁负责？", ["01-公司与产品.md"], ["华南区"]),
    Case("Atlas 包含哪些模块？", ["01-公司与产品.md"], ["数据目录", "血缘"]),
    Case("《数据合规政策》由谁制定？", ["02-合规政策.md"], ["法务部"]),
    Case("数据保留期限是多久？", ["02-合规政策.md"], ["24"]),
    Case("《数据合规政策》受什么约束？", ["02-合规政策.md"], ["集团信息安全总纲"]),
    Case("Chroma 需要手动调用 persist 吗？", ["03-技术栈.md"], ["自动持久化"]),
    Case("混合检索由哪两种检索组成？", ["03-技术栈.md"], ["BM25", "向量"]),
    Case("命中子块后要做什么？", ["03-技术栈.md"], ["父块"]),
    # ---- 多跳难题：单次向量/BM25 检索天然吃力，用于演示「评估暴露边界」----
    Case("既受《数据合规政策》约束、又由华东区负责的是哪个产品？",
         ["01-公司与产品.md", "02-合规政策.md"], ["Atlas"]),
]


@dataclass
class Result:
    case: Case
    hit: bool                 # 期望来源是否进入前 k
    rank: int | None          # 首个正确结果的排名（1-based）
    source_recall: float
    keyword_coverage: float


def evaluate_case(retriever: HybridRetriever, case: Case, k: int) -> Result:
    hits = retriever.search(case.question, k=k)
    sources = [h.source for h in hits]
    context = "\n".join(h.text for h in hits)

    rank = next((i + 1 for i, s in enumerate(sources) if s in case.sources), None)
    hit = rank is not None

    found_sources = {s for s in sources if s in case.sources}
    source_recall = len(found_sources) / len(case.sources) if case.sources else 0.0

    hit_keywords = sum(1 for kw in case.keywords if kw in context)
    keyword_coverage = hit_keywords / len(case.keywords) if case.keywords else 0.0

    return Result(case, hit, rank, source_recall, keyword_coverage)


def summarize(results: list[Result]) -> dict:
    n = len(results)
    hit_rate = sum(r.hit for r in results) / n
    mrr = sum((1.0 / r.rank) if r.rank else 0.0 for r in results) / n
    recall = sum(r.source_recall for r in results) / n
    coverage = sum(r.keyword_coverage for r in results) / n
    return {"hit@k": hit_rate, "mrr": mrr,
            "source_recall": recall, "keyword_coverage": coverage}


def judge_faithfulness_llm(question: str, context: str, answer: str) -> float:
    """用 LLM 判定"答案是否忠于检索上下文"，返回 0–1 分。

    ⚠️ 需要 API Key，且**只应作为补充**：LLM-judge 有偏差、不可复现、有成本。
    能程序化判定的（来源命中、关键词覆盖）就不要交给 LLM。
    """
    import os

    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=os.getenv("LLM_MODEL_NAME", "gpt-5.5"),
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
        temperature=0,
    )
    prompt = (
        "请判断「回答」是否完全基于「上下文」，不得引入上下文之外的信息。\n"
        "只输出一个 0 到 1 之间的小数（1=完全忠于上下文，0=大量编造）。\n\n"
        f"【问题】{question}\n【上下文】{context}\n【回答】{answer}\n"
    )
    raw = llm.invoke(prompt).content
    try:
        return max(0.0, min(1.0, float(str(raw).strip())))
    except ValueError:
        return 0.0


def main() -> int:
    k = DEFAULT.top_k
    retriever = HybridRetriever.from_disk(DEFAULT, vectorstore=None)   # 离线：纯 BM25

    results = [evaluate_case(retriever, c, k) for c in GOLDEN]

    print(f"RAG 检索评测（离线 BM25 通道，k={k}）")
    print("=" * 78)
    print(f"{'#':>2}  {'问题':<26} {'命中':<4} {'排名':<4} {'来源召回':<8} {'关键词':<6}")
    print("-" * 78)
    for i, r in enumerate(results, 1):
        q = r.case.question[:24] + ("…" if len(r.case.question) > 24 else "")
        print(f"{i:>2}  {q:<26} {'✅' if r.hit else '❌':<4} "
              f"{str(r.rank or '-'):<4} {r.source_recall:<8.2f} {r.keyword_coverage:<6.2f}")

    s = summarize(results)
    print("-" * 78)
    print(f"Hit@{k} = {s['hit@k']:.2%}   MRR = {s['mrr']:.3f}   "
          f"Source Recall = {s['source_recall']:.2%}   "
          f"Keyword Coverage = {s['keyword_coverage']:.2%}")

    # 打印失败样例，便于定位（教程强调：记录失败原因比只记通过率更有价值）
    fails = [r for r in results if not r.hit]
    if fails:
        print("\n未命中样例（用于归因）：")
        for r in fails:
            print(f"  - {r.case.question}  →  期望来源 {r.case.sources}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
