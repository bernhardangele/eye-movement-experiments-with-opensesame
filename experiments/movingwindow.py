"""Experiment 3: moving window paradigm (McConkie & Rayner, 1975).

Only characters within WINDOW characters of the current gaze position are
visible; all other letters are replaced by 'x' (spaces are preserved).
"""
from common import *

disp, kb, tracker = setup("movingwindow")
tracker.log("EXPERIMENT movingwindow")
disp.fill(text_screen("Read each sentence silently, then press SPACE."))
disp.show()
wait_for_key(kb)


def masked(sentence, centre, window):
    return "".join(c if c == " " or abs(i - centre) <= window else "x"
                   for i, c in enumerate(sentence))


for n, trial in enumerate(load_trials("movingwindow.csv")):
    sentence, window = trial["sentence"], int(trial["window"])
    fixation_check(disp, tracker, kb)
    _, xs = sentence_screen(sentence)
    charw = xs[1] - xs[0]
    tracker.start_recording()
    tracker.log("TRIALSTART %d item %s window %d" % (n, trial["item"], window))
    last = None
    while True:
        key, _ = kb.get_key(keylist=["space", "escape"], timeout=1)
        if key is not None:
            break
        char = int((gaze_x(tracker) - xs[0]) // charw)
        char = min(max(char, 0), len(sentence) - 1)
        if char != last:
            scr, _ = sentence_screen(masked(sentence, char, window))
            disp.fill(scr)
            disp.show()
            tracker.log("WINDOWMOVE char %d" % char)
            last = char
    tracker.log("TRIALEND")
    tracker.stop_recording()

tracker.close()
disp.close()
libtime.expend()
