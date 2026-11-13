"""Strict evidence retrieval metrics and explicit, reviewable traces."""
import re
from collections import defaultdict


def flat(text):
    return re.sub(r"\s+", " ", text).strip()


def evaluate_query(question, hits):
    golds = [{"source_id": question["gold_source_id"], "page": question["gold_page"],
              "evidence_quote": question["evidence_quote"]}, *question.get("gold_alternatives", [])]
    for hit in hits:
        hit["evidence_hit"] = any(
            hit["metadata"]["document_id"] == g["source_id"]
            and hit["metadata"]["page"] == g["page"]
            and flat(g["evidence_quote"]) in flat(hit["text"]) for g in golds)
    return {"question_id": question["id"], "split": question["split"],
            "question": question["question"], "expected_answer": question["expected_answer"],
            "requested_filter": question.get("filter", {}), "golds": golds,
            "hits": hits, "hit1": bool(hits and hits[0]["evidence_hit"]),
            "hit3": any(h["evidence_hit"] for h in hits)}


def summarize(traces):
    groups = defaultdict(list)
    for trace in traces:
        groups[trace["strategy"], trace["split"]].append(trace)
    return [{"strategy": strategy, "split": split, "n": len(rows),
             "hit1_n": sum(t["hit1"] for t in rows), "hit3_n": sum(t["hit3"] for t in rows),
             "hit1": sum(t["hit1"] for t in rows) / len(rows),
             "hit3": sum(t["hit3"] for t in rows) / len(rows)}
            for (strategy, split), rows in sorted(groups.items())]
