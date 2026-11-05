# -*- coding: utf-8 -*-
"""ups_core.py — منطق لقطة UPS القابل للاختبار (بدون متصفح).

يُستخدم من ups_sync_fast.py وdashboard.py والاختبارات:
- تطبيع أرقام الطلبات كنص مع الحفاظ على الأصفار البادئة.
- رفض المعرّفات الفارغة والتكرار المتعارض.
- مقارنة كل حقول الطلب (لا الحالة فقط).
- كتابة لقطة Excel بشكل ذرّي مع نسخة سابقة وحالة مزامنة متطابقة.
- التحقق من تطابق الملف مع الحالة (SHA-256 + عدد الصفوف).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import tempfile
import time
from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd
from zoneinfo import ZoneInfo

RIYADH = ZoneInfo("Asia/Riyadh")
COLS = ["رقم الطلب", "رقم الرخصة", "تاريخ الطلب", "اسم المستفيد", "الحي", "حالة الطلب", "نوع الخدمة"]
KEY = "رقم الطلب"
STATE_SCHEMA = 2


class SnapshotError(RuntimeError):
    """فشل تحقق أو كتابة لقطة — لا يجوز اعتمادها."""


def now_riyadh() -> datetime:
    return datetime.now(RIYADH)


def iso_riyadh(dt: datetime | None = None) -> str:
    return (dt or now_riyadh()).isoformat(timespec="seconds")


def clean_cell(value: Any) -> str:
    """تنظيف خلية: إزالة الفراغات الطرفية وتوحيد المسافات الداخلية والقيم الفارغة."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    s = str(value).replace("\u00a0", " ").replace("\u200f", "").replace("\u200e", "")
    s = " ".join(s.split())
    if s.strip().lower() in {"nan", "none", "null", "nat", "<na>"}:
        return ""
    return s


def normalize_request_id(value: Any) -> str:
    """رقم الطلب نصًا. لا يحذف الأصفار البادئة.

    القيم الرقمية التي وصلت من Excel كـ 123.0 تُعرض 123، لكن النص "00123"
    يبقى "00123" كما هو.
    """
    s = clean_cell(value)
    if not s:
        return ""
    if re.fullmatch(r"\d+\.0+", s):
        s = s.split(".", 1)[0]
    return s


def normalize_rows(rows: Iterable[Sequence[Any] | Mapping[str, Any]], cols: Sequence[str] = COLS):
    """يُعيد (list[dict], stats). يرفض المعرّف الفارغ والتكرار المتعارض.

    التكرار الحرفي (كل الحقول متطابقة) يُسقط ويُسجّل؛ التكرار المتعارض يُرفض.
    """
    normalized: list[dict[str, str]] = []
    by_key: dict[str, dict[str, str]] = {}
    first_index: dict[str, int] = {}
    exact_duplicates: list[str] = []
    conflicts: list[str] = []
    blank_indices: list[int] = []

    for idx, row in enumerate(rows):
        if isinstance(row, Mapping):
            raw = {c: row.get(c, "") for c in cols}
        else:
            values = list(row)
            raw = {c: (values[i] if i < len(values) else "") for i, c in enumerate(cols)}
        item = {c: clean_cell(raw.get(c, "")) for c in cols}
        item[KEY] = normalize_request_id(item.get(KEY, ""))
        k = item[KEY]
        if not k:
            blank_indices.append(idx)
            continue
        if k in by_key:
            if all(by_key[k].get(c, "") == item.get(c, "") for c in cols):
                exact_duplicates.append(k)
                continue
            conflicts.append(k)
            continue
        by_key[k] = item
        first_index[k] = idx
        normalized.append(item)

    if blank_indices:
        raise SnapshotError(
            "معرّفات طلبات فارغة: " + ", ".join(str(i) for i in blank_indices[:20]) +
            (f" ... (+{len(blank_indices) - 20})" if len(blank_indices) > 20 else "")
        )
    if conflicts:
        uniq = sorted(set(conflicts))
        raise SnapshotError(
            "تكرار متعارض في رقم الطلب (نفس المفتاح بحقول مختلفة): " + ", ".join(uniq[:20]) +
            (f" ... (+{len(uniq) - 20})" if len(uniq) > 20 else "")
        )

    stats = {
        "rows_input": idx + 1 if "idx" in locals() else 0,
        "rows_unique": len(normalized),
        "exact_duplicates_dropped": len(exact_duplicates),
        "exact_duplicate_ids": sorted(set(exact_duplicates))[:20],
        "conflicting_duplicates": [],
        "blank_ids": 0,
    }
    return normalized, stats


