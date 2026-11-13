# Data Ingestion Engineering — Bài cá nhân

Pipeline Python đọc tài liệu, chuẩn hóa, chia chunk, tạo embedding đa ngữ và truy xuất bằng Chroma persistent. Tài liệu tiếng Anh; benchmark gồm 20 câu tiếng Việt, chia cố định 15 dev / 5 test, 4 câu có filter chương (1 câu test).

## Dữ liệu và cấu hình

- `data/raw/economics-chapters-3-4.pdf`: 53 trang, gồm 1 trang bản quyền và 52 trang nội dung được chọn từ chương 3–4 của *Principles of Economics 3e*, OpenStax.
- `data/manifest.json`: nguồn, giấy phép, hash, số trang/ký tự và cách tính trang. Mapping trang gốc: `data/excerpt_page_map.csv`.
- Embedding: `intfloat/multilingual-e5-small`, 384 chiều, revision cố định trong `artifacts/strategies.json`; prefix `query: ` / `passage: `, chuẩn hóa L2, CPU.
- Store: Chroma local persistent, cosine, HNSW approximate, lưu ở `.local/chroma`.
- A: 500 ký tự, overlap 50. B: ưu tiên ranh giới câu, tối đa 1000 ký tự, overlap 0. C: cùng chunk/vector B, thêm filter `chapter` khi câu hỏi cung cấp.
- A–B so sánh toàn bộ chính sách chunking; B–C chỉ thay filter. Chi phí API 0 USD; chưa đo điện/phần cứng.

## Cài và chạy (PowerShell từ thư mục gốc)

