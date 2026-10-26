"""Shared helpers for the PyGaze/OpenSesame eye-movement experiments.

The experiments only use the tracker-independent PyGaze API, so switching from
the advanced dummy tracker (mouse-simulated gaze) to a real tracker only requires
changing TRACKERTYPE (e.g. 'eyelink', 'tobii', 'eyetribe', ...).
"""
import csv
import os
import random

from pygaze import libscreen, libtime, libinput, eyetracker

TRACKERTYPE = os.environ.get("TRACKERTYPE", "dummy")  # 'dummy' = advanced dummy
DISPSIZE = (1024, 768)
BGC = (255, 255, 255)
FGC = (0, 0, 0)
FONT = "mono"
FONTSIZE = 24
STIMDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stimuli")


def setup(logfile="data"):
    """Create display, input devices and tracker; run calibration."""
    disp = libscreen.Display(disptype="pygame", dispsize=DISPSIZE,
                             fgc=FGC, bgc=BGC, screennr=0)
    kb = libinput.Keyboard(keylist=["space", "escape"], timeout=None)
    tracker = eyetracker.EyeTracker(disp, trackertype=TRACKERTYPE,
                                    logfile=logfile)
    tracker.calibrate()
    return disp, kb, tracker


def load_trials(name, shuffle=True):
    with open(os.path.join(STIMDIR, name), newline="", encoding="utf-8") as f:
        trials = list(csv.DictReader(f))
    if shuffle:
        random.shuffle(trials)
    return trials


def text_screen(text, pos=None, fontsize=FONTSIZE):
    scr = libscreen.Screen(disptype="pygame", dispsize=DISPSIZE,
                           fgc=FGC, bgc=BGC)
    scr.draw_text(text=text, pos=pos or (DISPSIZE[0] // 2, DISPSIZE[1] // 2),
                  colour=FGC, font=FONT, fontsize=fontsize)
    return scr


def sentence_screen(sentence, left=100, fontsize=FONTSIZE):
    """Draw a sentence left-aligned; return screen and x-position of each char."""
    scr = libscreen.Screen(disptype="pygame", dispsize=DISPSIZE,
                           fgc=FGC, bgc=BGC)
    charw = fontsize * 0.6  # monospaced font: constant character width
    y = DISPSIZE[1] // 2
    for i, ch in enumerate(sentence):
        scr.draw_text(text=ch, pos=(left + i * charw + charw / 2, y),
                      colour=FGC, font=FONT, fontsize=fontsize)
    return scr, [left + i * charw for i in range(len(sentence) + 1)]


def fixation_check(disp, tracker, kb, pos=(100, DISPSIZE[1] // 2)):
    """Gaze-contingent drift check on the left of the screen."""
    scr = libscreen.Screen(disptype="pygame", dispsize=DISPSIZE,
                           fgc=FGC, bgc=BGC)
    scr.draw_fixation(fixtype="cross", pos=pos, colour=FGC, pw=2, diameter=12)
    disp.fill(scr)
    disp.show()
    tracker.drift_correction(pos=pos, fix_triggered=False)


def wait_for_key(kb, keys=("space",)):
    return kb.get_key(keylist=list(keys), timeout=None)[0]


def gaze_x(tracker):
    return tracker.sample()[0]


def gaze_pos(tracker):
    return tracker.sample()
