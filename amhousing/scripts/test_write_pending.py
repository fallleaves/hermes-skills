#!/usr/bin/env python3
"""Unit tests for write_pending.py (r17-n1).

The script under test lives in the same directory as this file — resolve it
relative to __file__ so the test never hardcodes a profile path.
"""
import contextlib
import importlib.util
import io
import json
import os
import sys
import unittest
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "write_pending", os.path.join(_HERE, "write_pending.py")
)
wp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wp)


def _argv(target_id):
    return [
        "write_pending.py",
        "--house-id", "h1",
        "--target-model", "RoomFixture",
        "--target-id", target_id,
        "--confidence", "0.45",
        "--proposed-data", '{"condition":"fair"}',
    ]


def _run_main(argv):
    out = io.StringIO()
    with mock.patch("sys.argv", argv), contextlib.redirect_stdout(out):
        try:
            wp.main()
        except SystemExit as e:
            return e.code, out.getvalue()
    return None, out.getvalue()


class TargetIdValidationTest(unittest.TestCase):
    """r17-n1: an empty --target-id must be rejected up front.

    The old `if args.target_id:` truthiness guard let `--target-id ""`
    (required=True only guarantees presence, not non-emptiness) skip the
    target-existence verification and INSERT a pending row with
    targetId = "" — a row the approval flow can never APPLY (it can only
    update existing records), i.e. a permanently un-approvable parked
    proposal. The guard must reject "" BEFORE any DB work.
    """

    def test_empty_target_id_exits_1_with_json_error_and_no_db_access(self):
        code, out = _run_main(_argv(""))

        self.assertEqual(code, 1)
        payload = json.loads(out)
        self.assertFalse(payload["ok"])
        self.assertIn("target-id", payload["error"])
        # the rejection must happen before get_db() — no connection, no
        # INSERT of the un-approvable row
        with mock.patch.object(wp, "get_db", side_effect=AssertionError("get_db called")) as db:
            code2, out2 = _run_main(_argv(""))
            self.assertEqual(code2, 1)
            db.assert_not_called()

    def test_non_empty_target_id_passes_the_guard(self):
        # a real id must NOT be rejected by the new guard — it reaches the
        # DB layer (house lookup), where a missing house exits 1 normally
        fake_con = mock.Mock()
        fake_con.execute.return_value.fetchone.return_value = None  # house not found
        with mock.patch.object(wp, "get_db", return_value=fake_con) as db:
            code, out = _run_main(_argv("fixture-1"))

        self.assertEqual(code, 1)
        payload = json.loads(out)
        self.assertFalse(payload["ok"])
        # reached the DB (guard let it through) — and the error is the
        # house-not-found path, not a target-id rejection
        self.assertIn("house h1 not found", payload["error"])
        self.assertNotIn("target-id", payload["error"])
        db.assert_called_once()


if __name__ == "__main__":
    unittest.main()
