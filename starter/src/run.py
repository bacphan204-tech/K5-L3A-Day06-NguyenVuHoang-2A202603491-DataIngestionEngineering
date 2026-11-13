"""Reproducible local experiment. Run from root: python -m starter.src.run --stage all."""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import statistics
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .chunking import by_paragraph, fixed_size
from .evaluation import evaluate_query, flat, summarize
from .ingestion import load_corpus

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
CONFIG_PATH = ROOT / "artifacts/strategies.json"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fingerprint():
    files = [CONFIG_PATH, ROOT / "benchmark/questions.jsonl", ROOT / "data/processed/pages.jsonl"]
    files += sorted((ROOT / "starter/src").glob("*.py"))
    # Git may convert CRLF/LF at checkout; hash text content consistently.
    # POSIX-style relative keys also avoid Windows/Linux path separator differences.
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(
        p.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    ).hexdigest() for p in files}


def validate(pages, questions):
    by_page = {p.page: p for p in pages}
    assert len(by_page) == len(pages) >= 30
    assert len({q["id"] for q in questions}) == len(questions) >= 20
    assert sum(q["split"] == "dev" for q in questions) >= 15
    assert sum(q["split"] == "test" for q in questions) >= 5
    assert sum(bool(q["filter"]) for q in questions) >= 3
    assert any(q["filter"] for q in questions if q["split"] == "test")
    for q in questions:
        assert q["split"] in ("dev", "test")
        p = by_page[q["gold_page"]]
        assert p.document_id == q["gold_source_id"]
        assert flat(q["evidence_quote"]) in flat(p.text), q["id"]
        assert all(p.metadata[k] == v for k, v in q["filter"].items()), q["id"]
        for g in q.get("gold_alternatives", []):
            p = by_page[g["page"]]
            assert p.document_id == g["source_id"] and flat(g["evidence_quote"]) in flat(p.text)
    print(f"Validated: {len(pages)} selected pages; {len(questions)} questions; all gold quotes exist.", flush=True)


def build_chunks(pages, config):
    chunks = {}
    a, b = config["strategies"]["A"], config["strategies"]["B"]
    chunks["A"] = [c for p in pages for c in fixed_size(p, a["size"], a["overlap"])]
    chunks["B"] = [c for p in pages for c in by_paragraph(p, b["size"])]
    chunks["C"] = chunks["B"]
    return chunks


