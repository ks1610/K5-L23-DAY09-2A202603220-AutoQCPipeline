"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


# def run(ds, cfg):
#     # TODO: duyệt từng file nhãn, từng dòng
#     raise NotImplementedError("check label_format chưa làm")


CHECK = "label_format"


def run(ds, cfg):
    p = cfg["label_format"]                          # ngưỡng lấy từ config
    n_classes = len(ds.classes)
    issues = []
    for lf in ds.label_files():                      # mỗi file nhãn .txt
        stem = lf.stem
        lines = ds.read_label_lines(stem) or []      # [(số dòng, nội dung)], bỏ dòng trống
        seen = []                                    # box hợp lệ đã gặp trong file này
        size = None                                  # (W, H) ảnh, lấy lười 1 lần/file
        size_loaded = False
        for no, raw in lines:
            try:
                cls, cx, cy, w, h = parse_yolo_line(raw)
            except ValueError as e:
                issues.append(Issue(CHECK, ERROR, "BAD_FORMAT", stem, str(e), line=no))
                continue
            if not 0 <= cls < n_classes:
                issues.append(Issue(CHECK, ERROR, "BAD_CLASS_ID", stem,
                                    f"id {cls} ngoài 0..{n_classes - 1}", line=no))
                continue
            if w <= 0 or h <= 0:
                issues.append(Issue(CHECK, ERROR, "BOX_ZERO", stem,
                                    "w hoặc h <= 0", line=no))
                continue

            # mép trái = cx - w/2, mép phải = cx + w/2 (tương tự cho trên/dưới)
            over = max(-(cx - w / 2), (cx + w / 2) - 1,
                       -(cy - h / 2), (cy + h / 2) - 1, 0.0)
            if over > p["overflow_tol"]:
                issues.append(Issue(CHECK, ERROR, "BOX_OUT_OF_IMAGE", stem,
                                    "box tràn ảnh", line=no,
                                    extra={"overflow": round(over, 4)}))

            box = (cx, cy, w, h)
            if any(c == cls and iou_xywh(box, b) > p["dup_box_iou"] for c, b in seen):
                issues.append(Issue(CHECK, ERROR, "DUP_BOX", stem,
                                    "trùng box cùng lớp với dòng trước", line=no))
            seen.append((cls, box))

            if w * h > p["max_box_frac"]:
                issues.append(Issue(CHECK, WARN, "BOX_HUGE", stem,
                                    "box quá lớn", line=no))

            if "min_box_px" in p:
                if not size_loaded:
                    size = ds.image_size(stem)
                    size_loaded = True
                if size is not None:                 # ảnh không mở được thì bỏ qua check này
                    W, H = size
                    if min(w * W, h * H) < p["min_box_px"]:
                        issues.append(Issue(CHECK, WARN, "BOX_TINY", stem,
                                            "box quá nhỏ", line=no))
    return issues