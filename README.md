# eye-movement-experiments-with-opensesame
A workshop and template scripts for running eye-movement experiments using Opensesame and Pygaze

## Contents

- `experiments/osexp/` – OpenSesame experiments using PyGaze (advanced dummy tracker by default):
  `reading.osexp`, `boundary.osexp` (display change), `movingwindow.osexp`, `vwp.osexp` (visual world).
  `experiments/build_osexp.py` regenerates them.
- `slides/workshop.qmd` – Quarto slides (`quarto render slides/workshop.qmd`).
- `Dockerfile` – `bangele1/opensesame-test-container` plus Quarto.
