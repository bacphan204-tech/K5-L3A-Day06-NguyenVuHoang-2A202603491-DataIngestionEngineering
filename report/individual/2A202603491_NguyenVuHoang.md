# Báo cáo cá nhân — Day 06

## 1. Dữ liệu và cách làm

Em chọn phần cung–cầu và thị trường lao động, tài chính trong sách *Principles of Economics 3e* của OpenStax. Phạm vi này có hai chương nên có thể thử lọc theo chương. File nộp là PDF rút gọn 53 trang, gồm 1 trang bản quyền và 52 trang nội dung. Trang bản quyền không được tính hay đưa vào index.

Nguồn có giấy phép CC BY-NC-SA 4.0. Thông tin nguồn, hash file, số trang và số ký tự nằm trong `data/manifest.json`; bảng đối chiếu trang nằm ở `data/excerpt_page_map.csv`. Em dùng số trang PDF rút gọn làm mốc chính, có giữ thêm trang in và trang PDF gốc để kiểm tra.

Pipeline dùng Python và pypdf để lấy chữ từng trang, chuẩn hóa Unicode NFC và khoảng trắng, bỏ các footer nhận diện được. Lượt chạy không gặp trang rỗng hay lỗi trích xuất. Tuy vậy, đọc được chữ chưa có nghĩa là giữ được toàn bộ bảng và hình. Phần này em mới xử lý text, chưa làm OCR hay phân tích biểu đồ.

