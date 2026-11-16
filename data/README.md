# Collecting gesture samples

1. Double-click **Collect Gestures.cmd** on Windows or **Collect Gestures.command** on Mac. The default webcam starts automatically.
2. Enter your name, choose a gesture, and click **Save Sample** or press **S**.
3. Move your hand between saves. Change the dropdown for the next gesture.
4. Close the window when finished. Your CSV is in **data/raw/**. Commit and push it.

While typing your name, S just types a letter. Press Enter or click the camera
preview when you want to use S to save. Save Sample is enabled when a hand is
visible. Only one hand should be in view. Left/right gestures refer to the
mirrored preview.

Each save adds one labeled set of 21 hand points (63 x/y/z values), not a photo.
The label is whichever gesture you selected; no gesture classifier runs.
Each launch gets a separate CSV, named with your name and a session ID.
Changing your name starts a separate file rather than mixing people's samples.
There are no lighting, camera-source, or session controls.

The CSV includes the name, session ID, capture time, gesture, frame details,
MediaPipe version, and hand coordinates. Coordinates use MediaPipe's image-space
landmark order. CSV format version 2 omits the old lighting and camera-source fields.
These files can be combined later for training; keep names and session IDs so
training and test recordings can be separated. The historical dataset under
`deprecated/` is preserved separately.

First launch downloads an isolated Python environment and camera dependencies;
internet is needed for setup. Later launches work offline. No VS Code changes.

Windows setup lives in `%LOCALAPPDATA%/GestrRuntime`. Mac setup lives in
`~/Library/Application Support/GestrRuntime`. The Mac launcher selects dependencies
for Apple Silicon or Intel automatically. Intel uses an older MediaPipe release
because version 1.2.3 does not provide Intel Mac wheels; both use the same bundled
hand-landmark asset and CSV format. Mac dependency resolution and shell syntax
have been checked from Windows; an actual Mac camera run still needs confirmation.

On Mac, allow camera access when requested. If Finder reports that the launcher
is not executable, open Terminal in the project folder and run:

```bash
bash "Collect Gestures.command"
```
