"""Experiment 1: simple sentence-reading experiment (PyGaze, any tracker)."""
from common import *

disp, kb, tracker = setup("reading")
tracker.log("EXPERIMENT reading")
disp.fill(text_screen("Read each sentence silently, then press SPACE."))
disp.show()
wait_for_key(kb)

for n, trial in enumerate(load_trials("reading.csv")):
    fixation_check(disp, tracker, kb)
    scr, _ = sentence_screen(trial["sentence"])
    tracker.start_recording()
    tracker.status_msg("trial %d" % n)
    tracker.log("TRIALSTART %d item %s cond %s" % (n, trial["item"], trial["condition"]))
    disp.fill(scr)
    t0 = disp.show()
    tracker.log("STIMONSET")
    wait_for_key(kb)
    tracker.log("TRIALEND")
    tracker.stop_recording()

tracker.close()
disp.close()
libtime.expend()
