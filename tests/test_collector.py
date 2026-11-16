"""Check dataset integrity and recording boundaries without opening a webcam."""

import csv
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from collector.app import Collector
from collector.data import COORDINATE_FIELDS, FIELDS, CollectionSession, participant_slug


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.session = CollectionSession(self.folder, "Test Person", "test")
        self.sample = dict(
            gesture="open_palm", coordinates=tuple(i / 100 for i in range(63)),
            captured_at_utc="2026-11-15T15:00:00.000+00:00", width=640, height=480,
            handedness="Right", handedness_score=0.99,
        )

    def tearDown(self):
        self.session.close()
        self.temp.cleanup()

    def read_rows(self):
        with self.session.path.open(newline="", encoding="utf-8") as file:
            return list(csv.DictReader(file))

    def test_manual_labels_metadata_coordinates_and_immediate_save(self):
        self.session.save(**self.sample)
        self.session.save(**dict(self.sample, gesture="fist"))
        # Read while the session is still open: saves must already be on disk.
        rows = self.read_rows()
        self.assertEqual(list(rows[0]), FIELDS)
        self.assertEqual([row["gesture"] for row in rows], ["open_palm", "fist"])
        self.assertEqual(rows[0]["participant_id"], "test_person")
        self.assertEqual(rows[0]["session_id"], self.session.session_id)
        self.assertEqual([float(rows[0][key]) for key in COORDINATE_FIELDS], list(self.sample["coordinates"]))
        self.assertNotEqual(rows[0]["sample_id"], rows[1]["sample_id"])
        self.assertEqual(self.session.total, 2)
        self.assertEqual(list(self.folder.iterdir()), [self.session.path])  # CSV only.

    def test_invalid_samples_do_not_create_files(self):
        for change in ({"coordinates": ()}, {"coordinates": [float("nan")] * 63}, {"gesture": "unknown"}):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    self.session.save(**dict(self.sample, **change))
        self.assertEqual(list(self.folder.iterdir()), [])
        self.assertEqual(self.session.total, 0)

    def test_new_sessions_never_share_or_overwrite_files(self):
        other = CollectionSession(self.folder, "Test Person", "test")
        try:
            self.assertNotEqual(self.session.path, other.path)
            self.session.save(**self.sample)
            other.save(**dict(self.sample, gesture="fist"))
            self.assertEqual(len(list(self.folder.glob("*.csv"))), 2)
            self.assertEqual(self.read_rows()[0]["gesture"], "open_palm")
        finally:
            other.close()

    def test_closed_session_cannot_reopen_or_overwrite_data(self):
        self.session.save(**self.sample)
        self.session.close()
        with self.assertRaises(ValueError):
            self.session.save(**self.sample)
        self.assertEqual(len(self.read_rows()), 1)

    def test_participant_ids_cannot_escape_output_directory(self):
        self.assertEqual(participant_slug("../../Test Person"), "test_person")
        for bad_name in ("", "../", "x" * 41):
            with self.assertRaises(ValueError):
                participant_slug(bad_name)

    def fake_collector(self, coordinates=None, age=0):
        now = time.monotonic()
        app = Collector.__new__(Collector)
        app.session = self.session
        app.closing = False
        app.stop_event = threading.Event()
        app.latest = SimpleNamespace(
            coordinates=self.sample["coordinates"] if coordinates is None else coordinates,
            captured_monotonic=now - age, captured_at_utc=self.sample["captured_at_utc"],
            width=640, height=480, handedness="Right", handedness_score=0.99,
        )
        app.last_save = 0
        app.last_saved_frame = None
        app.gesture = Mock()
        app.gesture.get.return_value = "Fist"
        app.participant = Mock()
        app.participant.get.return_value = "Test Person"
        app.root = Mock()
        app.s_held = False
        return app

    def test_save_rejects_missing_stale_and_duplicate_frames(self):
        app = self.fake_collector(coordinates=())
        app.save_sample()
        app.latest.coordinates = self.sample["coordinates"]
        app.latest.captured_monotonic -= 2
        app.save_sample()
        self.assertEqual(self.session.total, 0)
        app.latest.captured_monotonic = time.monotonic()
        app.save_sample()
        app.last_save = 0  # Duplicate-frame guard independently of the click cooldown.
        app.save_sample()
        self.assertEqual(self.session.total, 1)
        self.assertEqual(self.read_rows()[0]["gesture"], "fist")

    def test_holding_s_does_not_record_repeatedly(self):
        app = self.fake_collector()
        app.save_sample = Mock()
        event = SimpleNamespace(keysym="s", state=0, widget=object())
        for _ in range(5):
            app._key_pressed(event)
        self.assertEqual(app.save_sample.call_count, 1)
        app._key_released()
        app._key_pressed(event)
        self.assertEqual(app.save_sample.call_count, 2)


if __name__ == "__main__":
    unittest.main()
