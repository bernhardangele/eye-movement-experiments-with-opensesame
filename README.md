# eye-movement-experiments-with-opensesame
A workshop and template scripts for running eye-movement experiments using Opensesame and Pygaze

## Contents

- `experiments/osexp/` – OpenSesame experiments using PyGaze (advanced dummy tracker by default):
  `reading.osexp`, `boundary.osexp` (display change), `movingwindow.osexp`, `vwp.osexp` (visual world).
  `experiments/build_osexp.py` regenerates them.
- `experiments/sentences.csv` – real Spanish sentence table (10 practice + 3 × 70 experimental
  items) extracted from the published experiment in `examples/`.
- `examples/ella_experiment_A.osexp` – published gaze-contingent display-change experiment used
  as the model for `boundary.osexp`.
- `slides/workshop.qmd` – Quarto slides (`quarto render slides/workshop.qmd`).
- `.devcontainer/` – development container with the OpenSesame image plus Quarto and noVNC.

All experiments share the same trial skeleton:

1. drift correction;
2. a 50 px gaze-contingent target at the start of the sentence (250 ms fixation);
3. the sentence or scene;
4. look at the small square in the bottom-right corner to end the trial (100 ms fixation);
5. a yes/no comprehension question (1 = SI, 2 = NO).

`boundary.osexp` uses the real sentences and a simplified counterbalancing scheme: preview
validity is assigned from subject parity instead of rotating three counterbalanced blocks.
