# Báo cáo Day 09 — Trịnh Vinh Khánh, 2A202603220


## 1. Kết luận trước

```
Kết luận: RELEASE. Pipeline nhận 193/224 ảnh, loại 31 ảnh tại Intake. Sau autofix và mô phỏng review với ngân sách 80 ảnh, không còn lỗi bắt buộc; còn 13/193 ảnh có cảnh báo, tương ứng 0.0674, thấp hơn ngưỡng 0.10.

Số ảnh vào: 224 ảnh thô.
Số ảnh sau Intake: 193 ảnh.
Số ảnh bị loại tại Intake: 31 ảnh.
Số ảnh xuất dataset: cần xác nhận số ảnh thực tế trong submission/export/clean_v1.
```

## 2. Lỗi và phân việc
Lấy từ `02_error_list_v1` (gom theo mã lỗi). Cột "ai sửa": **máy** (autofix) hay **người** (hàng đợi); chỉ ghi những mã có mặt trong lô của bạn.

## **Bảng tổng hợp Error**

| Mã lỗi               | Số ảnh/dòng                                                                                                                                                                                                       | Ai xử lý                     | Vì sao                                                      |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- | ----------------------------------------------------------- |
| `CORRUPT_IMAGE`      | **2 ảnh:** `img_0010`, `img_0136`                                                                                                                                                                                 | Máy (Intake)                 | Ảnh không đọc được, loại khỏi dataset                       |
| `BAD_SIZE`           | **3 ảnh:** `img_0107`, `img_0113`, `img_0122`                                                                                                                                                                     | Máy (Intake)                 | Cạnh ngắn dưới 250 px                                       |
| `DUP_IMAGE_EXACT`    | **8 ảnh:** `img_0039` ↔ `img_0012`; `img_0080` ↔ `img_0071`; `img_0102` ↔ `img_0082`; `img_0156` ↔ `img_0147`; `img_0162` ↔ `img_0054`; `img_0203` ↔ `img_0145`; `img_0207` ↔ `img_0182`; `img_0222` ↔ `img_0151` | Máy (Intake)                 | Trùng ảnh chính xác, giữ một bản                            |
| `DUP_IMAGE_NEAR`     | **7 ảnh:** `img_0011` ↔ `img_0008`; `img_0076` ↔ `img_0042`; `img_0084` ↔ `img_0074`; `img_0143` ↔ `img_0037`; `img_0177` ↔ `img_0113`; `img_0186` ↔ `img_0061`; `img_0223` ↔ `img_0077`                          | Máy (Intake), người kiểm tra | Phát hiện trùng gần đúng bằng pHash; cần kiểm tra trực quan |
| `LEAK_TEST`          | **11 ảnh:** `img_0013`, `img_0017`, `img_0021`, `img_0033`, `img_0038`, `img_0049`, `img_0101`, `img_0115`, `img_0167`, `img_0174`, `img_0221`                                                                    | Máy (Intake)                 | Trùng với ảnh trong kho test/val, loại khỏi training        |
| `MISSING_LABEL_FILE` | **6 ảnh:** `img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219`                                                                                                                                 | Người (review)               | Không có file nhãn; máy không được tự tạo nhãn              |
| `BAD_FORMAT`         | **3 dòng:** `img_0014` (dòng 1), `img_0022` (dòng 1), `img_0179` (dòng 1)                                                                                                                                         | Máy (`drop_line`)            | Dòng nhãn sai định dạng hoặc có giá trị nan/inf             |
| `BAD_CLASS_ID`       | **6 dòng:** `img_0020` (dòng 3), `img_0099` (dòng 2), `img_0104` (dòng 1), `img_0117` (dòng 12), `img_0194` (dòng 1), `img_0199` (dòng 7)                                                                         | Máy (`drop_line`)            | Class ID nằm ngoài phạm vi 0–3                              |
| `BOX_ZERO`           | **4 dòng:** `img_0050` (dòng 1), `img_0066` (dòng 3), `img_0092` (dòng 2), `img_0185` (dòng 10)                                                                                                                   | Máy (`drop_line`)            | Chiều rộng hoặc chiều cao box bằng 0 hoặc âm                |
| `DUP_BOX`            | **7 dòng:** `img_0001` (dòng 3), `img_0006` (dòng 2), `img_0024` (dòng 8), `img_0094` (dòng 13), `img_0109` (dòng 2), `img_0141` (dòng 2), `img_0193` (dòng 7)                                                    | Máy (`drop_line`)            | Box trùng cùng lớp                                          |
| `BOX_OUT_OF_IMAGE`   | **8 dòng / 8 ảnh:** `img_0030` (dòng 9), `img_0043` (dòng 1), `img_0078` (dòng 2), `img_0087` (dòng 1), `img_0108` (dòng 1), `img_0144` (dòng 1), `img_0152` (dòng 1), `img_0204` (dòng 1)                        | Máy (`clip_box`)             | Box vượt khỏi biên ảnh, có thể cắt về phạm vi hợp lệ        |
| `BAD_CLASS_NAME`     | **2 mục trong&#x20;**`data.yaml`**:** `Person`, `Bus`                                                                                                                                                             | Máy (`rename_classes`)       | Tên lớp không khớp cấu hình lớp                             |