def frame_from_rows(rows: Iterable[Sequence[Any] | Mapping[str, Any]], cols: Sequence[str] = COLS):
    normalized, stats = normalize_rows(rows, cols)
    normalized.sort(key=lambda r: r[KEY])
    df = pd.DataFrame(normalized, columns=list(cols), dtype="object")
    for c in cols:
        df[c] = df[c].astype("string").fillna("")
    return df, stats


def validate_frame(df: pd.DataFrame, cols: Sequence[str] = COLS) -> dict[str, Any]:
    """يتحقق من إطار موجود ويُعيد إحصاءات. يرفض الفراغ/التعارض."""
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise SnapshotError("أعمدة ناقصة في اللقطة: " + ", ".join(missing))
    rows = []
    for _, r in df.iterrows():
        rows.append({c: r.get(c, "") for c in cols})
    _, stats = normalize_rows(rows, cols)
    return stats


def read_snapshot(path: str, cols: Sequence[str] = COLS) -> pd.DataFrame:
    """يقرأ Excel كنص (بما يحفظ الأصفار البادئة) ويتحقق من المفاتيح."""
    if not os.path.exists(path):
        raise SnapshotError(f"ملف اللقطة غير موجود: {path}")
    try:
        df = pd.read_excel(path, dtype=str, keep_default_na=False)
    except Exception as e:
        raise SnapshotError(f"تعذر قراءة {path}: {e}") from e
    # إزالة عمود الفهرس غير المقصود إن وُجد
    if "Unnamed: 0" in df.columns and KEY not in df.columns:
        df = df.drop(columns=["Unnamed: 0"])
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise SnapshotError("أعمدة ناقصة في اللقطة: " + ", ".join(missing))
    normalized, _ = normalize_rows(
        ({c: r[c] for c in cols} for _, r in df[list(cols)].iterrows()), cols
    )
    normalized.sort(key=lambda r: r[KEY])
    out = pd.DataFrame(normalized, columns=list(cols), dtype="object")
    for c in cols:
        out[c] = out[c].astype("string").fillna("")
    return out


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def diff_snapshots(old_df: pd.DataFrame | None, new_df: pd.DataFrame, cols: Sequence[str] = COLS):
    """مقارنة كل الحقول. يُعيد المضاف/المحذوف/المعدل وتوزيع الحقول المتغيرة."""
    old_map: dict[str, dict[str, str]] = {}
    if old_df is not None and len(old_df):
        for _, r in old_df.iterrows():
            k = normalize_request_id(r.get(KEY, ""))
            if k:
                old_map[k] = {c: clean_cell(r.get(c, "")) for c in cols}
    new_map: dict[str, dict[str, str]] = {}
    for _, r in new_df.iterrows():
        k = normalize_request_id(r.get(KEY, ""))
        if k:
            new_map[k] = {c: clean_cell(r.get(c, "")) for c in cols}

    added = sorted(set(new_map) - set(old_map))
    deleted = sorted(set(old_map) - set(new_map))
    modified: list[str] = []
    by_field: dict[str, int] = {}
    for k in sorted(set(old_map) & set(new_map)):
        changed = [c for c in cols if old_map[k].get(c, "") != new_map[k].get(c, "")]
        if changed:
            modified.append(k)
            for c in changed:
                by_field[c] = by_field.get(c, 0) + 1
    return {
        "added": added,
        "deleted": deleted,
        "modified": modified,
        "added_count": len(added),
        "deleted_count": len(deleted),
        "modified_count": len(modified),
        "modified_by_field": dict(sorted(by_field.items(), key=lambda x: -x[1])),
        "old_rows": len(old_map),
        "new_rows": len(new_map),
        "sample_added": added[:20],
        "sample_deleted": deleted[:20],
        "sample_modified": modified[:20],
    }


