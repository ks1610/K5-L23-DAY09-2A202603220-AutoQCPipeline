"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401
from ..model_cache import get_preds  # noqa: F401


# def run(ds, cfg, preds=None):
#     # TODO
#     raise NotImplementedError("check second_opinion chưa làm")

CHECK = "second_opinion"


def run(ds, cfg, preds=None):
    p = cfg["second_opinion"]                              # ngưỡng lấy từ config
    if preds is None:
        preds = get_preds(ds, cfg, "checker")              # dự đoán của model lớn
    n_classes = len(ds.classes)
    issues = []

    for img in ds.image_files():                           # duyệt theo thứ tự tên ảnh
        stem = img.stem
        if stem not in preds:                              # không có dự đoán: bỏ qua
            continue
        if ds.read_label_lines(stem) is None:              # không có file nhãn: bỏ qua
            continue
        size = ds.image_size(stem)
        if size is None:                                   # không mở được ảnh: không tính diện tích px
            continue
        W, H = size
        pred_list = preds[stem]
        labels = ds.valid_boxes(stem)                      # [(lớp, cx, cy, w, h)], đã bỏ dòng hỏng

        # 1) Dự đoán tin cậy và đủ lớn -> so với nhãn
        for r in pred_list:
            rc, conf, rcx, rcy, rw, rh = r
            if conf < p["conf"] or rw * W * rh * H < p["min_area_px"]:
                continue                                   # dự đoán yếu hoặc quá nhỏ: bỏ qua
            rbox = (rcx, rcy, rw, rh)

            # nhãn có IoU >= iou_missing với dự đoán này
            cands = []
            for lc, cx, cy, w, h in labels:
                v = iou_xywh(rbox, (cx, cy, w, h))
                if v >= p["iou_missing"]:
                    cands.append((lc, v))

            if not cands:                                  # model thấy vật mà nhãn không có box
                issues.append(Issue(CHECK, WARN, "POSSIBLE_MISSING", stem,
                                    f"model thấy lớp {rc} nhưng không có nhãn",
                                    extra={"conf": round(conf, 4)}))
                continue

            same = [v for lc, v in cands if lc == rc]
            if same:
                best = max(same)
                if best < p["iou_loose"]:                  # đúng lớp nhưng box lệch
                    issues.append(Issue(CHECK, WARN, "POSSIBLE_LOOSE_BOX", stem,
                                        f"box lớp {rc} lệch (IoU {best:.2f})",
                                        extra={"conf": round(conf, 4), "iou": round(best, 4)}))
                # best >= iou_loose: nhãn đúng lớp đã phủ vật này, không cờ
                continue

            # không có nhãn cùng lớp: chỉ cờ khi nhãn khác lớp khớp rõ ràng
            other = max(v for _, v in cands)
            if other >= p["iou_match"]:
                issues.append(Issue(CHECK, WARN, "POSSIBLE_WRONG_CLASS", stem,
                                    f"model cho lớp {rc}, nhãn khác lớp (IoU {other:.2f})",
                                    extra={"conf": round(conf, 4), "iou": round(other, 4)}))
            # IoU trong [iou_missing, iou_match): mơ hồ, không cờ ở đây

        # 2) Nhãn không khớp vật nào model thấy -> nghi false positive
        for no, raw in ds.read_label_lines(stem):          # số dòng gốc, kể cả dòng hỏng
            try:
                lc, cx, cy, w, h = parse_yolo_line(raw)
            except ValueError:
                continue                                   # dòng hỏng do check khác báo
            if not 0 <= lc < n_classes:
                continue
            best = max((iou_xywh((cx, cy, w, h), (r[2], r[3], r[4], r[5]))
                        for r in pred_list if r[1] >= p["fp_conf"]), default=0.0)
            if best < p["iou_missing"]:
                issues.append(Issue(CHECK, WARN, "POSSIBLE_FALSE_POS", stem,
                                    f"nhãn lớp {lc} không khớp vật nào model thấy",
                                    line=no, extra={"iou": round(best, 4)}))
    return issues