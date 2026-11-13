# Demo 4–5 phút cho giảng viên

## Mở demo

Tại thư mục gốc project:

```powershell
.\starter\.venv\Scripts\python.exe -B .\demo\app.py
```

Đợi dòng `DEMO READY`, mở **http://127.0.0.1:8765**. Giữ terminal này chạy, Ctrl+C để dừng. Không cần chạy lại ingestion mỗi lần mở UI. Nếu server đang chạy rồi thì chỉ mở URL, không mở thêm cùng cổng.

Chọn checkbox A/B/C tùy ý: một cấu hình, AB, AC, BC hoặc ABC đều được. Một lượt chỉ embedding câu hỏi một lần, rồi các cấu hình được chọn tìm kiếm song song trên cùng vector. Filter chương chỉ áp dụng cho C; A/B vẫn không filter để giữ đúng thiết kế thí nghiệm.

UI hiển thị diễn giải tiếng Việt trước, tiếng Anh ở mục mở rộng. Các diễn giải được biên soạn cho đoạn nguồn của những ví dụ demo, ghép theo nội dung thực sự có trong chunk; không lấy gold theo câu hỏi để trả lời. Đây không phải dịch tự động mọi tài liệu hoặc câu trả lời do E5 sinh. Đoạn chưa có diễn giải sẽ được báo rõ và vẫn có nguyên văn để kiểm chứng. Phần trình bày này không tham gia retrieval hay tính điểm benchmark.

## Thứ tự demo đề xuất

Trước phần hỏi đáp, mở tab **Xem pipeline từ PDF**, chọn trang **36** (hoặc 52 để xem đoạn điều dưỡng). Đi theo sơ đồ: mở PDF gốc → so text thô và sau chuẩn hóa → xem số ký tự/đường xuống dòng thay đổi → mở chunk A/B và offset → xem 12 số đầu của vector thật đã lưu, chiều 384 và chuẩn L2 gần 1 → chuyển sang tìm top-3. Hai ô text giữ tiếng Anh để chứng minh chuẩn hóa chỉ làm sạch/giữ truy vết, không dịch nguồn. Đây là dữ liệu thực từ PDF/artifacts/Chroma của bài, không phải ví dụ giả lập.

| Thứ tự | Câu hỏi nên copy | Chọn | Phạm vi C | Điều cần chỉ cho giảng viên |
|---|---|---|---|---|
| 1 | Trong ví dụ xăng, giá và lượng cân bằng là bao nhiêu? | ABC | Không lọc | Có bằng chứng 1.40 USD/gallon và 600 triệu gallon. A có thể cắt câu; B giữ câu dài hơn. Mở nguồn ở trang PDF 8 để đối chiếu. |
| 2 | Ai cung ứng lao động? | BC | Chương 4 | Top-1 đã kiểm tra nằm ở PDF trang 36: người tìm việc cung lao động, doanh nghiệp có cầu lao động. C chỉ trả chương 4. |
| 3 | Khi cầu điều dưỡng tăng đồng thời cung giảm, lương và lượng điều dưỡng cân bằng thay đổi thế nào? | AB hoặc ABC | Không lọc | A tìm gần đúng trang 52 nhưng cắt phần kết luận; B/C có kết luận ở trang 52/53. Đây là ví dụ điều kiện quan trọng hơn việc chỉ đúng trang. |
| 4 | Vì sao cầu lao động được gọi là cầu dẫn xuất? | BC | Không lọc | Đọc ví dụ nhu cầu ô tô dẫn đến nhu cầu lao động ở trang 38. Giải thích vì sao strict matcher có thể miss dù đoạn đủ ý. |
| 5, nếu còn thời gian | Theo chương 3, giá trần là gì? | ABC | Chương 3 | Đây là câu hệ thống làm chưa tốt. Chỉ đúng chương chưa có nghĩa là đúng evidence; không cố đọc câu trả lời từ một đoạn chỉ có tiêu đề. |

Các ví dụ trên đã được dùng trong kiểm tra bài; đây là minh họa, không phải test mới chưa xem. Thứ tự top-3 có thể có biến động nhỏ do HNSW. Hãy đọc đoạn thực tế, không nói trước rằng kết quả chắc chắn đúng.

Để minh họa filter riêng: dùng câu hỏi lao động, chọn C và chương 3, rồi đổi sang chương 4. Nêu rõ lần chọn chương 3 là **cố ý đưa phạm vi không phù hợp** để quan sát hành vi filter, không phải một phép đo chất lượng benchmark.

## Lời mở đầu khoảng 30 giây

“Bài của em tập trung vào chuẩn bị dữ liệu và đánh giá truy xuất. Em lấy 52 trang nội dung về cung–cầu trong sách OpenStax, giữ nguồn và trang. Sau đó em chia chunk, tạo vector bằng cùng một model và lưu vào Chroma. UI này chỉ để nhìn rõ kết quả A/B/C cạnh nhau, không phải phần bắt buộc của đề và chưa sinh câu trả lời bằng LLM.”

## Vì sao chọn model này?

“Em dùng `intfloat/multilingual-e5-small` vì bài hỏi tiếng Việt nhưng nguồn tiếng Anh, nên cần embedding đa ngữ. Em chọn bản small để chạy được local trên CPU, không cần API key, không phát sinh phí API. Vector có 384 chiều. Em chưa thử đủ nhiều model để kết luận đây là model tốt nhất cho tiếng Việt hay kinh tế.”