Embedding chạy local bằng `intfloat/multilingual-e5-small`, revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`, vector 384 chiều. Query tiếng Việt có prefix `query: `, đoạn tiếng Anh có prefix `passage: `; vector được chuẩn hóa L2. Store là Chroma 1.5.9, lưu bền vững ở `.local/chroma`, dùng cosine và HNSW approximate. Các collection là `economics_a`, `economics_b`, `economics_c`.

Mỗi chunk có `document_id`, `source`, `page`. Em giữ thêm `chapter` kiểu số nguyên (3 hoặc 4), tên chương, trang in, trang gốc và offset ký tự. Giá trị chương lấy từ cấu trúc sách. `source/page/offset` giúp tìm lại đoạn; `chapter` giúp giới hạn phạm vi khi người hỏi đã chỉ rõ chương. Hạn chế là lọc theo chương vẫn khá rộng và không đánh giá được nội dung có đúng ý người hỏi hay chưa.

Lượt chạy gần nhất ghi lúc 2026-11-13T11:46:00.215089+00:00 (UTC), Python 3.14.6, CPU. Chi phí API là 0 USD vì dùng local; em chưa đo tiền điện và chi phí phần cứng. Phiên bản thư viện đầy đủ nằm trong `starter/requirements.txt` và thông tin chạy ở `results/environment.json`.

## 2. Ba cấu hình và benchmark

| Cấu hình | Cách chia và truy xuất |
|---|---|
| A | Cố định 500 ký tự, overlap 50, không filter |
| B | Ưu tiên kết thúc câu, tối đa 1000 ký tự, không overlap, không filter |
| C | Dùng nguyên chunk/vector của B, thêm filter chương khi câu hỏi cung cấp |

A–B thay cả chính sách chia chunk, gồm độ dài, overlap và ranh giới. Vì vậy em chỉ so sánh được hai cách chuẩn bị dữ liệu, chưa tách riêng tác dụng của từng tham số. B–C thì chỉ khác filter. Câu không yêu cầu chương sẽ chạy C không filter.

Benchmark có 20 câu tiếng Việt, đáp án kỳ vọng tiếng Việt và evidence nguyên văn tiếng Anh. Bộ câu được chia trước thành q01–q15 dev, q16–q20 test. Có 4 câu filter: q03, q12, q15 ở dev và q18 ở test; chương đã được nêu trong câu hỏi nên không lấy gold làm filter. Evidence chính và các nguồn thay thế đã được đối chiếu tồn tại trong nguồn trước retrieval.

Hai tập vẫn có kiến thức gần nhau vì cùng lấy từ hai chương. Em đã ghi hạn chế này, không coi test là kiểm tra trên một chủ đề hoàn toàn mới. Model, corpus, câu hỏi và định nghĩa điểm được giữ như nhau cho A/B/C.

Quy tắc chọn đã ghi trước khi xem điểm test: ưu tiên strict Evidence Hit@3 trên dev, rồi Hit@1, rồi ít chunk hơn; nếu vẫn bằng nhau thì theo tên cấu hình. Theo quy tắc này, cấu hình chọn là **B**. Hash code, dữ liệu và benchmark nằm trong `results/experiment_lock.json`. Những lần chạy lại chỉ kiểm tra tái lập, không sửa tham số theo test.

## 3. Kết quả truy xuất

Bảng dưới là điểm tự động theo cách khớp evidence nghiêm ngặt: đúng nguồn/trang và một chunk chứa đủ đoạn evidence đã ghi. Hit@1 xét kết quả đầu; Hit@3 xét có ít nhất một chunk đạt trong top-3. Đúng trang nhưng thiếu evidence vẫn chưa được tính. Bằng chứng tương đương có thể bị cách khớp này bỏ sót, nên em có đọc thêm trace ở phần đánh giá.

| Cấu hình | Tập | Hit@1 | Strict Evidence Hit@3 | Số chunk | Ingest (giây) | API USD |
|---|---|---|---|---|---|---|
| A | dev | 0/15 | 3/15 | 344 | 40.32 | 0 |
| A | test | 0/5 | 1/5 | 344 | 40.32 | 0 |
| B | dev | 2/15 | 6/15 | 183 | 34.21 | 0 |
| B | test | 2/5 | 4/5 | 183 | 34.21 | 0 |
| C | dev | 2/15 | 6/15 | 183 | 0.85 | 0 |
| C | test | 2/5 | 4/5 | 183 | 0.85 | 0 |

C dùng lại embedding B nên thời gian ingest C không gồm phần embedding đã tính cho B. Không nên nhìn thời gian này rồi kết luận C nhanh hơn toàn bộ pipeline. Thời gian ingest cũng chưa gồm tải/khởi tạo model và lần upsert kiểm tra thứ hai.

| Cấu hình | Độ dài min / trung bình / max (ký tự) | Tổng ký tự chunk | Tổng token có prefix |
|---|---|---|---|
| A | 69 / 466.9 / 500 | 160601 | 38829 |
| B | 33 / 797.8 / 999 | 146001 | 34494 |
| C | 33 / 797.8 / 999 | 146001 | 34494 |

Các chunk không vượt giới hạn 512 token của model. A có tổng text lớn hơn do overlap. Em đã nạp lại cùng dữ liệu, số bản ghi không tăng; code upsert theo ID ổn định và xóa ID cũ không còn trong lần ingest mới. Trace đầy đủ ở `results/traces.jsonl`, thống kê ở `results/metrics.csv` và `results/ingestion_stats.csv`.

## 3.1. Đối chiếu evidence tương đương

Em giữ riêng hai cách tính để không che mất hạn chế của bộ chấm ban đầu. `metrics.csv` là điểm strict đã dùng để chọn B trên dev. `metrics_adjudicated.csv` là kết quả đọc lại từng kết quả truy xuất, theo tiêu chí một chunk phải có đủ ý và điều kiện để trả lời, có nguồn/trang và quote kiểm chứng được. Cả 180 kết quả top-3 đều có quyết định và lý do trong `results/audit/retrieval_adjudication.csv`, kể cả những đoạn bị loại. Không ghép nhiều chunk để biến một miss thành hit.

Việc đối chiếu được làm sau khi đã xem test và vẫn do AI thực hiện. Vì vậy đây là sửa cách đo/ghi nhận evidence của cùng lượt truy xuất, không phải một lần test mới và không phải đánh giá mù. Bộ câu, gold gốc, model, chunk và thứ tự top-3 không được sửa để lấy điểm này; cấu hình chọn trước đó vẫn là B. Học viên chưa được ghi nhận xác nhận độc lập.

| Cấu hình | Tập | Hit@1 sau đối chiếu (AI) | Evidence Hit@3 sau đối chiếu (AI) |
|---|---|---|---|
| A | dev | 3/15 | 6/15 |
| A | test | 0/5 | 1/5 |
| B | dev | 4/15 | 8/15 |
| B | test | 3/5 | 5/5 |
| C | dev | 4/15 | 8/15 |
| C | test | 3/5 | 5/5 |

Ví dụ A/q04: chunk ở trang 8 có đủ 1.40 USD/gallon và 600 triệu gallon nhưng mất cụm In Figure 3.4 ở đầu gold; đây là false negative của khớp nguyên văn. A/q10 và B/C/q10 có ví dụ chi phí thép giảm làm tăng lượng cung ở mỗi giá và dịch phải, nằm ở trang 16 thay vì gold chính trang 15. Với q17, từng đoạn đủ giải thích quan hệ cầu sản phẩm–cầu lao động được ghi nhận riêng. Các đoạn chỉ nhắc đúng chủ đề nhưng thiếu điều kiện vẫn bị loại, ví dụ A/q02 thiếu ceteris paribus và A/q20 thiếu kết luận lượng không chắc chắn.

### Mẫu test nhỏ nên điểm còn dễ thay đổi

| Cấu hình | Strict Hit@3 test | Khoảng Wilson 95% minh họa | Hit@3 sau đối chiếu | Khoảng Wilson 95% minh họa |
|---|---|---|---|---|
| A | 1/5 | 3.6%–62.4% | 1/5 | 3.6%–62.4% |
| B | 4/5 | 37.6%–96.4% | 5/5 | 56.6%–100.0% |
| C | 4/5 | 37.6%–96.4% | 5/5 | 56.6%–100.0% |

Các khoảng này chỉ minh họa bất định nếu xem từng câu như phép thử nhị thức. Câu hỏi do tự soạn, có liên quan cùng chương và không lấy mẫu ngẫu nhiên nên không dùng khoảng này để khẳng định chất lượng trên mọi câu hỏi kinh tế. Dù có 5/5 sau đối chiếu, chỉ cần sai thêm một câu là còn 4/5; em không xem đó là bằng chứng hệ thống đã hoàn hảo.

## 4. Đánh giá chunk, metadata và grounding

**Cách chấm và việc dùng AI:** code, benchmark và báo cáo có AI hỗ trợ. Các nhãn trong lượt này do trợ lý Codex AI đọc từng mẫu, so với câu hỏi và nguồn rồi ghi điểm/lý do. Metadata được đối chiếu trực tiếp với text PDF, trang và offset. Đây là đánh giá có AI hỗ trợ, chưa có xác nhận chấm độc lập của học viên. Cùng trợ lý cũng tham gia viết pipeline, lại đã nhìn thấy điểm retrieval, nên có thể thiên lệch. Người chấm thực tế và cách kiểm tra được ghi trong các CSV và `results/audit/sampling.json`.

Coherence lấy cùng 10 vị trí là midpoint của 10 trang được chọn đầu tiên. Nếu nhiều chunk bao phủ một vị trí thì lấy trung bình trong vị trí rồi mới tính trên 10 vị trí. Thang 0 là khó hiểu do cắt ý/thiếu chủ thể, 1 là hiểu một phần nhưng thiếu ngữ cảnh, 2 là tự hiểu được và giữ trọn ý. Grounding đọc top-3 của cùng 5 câu test: 0 không có evidence, 1 có nhưng thiếu điều kiện, 2 đủ để trả lời và truy nguồn. Đây là chất lượng bằng chứng, chưa phải điểm câu trả lời của LLM.

| Cấu hình | Coherence /2 (10 vị trí) | Metadata đủ và đúng (n/N) | Grounding số câu mức 0/1/2 | Grounding trung bình /2 |
|---|---|---|---|---|
| A | 1.00 | 15/15 | 2/2/1 | 0.80 |
| B | 1.70 | 15/15 | 0/0/5 | 2.00 |
| C | 1.70 | 15/15 | 0/0/5 | 2.00 |

A thường cắt giữa từ/câu nên đọc được một phần nhưng hay thiếu đầu hoặc cuối ý. B/C giữ câu tốt hơn, tuy vậy vẫn có các đoạn mở đầu bằng This decline hay Additionally và phải dựa vào đoạn trước. Bảng số liệu sang trang cũng chưa được ghép lại. Vì vậy B/C chưa được chấm coherence tối đa ở mọi vị trí.

Metadata được kiểm tra trên 5 câu test × top-3 = 15 bản ghi mỗi cấu hình. Các bản ghi khớp nguồn, chương, trang và vị trí text. Kết quả này mới cho thấy metadata đúng và truy vết được; em chưa kết luận filter hữu ích trong mọi trường hợp. Cột `human_correct` là tên cột cũ của chương trình; trường `reviewer` ghi rõ lần này người chấm là AI và `student_confirmed=false`.

| Cấu hình | Tập | Câu có toàn bộ top-3 đúng phạm vi / câu có filter |
|---|---|---|
| A | dev | 2/3 |
| A | test | 1/1 |
| B | dev | 3/3 |
| B | test | 1/1 |
| C | dev | 3/3 |
| C | test | 1/1 |

A/B không áp dụng filter; đúng phạm vi có thể do truy xuất tự nhiên. Ở bộ câu này, B đã đúng phạm vi cho các câu filter nên C chưa làm tăng Hit@3. Test chỉ có một câu filter, số liệu này còn ít để kết luận chắc.

## 5. Ví dụ lỗi và điều em rút ra

- **A, q20 (test):** gold ở trang 52/53. Rank 2 đã đến trang 52 nhưng chunk bị cắt trước kết luận lương tăng và số lượng điều dưỡng chưa chắc tăng hay giảm. Grounding chấm 1/2. B/C lấy được đoạn kết luận ở trang 53 và 52 nên đủ ý hơn. Đây là ví dụ tìm gần đúng trang vẫn chưa đủ.

- **B/C, q17 (test):** gold chính ở trang 38 gồm nhiều câu. Rank 1 có ví dụ nhu cầu ô tô làm tăng nhu cầu lao động và tên derived demand, còn câu tổng quát nằm trong chunk khác. Strict matcher báo miss, nhưng khi đọc nội dung thì rank 1 đã có bằng chứng tương đương giải thích câu hỏi, nên grounding chấm 2/2. Em giữ nguyên strict metrics và ghi riêng hạn chế này, không sửa gold/test sau khi đã xem kết quả.

- **A, q16 (test):** top-3 ở trang 16, 27, 29 chỉ nói công nghệ, thiếu hụt và hiệu quả chung. Chưa có định nghĩa deadweight loss ở trang 31/33, nên grounding chấm 0/2. Đây là lỗi truy xuất nội dung, không chỉ là cách khớp câu chữ.

So với A, B tăng strict Hit@3 từ 3/15 lên 6/15 ở dev và từ 1/5 lên 4/5 ở test. Số chunk giảm từ 344 xuống 183. B/C cũng có coherence và grounding tốt hơn trong mẫu đã đọc. Em nghiêng về B trong phạm vi bài này vì kết quả dev tốt hơn A và bằng C, cách truy xuất cũng đơn giản hơn C. Tuy nhiên phần tăng điểm không thể quy hết cho ranh giới câu vì B còn đổi kích thước và overlap.

B–C chưa có chênh lệch Hit@3 ở bộ câu hiện tại. Filter vẫn giúp thực hiện đúng yêu cầu giới hạn chương, nhưng input lọc sai cũng có thể loại mất đoạn cần tìm. Em nghĩ cần thêm câu hỏi dễ nhầm giữa hai chương để thử rõ hơn, thay vì kết luận metadata không có tác dụng.

## 6. Hạn chế và chạy lại

Điểm còn thấp ở một số câu, đặc biệt A. Em chưa tách được ảnh hưởng của hỏi tiếng Việt trên tài liệu tiếng Anh với ảnh hưởng chunking. Bộ 20 câu còn nhỏ và gần nhau về kiến thức; 5 câu test chỉ để minh họa. Chấm bằng AI chưa độc lập, có yếu tố chủ quan; một phần nhãn coherence ở mức 1/2 hay 2/2 vẫn có thể được người khác chấm khác. Em cũng chưa xử lý tốt bảng, hình và ngữ cảnh qua trang, chưa đo nhiều lượt để lấy độ biến động thời gian.

Nếu làm tiếp, em sẽ kiểm tra lại các nhãn với người học, dùng một bộ test mới chưa xem để so sánh tiếng Việt/tiếng Anh, và thử giữ tiêu đề/đoạn nguồn tốt hơn. Những việc đó chưa được chạy trong kết quả báo cáo này.

Lệnh cài và chạy nằm trong `README.md`. Chạy `powershell -NoProfile -ExecutionPolicy Bypass -File .\starter\scripts\run_all.ps1` để trích xuất, ingest, dev, khóa cấu hình, test, tạo báo cáo và kiểm tra lại store. Cập nhật báo cáo sau khi sửa nhãn bằng `python starter/scripts/build_report.py` với Python của venv. Model/database và môi trường local được Git bỏ qua, không nộp kèm.

Bài vẫn cần học viên đọc hiểu, xác nhận thông tin và chốt commit/push repo trước khi nộp. Việc AI đã điền nhãn không thay cho việc học viên hiểu và chịu trách nhiệm về đánh giá.

Access for free at openstax.org. OpenStax, Rice University, *Principles of Economics 3e*. Nội dung sách trích trong corpus, benchmark và trace theo CC BY-NC-SA 4.0.

## 7. Kiểm chứng và vị trí minh chứng

| Yêu cầu | File/minh chứng |
|---|---|
| Corpus, quyền sử dụng, số trang và lỗi | `data/manifest.json`, `data/corpus_review.json`, `data/processed/page_inventory.csv`, `extraction_log.json` |
| Ba chiến lược, giả thuyết và tham số | `artifacts/strategies.json`, `artifacts/experiment_log.csv` |
| Câu hỏi, split, gold và filter | `benchmark/questions.jsonl` |
| Retrieval và nguồn từng kết quả | `results/traces.jsonl`, `metrics.csv`, `metrics_adjudicated.csv`, `audit/retrieval_adjudication.csv` |
| Coherence, metadata, grounding và phương pháp chấm | `results/audit/coherence.csv`, `metadata.csv`, `grounding.csv`, `sampling.json` |
| Model, tài nguyên, tái lập và kiểm thử | `results/environment.json`, `ingestion_stats.csv`, `validation.json`, `starter/scripts/check_results.py` |

Script kiểm tra không chỉ đếm số dòng. Nó tính lại chỉ số, đối chiếu chunk với text nguồn, kiểm tra chiều/chuẩn vector và chạy thử trong một Chroma tạm bằng vector thật. Các trường hợp kiểm tra gồm nạp lại không trùng, xóa chunk lỗi thời, cập nhật metadata, lọc chương, cosine tự khớp, từ chối dữ liệu sai chiều/sai số lượng và mở lại store trong tiến trình khác. Kết quả chạy thực tế được ghi trong `results/validation.json`.

Có một sửa đổi kỹ thuật sau khi xem test: chuẩn hóa LF/CRLF và dấu phân cách đường dẫn khi tính fingerprint để Git checkout không làm báo sai khóa. Hash gốc và lịch sử sửa đổi vẫn được giữ trong `results/experiment_lock.json`; logic embedding, chunking, truy xuất và strict scoring không đổi. Việc chạy lại sau đó là kiểm tra tái lập, không gọi là holdout mới.

### Các ý em cần giải thích khi trình bày

- Hit@3 chỉ cần một chunk đủ evidence; grounding đọc cả top-3 và xét thiếu điều kiện. Hai điểm có thể khác nhau.
- C dùng đúng vector/chunk B nên B–C mới kiểm tra riêng filter. A–B đổi nhiều tham số chunking nên không kết luận riêng độ dài hay ranh giới câu gây ra bao nhiêu phần cải thiện.
- Metadata đúng không đồng nghĩa tìm đúng nội dung; cần xem cả tỷ lệ tuân thủ filter và ví dụ có ích khi truy nguồn.
- Không chọn lại cấu hình theo bảng đối chiếu sau test. Nếu thử model/chunking mới, cần dev và test mới phù hợp, rồi công bố việc đã xem tập cũ.
- Điểm cao hơn sau đối chiếu cho thấy bộ chấm nguyên văn còn hạn chế, không có nghĩa vector hay thứ tự truy xuất vừa tốt lên.

### Chạy từ bản sao bộ nộp

Đã chạy lại lúc 2026-11-13T11:37:29.550617+00:00 (UTC) từ bản sao các file nộp, với database Chroma mới hoàn toàn và file Python được chuẩn hóa LF như khi Git checkout. Bản sao dùng cùng model đã khóa và cùng bộ thư viện Python đã cài; không dùng lại index cũ. Kết quả đủ 60 trace/180 kết quả top-3, số chunk 344/183/183 và bảng strict/adjudicated khớp lượt gốc. Các kiểm tra nguồn, vector, filter và store tạm cũng chạy qua.

Phạm vi kiểm tra này là tái lập từ source và database mới, có dùng chung thư viện đã cài và copy model local. Em chưa gọi đây là thử cài dependencies trên một máy sạch hoàn toàn, và chưa xác minh quyền truy cập repo của giảng viên. Chi tiết nằm trong `results/experiment_lock.json`, mục `reproduction_checks`.
