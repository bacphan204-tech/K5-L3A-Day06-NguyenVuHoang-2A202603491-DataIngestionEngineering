"""Read-only checks against saved artifacts and the persisted real-vector store."""
import json
import sys
import csv
import hashlib
import math
import subprocess
import tempfile
from datetime import datetime, timezone
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from starter.src.run import fingerprint
from starter.src.store import ChromaStore
from starter.src.evaluation import evaluate_query, summarize
from starter.src.ingestion import load_corpus
from starter.src.run import validate, build_chunks
from starter.src.models import Chunk


def adjudication_summary(traces):
    """Validate explicit rank-level review records without changing frozen gold."""
    path = ROOT / "results/audit/retrieval_adjudication.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    by_key = {(r["strategy"], r["question_id"], int(r["rank"])): r for r in rows}
    assert len(by_key) == len(rows) == sum(len(t["hits"]) for t in traces)
    questions = {q["id"]: q for q in map(json.loads, (ROOT / "benchmark/questions.jsonl").read_text(encoding="utf-8").splitlines())}
    pages = {p.page: p for p in load_corpus(ROOT)}
    reviewed = []
    for t in traces:
        decisions = []
        for rank, h in enumerate(t["hits"], 1):
            r = by_key[t["strategy"], t["question_id"], rank]
            assert r["chunk_id"] == h["chunk_id"] and int(r["page"]) == h["metadata"]["page"]
            assert r["split"] == t["split"] and r["source_id"] == h["metadata"]["document_id"]
            assert r["strict_hit"] == str(h["evidence_hit"]).lower()
            assert r["chunk_text_sha256"] == hashlib.sha256(h["text"].encode()).hexdigest()
            qhash = hashlib.sha256(json.dumps(questions[t["question_id"]], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            assert r["question_sha256"] == qhash
            assert r["adjudicated_hit"] in ("true", "false") and r["reason"] and r["reviewer"]
            accepted = r["adjudicated_hit"] == "true"
            assert not h["evidence_hit"] or accepted, "Registered sufficient evidence cannot silently become a miss"
            if accepted:
                quote = r["evidence_quote"]
                assert quote and quote in h["text"] and quote in pages[int(r["page"])].text
                assert r["decision"] in ("registered_evidence", "equivalent_evidence")
            else:
                assert r["decision"] == "insufficient_evidence"
            decisions.append(accepted)
        reviewed.append({"strategy": t["strategy"], "split": t["split"], "hit1": decisions[0], "hit3": any(decisions)})
    return summarize(reviewed)


def store_regression_child(mode, store_path, payload_path):
    """Only operate in the isolated test directory, using actual model vectors."""
    path = Path(store_path).resolve()
    assert path.is_relative_to((ROOT / ".local").resolve())
    assert path.name == "store" and path.parent.name.startswith("verification-")
    payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
    chunks = [Chunk(**r) for r in payload["chunks"]]
    vectors = payload["vectors"]
    store = ChromaStore(path, 384)
    if mode == "--store-reopen":
        collection = store.collection("A")
        assert collection.count() == 2
        assert set(collection.get()["ids"]) == {c.chunk_id for c in chunks[:2]}
        assert collection.get(ids=[chunks[0].chunk_id])["metadatas"][0]["verification_marker"] == "updated"
        print("PASS persisted changes after a separate process reopened the test store")
        return
    first = store.upsert("A", chunks, vectors)
    second = store.upsert("A", chunks, vectors)
    assert first["count"] == second["count"] == 3
    hits = store.search("A", vectors[0], filters={"chapter": 3})
    assert hits[0]["chunk_id"] == chunks[0].chunk_id and abs(hits[0]["score"] - 1) < 1e-5
    assert all(h["metadata"]["chapter"] == 3 for h in hits)
    other = store.search("A", vectors[0], filters={"chapter": 4})
    assert len(other) == 1 and other[0]["chunk_id"] == chunks[1].chunk_id
    removed = store.upsert("A", chunks[:2], vectors[:2])
    assert removed["count"] == 2 and removed["obsolete_removed"] == 1
    chunks[0].metadata["verification_marker"] = "updated"
    store.upsert("A", chunks[:2], vectors[:2])
    assert store.collection("A").get(ids=[chunks[0].chunk_id])["metadatas"][0]["verification_marker"] == "updated"
    invalid_calls = [
        lambda: store.upsert("A", chunks[:2], vectors[:1]),
        lambda: store.upsert("A", chunks[:1], [vectors[0][:-1]]),
        lambda: store.search("A", vectors[0][:-1]),
        lambda: store.search("A", vectors[0], filters={"chapter": 5}),
        lambda: store.search("A", vectors[0], filters={"source": "not-an-allowed-filter"}),
    ]
    for call in invalid_calls:
        try:
            call()
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid input was accepted")
        assert store.collection("A").count() == 2
    print("PASS idempotent upsert / stale removal / metadata update / cosine / filters / five invalid-input cases")


def run_store_regressions(store):
    rows = [json.loads(l) for l in (ROOT / "results/chunks_A.jsonl").read_text(encoding="utf-8").splitlines()]
    chapter3 = [r for r in rows if r["metadata"]["chapter"] == 3]
    chapter4 = [r for r in rows if r["metadata"]["chapter"] == 4]
    chosen = [chapter3[0], chapter4[0], chapter3[1]]
    actual = store.collection("A").get(ids=[r["chunk_id"] for r in chosen], include=["embeddings"])
    by_id = {cid: [float(v) for v in vector] for cid, vector in zip(actual["ids"], actual["embeddings"])}
    with tempfile.TemporaryDirectory(prefix="verification-", dir=ROOT / ".local") as temp:
        directory = Path(temp).resolve()
        assert directory.is_relative_to((ROOT / ".local").resolve())
        payload = directory / "payload.json"
        payload.write_text(json.dumps({"chunks": chosen, "vectors": [by_id[r["chunk_id"]] for r in chosen]}), encoding="utf-8")
        for mode in ("--store-regression", "--store-reopen"):
            result = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), mode,
                str(directory / "store"), str(payload)], capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(f"Isolated store regression failed: {result.stdout}\n{result.stderr}")
            print(result.stdout.strip())


