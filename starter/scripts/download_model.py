"""Download the pinned model into the project; verify Hugging Face LFS SHA256."""
import hashlib
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = json.loads((ROOT / "artifacts/strategies.json").read_text(encoding="utf-8"))
MODEL = CONFIG["model"]
REVISION = CONFIG["model_revision"]
DEST = ROOT / ".local/models/multilingual-e5-small"
FILES = {"1_Pooling/config.json", "config.json", "model.safetensors", "modules.json",
         "sentence_bert_config.json", "sentencepiece.bpe.model", "special_tokens_map.json",
         "tokenizer.json", "tokenizer_config.json"}


def main():
    with urllib.request.urlopen(f"https://huggingface.co/api/models/{MODEL}/revision/{REVISION}?blobs=true", timeout=60) as response:
        info = json.load(response)
    assert info["sha"] == REVISION
    DEST.mkdir(parents=True, exist_ok=True)
    def fetch(entry):
        name = entry["rfilename"]
        target = DEST / name
        expected = entry.get("lfs", {}).get("sha256")
        if target.exists() and expected and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".partial")
        digest = hashlib.sha256()
        count = 0
        with urllib.request.urlopen(f"https://huggingface.co/{MODEL}/resolve/{REVISION}/{name}", timeout=120) as response, temporary.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
                digest.update(chunk)
                count += len(chunk)
                if count % (32 * 1024 * 1024) == 0:
                    print(f"{name}: {count // (1024 * 1024)} MiB", flush=True)
        if expected and digest.hexdigest() != expected:
            raise ValueError(f"SHA256 mismatch: {name}")
        temporary.replace(target)
        print(f"Downloaded {name}: {count} bytes", flush=True)
    entries = [entry for entry in info["siblings"] if entry["rfilename"] in FILES]
    if {e["rfilename"] for e in entries} != FILES:
        raise ValueError("Model repository missing expected files")
    with ThreadPoolExecutor(max_workers=3) as executor:
        list(executor.map(fetch, entries))
    (DEST / "download_info.json").write_text(json.dumps({"model": MODEL, "revision": REVISION}, indent=2), encoding="utf-8")
    print(f"Model ready: {DEST}", flush=True)


if __name__ == "__main__":
    main()