def generate_audit(traces, chunks, pages):
    """Keep human labels blank; never infer coherence/grounding from retrieval score."""
    audit = RESULTS / "audit"
    audit.mkdir(exist_ok=True)
    # Midpoint in first 10 sorted source pages: fixed before retrieval scores.
    coherence = []
    for strategy, rows in chunks.items():
        for page in sorted(pages, key=lambda p: p.page)[:10]:
            position = len(page.text) // 2
            covering = [c for c in rows if c.page == page.page and c.metadata["start_char"] <= position < c.metadata["end_char"]]
            for c in covering:
                coherence.append({"strategy": strategy, "page": page.page, "position": position,
                    "chunk_id": c.chunk_id, "source_text": page.text, "chunk_text": c.text,
                    "score_0_2": "", "reason": "", "reviewer": ""})
    grounding, metadata = [], []
    by_page = {p.page: p for p in pages}
    for t in traces:
        if t["split"] != "test":
            continue
        grounding.append({"strategy": t["strategy"], "question_id": t["question_id"],
            "question": t["question"], "expected_answer": t["expected_answer"],
            "top3": json.dumps(t["hits"], ensure_ascii=False),
            "score_0_2": "", "reason": "", "reviewer": ""})
        for rank, hit in enumerate(t["hits"], 1):
            m = hit["metadata"]
            p = by_page.get(m["page"])
            machine_ok = bool(p and p.source == m["source"] and p.document_id == m["document_id"]
                and p.metadata["chapter"] == m["chapter"]
                and p.text[m["start_char"]:m["end_char"]] == hit["text"])
            metadata.append({"strategy": t["strategy"], "question_id": t["question_id"], "rank": rank,
                "chunk_id": hit["chunk_id"], "metadata": json.dumps(m, ensure_ascii=False),
                "automatic_consistency_check": machine_ok,
                "human_correct": "", "reason": "", "reviewer": ""})
    # Do not overwrite work already labeled by a person.
    for name, rows in [("coherence", coherence), ("grounding", grounding), ("metadata", metadata)]:
        path = audit / f"{name}.csv"
        if not path.exists():
            write_csv(path, rows)
    write_json(audit / "sampling.json", {
        "coherence": "All covering chunks at midpoint of first 10 sorted selected PDF pages; report mean within position, then mean over 10 positions.",
        "grounding": "All five fixed test questions for every strategy, top-3 union evidence.",
        "metadata": "All five fixed test questions x top-3 x three strategies.",
        "human_review_status": "pending; automatic consistency does not replace checking PDF source",
    })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["validate", "ingest", "dev", "freeze", "test", "all", "ask"], default="validate")
    parser.add_argument("--question")
    parser.add_argument("--chapter", type=int, choices=[3, 4])
    parser.add_argument("--strategy", choices=["A", "B", "C"], default="C")
    args = parser.parse_args()
    RESULTS.mkdir(exist_ok=True)
    pages = load_corpus(ROOT)
    questions = read_jsonl(ROOT / "benchmark/questions.jsonl")
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    validate(pages, questions)
    chunks = build_chunks(pages, config)
    write_json(RESULTS / "validation.json", {"selected_pages": len(pages), "questions": len(questions),
        "evidence_quotes_verified": True, "human_corpus_review": "pending"})
    if args.stage == "validate":
        for s, rows in chunks.items():
            print(f"{s}: {len(rows)} chunks")
        return
    lock_path = RESULTS / "experiment_lock.json"
    if lock_path.exists():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        if lock["fingerprints"] != fingerprint():
            raise RuntimeError("Frozen experiment inputs changed. Preserve old results and explicitly start a new experiment; do not reuse test as holdout.")
    from .embeddings import MyEmbedder
    from .store import ChromaStore
    embedder = MyEmbedder(config["model"], config.get("model_revision"))
    store = ChromaStore(ROOT / ".local/chroma", embedder.dimensions)
    env = {"python": platform.python_version(), "model": embedder.model_name,
        "model_revision": embedder.revision, "dimensions": embedder.dimensions,
        "prefixes": {"query": "query: ", "document": "passage: "},
        "normalize_embeddings": True, "device": "cpu", "metric": "cosine",
        "search": "Chroma HNSW approximate; backend defaults", "api_cost_usd": 0,
        "cost_note": "Local execution; hardware/electricity/network costs not measured",
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "packages": {p: importlib.metadata.version(p) for p in ["sentence-transformers", "transformers", "torch", "chromadb", "pypdf"]}}
    write_json(RESULTS / "environment.json", env)
    if args.stage in ("ingest", "all"):
        stats, vectors_by_strategy = [], {}
        for strategy, rows in chunks.items():
            start = time.perf_counter()
            tokens = embedder.token_lengths([c.text for c in rows], "passage: ")
            if strategy == "C":
                vectors = vectors_by_strategy["B"]
            else:
                vectors = embedder.embed_documents([c.text for c in rows])
            vectors_by_strategy[strategy] = vectors
            first = store.upsert(strategy, rows, vectors)
            seconds = time.perf_counter() - start
            second = store.upsert(strategy, rows, vectors)
            assert first["count"] == second["count"] == len(rows)
            write_jsonl(RESULTS / f"chunks_{strategy}.jsonl", [asdict(c) for c in rows])
            lengths = [len(c.text) for c in rows]
            stats.append({"strategy": strategy, "chunk_count": len(rows), "min_chars": min(lengths),
                "mean_chars": statistics.mean(lengths), "max_chars": max(lengths),
                "total_chars": sum(lengths), "total_tokens_including_prefix": sum(tokens),
                "max_tokens": max(tokens), "ingest_seconds": seconds, "api_cost_usd": 0,
                "embeddings_reused_from_B": strategy == "C", "reingest_count": second["count"],
                "obsolete_removed": first["obsolete_removed"]})
            print(f"Ingested {strategy}: {len(rows)} chunks, {seconds:.2f}s; repeat count unchanged", flush=True)
        write_csv(RESULTS / "ingestion_stats.csv", stats)
        if args.stage == "ingest":
            return
    if args.stage == "ask":
        if not args.question:
            parser.error("--question is required")
        filters = {"chapter": args.chapter} if args.chapter and args.strategy == "C" else None
        hits = store.search(args.strategy, embedder.embed_query(args.question), filters=filters)
        print(json.dumps(hits, ensure_ascii=False, indent=2))
        return
    traces = []
    trace_path = RESULTS / "traces.jsonl"
    if trace_path.exists():
        traces = read_jsonl(trace_path)
    def run_split(split):
        nonlocal traces
        traces = [t for t in traces if t["split"] != split]
        for q in questions:
            if q["split"] != split:
                continue
            query_vector = embedder.embed_query(q["question"])
            for strategy in ("A", "B", "C"):
                start = time.perf_counter()
                filters = q["filter"] if strategy == "C" else None
                hits = store.search(strategy, query_vector, filters=filters)
                t = evaluate_query(q, hits)
                t.update(strategy=strategy, applied_filter=filters or {},
                         search_seconds=time.perf_counter() - start)
                traces.append(t)
        write_jsonl(trace_path, traces)
        write_csv(RESULTS / "metrics.csv", summarize(traces))
        print(f"Saved {split} traces and strict evidence metrics", flush=True)
    if args.stage in ("dev", "all"):
        run_split("dev")
    if args.stage in ("freeze", "all"):
        dev = [r for r in summarize(traces) if r["split"] == "dev"]
        if len(dev) != 3:
            raise RuntimeError("Run all three strategies on dev before freezing")
        # Rule fixed in strategies.json before retrieval; test is not read here.
        selected = sorted(dev, key=lambda r: (-r["hit3"], -r["hit1"], len(chunks[r["strategy"]]), r["strategy"]))[0]["strategy"]
        lock = {"fingerprints": fingerprint(), "selected_on_dev": selected,
            "selection_rule": config["selection_rule"], "model_revision": embedder.revision,
            "frozen_at_utc": datetime.now(timezone.utc).isoformat()}
        if not lock_path.exists():
            write_json(lock_path, lock)
        print(f"Frozen; selected on dev: {selected}", flush=True)
    if args.stage in ("test", "all"):
        if not lock_path.exists():
            raise RuntimeError("Freeze configurations on dev before test")
        run_split("test")
        generate_audit(traces, chunks, pages)
    for row in summarize(traces):
        print(f"{row['strategy']} {row['split']}: Hit@1 {row['hit1_n']}/{row['n']}; strict Evidence Hit@3 {row['hit3_n']}/{row['n']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        RESULTS.mkdir(exist_ok=True)
        with (RESULTS / "run_errors.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(),
                "type": type(exc).__name__, "error": str(exc)}, ensure_ascii=False) + "\n")
        raise
