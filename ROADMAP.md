# GESTR Roadmap

Pick a task, add your name beside it, and check it off when it is finished.

- [x] Build the desktop UI prototype with Home, Mappings, Gesture Settings, and Camera tabs.
- [x] Choose the first gestures, keyboard controls, and game for the demo.
- [x] Set up Python and MediaPipe to find hands and their finger and joint points.
- [x] Build a webcam preview that shows the hand points from MediaPipe.
- [x] Build a manual collector with gesture labels and separate participant/session CSVs.
- [ ] Collect labeled hand-coordinate samples from different people, sessions, and lighting conditions, including the neutral gesture.
- [ ] Split the data into training, validation, and test sets, keeping people or recording sessions separate.
- [ ] Train and document a new gesture model using the team's collected dataset (earlier prototype preserved in deprecated/).
- [ ] Use the validation set to improve the model and choose confidence and timing settings.
- [ ] Run the model on live webcam frames and show the predicted gesture.
- [ ] Connect the camera preview, predictions, and settings to the desktop UI.
- [ ] Connect recognized gestures to the selected keyboard controls and add mouse controls if needed for the demo.
- [ ] Add working start, pause, and stop controls, including a way to release held keys safely.
- [ ] Package the Windows app and prepare the demo, instructions, and presentation.
- [ ] Test and evaluate the final model and app on held-out data and gameplay, recording accuracy, false inputs, missed gestures, and delay.
