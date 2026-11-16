"""Standalone webcam collector. Labels come from the person, never a classifier."""

import argparse
import logging
import queue
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tkinter import messagebox, ttk

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from PIL import Image, ImageTk

from collector.data import CollectionSession, GESTURES, participant_slug

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "raw"
MODEL = ROOT / "hand_landmarker.task"

# Hand skeleton connections from Suliman's original webcam demo.
CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12), (9, 13), (13, 14), (14, 15),
    (15, 16), (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),
]


@dataclass
class Frame:
    rgb: object
    coordinates: tuple
    captured_at_utc: str
    captured_monotonic: float
    width: int
    height: int
    handedness: str = ""
    handedness_score: object = ""


def track_camera(frames, events, stop):
    """Own the camera and detector on one worker so the window remains responsive."""
    camera = None
    try:
        if not MODEL.is_file():
            raise RuntimeError("hand_landmarker.task is missing. Restore it from the repository.")
        options = vision.HandLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(MODEL)),
            running_mode=vision.RunningMode.VIDEO, num_hands=1,
        )
        with vision.HandLandmarker.create_from_options(options) as detector:
            camera = cv2.VideoCapture(0)
            if not camera.isOpened():
                raise RuntimeError("Could not open the webcam. Close other camera apps and reopen this program.")
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            start = time.monotonic()
            last_timestamp = -1
            while not stop.is_set():
                success, bgr = camera.read()
                if not success:
                    raise RuntimeError("The webcam stopped sending frames. Close and reopen this program.")
                captured = time.monotonic()
                captured_utc = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
                bgr = cv2.flip(bgr, 1)
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                timestamp = max(int((captured - start) * 1000), last_timestamp + 1)
                last_timestamp = timestamp
                result = detector.detect_for_video(
                    mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp,
                )
                height, width = rgb.shape[:2]
                coordinates, handedness, score = (), "", ""
                if result.hand_landmarks:
                    hand = result.hand_landmarks[0]
                    coordinates = tuple(v for point in hand for v in (point.x, point.y, point.z))
                    points = [(int(p.x * width), int(p.y * height)) for p in hand]
                    for a, b in CONNECTIONS:
                        cv2.line(rgb, points[a], points[b], (74, 222, 128), 2)
                    for point in points:
                        cv2.circle(rgb, point, 4, (255, 110, 105), -1)
                    if result.handedness and result.handedness[0]:
                        handedness = result.handedness[0][0].category_name
                        score = result.handedness[0][0].score
                frame = Frame(rgb, coordinates, captured_utc, captured, width, height, handedness, score)
                # Discard old preview frames; never save an accumulated backlog.
                try:
                    frames.get_nowait()
                except queue.Empty:
                    pass
                frames.put_nowait(frame)
    except Exception as error:
        logging.exception("Camera session failed")
        events.put(("error", str(error)))
    finally:
        if camera is not None:
            camera.release()
        events.put(("stopped", None))