```
`05_review_queue.csv` sắp theo priority giảm dần, nếu bằng nhau thì theo tên ảnh. Điểm priority là tổng trọng số của các mã lỗi trên ảnh đó, lấy từ review_queue.py. Ảnh có nhiều cờ ngữ nghĩa (POSSIBLE_*) từ second_opinion được xếp cao. Ảnh chỉ có cờ FIXED_* (máy đã sửa) được xếp thấp.

Ngân sách 80 ảnh xem được bao nhiêu lỗi ngữ nghĩa: Hàm simulate chỉ xét 80 dòng đầu của hàng đợi. Trong 80 dòng đầu:
- 6 dòng là NEEDS_LABEL, không có cờ ngữ nghĩa.
- 67 ảnh có ít nhất một cảnh báo ngữ nghĩa POSSIBLE_*, với tổng cộng 76 cờ ngữ nghĩa.

Các cờ này gồm POSSIBLE_MISSING, POSSIBLE_WRONG_CLASS, POSSIBLE_FALSE_POS và POSSIBLE_LOOSE_BOX. Đây là số cảnh báo do model đưa ra, không phải số lỗi thật đã được xác nhận. Một ảnh có thể có nhiều cờ cùng lúc.
```

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 16 | 	Near duplicate: 1.00/0.50 -> 1.00/0.83; Exact duplicate: 1.00/1.00 -> 1.00/1.00  | Tại ngưỡng 16, recall near-duplicate tăng từ 0.50 lên 0.83 trong khi precision vẫn đạt 1.00 trên calibration. F1 near-duplicate tăng từ 0.67 lên 0.91. Ngưỡng 20 làm kết quả suy giảm rõ rệt nên không chọn. |
| `second_opinion.conf` | 0.25 | 0.80 | 	WRONG_CLASS: 0.56/0.83 -> 1.00/0.83; MISSING: 0.50/1.00 -> 0.67/0.75; LOOSE_BOX: 0.29/0.40 -> 0.50/0.20; FALSE_POS: 0.31/1.00 -> 0.31/1.00 | Ngưỡng 0.80 cải thiện precision của WRONG_CLASS và MISSING, đồng thời tăng macro-average F1 của 4 nhóm từ 0.5375 lên 0.5975. Tuy nhiên, recall của MISSING và LOOSE_BOX giảm. Chọn ngưỡng này nhằm ưu tiên chất lượng cảnh báo, không coi prediction của model là ground truth. |

**một chỗ calibration có thể đánh lừa bạn**, kèm bằng chứng từ dữ liệu của bạn (vd. mở xem vài cặp ảnh bị cho là trùng; số ảnh bị loại ở bước 1 có hợp lý không?).
```
Ảnh bị trùng:
img_0039.jpg & img_0012.jpg
img_0076.jpg & img_0042.jpg
img_0084.jpg & img_0074.jpg

Chỗ calibration có thể đánh lừa: ngưỡng second_opinion.conf được chọn là 0.80, điểm cuối của lưới sweep (0.1–0.8). 
Ngưỡng này làm precision tăng vì giữ lại ít dự đoán hơn, không phải vì check chính xác hơn: ví dụ img_0127 có 8 cảnh báo MISSING với conf 0.32–0.68, và các cảnh báo này biến mất ở ngưỡng 0.80. 
Hệ quả trực tiếp: cùng pipeline, ngưỡng 0.25 cho HOLD (60/205 ảnh còn cảnh báo, tỉ lệ 0.2927), còn ngưỡng 0.80 cho RELEASE (13/193, tỉ lệ 0.0674). 
```
## 4. Cửa chặn và điều pipeline KHÔNG bắt được
(a) chứng minh gate chặn đúng: chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt nên ảnh thiếu file nhãn còn nguyên), chỉ ra kết luận **Rework**, mã thoát 20 và việc **không xuất** dataset. (Đừng sửa tay `work/run/ds`: pipeline dựng lại thư mục này từ raw mỗi lần chạy.) 
```
Để kiểm tra gate, tôi chạy pipeline với ngân sách review bằng 0:

`python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`

Kết quả:
- Intake nhận 193/224 ảnh, loại 31 ảnh.
- Sau autofix vẫn còn 6 lỗi bắt buộc MISSING_LABEL_FILE.
- Không có người review nên 6 ảnh thiếu file nhãn vẫn chưa được xử lý.
- Gate kết luận REWORK, mã thoát 20.
- Test-Path work/exp_nb trả về False, chứng minh pipeline không xuất dataset khi còn lỗi bắt buộc.

6 ảnh còn lỗi: img_0031, img_0053, img_0126,
img_0135, img_0170, img_0219.

Điều này chứng minh gate ngăn việc phát hành dataset khi các lỗi bắt buộc chưa được giải quyết.
```