Máy hiện tại đã cài môi trường/model. Chạy lại toàn bộ:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\starter\scripts\run_all.ps1
```

Máy mới dùng cùng lệnh và thêm `-Install` ở cuối. Cần Python (đã kiểm tra trên Windows, Python 3.14.6) và mạng lần đầu để tải thư viện/model. `Bypass` chỉ áp dụng tiến trình này, không đổi chính sách toàn máy. Không cần Docker hay API key.

Hoặc cài thủ công:

```powershell
python -m venv starter\.venv
.\starter\.venv\Scripts\python.exe -m pip install -r .\starter\requirements.txt
.\starter\.venv\Scripts\python.exe .\starter\scripts\download_model.py
```

Script tổng hợp trích xuất → kiểm chứng gold → ingest A/B/C → kiểm tra nạp lại không trùng → dev → khóa cấu hình → test → tạo báo cáo → kiểm tra kết quả/store.

```powershell
.\starter\.venv\Scripts\python.exe -m starter.src.run --stage validate
.\starter\.venv\Scripts\python.exe -m starter.src.run --stage all
.\starter\.venv\Scripts\python.exe .\starter\scripts\build_report.py
```

Khóa trong `results/experiment_lock.json` ngăn thay code/corpus/benchmark/config sau khi xem test. Không tinh chỉnh theo test rồi báo kết quả như holdout độc lập. HNSW có thể có biến động nhỏ; số đo thời gian phụ thuộc tải máy.

## Hỏi thử bằng tiếng Việt

### Giao diện demo local

Sau khi cài môi trường và chạy pipeline, mở giao diện:

```powershell
.\starter\.venv\Scripts\python.exe -B .\demo\app.py
```

Đợi `DEMO READY`, truy cập **http://127.0.0.1:8765**. Chọn A/B/C riêng lẻ hoặc AB, AC, BC, ABC. Tab pipeline cho xem PDF, text trước/sau chuẩn hóa, chunk, metadata và vector thật đã lưu. Ctrl+C để dừng server; không mở nhiều tiến trình trên cùng cổng.

Phần diễn giải tiếng Việt được biên soạn cho các đoạn demo, không phải câu trả lời do E5 sinh hay bản dịch tự động toàn bộ nguồn. Nguyên văn tiếng Anh có thể mở để kiểm chứng. Kịch bản trình bày: [demo/DEMO.md](demo/DEMO.md). Demo đọc database đã có, không thay cấu hình hay kết quả benchmark.

```powershell
$env:PYTHONIOENCODING = 'utf-8'
.\starter\.venv\Scripts\python.exe -m starter.src.run --stage ask --question "Ai cung ứng lao động?" --chapter 4
```

Trả top-3 đoạn tiếng Anh và metadata nguồn/trang; chưa sinh câu trả lời LLM. `page` là trang PDF rút gọn tính từ 1, `printed_page` là trang in, `original_pdf_page` là trang PDF gốc. Trang bản quyền không index.

## Bài nộp và kết quả

| Thư mục/file | Nội dung |
|---|---|
| `STUDENT.md` | Thông tin học viên, repo và commit |
| `starter/src/`, `starter/scripts/`, `starter/requirements.txt` | Code và cách tái lập |
| `data/` | Corpus, manifest, mapping, text từng trang và log trích xuất |
| `benchmark/questions.jsonl` | Câu hỏi, split, đáp án, gold evidence và nguồn thay thế |
| `artifacts/` | Cấu hình và nhật ký thí nghiệm |
| `results/metrics.csv`, `ingestion_stats.csv`, `environment.json` | Chỉ số dev/test, tài nguyên và phiên bản chạy |
| `results/traces.jsonl`, `chunks_*.jsonl` | Trace top-3 và chunk có nguồn/offset |
| `results/metrics_adjudicated.csv`, `results/audit/retrieval_adjudication.csv` | Điểm sau đối chiếu evidence và 180 quyết định từng kết quả; giữ riêng điểm strict ban đầu |
| `results/audit/` | Mẫu và nhãn đánh giá coherence, metadata, grounding |
| `report/individual/2A202603491_NguyenVuHoang.md` | Báo cáo cá nhân |

Hit yêu cầu đúng nguồn/trang và đủ evidence trong một chunk. Phép chấm tự động dùng khớp evidence đã chuẩn hóa; có thể bỏ sót bằng chứng tương đương, cần đối chiếu riêng. Grounding không phải độ đúng câu trả lời LLM. Hai tập cùng chương/chủ đề, test chỉ có 5 câu nên không suy rộng kết quả.

Đối chiếu evidence được AI thực hiện sau khi đã xem test, có quote, lý do và hash câu hỏi/chunk để kiểm chứng. Không thay benchmark, model hay thứ tự truy xuất và không chọn lại cấu hình từ điểm đối chiếu. `metrics.csv` vẫn là điểm strict dùng để chọn B trước test; bảng sau đối chiếu được ghi nhãn riêng, không gọi là test mới hay kết quả chấm độc lập của học viên.

Script kiểm tra còn chạy một Chroma tạm bằng vector thật để thử nạp lại, xóa chunk cũ, cập nhật metadata, filter, dữ liệu sai chiều và mở lại store trong tiến trình khác. Kết quả nằm trong `results/validation.json`. Khóa hash dùng text chuẩn hóa LF và đường dẫn tương đối thống nhất; hash gốc và lịch sử sửa lỗi đóng gói sau test được giữ trong `results/experiment_lock.json`.

Các bảng audit đã có điểm, lý do và người chấm thực tế là Codex AI hỗ trợ đọc/đối chiếu nguồn. Phương pháp và hạn chế nằm trong `results/audit/sampling.json`; `student_confirmed=false` vì chưa ghi nhận học viên tự xác nhận. Cột `human_correct` trong metadata là tên cột cũ, không có nghĩa người học đã trực tiếp chấm. Cần đọc lại nguồn/gold, thông tin học viên và repo/commit trước khi nộp. Học viên phải hiểu và giải thích được bài.

`.local/` chứa model/database và `starter/.venv/` chứa môi trường chạy tại máy, được Git bỏ qua. Không nộp hai thư mục này; có thể tạo lại bằng lệnh cài/chạy trên.

Access for free at openstax.org. OpenStax, Rice University, *Principles of Economics 3e*. Văn bản trích xuất, evidence và trace chứa nội dung sách được chia sẻ theo CC BY-NC-SA 4.0, giữ ghi nguồn. Giấy phép này không thay giấy phép dependencies bên thứ ba.