class Collector:
    def __init__(self, root):
        self.root = root
        self.session = None
        self.stop_event = threading.Event()
        self.frames = queue.Queue(maxsize=1)
        self.events = queue.SimpleQueue()
        self.latest = None
        self.last_saved_frame = None
        self.last_save = 0
        self.s_held = False
        self.closing = False
        self.close_deadline = None
        self.photo = None
        self.participant = tk.StringVar()
        self.gesture = tk.StringVar(value=next(iter(GESTURES)))
        self._build()
        root.bind("<KeyPress>", self._key_pressed)
        root.bind("<KeyRelease-s>", self._key_released)
        root.bind("<KeyRelease-S>", self._key_released)
        root.bind("<FocusOut>", self._key_released)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.worker = threading.Thread(
            target=track_camera, args=(self.frames, self.events, self.stop_event), daemon=True,
        )
        self.worker.start()
        root.after(35, self.poll)

    def _build(self):
        root = self.root
        root.title("Collect Gestures")
        root.geometry("800x650")
        root.minsize(640, 520)
        controls = ttk.Frame(root, padding=8)
        controls.pack(fill="x")
        controls.columnconfigure(1, weight=1)
        ttk.Label(controls, text="Name").grid(row=0, column=0, padx=(0, 6))
        self.name_entry = ttk.Entry(controls, textvariable=self.participant, width=20)
        self.name_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.name_entry.bind("<Return>", lambda _: root.focus_set())
        self.gesture_combo = ttk.Combobox(
            controls, textvariable=self.gesture, values=list(GESTURES), state="readonly", width=20,
        )
        self.gesture_combo.grid(row=0, column=2, padx=(0, 8))
        self.gesture_combo.bind("<<ComboboxSelected>>", lambda _: root.focus_set())
        self.save_button = ttk.Button(controls, text="Save Sample", command=self.save_sample, state="disabled")
        self.save_button.grid(row=0, column=3)
        self.preview = tk.Label(root, bg="black")
        self.preview.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.preview.bind("<Button-1>", lambda _: root.focus_set())
        self.name_entry.focus_set()

    def _key_pressed(self, event):
        if event.keysym.lower() != "s" or event.state & (0x4 | 0x8):
            return
        if isinstance(event.widget, (ttk.Entry, ttk.Combobox, tk.Entry)):
            return
        if not self.s_held:
            self.s_held = True
            self.save_sample()
        return "break"

    def _key_released(self, _event=None):
        self.s_held = False

    def save_sample(self):
        if self.closing or self.stop_event.is_set():
            return
        frame = self.latest
        now = time.monotonic()
        if frame is None or not frame.coordinates or now - frame.captured_monotonic > 0.5:
            return
        if now - self.last_save < 0.25 or frame.captured_monotonic == self.last_saved_frame:
            return
        try:
            participant = participant_slug(self.participant.get())
        except ValueError as error:
            messagebox.showerror("Name needed", str(error), parent=self.root)
            self.name_entry.focus_set()
            return
        try:
            # A different name gets a separate file; labels can change within a file.
            if self.session is None or participant != self.session.participant:
                if self.session:
                    self.session.close()
                self.session = CollectionSession(OUTPUT, participant, mp.__version__)
            self.session.save(
                gesture=GESTURES[self.gesture.get()], coordinates=frame.coordinates,
                captured_at_utc=frame.captured_at_utc, width=frame.width, height=frame.height,
                handedness=frame.handedness, handedness_score=frame.handedness_score,
            )
        except (OSError, ValueError) as error:
            self.stop_event.set()
            self.save_button.state(["disabled"])
            logging.exception("Could not save sample")
            messagebox.showerror("Sample not saved", str(error), parent=self.root)
            return
        self.last_save = now
        self.last_saved_frame = frame.captured_monotonic
        self.root.focus_set()

    def poll(self):
        while not self.events.empty():
            event, detail = self.events.get()
            if event == "error":
                self.latest = None
                self.stop_event.set()
                if not self.closing:
                    messagebox.showerror("Webcam unavailable", detail, parent=self.root)
            elif event == "stopped":
                self.latest = None
                self.stop_event.set()
                if self.session:
                    self.session.close()
                self.photo = None
                self.preview.configure(image="")
        try:
            frame = self.frames.get_nowait()
        except queue.Empty:
            frame = None
        if frame is not None and not self.stop_event.is_set():
            self.latest = frame
            width = max(self.preview.winfo_width(), 1)
            height = max(self.preview.winfo_height(), 1)
            scale = min(width / frame.width, height / frame.height)
            image = Image.fromarray(frame.rgb).resize(
                (max(1, int(frame.width * scale)), max(1, int(frame.height * scale))),
                Image.Resampling.BILINEAR,
            )
            self.photo = ImageTk.PhotoImage(image)
            self.preview.configure(image=self.photo)
        fresh_hand = self.latest is not None and bool(self.latest.coordinates) and time.monotonic() - self.latest.captured_monotonic <= 0.5
        self.save_button.state(["!disabled"] if fresh_hand and not self.stop_event.is_set() and not self.closing else ["disabled"])
        if self.closing:
            if not self.worker.is_alive() or time.monotonic() >= self.close_deadline:
                if self.session:
                    self.session.close()
                self.root.destroy()
                return
        self.root.after(35, self.poll)

    def close(self):
        self.closing = True
        self.close_deadline = time.monotonic() + 5
        self.stop_event.set()
        self.latest = None
        self.save_button.state(["disabled"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ready-file", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    root = tk.Tk()
    Collector(root)
    root.update_idletasks()
    if args.ready_file:
        args.ready_file.write_text("ready", encoding="utf-8")
    root.mainloop()


if __name__ == "__main__":
    main()
