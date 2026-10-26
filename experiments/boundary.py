"""Experiment 2: boundary paradigm (Rayner, 1975) - gaze-contingent display change.

A preview string is shown in the target position until gaze crosses an invisible
boundary just left of it; the display then changes to the target word.
"""
from common import *

disp, kb, tracker = setup("boundary")
tracker.log("EXPERIMENT boundary")
disp.fill(text_screen("Read each sentence silently, then press SPACE."))
disp.show()
wait_for_key(kb)

for n, trial in enumerate(load_trials("boundary.csv")):
    fixation_check(disp, tracker, kb)
    pre_text = trial["sentence"].replace("TARGET", trial["preview"])
    tar_text = trial["sentence"].replace("TARGET", trial["target"])
    pre_scr, xs = sentence_screen(pre_text)
    tar_scr, _ = sentence_screen(tar_text)
    boundary = xs[trial["sentence"].index("TARGET") - 1]  # space before target

    tracker.start_recording()
    tracker.log("TRIALSTART %d item %s" % (n, trial["item"]))
    disp.fill(pre_scr)
    disp.show()
    tracker.log("STIMONSET preview")
    changed = False
    while True:
        key, _ = kb.get_key(keylist=["space", "escape"], timeout=1)
        if key is not None:
            break
        if not changed and gaze_x(tracker) > boundary:
            disp.fill(tar_scr)
            disp.show()
            tracker.log("DISPLAYCHANGE target")
            changed = True
    tracker.log("TRIALEND changed=%s" % changed)
    tracker.stop_recording()

tracker.close()
disp.close()
libtime.expend()
