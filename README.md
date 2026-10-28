# eye-movement-experiments-with-opensesame
A workshop and template experiments for running eye-movement experiments with OpenSesame and PyGaze.

## Contents

- `slides/workshop.qmd` – Quarto slides, 16:9 (`quarto render slides/workshop.qmd`); screenshots in `slides/images/`,
  GSAP animations in `slides/animations.js`; `slides/check_slides.py` checks the rendered slides in a headless browser.
- `experiments/osexp/` – OpenSesame experiments using PyGaze (advanced dummy tracker by default):
  `reading.osexp` (the published comma study: sentences with and without commas),
  `boundary.osexp` (display change), `movingwindow.osexp`,
  `vwp.osexp` (visual world with pictures, speech and mouse clicks).
- `experiments/build_osexp.py` – generates the `.osexp` files (the readable source of the experiments).
- `experiments/test_headless.py` – runs the experiments with a simulated participant and checks the data
  (`--fake-eyelink` also tests the EyeLink-only items).
- `experiments/check_interest_areas.py` – checks the computed letter and word positions (interest areas)
  against the rendered pixels.
- `experiments/comas.csv` (from `extract_comas.py`, used by `reading.osexp`),
  `experiments/movingwindow.csv` (from `extract_eyelogic.py`, used by `movingwindow.osexp`), `experiments/vwp_pool/`
  (from `make_vwp_stimuli.py`) – stimulus materials.
- `experiments/sentences.csv` – real Spanish sentence table (10 practice + 3 × 70 experimental
  items) extracted from the published experiment in `examples/`.
- `examples/ella_experiment_A.osexp` – published gaze-contingent display-change experiment used
  as the model for `boundary.osexp`.
- `examples/EyeLogic_LITE.osexp` – lab experiment used as the reference for the interest-area calculation.
- `examples/frases-comas/` – EyeTrack (UMass) script, stimuli and manuscript of the published comma
  experiment that `reading.osexp` reproduces.
- `.devcontainer/` – development container with the OpenSesame image plus Quarto and noVNC.

All experiments share the same trial skeleton:

1. drift correction;
2. a 50 px gaze-contingent target at the start of the sentence (250 ms fixation; after 10 s without
   a fixation a drift correction is run and the target is shown again);
3. the sentence or scene;
4. look at the small square in the bottom-right corner to end the trial (100 ms fixation);
5. a yes/no comprehension question (1 = YES/SÍ, 2 = NO).

The visual world trial ends with a mouse click on a picture instead of steps 4–5.

`reading.osexp` counterbalances with two lists: even subject numbers read the odd items with commas,
odd subject numbers the even items, so every item is read in both versions across each pair of participants.

After calibration, a validation measures the accuracy in degrees (any tracker); during the gaze target
the experimenter can press C to re-calibrate. `boundary.osexp` assigns preview validity by subject parity
and rotates the block order with `subject_nr % 3`, as in the published experiment.

The items `eyelink_setup`, `eyelink_trial_start` and `eyelink_trial_end` draw on the EyeLink Host PC and
write Data Viewer messages. **They only work with an SR Research EyeLink**; with any other tracker they do
nothing.

## Quick start

```bash
python experiments/build_osexp.py                      # regenerate the .osexp files
python experiments/test_headless.py --max-trials 4     # run all four with a simulated participant
quarto render slides/workshop.qmd                      # build the slides
```

`test_headless.py` needs the OpenSesame Python (`/home/ubuntu/venv/bin/python` in the container)
and an X display (the devcontainer starts Xvfb on `:0`; elsewhere use `xvfb-run`).
See `AGENTS.md` for conventions and `plan.md` for next steps.
