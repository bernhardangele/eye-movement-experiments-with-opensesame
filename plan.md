# Plan: next steps for the workshop

Status on 2026-10-27: four experiments (reading = the published comma study, boundary, moving
window, visual world) run end to end with the simulated participant (`experiments/test_headless.py`),
including full-length runs of `boundary.osexp` for subjects 1–3 (all three block orders) and of
`reading.osexp` for subjects 1 and 2 (both lists). The
EyeLink-only items were tested with `--fake-eyelink` (dummy tracker, recorded Host PC commands),
**not** on a real EyeLink. Items are ordered by priority within each section.

## Done

Round 1:

- Fixed: the boundary run phase used a global `changed`, which in OpenSesame 4 overwrote the loop
  column `changed` (the preview word), so the log file said `True` instead of the word.
- Fixed: character width was taken from `text_size('x')` (13 px, rounded) instead of ≈14.4 px.
- Fixed: sentences were drawn ≈18 px below the gaze target; now vertically centred.
- An unfixated gaze target triggers a drift correction instead of silently dropping the trial.
- Moving window canvases prepared in advance; `REGION` messages; OpenSesame 4 syntax;
  `test_headless.py`, `AGENTS.md`, slide screenshots.

Round 2:

- **Boundary counterbalancing**: block order rotates with `subject_nr % 3` (1-2-3 / 2-3-1 / 3-1-2) as
  in the published experiment; with the parity rule, subjects 1–6 cover all combinations.
  Found and avoided a data-loss trap: variables created after the first `logger` call are never
  written, so `counterbalance` runs before the practice block.
- Instructions and SÍ/NO labels in Spanish for the Spanish experiments.
- **Visual world**: 16 drawn pictures and 8 spoken instructions (Piper TTS, LJ Speech voice) in the file
  pool, spliced so the target-word onset is known; `Sampler` + `AUDIO_ONSET` / `TARGET_ONSET`
  messages; the trial ends with a mouse click on a picture (`clicked`, `click_correct`, `click_rt`);
  gaze target in the screen centre; the "Did you look at …" question is gone.
- **EyeLink extras** in three clearly marked items (`eyelink_setup`, `eyelink_trial_start`,
  `eyelink_trial_end`): Host PC drawing (gaze target, word/picture boxes, boundary line, corner),
  `DISPLAY_COORDS`, `TRIALID`, `!V IAREA RECTANGLE`, `!V TRIAL_VAR`, `TRIAL_RESULT`. They do nothing
  with other trackers (checked by the harness).
- **Experimenter controls**: C during the gaze target = calibration + validation; status line
  `trial n/N item … condition` via the generic `status_msg`.
- **Validation** after every calibration (any tracker), error in degrees from `screen_width_cm` and
  `viewing_distance_cm`; optional **fixation-triggered drift check** (`fixation_triggered_drift_check`).
- **Comma study** ported (materials extracted by `extract_comas.py`). Item 19's
  missing comma (identical versions in the source script) restored after "deliciosa", as marked in
  the manuscript's word table; flagged `corrected = 1`.

Round 3:

- `reading.osexp` **is** the comma study (130 items with/without commas, two lists by subject
  parity, logged as `item_list`); the separate `comas.osexp` and the 8-frame word-frequency set
  (`reading.csv`) were removed.
- Slides: the reading section uses the comma study and explains counterbalancing in eight slides
  (why not repeat items, why not let items decide, two lists / Latin square, balance per participant,
  implementation in Python and with Run-if loops only, order effects, checking and analysis);
  the boundary section explains the block-order rotation.

Round 4:

- **Interest areas fixed.** `canvas.text_size()` returns the size of the inked pixels, so computing
  positions with it puts word and letter boundaries too far left: plain `text_size()` up to 0.8 letter
  (word ends); this repository's old calculation ~0.3 letter (ignored the 4 px Qt text margin).
  For data already collected with `text_size()`-based boundaries (`examples/ella_experiment_A.osexp`),
  the positions have to be calculated by hand in the analysis (monospace: first letter at the drawing
  x + ~4 px, every character 0.6 × font size wide in Courier New).
  `TEXT_LAYOUT` (`text_width()`, `letter_edges()`) now measures with a trailing `'|'` and
  `center=False`, like `examples/EyeLogic_LITE.osexp`, plus the text margin and `max_width`.
  Verified against rendered pixels with `check_interest_areas.py`: all 488 sentences on the legacy
  backend (< 1 px); 40 sentences each on the psycho backend with Droid Sans Mono 24, Courier New 24
  and Courier New 30 bold (< 1.5 px), using local copies of the Courier New font files
  (`--font-file`; git-ignored, not redistributable). The demo experiments use the bundled `mono` font.
  Word areas touch (space after a word belongs to it); every letter is logged (`LETTER`). The
  boundary is now exactly 0.4 X after the last letter of the pre-target word.
- Found an OpenSesame 4.1.17 bug: fonts in the file pool are not loaded ("Font … not found") and Qt
  silently uses another font. The lab PCs have Courier New installed, so the published experiments
  were not affected; report upstream.
- The EyeLogic experiment's right edges are correct to within ~0.25 letter (they depend slightly on
  the first letter of the sentence), but its first left edge (`sentence_left_boundary`) is ~0.9 letter
  too far left, and its `boundary` is one X after the *space* after the pre-target word (it is only
  drawn on the Host PC there, no display change).