Theo [model card chính thức](https://huggingface.co/intfloat/multilingual-e5-small), model có vector 384 chiều, giới hạn đầu vào 512 token và dùng prefix `query: ` cho câu hỏi, `passage: ` cho đoạn tài liệu, kể cả văn bản không phải tiếng Anh. Code kiểm tra giới hạn token và chuẩn hóa vector L2. Các chunk hiện tại đều dưới giới hạn; giữ revision cố định để tái lập.

**Embedding** biến câu/đoạn thành dãy số để so sánh ý nghĩa; nó không tự viết câu trả lời. Khả năng đa ngữ không đảm bảo mọi câu tiếng Việt sẽ tìm đúng đoạn tiếng Anh.

## Các ý cần giải thích trong lúc demo

- **Corpus:** PDF nộp có 53 trang, trong đó 1 trang bản quyền không index, 52 trang nội dung được chọn. Giấy phép CC BY-NC-SA 4.0, giữ ghi nguồn OpenStax. `page` trên UI là trang của PDF rút gọn, khác `printed_page` in trên sách.
- **Chunking:** A 500 ký tự/overlap 50; B ưu tiên ranh giới câu, tối đa 1000 ký tự/không overlap. A–B đổi cả chính sách chunking, không thể nói riêng ranh giới câu làm tăng bao nhiêu điểm. C giữ chunk và vector B, chỉ thêm filter khi có input chương.
- **Store:** Chroma lưu vector và metadata trên đĩa, tìm bằng cosine với HNSW approximate. Dừng rồi mở lại vẫn giữ dữ liệu. Không phải chỉ tính cosine trên một list Python rồi gọi đó là vector database.
- **Metadata:** `source`, `page`, `document_id` giúp truy nguồn; `chapter` dùng filter; offset giúp kiểm tra text. Mở Metadata để chỉ ID và bấm nguồn để đối chiếu PDF.
- **Cosine:** số gần nhau giúp xếp hạng tương đồng; `0.79` không có nghĩa xác suất đúng 79%. Kết quả có điểm cao vẫn có thể thiếu điều kiện trả lời.
- **Benchmark:** 20 câu, tách trước 15 dev/5 test, có 4 câu filter gồm 1 câu test. Chọn B trên dev trước khi xem test, không chỉnh theo test. 5 câu test ít và cùng chủ đề nên chưa suy rộng được.
- **Hit@1/Hit@3:** chunk phải có đủ bằng chứng ở nguồn/trang hợp lệ. Đúng trang hay có từ khóa không tự động được hit. Không ghép nhiều chunk để nâng định nghĩa Hit@3 chính.
- **Strict và đối chiếu:** strict test Hit@3 là A 1/5, B/C 4/5. Sau AI đối chiếu evidence tương đương: A 1/5, B/C 5/5. Giữ hai bảng riêng; điểm tăng do cách đo nhận ra evidence, thứ tự truy xuất giữ nguyên. Đối chiếu làm sau test và chưa có xác nhận độc lập của học viên.
- **Năm tiêu chí:** retrieval; coherence của chunk; metadata đủ/đúng và có ích; grounding của top-3; tác động và đánh đổi giữa các chiến lược. Grounding đang đánh giá bằng chứng, chưa phải câu trả lời LLM.
- **Tài nguyên:** A 344 chunk, B/C 183. C tái dùng embedding B, nên thời gian ingest C chưa gồm phần embedding đã tính cho B. Thời gian trên UI chỉ là demo, không thay số liệu benchmark.
- **Trung thực:** AI hỗ trợ code, câu hỏi, nhãn và báo cáo; phương pháp/người chấm có ghi trong artifacts. Cùng AI vừa viết vừa chấm có thể thiên lệch. Không nói đã được người học chấm độc lập nếu chưa làm.

## Lời kết khoảng 20 giây

“Trong corpus và benchmark này em chọn B theo điểm dev. C có filter đúng nhưng chưa cải thiện Hit@3 so với B trên bộ câu hiện tại. Điểm còn hạn chế ở một số câu; em chưa xử lý tốt bảng, hình và ngữ cảnh qua trang. Nếu làm tiếp em sẽ dùng thêm bộ test mới, kiểm tra nhãn với người học và thử giữ cấu trúc tài liệu tốt hơn.”

## Nếu giảng viên hỏi nhanh

**Sao không dùng chatbot?** Đề tập trung ingestion/retrieval và benchmark; UI trả bằng chứng để kiểm tra được pipeline, chưa cần thêm bước sinh câu trả lời.

**Sao B và C giống nhau?** C dùng cùng chunk/vector B; không filter thì đầu vào tìm kiếm như nhau. Ngay cả có filter, B có thể đã lấy đúng chương, nên kết quả vẫn giống. Không suy ra filter vô ích từ vài câu này.

**Sao không tăng model để có điểm tốt hơn?** Mục tiêu là so sánh chiến lược dữ liệu có kiểm soát. Đổi model sẽ thêm một yếu tố khác; muốn so sánh tiếp cần thiết kế thí nghiệm riêng và tập chưa dùng để chỉnh.

**Có sửa số liệu sau test không?** Giữ bảng strict và gold gốc, thêm bảng AI đối chiếu có quote/lý do, công bố rõ làm sau test. Có sửa cách hash để tương thích xuống dòng Git, lịch sử nằm trong khóa; không đổi model hay chunking để nâng kết quả test.

## Dừng demo

Ctrl+C ở terminal chạy server. Thư mục `demo/` được nộp cùng repo để người chấm có thể chạy giao diện. Model, database và môi trường Python local vẫn được Git bỏ qua; người chấm tạo lại bằng hướng dẫn ở README. Demo là phần trình bày bổ sung, không tham gia tính điểm benchmark.
