"""CSV storage only: this module does not import camera or classifier libraries."""

import csv
import math
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path


# Keep Suliman's original labels; the team can collect a chosen subset.
GESTURES = {
    "Open palm (neutral)": "open_palm",
    "Fist": "fist",
    "Point up": "point_up",
    "Point down": "point_down",
    "Point left": "point_left",
    "Point right": "point_right",
    "Two fingers": "two_fingers",
    "Pinch": "pinch",
}
COORDINATE_FIELDS = [f"lm_{point:02d}_{axis}" for point in range(21) for axis in "xyz"]
FIELDS = [
    "schema_version", "sample_id", "participant_id", "session_id", "captured_at_utc",
    "gesture", "image_width", "image_height", "mirrored",
    "handedness", "handedness_score", "mediapipe_version",
] + COORDINATE_FIELDS


def participant_slug(value):
    """A stable, filename-safe ID; use the same spelling for every session."""
    slug = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    if not slug or len(slug) > 40:
        raise ValueError("Enter a name or short ID using 1–40 letters or numbers.")
    return slug


class CollectionSession:
    def __init__(self, output_folder, participant, mediapipe_version):
        self.participant = participant_slug(participant)
        self.mediapipe_version = mediapipe_version
        self.session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "_" + uuid.uuid4().hex[:8]
        self.path = Path(output_folder) / f"{self.participant}_{self.session_id}.csv"
        self.total = 0
        self._file = None
        self._writer = None
        self._closed = False

    def save(self, *, gesture, coordinates, captured_at_utc, width, height,
             handedness="", handedness_score=""):
        if self._closed:
            raise ValueError("This session has ended. Start a new session before saving.")
        if gesture not in GESTURES.values():
            raise ValueError("Choose a gesture from the list.")
        if len(coordinates) != 63 or not all(math.isfinite(float(v)) for v in coordinates):
            raise ValueError("A sample needs all 21 hand points (63 finite coordinates).")
        if self._file is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Never append to or overwrite another person's/session's file.
            self._file = self.path.open("x", newline="", encoding="utf-8")
            self._writer = csv.DictWriter(self._file, fieldnames=FIELDS)
            self._writer.writeheader()
        row = dict(zip(COORDINATE_FIELDS, coordinates))
        row.update(
            schema_version=2, sample_id=f"{self.session_id}_{self.total + 1:04d}",
            participant_id=self.participant, session_id=self.session_id,
            captured_at_utc=captured_at_utc, gesture=gesture,
            image_width=width, image_height=height,
            mirrored=True, handedness=handedness, handedness_score=handedness_score,
            mediapipe_version=self.mediapipe_version,
        )
        self._writer.writerow(row)
        self._file.flush()
        self.total += 1

    def close(self):
        self._closed = True
        if self._file is not None:
            self._file.close()
            self._file = None
            self._writer = None