Round 5:

- Slides restructured around three challenges (comma study → boundary study, Experiment 1 of
  Serrano-Carot & Angele, 2026 → moving window), then the visual world; the comma study's
  sentences are used as examples throughout (animations, interest-area figure, tables).
- Add Experiment 1's method details (participants, apparatus, font, letters per degree) to the
  challenge 2 slide: the article page could not be read automatically here (publisher blocks bots),
  so the slide only uses the abstract and the original experiment file.

## 1. Before the workshop (must)

1. **Pilot on a real EyeLink**: switch `pygaze_init` to EyeLink and check, for each experiment,
   - Host PC drawing (boxes, boundary line) and the status line,
   - `TRIALID`, `!V IAREA`, `!V TRIAL_VAR` in Data Viewer (trial list, interest areas, variables),
   - the generic validation (does `sample()` return valid data right after `start_recording()`?),
   - C during the gaze target (EyeLink `calibrate()` opens the camera setup screen),
   - display-change latency on the lab monitor (≥ 120 Hz).
   The harness only checks logic and message content; `--fake-eyelink` cannot detect a command the
   Host PC rejects.
2. **Check the interest areas on the lab PC** (Windows, installed fonts):
   `check_interest_areas.py --backend psycho --font "Courier New"`. Tested here on Linux with the same
   Courier New files; Windows font rendering (hinting) may differ by a pixel.
3. **Set lab values**: `screen_width_cm`, `viewing_distance_cm` (validation in degrees),
   `validation_threshold`.
4. **Measure the audio delay** for `vwp.osexp` (play() → loudspeaker) and listen to the 8 spliced
   sentences; re-synthesise or record them if the splice is audible.
5. **Walk through the slides in the devcontainer** as a participant would, and look at the
   animations on the projector you will use (speed, colours, contrast). `slides/check_slides.py`
   checks that every slide fits and the animations run, but not how they look to an audience.
6. **Rebuild the devcontainer** and run `slides/check_slides.py` with `/opt/slides-check/bin/python`:
   the Playwright/Chromium layer in `.devcontainer/Dockerfile` has not been test-built (no Docker
   in this environment; the same Playwright version was used from a scratch venv).
7. Confirm with the authors of the comma study that the port matches the original design
   (block structure, counterbalancing by parity, practice without questions). Note for the
   authors: in the original EyeTrack script (and `frases.csv`) item 19's comma version had no comma,
   so in the published data that item had no comma condition. The port restores the comma after
   "deliciosa" (`corrected = 1`); check whether item 19 was excluded from the published analysis.
   Tell the authors of the EyeLogic experiment about its first-word left edge (see Round 4) and
   about item 1005: the answer key of the low-frequency question says YES, but the correct answer
   is NO (corrected in `extract_eyelogic.py`).

## 2. Experiments (could)

1. Reading (comma study): the original EyeTrack script used Courier New 14 pt (≈ 3 characters per degree in the
   original lab); the port uses the shared mono 24 px. Match the original letter size if results are
   to be compared.
2. Moving window: tune `min_saccade_letters` (1.5) and the 20 ms settling time with real tracker
   noise in the lab (participants with poor calibration may need more); more sentences than the 10
   practice sentences of the EyeLogic experiment (its experimental `trials_b1/b2.csv` are not in
   the `.osexp` file).
3. A fixation-triggered gaze-target alternative for participants who cannot hold fixation.
4. Visual world: record natural speech instead of TTS; more items; an analysis of fixation
   proportions over time.

## 3. Analysis (should)

1. Add `analysis/` with a worked example: read `subject-*.csv` and an EDF (`eyelinkReader` in R or
   `pyedfread`), use `REGION` messages as interest areas, compute first fixation duration,
   gaze duration, total time, skipping, and display-change exclusions for the boundary data.
2. Generate a small **simulated data set** (harness output + synthetic fixations) so the analysis
   part works without the lab.
3. Add an analysis section to the slides (currently only a one-slide overview).

## 4. Tooling (could)

1. Fix or wrap `opensesamerun` in the container image (the entry point is missing in 4.1.17), or
   report it upstream.
2. Run `test_headless.py --max-trials 4` (normal and `--fake-eyelink`) in GitHub Actions using the
   container image and `xvfb-run`.
3. Test more behaviours: Escape → abort path, corner/click timeouts, rejected validation (C at the
   validation screen), gaze landing exactly on the boundary.
4. Done: the simulated reader makes fixations (with drift on letter boundaries) and saccades. Next:
   vary fixation durations and saccade lengths, and add regressions.
5. Investigate one intermittent harness failure (2026-10-27): `reading` reported a corner/boundary/
   click timeout in one `--max-trials 3 --subject 2` run of all four experiments; not reproduced in
   five reruns. A 60 s corner timeout means the simulated gaze never reached the corner, so the
   cause is probably on the harness side (state change missed), but the log was not kept.
   The check now prints the trial and message, so the next occurrence is diagnosable.
6. Generate slide screenshots automatically so they never go stale.

## Open questions for the workshop organiser

- Target tracker(s) in the lab (EyeLink 1000? Tobii?) and monitor refresh rate.
- Length of the session (the slides now fit ≈3.5 h with exercises).
- Should participants build an experiment from scratch in the GUI (more didactic, slower) rather
  than reading the generated ones?
