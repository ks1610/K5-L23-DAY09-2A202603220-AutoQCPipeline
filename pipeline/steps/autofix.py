"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


# def fix(ds, issues, cfg):
#     # TODO
#     raise NotImplementedError("autofix chưa làm")


DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}   # xoá cả dòng
REMOVE_PREFIXES = ("DUP_IMAGE", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE")  # xoá ảnh + nhãn


def _clip(text):
    """Cắt box về trong [0,1]. Trả về dòng mới, None nếu box không còn diện tích."""
    try:
        cls, cx, cy, w, h = parse_yolo_line(text)
    except ValueError:
        return text                                   # không parse được: giữ nguyên
    x1, x2 = max(0.0, cx - w / 2), min(1.0, cx + w / 2)
    y1, y2 = max(0.0, cy - h / 2), min(1.0, cy + h / 2)
    nw, nh = x2 - x1, y2 - y1
    if nw <= 0 or nh <= 0:
        return None                                   # nằm hẳn ngoài ảnh: xoá dòng
    return f"{cls} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {nw:.6f} {nh:.6f}"


def fix(ds, issues, cfg):
    changes = []

    def log(image, line, action, before, after):
        changes.append({"image": image, "line": line, "action": action,
                        "before": before, "after": after})

    errors = [i for i in issues if i.severity == ERROR]   # không đụng cảnh báo WARN

    # 1) Xoá ảnh lỗi cùng nhãn của nó
    removed = set()
    for i in errors:
        if i.code.startswith(REMOVE_PREFIXES) and i.image not in removed:
            removed.add(i.image)
            img = ds.image_path(i.image)
            if img is not None:
                img.unlink()
                lp = ds.label_path(i.image)
                if lp.exists():
                    lp.unlink()
                log(i.image, None, "remove_image", i.code, "(đã xoá ảnh và nhãn)")

    # 2) Gom lỗi theo file và số dòng GỐC (bỏ qua ảnh đã xoá)
    line_codes = DROP_CODES | {"BOX_OUT_OF_IMAGE"}
    by_img = defaultdict(lambda: defaultdict(set))
    for i in errors:
        if i.line is not None and i.code in line_codes and i.image not in removed:
            by_img[i.image][i.line].add(i.code)

    # 3) Sửa từng file nhãn, ghi MỘT lần cho mỗi file
    for lf in ds.label_files():
        stem = lf.stem
        if stem in removed:
            continue
        codes_at = by_img.get(stem, {})
        raw = lf.read_text(encoding="utf-8", errors="replace").splitlines()
        new, changed = [], False
        for no, text in enumerate(raw, start=1):    # số dòng gốc, kể cả dòng trống
            codes = codes_at.get(no, set())
            if not text.strip():
                new.append(text)                    # dòng trống: giữ nguyên, không thuộc bảng sửa
                continue
            if codes & DROP_CODES:                  # có lỗi xoá dòng: thắng, không cắt nữa
                log(stem, no, "drop_line", text, "(xoá dòng)")
                changed = True
                continue
            if "BOX_OUT_OF_IMAGE" in codes:
                clipped = _clip(text)
                if clipped is None:
                    log(stem, no, "drop_line", text, "(box nằm ngoài ảnh, xoá dòng)")
                    changed = True
                    continue
                if clipped != text:
                    log(stem, no, "clip_box", text, clipped)
                    changed = True
                new.append(clipped)
                continue
            new.append(text)
        if changed:
            lf.write_text("".join(f"{t}\n" for t in new), encoding="utf-8")

    # 4) Nhãn thiếu: KHÔNG tạo file rỗng, chỉ ghi để chuyển người gán
    seen_missing = set()
    for i in errors:
        if i.code == "MISSING_LABEL_FILE" and i.image not in removed and i.image not in seen_missing:
            seen_missing.add(i.image)
            log(i.image, None, "needs_label", "(không có file)", "chuyển người gán")

    # 5) Ghi lại tên lớp trong data.yaml theo cfg
    if any(i.code == "BAD_CLASS_NAME" for i in errors) and ds.yaml_path.exists():
        d = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        old, new_names = d.get("names"), list(cfg["classes"])
        if old != new_names:
            d["names"] = new_names
            ds.yaml_path.write_text(
                yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
            log("data.yaml", None, "rename_classes", str(old), str(new_names))

    return changes