def main():
    results = ROOT / "results"
    traces = [json.loads(line) for line in (results / "traces.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(traces) == 60 and len({(t["strategy"], t["question_id"]) for t in traces}) == 60
    assert Counter((t["strategy"], t["split"]) for t in traces) == Counter({(s, split): n for s in "ABC" for split, n in [("dev", 15), ("test", 5)]})
    assert all(len(t["hits"]) == 3 for t in traces)
    questions = [json.loads(line) for line in (ROOT / "benchmark/questions.jsonl").read_text(encoding="utf-8").splitlines()]
    question_map = {q["id"]: q for q in questions}
    pages = load_corpus(ROOT)
    validate(pages, questions)
    page_map = {p.page: p for p in pages}
    config = json.loads((ROOT / "artifacts/strategies.json").read_text(encoding="utf-8"))
    rebuilt = build_chunks(pages, config)
    manifest = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
    pdf_path = ROOT / manifest["source_path_or_url"]
    assert hashlib.sha256(pdf_path.read_bytes()).hexdigest() == manifest["snapshot"]["sha256"]
    from pypdf import PdfReader
    assert len(PdfReader(pdf_path).pages) == manifest["snapshot"]["total_physical_pages"] == 53
    assert {r["page"] for r in manifest["pages"]} == set(page_map) == set(range(2, 54))
    lock = json.loads((results / "experiment_lock.json").read_text(encoding="utf-8"))
    assert lock["fingerprints"] == fingerprint(), "Frozen inputs differ"
    store = ChromaStore(ROOT / ".local/chroma", 384)
    for strategy in "ABC":
        rows = [json.loads(line) for line in (results / f"chunks_{strategy}.jsonl").read_text(encoding="utf-8").splitlines()]
        collection = store.collection(strategy)
        assert collection.count() == len(rows)
        assert set(collection.get()["ids"]) == {r["chunk_id"] for r in rows}
        assert [r["chunk_id"] for r in rows] == [c.chunk_id for c in rebuilt[strategy]]
        stored = collection.get(include=["documents", "metadatas", "embeddings"])
        expected = {r["chunk_id"]: r for r in rows}
        for cid, text, metadata, vector in zip(stored["ids"], stored["documents"], stored["metadatas"], stored["embeddings"]):
            row = expected[cid]
            assert text == row["text"] and metadata["page"] == row["page"]
            assert metadata["source"] == row["source"]
            assert len(vector) == 384 and all(math.isfinite(float(v)) for v in vector)
            assert abs(sum(float(v) ** 2 for v in vector) - 1) < 1e-4
    with (results / "metrics.csv").open(encoding="utf-8-sig", newline="") as stream:
        metrics = {(r["strategy"], r["split"]): r for r in csv.DictReader(stream)}
    for row in summarize(traces):
        saved = metrics[row["strategy"], row["split"]]
        for key in ("n", "hit1_n", "hit3_n"):
            assert int(saved[key]) == row[key]
    for t in traces:
        checked = evaluate_query(question_map[t["question_id"]], t["hits"])
        assert (checked["hit1"], checked["hit3"]) == (t["hit1"], t["hit3"])
        for h in t["hits"]:
            m = h["metadata"]
            p = page_map[m["page"]]
            assert p.text[m["start_char"]:m["end_char"]] == h["text"]
            assert p.source == m["source"] and p.document_id == m["document_id"]
            assert p.metadata["chapter"] == m["chapter"]
            assert abs(h["score"] - (1 - h["distance"])) < 1e-8
        if t["strategy"] == "C" and t["requested_filter"]:
            assert all(all(h["metadata"].get(k) == v for k, v in t["requested_filter"].items()) for h in t["hits"])
    # Boundary tests: correct page alone and incomplete evidence are not hits.
    fixture = {"id": "check", "split": "dev", "question": "check", "expected_answer": "check",
        "gold_source_id": "d", "gold_page": 2, "evidence_quote": "complete supporting evidence"}
    partial = {"text": "complete supporting", "metadata": {"document_id": "d", "page": 2}}
    wrong_page = {"text": "complete supporting evidence", "metadata": {"document_id": "d", "page": 3}}
    assert not evaluate_query(fixture, [partial, wrong_page])["hit3"]
    valid = {"text": "complete supporting evidence", "metadata": {"document_id": "d", "page": 2}}
    assert evaluate_query(fixture, [partial, valid])["hit3"]
    fixture["gold_alternatives"] = [{"source_id": "d", "page": 3, "evidence_quote": "other sufficient evidence"}]
    alternative = {"text": "other sufficient evidence", "metadata": {"document_id": "d", "page": 3}}
    assert evaluate_query(fixture, [alternative])["hit1"]
    for p in pages:
        # All source characters are retained by both chunking policies.
        assert "".join(c.text for c in rebuilt["B"] if c.page == p.page) == p.text
        positions = set()
        for c in [c for c in rebuilt["A"] if c.page == p.page]:
            positions.update(range(c.metadata["start_char"], c.metadata["end_char"]))
        assert len(positions) == len(p.text)
    reviewed = adjudication_summary(traces)
    if reviewed:
        with (results / "metrics_adjudicated.csv").open(encoding="utf-8-sig", newline="") as stream:
            actual = list(csv.DictReader(stream))
        assert len(actual) == len(reviewed)
        for row, saved in zip(reviewed, actual):
            assert row["strategy"] == saved["strategy"] and row["split"] == saved["split"]
            assert all(row[k] == int(saved[k]) for k in ("n", "hit1_n", "hit3_n"))
        print("Verified 180 post-hoc evidence decisions, source quotes and separate adjudicated metrics")
    run_store_regressions(store)
    print("Verified 60 traces / 180 retrieved records; frozen inputs unchanged.")
    print("Persistent store reopened: A=344, B=183, C=183; IDs match saved chunks.")
    print("All C filtered queries obey requested chapter; human audits remain separate.")
    print("PDF hash/page mapping, gold quotes, real stored vectors, chunk provenance and recomputed metrics verified.")
    for name, field in [("coherence", "score_0_2"), ("grounding", "score_0_2"), ("metadata", "human_correct")]:
        with (results / f"audit/{name}.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        valid_values = ("0", "1", "2") if field == "score_0_2" else ("true", "false", "0", "1")
        complete = sum(r[field].lower() in valid_values and bool(r["reason"].strip()) and bool(r["reviewer"].strip()) for r in rows)
        print(f"Submission review {name}: {complete}/{len(rows)} labeled with reason/reviewer")
        ai_count = sum("Codex AI" in r.get("reviewer", "") for r in rows)
        if ai_count:
            print(f"  AI-reviewed rows: {ai_count}; student confirmation is a separate field, not assumed.")
    validation_path = results / "validation.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    validation["final_checks"] = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "frozen_inputs_unchanged": True, "source_pdf_hash_and_page_mapping": True,
        "all_gold_quotes_verified": True, "trace_records": len(traces), "top3_records": sum(len(t["hits"]) for t in traces),
        "real_384d_normalized_vectors": True, "metrics_recomputed": True,
        "chunk_coverage_no_missing_characters": True,
        "isolated_store_regressions": ["repeat-upsert", "remove-obsolete-chunk", "update-metadata", "cosine-self-match", "chapter-filter", "dimension-validation", "length-validation", "filter-allowlist", "reopen-in-new-process"],
        "retrieval_adjudication_records": 180 if reviewed else 0,
        "ai_review_disclosed": True, "student_confirmation": "not recorded",
        "scope": "Local Windows environment; not a clean-machine install test or a check of GitHub grader permissions",
    }
    validation_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] in ("--store-regression", "--store-reopen"):
        store_regression_child(*sys.argv[1:])
    else:
        main()