def page_fingerprint(rows: Iterable[Sequence[Any]]) -> str:
    """بصمة محتوى الصفحة تعتمد على أرقام الطلبات مرتبة (لكشف تكرار محتوى صفحة)."""
    ids = []
    for r in rows:
        if isinstance(r, Mapping):
            ids.append(normalize_request_id(r.get(KEY, "")))
        else:
            vals = list(r)
            ids.append(normalize_request_id(vals[0] if vals else ""))
    ids = [x for x in ids if x]
    payload = "\n".join(sorted(ids)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_sync_completion(
    page_results: Mapping[int, Mapping[str, Any]],
    expected_pages: int,
    reported_total: int | None = None,
    page_size: int | None = None,
    explicit_zero: bool = False,
    cols: Sequence[str] = COLS,
) -> dict[str, Any]:
    """حارس الاعتماد: 100% صفحات، لا صفحة مفقودة/مكررة/متغيرة، ولا مفاتيح مكررة.

    page_results: {page_number: {"rows": [...], "reported_page": n,
                                  "total_pages": n, "total_results": n|None,
                                  "fingerprint": str, "url": str, "error": str|None}}
    """
    issues: list[str] = []
    expected = set(range(1, int(expected_pages) + 1))
    got = set(int(p) for p in page_results.keys())
    missing = sorted(expected - got)
    extra = sorted(got - expected)
    if missing:
        issues.append(f"صفحات مفقودة: {len(missing)} (أولها {missing[:10]})")
    if extra:
        issues.append(f"صفحات خارج النطاق: {extra[:10]}")

    failed = []
    for p, r in page_results.items():
        if r.get("error"):
            failed.append((int(p), str(r.get("error"))[:120]))
        rp = r.get("reported_page")
        if rp is not None and int(rp) != int(p):
            issues.append(f"صفحة {p}: البوابة أعلنت صفحة {rp} — محتوى/تنقل غير مطابق")
    if failed:
        issues.append(f"صفحات فشلت: {len(failed)} (أولها {failed[:10]})")

    # تكرار محتوى صفحة (فشل تنقل يعيد الصفحة السابقة)
    by_fp: dict[str, list[int]] = {}
    for p, r in page_results.items():
        fp = r.get("fingerprint") or page_fingerprint(r.get("rows") or [], cols)
        if fp and (r.get("rows") or []):
            by_fp.setdefault(fp, []).append(int(p))
    dup_pages = {fp: pages for fp, pages in by_fp.items() if len(pages) > 1}
    if dup_pages:
        groups = list(dup_pages.values())
        issues.append(f"صفحات بمحتوى مكرر (تنقل فاشل): {groups[:10]}")

    # تكرار رقم الطلب بين الصفحات
    key_pages: dict[str, set[int]] = {}
    for p, r in page_results.items():
        for row in r.get("rows") or []:
            if isinstance(row, Mapping):
                k = normalize_request_id(row.get(KEY, ""))
            else:
                vals = list(row)
                k = normalize_request_id(vals[0] if vals else "")
            if k:
                key_pages.setdefault(k, set()).add(int(p))
    cross = {k: sorted(v) for k, v in key_pages.items() if len(v) > 1}
    if cross:
        issues.append(
            f"أرقام طلب مكررة بين صفحات مختلفة: {len(cross)} "
            f"(أولها {list(cross.items())[:10]})"
        )

    # ثبات إجمالي الصفحات/النتائج أثناء السحب
    total_pages_seen = {
        int(r["total_pages"]) for r in page_results.values()
        if r.get("total_pages") is not None
    }
    if total_pages_seen and total_pages_seen != {int(expected_pages)}:
        issues.append(f"عدد الصفحات تغير أثناء السحب: {sorted(total_pages_seen)} بدل {expected_pages}")
    totals_seen = {
        int(r["total_results"]) for r in page_results.values()
        if r.get("total_results") is not None
    }
    if len(totals_seen) > 1:
        issues.append(f"إجمالي النتائج تغير أثناء السحب: {sorted(totals_seen)}")
    if reported_total is not None and totals_seen and totals_seen != {int(reported_total)}:
        issues.append(f"إجمالي النتائج في الصفحات {sorted(totals_seen)} لا يطابق البداية {reported_total}")

    unique_keys = len(key_pages)
    row_sum = sum(len(r.get("rows") or []) for r in page_results.values())
    if row_sum != unique_keys:
        issues.append(
            f"مجموع صفوف الصفحات {row_sum} لا يطابق عدد الطلبات الفريدة {unique_keys} "
            "(تكرار صفوف داخل/بين الصفحات)"
        )
    if reported_total is not None:
        if unique_keys != int(reported_total):
            issues.append(
                f"عدد الطلبات الفريدة {unique_keys} لا يطابق إجمالي البوابة {reported_total}"
            )

    if expected_pages == 0:
        if not explicit_zero:
            issues.append("سحب فارغ دون تأكيد صريح من البوابة أن الإجمالي صفر")
    elif unique_keys == 0:
        issues.append("لم تُقرأ أي طلبات من الصفحات رغم وجود صفحات متوقعة")

    completed = len(expected & got)
    coverage = completed / expected_pages if expected_pages else (1.0 if explicit_zero else 0.0)
    if expected_pages and completed != expected_pages:
        issues.append(f"التغطية {completed}/{expected_pages} وليست 100%")

    return {
        "ok": not issues,
        "issues": issues,
        "pages_expected": int(expected_pages),
        "pages_completed": int(completed),
        "coverage": round(float(coverage), 6),
        "unique_ids": int(unique_keys),
        "duplicate_page_groups": list(dup_pages.values())[:20],
        "cross_page_duplicates": dict(list(cross.items())[:20]),
        "cross_page_duplicate_count": len(cross),
        "failed_pages": failed[:50],
        "reported_total": reported_total,
        "totals_seen": sorted(totals_seen),
        "total_pages_seen": sorted(total_pages_seen),
    }


def _replace_file(src: str, dst: str) -> None:
    """استبدال ذرّي مع إعادة محاولة قصيرة (Windows قد يقفل الملف لحظياً)."""
    last: Exception | None = None
    for _ in range(8):
        try:
            os.replace(src, dst)
            return
        except PermissionError as e:  # pragma: no cover - يعتمد على نظام الملفات
            last = e
            time.sleep(0.25)
    if last:
        raise last
    os.replace(src, dst)


def _write_json_atomic(obj: Mapping[str, Any], path: str) -> None:
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".state-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        with open(tmp, encoding="utf-8") as f:
            json.load(f)
        _replace_file(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def load_state(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_state_atomic(state: Mapping[str, Any], path: str) -> None:
    _write_json_atomic(state, path)


def validate_state_fields(state: Mapping[str, Any]) -> list[str]:
    """فحص حقول الحالة الدالة على اكتمال السحب (بدون قراءة الملف)."""
    issues: list[str] = []
    if state.get("bootstrap") is True:
        issues.append("الحالة مصدرها bootstrap وليست سحبًا حيًا")
    if state.get("data_origin") != "live_sync":
        issues.append("مصدر البيانات ليس سحبًا حيًا موثقًا (data_origin != live_sync)")
    if state.get("verified") is not True:
        issues.append("اللقطة غير معلّمة كموثقة (verified != true)")
    cov = state.get("coverage")
    try:
        if cov is None or float(cov) < 1.0:
            issues.append(f"التغطية غير مكتملة: {cov}")
    except (TypeError, ValueError):
        issues.append("قيمة التغطية غير صالحة")
    pe = state.get("pages_expected")
    pc = state.get("pages_completed")
    try:
        if pe is None or pc is None or int(pc) != int(pe):
            issues.append(f"الصفحات المنجزة {pc} لا تطابق المتوقعة {pe}")
    except (TypeError, ValueError):
        issues.append("قيم الصفحات غير صالحة")
    if state.get("cross_page_duplicate_count"):
        issues.append("الحالة تسجل تكرارات بين الصفحات")
    if state.get("blank_ids"):
        issues.append("الحالة تسجل معرّفات فارغة")
    if state.get("conflicting_duplicates"):
        issues.append("الحالة تسجل تكرارات متعارضة")
    return issues


def commit_snapshot(
    new_df: pd.DataFrame,
    path: str,
    prev_path: str,
    state_path: str,
    state: Mapping[str, Any],
    cols: Sequence[str] = COLS,
    require_verified: bool = False,
) -> dict[str, Any]:
    """كتابة لقطة جديدة والتحقق منها ثم استبدال المعتمد والحالة بأمان.

    لا يلمس الملف الحالي قبل نجاح كتابة البديل وقراءته والتحقق من عدد صفوفه
    وتفرد مفاتيحه. يحتفظ بالملف السابق في prev_path. إذا فشلت كتابة الحالة
    بعد استبدال اللقطة، تُستعاد اللقطة السابقة.
    """
    stats = validate_frame(new_df, cols)
    if len(new_df) != stats["rows_unique"]:
        raise SnapshotError("عدد صفوف اللقطة لا يطابق عدد المفاتيح الفريدة")
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".ups-snapshot-", suffix=".xlsx", dir=directory)
    os.close(fd)
    state_tmp = None
    try:
        out = new_df.copy()
        for c in cols:
            out[c] = out[c].astype("string").fillna("")
        out = out[list(cols)]
        out.to_excel(tmp, index=False, engine="openpyxl")

        # 1) التحقق من الملف المؤقت قبل لمس أي ملف معتمد
        check = read_snapshot(tmp, cols)
        if len(check) != len(out):
            raise SnapshotError(f"عدد صفوف الملف المؤقت {len(check)} لا يطابق {len(out)}")
        if check[KEY].duplicated().any():
            raise SnapshotError("الملف المؤقت يحتوي أرقام طلب مكررة")
        if (check[KEY].astype(str).str.strip() == "").any():
            raise SnapshotError("الملف المؤقت يحتوي رقم طلب فارغ")
        new_hash = file_sha256(tmp)

        # 2) تجهيز الحالة والتحقق منها قبل الاستبدال
        final_state = dict(state)
        final_state.update({
            "schema_version": STATE_SCHEMA,
            "snapshot_sha256": new_hash,
            "snapshot_id": new_hash,
            "rows": int(len(check)),
            "file_rows": int(len(check)),
            "unique_ids": int(check[KEY].nunique()),
            "timezone": "Asia/Riyadh",
            "local_save": {
                "status": "ok",
                "path": os.path.basename(path),
                "rows": int(len(check)),
                "sha256": new_hash,
                "saved_at": iso_riyadh(),
            },
        })
        if require_verified:
            state_issues = validate_state_fields(final_state)
            if state_issues:
                raise SnapshotError("حالة غير موثقة: " + " | ".join(state_issues))
        fd2, state_tmp = tempfile.mkstemp(prefix=".ups-state-", suffix=".json", dir=directory)
        with os.fdopen(fd2, "w", encoding="utf-8") as f:
            json.dump(final_state, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        with open(state_tmp, encoding="utf-8") as f:
            if json.load(f).get("snapshot_sha256") != new_hash:
                raise SnapshotError("ملف الحالة المؤقت لا يطابق بصمة اللقطة")

        # 3) نسخة سابقة سليمة (لا نستبدل الحالي قبل التحقق منها)
        old_hash = None
        if os.path.exists(path):
            old_hash = file_sha256(path)
            fd3, prev_tmp = tempfile.mkstemp(prefix=".ups-prev-", suffix=".xlsx", dir=directory)
            os.close(fd3)
            try:
                with open(path, "rb") as src, open(prev_tmp, "wb") as dst:
                    for chunk in iter(lambda: src.read(1024 * 1024), b""):
                        dst.write(chunk)
                    dst.flush()
                    os.fsync(dst.fileno())
                if file_sha256(prev_tmp) != old_hash:
                    raise SnapshotError("نسخة الاحتياط المؤقتة لا تطابق الملف الحالي")
                prev_check = read_snapshot(prev_tmp, cols)
                if len(prev_check) < 1 and old_hash:
                    # قد تكون لقطة فارغة موثقة؛ نتحقق فقط من القراءة والتفرد
                    pass
                _replace_file(prev_tmp, prev_path)
            except Exception:
                try:
                    os.remove(prev_tmp)
                except OSError:
                    pass
                raise

        # 4) استبدال اللقطة ثم الحالة
        try:
            _replace_file(tmp, path)
        except Exception:
            raise
        try:
            _replace_file(state_tmp, state_path)
        except Exception:
            # استعادة اللقطة السابقة كي لا يبقى ملف بلا حالة مطابقة
            if os.path.exists(prev_path):
                restore = path + ".restore"
                with open(prev_path, "rb") as src, open(restore, "wb") as dst:
                    for chunk in iter(lambda: src.read(1024 * 1024), b""):
                        dst.write(chunk)
                _replace_file(restore, path)
            else:
                try:
                    os.remove(path)
                except OSError:
                    pass
            raise

        final_hash = file_sha256(path)
        if final_hash != new_hash:
            raise SnapshotError("بصمة الملف النهائي لا تطابق المؤقت")
        final_check = read_snapshot(path, cols)
        if len(final_check) != len(out):
            raise SnapshotError("عدد صفوف الملف النهائي لا يطابق المؤقت")
        return {
            "ok": True,
            "path": path,
            "prev_path": prev_path,
            "rows": int(len(final_check)),
            "sha256": final_hash,
            "previous_sha256": old_hash,
            "state": final_state,
            "stats": stats,
        }
    except Exception:
        for p in (tmp, state_tmp):
            if p:
                try:
                    os.remove(p)
                except OSError:
                    pass
        raise


def verify_snapshot_state(state: Mapping[str, Any] | None, path: str, cols: Sequence[str] = COLS):
    """تحقق اللوحة: الملف والحالة متطابقان، واللقطة موثقة وسحب حي مكتمل."""
    issues: list[str] = []
    result: dict[str, Any] = {
        "ok": False,
        "issues": issues,
        "path": path,
        "sha256": None,
        "rows": None,
        "state_rows": None,
        "state_sha256": None,
    }
    if not state:
        issues.append("لا توجد حالة مزامنة موثقة (ups_sync_state.json)")
    if not os.path.exists(path):
        issues.append(f"ملف اللقطة غير موجود: {os.path.basename(path)}")
        return result
    try:
        df = read_snapshot(path, cols)
        result["rows"] = int(len(df))
    except Exception as e:
        issues.append(f"تعذر قراءة/التحقق من اللقطة: {e}")
        return result
    try:
        sha = file_sha256(path)
        result["sha256"] = sha
    except Exception as e:
        issues.append(f"تعذر حساب بصمة الملف: {e}")
        sha = None

    if state:
        state_sha = state.get("snapshot_sha256") or state.get("sha256")
        state_rows = state.get("rows", state.get("file_rows"))
        result["state_sha256"] = state_sha
        result["state_rows"] = state_rows
        if not state_sha:
            issues.append("الحالة لا تحتوي بصمة SHA-256")
        elif sha and state_sha != sha:
            issues.append("بصمة الملف لا تطابق بصمة الحالة")
        if state_rows is None:
            issues.append("الحالة لا تحتوي عدد الصفوف")
        else:
            try:
                if int(state_rows) != int(len(df)):
                    issues.append(f"عدد صفوف الملف {len(df)} لا يطابق الحالة {state_rows}")
            except (TypeError, ValueError):
                issues.append("عدد الصفوف في الحالة غير رقمي")
        if state.get("bootstrap") is True:
            issues.append("الحالة مصدرها bootstrap وليست سحبًا حيًا")
        if state.get("data_origin") != "live_sync":
            issues.append("مصدر البيانات ليس سحبًا حيًا موثقًا (data_origin != live_sync)")
        if state.get("verified") is not True:
            issues.append("اللقطة غير معلّمة كموثقة (verified != true)")
        cov = state.get("coverage")
        try:
            if cov is None or float(cov) < 1.0:
                issues.append(f"التغطية غير مكتملة: {cov}")
        except (TypeError, ValueError):
            issues.append("قيمة التغطية غير صالحة")
        pe = state.get("pages_expected")
        pc = state.get("pages_completed")
        try:
            if pe is None or pc is None or int(pc) != int(pe):
                issues.append(f"الصفحات المنجزة {pc} لا تطابق المتوقعة {pe}")
        except (TypeError, ValueError):
            issues.append("قيم الصفحات غير صالحة")
        if state.get("cross_page_duplicate_count"):
            issues.append("الحالة تسجل تكرارات بين الصفحات")
        if state.get("blank_ids"):
            issues.append("الحالة تسجل معرّفات فارغة")
        if state.get("conflicting_duplicates"):
            issues.append("الحالة تسجل تكرارات متعارضة")
    result["ok"] = not issues
    return result


def pid_alive(pid: Any) -> bool:
    """هل العملية ما زالت حية؟ (بدون حذف قفل عملية حية)"""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class RunLock:
    """قفل تشغيل ذرّي. لا يحذف قفل عملية حية مهما كان عمره.

    القفل ملف JSON يحتوي pid/started_at/host. إذا كان الملف موجودًا وعملية
    صاحبه حية → يُرفض التشغيل. إذا كانت العملية ميتة → يُزال ويُعاد المحاولة.
    """

    def __init__(self, path: str):
        self.path = path
        self.held = False
        self.info: dict[str, Any] = {}

    def _read_info(self) -> dict[str, Any]:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            # قفل قديم نصي (PID فقط)
            try:
                with open(self.path, encoding="utf-8") as f:
                    raw = f.read().strip()
                return {"pid": int(raw)} if raw.isdigit() else {}
            except Exception:
                return {}

    def acquire(self) -> tuple[bool, str]:
        payload = {
            "pid": os.getpid(),
            "started_at": iso_riyadh(),
            "host": socket.gethostname(),
            "script": os.path.basename(__file__),
        }
        for _ in range(3):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                info = self._read_info()
                self.info = info
                if pid_alive(info.get("pid")):
                    return False, f"عملية سحب أخرى تعمل (pid={info.get('pid')})"
                try:
                    os.remove(self.path)
                except FileNotFoundError:
                    pass
                except OSError as e:
                    return False, f"تعذر إزالة قفل ميت: {e}"
                continue
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
            except Exception:
                try:
                    os.remove(self.path)
                except OSError:
                    pass
                raise
            self.held = True
            self.info = payload
            return True, "تم الحصول على القفل"
        return False, "تعذر الحصول على القفل"

    def release(self) -> None:
        if not self.held:
            return
        try:
            info = self._read_info()
            if int(info.get("pid", -1)) == os.getpid():
                os.remove(self.path)
        except Exception:
            pass
        finally:
            self.held = False

    def __enter__(self):
        ok, msg = self.acquire()
        if not ok:
            raise SnapshotError(msg)
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False


def state_summary(state: Mapping[str, Any] | None) -> dict[str, Any]:
    """ملخص آمن للعرض في اللوحة."""
    if not state:
        return {}
    keys = [
        "last_success", "last_attempt", "last_failure", "rows", "file_rows",
        "pages_expected", "pages_completed", "coverage", "added", "deleted",
        "modified", "modified_by_field", "duplicates", "cross_page_duplicate_count",
        "sync_started_at", "sync_finished_at", "source", "snapshot_sha256",
        "data_origin", "bootstrap", "verified", "local_save", "publish",
    ]
    return {k: state.get(k) for k in keys if k in state}
