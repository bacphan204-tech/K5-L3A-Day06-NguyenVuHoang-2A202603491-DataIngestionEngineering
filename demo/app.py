"""Local, read-only retrieval and ingestion-pipeline demo."""
import json
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from starter.src.embeddings import MyEmbedder
from starter.src.store import ChromaStore
from starter.src.ingestion import load_corpus

CONFIG = json.loads((ROOT / "artifacts/strategies.json").read_text(encoding="utf-8"))
MODEL = None
STORE = None
ENCODE_LOCK = threading.Lock()
COUNTS = {}
PAGE_LOCK = threading.Lock()
PDF_READER = None


def page_pipeline(number):
    global PDF_READER
    if number not in range(2, 54):
        raise ValueError("Chọn trang PDF nội dung từ 2 đến 53. Trang 1 là bản quyền.")
    with PAGE_LOCK:
        if PDF_READER is None:
            from pypdf import PdfReader
            PDF_READER = PdfReader(ROOT / "data/raw/economics-chapters-3-4.pdf")
        raw_text = PDF_READER.pages[number - 1].extract_text() or ""
    prepared = next(json.loads(line) for line in (ROOT / "data/processed/pages.jsonl").read_text(encoding="utf-8").splitlines() if json.loads(line)["page"] == number)
    page = next(p for p in load_corpus(ROOT) if p.page == number)
    chunks = {}
    for strategy in ("A", "B"):
        chunks[strategy] = [r for r in map(json.loads, (ROOT / f"results/chunks_{strategy}.jsonl").read_text(encoding="utf-8").splitlines()) if r["page"] == number]
    example = chunks["B"][0]
    stored = STORE.client.get_collection("economics_b", embedding_function=None).get(ids=[example["chunk_id"]], include=["embeddings"])
    vector = [float(x) for x in stored["embeddings"][0]]
    return {"page": number, "printed_page": prepared["printed_page"], "chapter": prepared["chapter"],
        "raw_text": raw_text, "prepared_text": prepared["text"], "normalized_text": page.text,
        "stats": {"raw_chars": len(raw_text), "prepared_chars": len(prepared["text"]), "normalized_chars": len(page.text),
                  "raw_linebreaks": raw_text.count("\n"), "normalized_linebreaks": page.text.count("\n")},
        "chunks": chunks, "vector": {"chunk_id": example["chunk_id"], "strategy": "B", "dimensions": len(vector),
            "preview": vector[:12], "l2_norm": sum(x*x for x in vector)**0.5,
            "model": CONFIG["model"], "revision": CONFIG["model_revision"]},
        "collections": COUNTS, "pdf_url": f"/source.pdf#page={number}"}


class Handler(BaseHTTPRequestHandler):
    def send_bytes(self, data, content_type, code=200):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, value, code=200):
        self.send_bytes(json.dumps(value, ensure_ascii=False).encode(), "application/json; charset=utf-8", code)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/":
            self.send_bytes((Path(__file__).parent / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/info":
            self.send_json({"model": CONFIG["model"], "dimensions": MODEL.dimensions, "counts": COUNTS})
        elif path == "/api/page":
            try:
                number = int(parse_qs(urlsplit(self.path).query).get("page", ["36"])[0])
                self.send_json(page_pipeline(number))
            except (ValueError, StopIteration) as exc:
                self.send_json({"error": str(exc)}, 400)
            except Exception as exc:
                self.send_json({"error": f"{type(exc).__name__}: {exc}"}, 500)
        elif path == "/source.pdf":
            self.send_bytes((ROOT / "data/raw/economics-chapters-3-4.pdf").read_bytes(), "application/pdf")
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        if self.path != "/api/search":
            return self.send_json({"error": "Not found"}, 404)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16000:
                raise ValueError("Yêu cầu không hợp lệ hoặc quá dài.")
            data = json.loads(self.rfile.read(length))
            question = str(data.get("question", "")).strip()
            selected = data.get("strategies", ["B", "C"])
            chapter = data.get("chapter")
            if not question or len(question) > 2000:
                raise ValueError("Nhập câu hỏi từ 1 đến 2000 ký tự.")
            if not isinstance(selected, list) or not selected or len(selected) > 3 or any(s not in ("A", "B", "C") for s in selected):
                raise ValueError("Chọn ít nhất một cấu hình A/B/C.")
            if chapter not in (None, 3, 4):
                raise ValueError("Chỉ có chương 3 hoặc 4.")
            selected = [s for s in "ABC" if s in selected]
            start = time.perf_counter()
            with ENCODE_LOCK:
                vector = MODEL.embed_query(question)
            embedding_ms = (time.perf_counter() - start) * 1000
            def search(strategy):
                filters = {"chapter": chapter} if strategy == "C" and chapter else None
                begin = time.perf_counter()
                hits = STORE.search(strategy, vector, filters=filters)
                return strategy, {"hits": hits, "filter": filters or {}, "search_ms": (time.perf_counter() - begin) * 1000}
            with ThreadPoolExecutor(max_workers=len(selected)) as pool:
                results = dict(pool.map(search, selected))
            self.send_json({"question": question, "embedding_ms": embedding_ms,
                "total_ms": (time.perf_counter() - start) * 1000,
                "results": results, "mode": "live retrieval; one shared query embedding; parallel vector searches"})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, 400)
        except Exception as exc:
            self.send_json({"error": f"{type(exc).__name__}: {exc}"}, 500)


class LocalDemoServer(ThreadingHTTPServer):
    allow_reuse_address = False


def main():
    global MODEL, STORE, COUNTS
    if not (ROOT / ".local/chroma/chroma.sqlite3").exists():
        raise RuntimeError("Chưa có database. Chạy run_all.ps1 trước khi demo.")
    print("Loading the real local embedding model once...", flush=True)
    MODEL = MyEmbedder(CONFIG["model"], CONFIG["model_revision"])
    STORE = ChromaStore(ROOT / ".local/chroma", MODEL.dimensions)
    for strategy in "ABC":
        collection = STORE.client.get_collection("economics_" + strategy.lower(), embedding_function=None)
        COUNTS[strategy] = collection.count()
        if not COUNTS[strategy]:
            raise RuntimeError(f"Collection {strategy} is empty")
    server = LocalDemoServer(("127.0.0.1", 8765), Handler)
    server.daemon_threads = True
    print("DEMO READY: http://127.0.0.1:8765 (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
