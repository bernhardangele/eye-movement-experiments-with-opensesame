"""Experiment 4: visual world paradigm.

Four object pictures are shown in the corners (placeholder labelled boxes are
used when no image file stimuli/<name>.png exists); the spoken-instruction text
is displayed, and the proportion of fixations to each object is logged.
"""
from common import *

W, H = DISPSIZE
POSITIONS = [(W // 4, H // 4), (3 * W // 4, H // 4),
             (W // 4, 3 * H // 4), (3 * W // 4, 3 * H // 4)]
SIZE = 200

disp, kb, tracker = setup("vwp")
tracker.log("EXPERIMENT vwp")
disp.fill(text_screen("Listen to the instruction and look at the named object.\nPress SPACE."))
disp.show()
wait_for_key(kb)


def object_screen(objects):
    scr = libscreen.Screen(disptype="pygame", dispsize=DISPSIZE, fgc=FGC, bgc=BGC)
    for name, (x, y) in zip(objects, POSITIONS):
        img = os.path.join(STIMDIR, name + ".png")
        if os.path.exists(img):
            scr.draw_image(img, pos=(x, y))
        else:
            scr.draw_rect(colour=FGC, x=x - SIZE // 2, y=y - SIZE // 2,
                          w=SIZE, h=SIZE, pw=2, fill=False)
            scr.draw_text(text=name, pos=(x, y), colour=FGC, font=FONT, fontsize=FONTSIZE)
    scr.draw_fixation(fixtype="cross", pos=(W // 2, H // 2), colour=FGC, pw=2, diameter=12)
    return scr


def region_of(pos):
    for i, (x, y) in enumerate(POSITIONS):
        if abs(pos[0] - x) <= SIZE // 2 and abs(pos[1] - y) <= SIZE // 2:
            return i
    return None


for n, trial in enumerate(load_trials("vwp.csv")):
    objects = [trial["target"], trial["competitor"], trial["distractor1"], trial["distractor2"]]
    random.shuffle(objects)
    fixation_check(disp, tracker, kb, pos=(W // 2, H // 2))
    tracker.start_recording()
    tracker.log("TRIALSTART %d item %s" % (n, trial["item"]))
    disp.fill(object_screen(objects))
    disp.show()
    tracker.log("PREVIEW_ONSET")
    libtime.pause(1000)
    # Replace with an OpenSesame sampler / pygaze sound for real audio.
    scr = object_screen(objects)
    scr.draw_text(text=trial["sentence"], pos=(W // 2, 40), colour=FGC, font=FONT, fontsize=FONTSIZE)
    disp.fill(scr)
    disp.show()
    tracker.log("AUDIO_ONSET")
    t0 = libtime.get_time()
    counts = [0] * 4
    while libtime.get_time() - t0 < 4000:
        r = region_of(gaze_pos(tracker))
        if r is not None:
            counts[r] += 1
        libtime.pause(10)
    for obj, c in zip(objects, counts):
        tracker.log("SAMPLES %s %d" % (obj, c))
    tracker.log("TRIALEND")
    tracker.stop_recording()

tracker.close()
disp.close()
libtime.expend()
