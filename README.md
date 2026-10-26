# eye-movement-experiments-with-opensesame
A workshop and template scripts for running eye-movement experiments using Opensesame and Pygaze

## Contents

- `experiments/` – PyGaze scripts (usable standalone or inside OpenSesame inline_script items):
  `reading.py`, `boundary.py` (display change), `movingwindow.py`, `vwp.py` (visual world); stimuli in `experiments/stimuli/`.
  They use the PyGaze advanced dummy tracker by default; set `TRACKERTYPE` to use another tracker.
- `slides/workshop.qmd` – Quarto slides (`quarto render slides/workshop.qmd`).

Suggested environment: `docker pull bangele1/opensesame-test-container`.