(b) ≥ 2 điểm mù có bằng chứng (box lỏng nhẹ, nhầm lớp mà model lớn cũng nhầm, ảnh trùng biến đổi mạnh…).
```
img_0002.png, box nhầm bộ phận điều khiển xuồng thành person. 
img_0015.png, box thiếu cho người mặc áo sanh dương.
```

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa train: ghi "chưa chạy" và lý do, rồi bỏ qua phần còn lại của mục này. Nếu đã train: dán bảng từ `submission/results/comparison.md` (model, epoch, seed, số ảnh train mỗi biến thể).
```
chưa chạy
```

## 6. Quyết định và ghi chú AI
(a) quyết định cuối; nếu Hold/Rework cần làm gì để thành Release? 
**(a) Quyết định cuối**
```
Decision: RELEASE

Lý do:
- 07_error_list_v3 không còn lỗi mandatory (severity=error).
- Các vấn đề còn lại đều là warning, không tự động xem là lỗi đã xác nhận.
- Có thể phát hành dataset sau khi Gate xác nhận các điều kiện Release được đáp ứng.

Các điểm cần tiếp tục theo dõi:
- EMPTY_LABEL: kiểm tra ảnh nền hay thiếu nhãn.
- BOX_TINY / BOX_HUGE: kiểm tra kích thước và tính hợp lý của bounding box.
- POSSIBLE_FALSE_POS / POSSIBLE_WRONG_CLASS / POSSIBLE_MISSING:
  kiểm tra trực quan để xác nhận dự đoán của model trước khi chỉnh sửa nhãn.
- Ưu tiên kiểm tra img_0183 và img_0078 vì có cảnh báo đáng chú ý.

Nếu Gate không đạt:
- REWORK: xử lý các lỗi mandatory còn tồn tại, chạy lại QC và Gate.
- HOLD: tạm dừng phát hành nếu còn vấn đề chưa thể tự động hoặc thủ công giải quyết an toàn.
```

(b) Dùng AI viết code? Ghi 3 dòng: prompt chính, cách bạn kiểm code AI, 1 lần AI sai. Không dùng: ghi "không dùng".
```
- Có dùng AI - Claude cho tóm tắt quy trình làm bài, tạo nodule cho pipeline và tổng hợp mã lỗi, ảnh cho mục 2 .

- Prompt sử dụng:
"
dựa theo những gì bạn đã biết về các thông tin có trong Repo, hãy viết cho chương trình pipeline/<>/<> nhằm...(mục đích của chương trình)

Chỉ đưa ra chương trình khi có thông tin chắc chắn và đảm bảo đúng với kết quả cầu ra đúng với yêu cầu của repo cho phần liên quan,  follow theo các rules đã đặt ra dưới đây: 
- Viết script Python 3 kiểm thư mục labels/ (YOLO txt).                  # (1) định dạng vào
- Mỗi dòng: id x_tam y_tam rong cao, tỉ lệ 0-1. Ví dụ: 1 0.50 0.50 0.20 0.30
- In "tên file, số dòng, lý do" cho dòng có box tràn ảnh.               # (2) quy tắc kiểm + (3) kiểu in ra
- Chỉ đọc file, không sửa, không xóa. Dưới 12 dòng.                      # (4) giới hạn an toàn
- Giải thích từng dòng bằng tiếng Việt.
- Dựa theo template đã có không tự sửa chương trình
- Với các điều in ra kết quả thành công, hãy đảm bảo có điều kiện phụ để in ra lỗi.
"

- Không có lỗi sảy ra 
```

*(Thưởng +2, tùy chọn)* CVAT: lọc `width < 20`, ảnh/số box khớp, đối chiếu `BOX_TINY` (xem docs/CVAT_FILTER.md), 1 câu về `can_review`.
