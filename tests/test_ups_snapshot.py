# -*- coding: utf-8 -*-
"""اختبارات منطق لقطة UPS — تعمل دون البوابة أو المتصفح."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import ups_core as core


def row(req_id, **kw):
    base = {
        "رقم الطلب": req_id,
        "رقم الرخصة": "LIC-" + str(req_id),
        "تاريخ الطلب": "01/01/1448 هـ",
        "اسم المستفيد": "مستفيد",
        "الحي": "حي",
        "حالة الطلب": "مكتمل",
        "نوع الخدمة": "رخصة بناء",
    }
    base.update(kw)
    return base


def make_df(rows):
    df, _ = core.frame_from_rows(rows, core.COLS)
    return df


def valid_state(**over):
    state = {
        "data_origin": "live_sync",
        "bootstrap": False,
        "verified": True,
        "coverage": 1.0,
        "pages_expected": 2,
        "pages_completed": 2,
        "cross_page_duplicate_count": 0,
        "blank_ids": 0,
        "conflicting_duplicates": [],
        "last_success": "2026-01-01T00:00:00+03:00",
        "sync_started_at": "2026-01-01T00:00:00+03:00",
        "sync_finished_at": "2026-01-01T00:10:00+03:00",
        "source": "test",
    }
    state.update(over)
    return state


class DiffTests(unittest.TestCase):
    def test_deletion_only(self):
        old = make_df([row("1"), row("2")])
        new = make_df([row("1")])
        diff = core.diff_snapshots(old, new)
        self.assertEqual(diff["deleted_count"], 1)
        self.assertEqual(diff["deleted"], ["2"])
        self.assertEqual(diff["added_count"], 0)
        self.assertEqual(diff["modified_count"], 0)

    def test_non_status_field_change_detected(self):
        old = make_df([row("1", الحي="الأول")])
        new = make_df([row("1", الحي="الثاني")])
        diff = core.diff_snapshots(old, new)
        self.assertEqual(diff["modified_count"], 1)
        self.assertEqual(diff["modified_by_field"], {"الحي": 1})

    def test_added_and_status_change(self):
        old = make_df([row("1", **{"حالة الطلب": "قيد العمل"})])
        new = make_df([row("1", **{"حالة الطلب": "مكتمل"}), row("2")])
        diff = core.diff_snapshots(old, new)
        self.assertEqual(diff["added_count"], 1)
        self.assertEqual(diff["modified_count"], 1)
        self.assertEqual(diff["modified_by_field"], {"حالة الطلب": 1})


class NormalizationTests(unittest.TestCase):
    def test_leading_zeros_preserved(self):
        self.assertEqual(core.normalize_request_id("00123"), "00123")
        self.assertEqual(core.normalize_request_id(" 00123 "), "00123")
        self.assertEqual(core.normalize_request_id(123.0), "123")
        df = make_df([row("00123")])
        self.assertEqual(df.iloc[0][core.KEY], "00123")

    def test_blank_id_rejected(self):
        with self.assertRaises(core.SnapshotError):
            core.normalize_rows([row(""), row("1")])

    def test_conflicting_duplicate_rejected(self):
        with self.assertRaises(core.SnapshotError):
            core.normalize_rows([row("1", الحي="أ"), row("1", الحي="ب")])

    def test_exact_duplicate_dropped_and_counted(self):
        rows, stats = core.normalize_rows([row("1"), row("1")])
        self.assertEqual(len(rows), 1)
        self.assertEqual(stats["exact_duplicates_dropped"], 1)


class CompletionTests(unittest.TestCase):
    def _pages(self, n, total=None):
        out = {}
        for p in range(1, n + 1):
            out[p] = {
                "rows": [row(f"{p}0{i}") for i in range(2)],
                "reported_page": p,
                "total_pages": n,
                "total_results": total,
                "fingerprint": core.page_fingerprint([row(f"{p}0{i}") for i in range(2)]),
                "error": None,
            }
        return out

    def test_complete_pull_ok(self):
        pages = self._pages(3, total=6)
        res = core.validate_sync_completion(pages, 3, reported_total=6)
        self.assertTrue(res["ok"], res["issues"])
        self.assertEqual(res["coverage"], 1.0)
        self.assertEqual(res["unique_ids"], 6)

    def test_missing_page_fails(self):
        pages = self._pages(3, total=6)
        pages.pop(3)
        res = core.validate_sync_completion(pages, 3, reported_total=6)
        self.assertFalse(res["ok"])
        self.assertLess(res["coverage"], 1.0)

    def test_duplicate_page_content_fails(self):
        pages = self._pages(2, total=4)
        pages[2]["rows"] = pages[1]["rows"]
        pages[2]["fingerprint"] = pages[1]["fingerprint"]
        res = core.validate_sync_completion(pages, 2, reported_total=4)
        self.assertFalse(res["ok"])
        self.assertTrue(any("مكرر" in i for i in res["issues"]))

    def test_cross_page_duplicate_id_fails(self):
        pages = self._pages(2, total=4)
        pages[2]["rows"] = [row("101"), row("999")]
        pages[2]["fingerprint"] = core.page_fingerprint(pages[2]["rows"])
        res = core.validate_sync_completion(pages, 2, reported_total=4)
        self.assertFalse(res["ok"])
        self.assertEqual(res["cross_page_duplicate_count"], 1)

    def test_total_changes_during_pull_fails(self):
        pages = self._pages(2, total=4)
        pages[2]["total_results"] = 5
        res = core.validate_sync_completion(pages, 2, reported_total=4)
        self.assertFalse(res["ok"])

    def test_pages_change_during_pull_fails(self):
        pages = self._pages(2, total=4)
        pages[2]["total_pages"] = 3
        res = core.validate_sync_completion(pages, 2, reported_total=4)
        self.assertFalse(res["ok"])

    def test_empty_pull_needs_explicit_zero(self):
        res = core.validate_sync_completion({}, 0, reported_total=0, explicit_zero=False)
        self.assertFalse(res["ok"])
        res = core.validate_sync_completion({}, 0, reported_total=0, explicit_zero=True)
        self.assertTrue(res["ok"], res["issues"])


class CommitAndStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.path = os.path.join(self.dir, "ups_requests.xlsx")
        self.prev = os.path.join(self.dir, "ups_prev.xlsx")
        self.state_path = os.path.join(self.dir, "ups_sync_state.json")

    def tearDown(self):
        self.tmp.cleanup()

    def _commit(self, rows, state=None, require_verified=False):
        return core.commit_snapshot(
            make_df(rows), self.path, self.prev, self.state_path,
            state or valid_state(), core.COLS, require_verified=require_verified,
        )

    def test_matching_snapshot_state_updates_success_time(self):
        res = self._commit([row("1"), row("2")], valid_state(last_success="2026-01-01T00:10:00+03:00"))
        self.assertEqual(res["rows"], 2)
        check = core.verify_snapshot_state(core.load_state(self.state_path), self.path)
        self.assertTrue(check["ok"], check["issues"])
        self.assertEqual(check["state_rows"], 2)
        self.assertEqual(check["sha256"], res["sha256"])

    def test_previous_snapshot_kept(self):
        self._commit([row("1")])
        first = core.file_sha256(self.path)
        self._commit([row("1"), row("2")])
        self.assertTrue(os.path.exists(self.prev))
        self.assertEqual(core.file_sha256(self.prev), first)

    def test_write_failure_keeps_current_and_state(self):
        self._commit([row("1")])
        old_file = core.file_sha256(self.path)
        old_state = core.load_state(self.state_path)
        with mock.patch.object(pd.DataFrame, "to_excel", side_effect=OSError("boom")):
            with self.assertRaises(Exception):
                self._commit([row("1"), row("2")])
        self.assertEqual(core.file_sha256(self.path), old_file)
        self.assertEqual(core.load_state(self.state_path), old_state)

    def test_unverified_state_does_not_replace_current(self):
        self._commit([row("1")])
        old_file = core.file_sha256(self.path)
        with self.assertRaises(core.SnapshotError):
            self._commit([row("1"), row("2")],
                         valid_state(coverage=0.5, pages_completed=1),
                         require_verified=True)
        self.assertEqual(core.file_sha256(self.path), old_file)

    def test_state_rows_mismatch_rejected(self):
        self._commit([row("1")])
        state = core.load_state(self.state_path)
        state["rows"] = 99
        core.write_state_atomic(state, self.state_path)
        check = core.verify_snapshot_state(core.load_state(self.state_path), self.path)
        self.assertFalse(check["ok"])
        self.assertTrue(any("عدد صفوف" in i for i in check["issues"]))

    def test_state_hash_mismatch_rejected(self):
        self._commit([row("1")])
        state = core.load_state(self.state_path)
        state["snapshot_sha256"] = "0" * 64
        core.write_state_atomic(state, self.state_path)
        check = core.verify_snapshot_state(core.load_state(self.state_path), self.path)
        self.assertFalse(check["ok"])
        self.assertTrue(any("بصمة" in i for i in check["issues"]))

    def test_bootstrap_state_rejected(self):
        self._commit([row("1")])
        state = core.load_state(self.state_path)
        state["bootstrap"] = True
        core.write_state_atomic(state, self.state_path)
        check = core.verify_snapshot_state(core.load_state(self.state_path), self.path)
        self.assertFalse(check["ok"])

    def test_missing_state_rejected(self):
        self._commit([row("1")])
        os.remove(self.state_path)
        check = core.verify_snapshot_state({}, self.path)
        self.assertFalse(check["ok"])


class LockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "ups_sync.lock")

    def tearDown(self):
        self.tmp.cleanup()

    def test_concurrent_pull_blocked(self):
        first = core.RunLock(self.path)
        ok, _ = first.acquire()
        self.assertTrue(ok)
        try:
            second = core.RunLock(self.path)
            ok2, msg = second.acquire()
            self.assertFalse(ok2)
            self.assertIn("أخرى", msg)
        finally:
            first.release()

    def test_live_lock_not_deleted_by_age(self):
        first = core.RunLock(self.path)
        self.assertTrue(first.acquire()[0])
        try:
            os.utime(self.path, (0, 0))  # عمر قديم جدًا
            second = core.RunLock(self.path)
            ok, _ = second.acquire()
            self.assertFalse(ok, "يجب ألا يُحذف قفل عملية حية مهما كان عمره")
        finally:
            first.release()

    def test_dead_lock_replaced(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"pid": 2147483000, "started_at": "2020-01-01T00:00:00"}, f)
        lock = core.RunLock(self.path)
        ok, _ = lock.acquire()
        self.assertTrue(ok)
        lock.release()
        self.assertFalse(os.path.exists(self.path))


class DashboardMetricTests(unittest.TestCase):
    def test_hijri_year_arabic_indic_digits(self):
        self.assertEqual(core.extract_hijri_year("١٧ - ربيع الآخر - ١٤٤٨ هـ"), "هـ 1448")
        self.assertEqual(core.extract_hijri_year("١ - جمادى الآخرة - ١٤٣١ هـ"), "هـ 1431")

    def test_hijri_year_latin_digits_and_fallback(self):
        self.assertEqual(core.extract_hijri_year("17 - ربيع الآخر - 1448 هـ"), "هـ 1448")
        self.assertEqual(core.extract_hijri_year("1448/04/17"), "هـ 1448")

    def test_hijri_year_missing(self):
        self.assertEqual(core.extract_hijri_year(""), "غير محدد")
        self.assertEqual(core.extract_hijri_year("تاريخ غير معروف"), "غير محدد")

    def test_active_excludes_closed_statuses(self):
        df = make_df([
            row("1", **{"حالة الطلب": "مكتمل"}),
            row("2", **{"حالة الطلب": "مرفوض"}),
            row("3", **{"حالة الطلب": "ملغي"}),
            row("4", **{"حالة الطلب": "قيد العمل - المهندس"}),
            row("5", **{"حالة الطلب": "بانتظار السداد"}),
            row("6", **{"حالة الطلب": "استكمال التعديلات"}),
        ])
        self.assertEqual(int(core.active_request_mask(df).sum()), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
