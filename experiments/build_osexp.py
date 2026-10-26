"""Builds the workshop experiments as OpenSesame .osexp files.

Run `python experiments/build_osexp.py` (any Python 3). Every experiment is
generated from the script text below, so the .osexp files can be re-created and
diffed easily; open them in OpenSesame as usual.
The experiments use the PyGaze plugin items (pygaze_init, pygaze_drift_correct,
pygaze_start_recording, pygaze_log, pygaze_stop_recording) and inline_script
items that only use the tracker-independent `eyetracker` object.
Change the tracker in the pygaze_init item to run on real hardware.
"""
import io
import os
import tarfile

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "osexp")

HEADER = """---
API: 3
Title: {title}
Description: {description}
OpenSesame: 4.1.0
Platform: posix
---
set width 1024
set height 768
set uniform_coordinates yes
set transparent_variables no
set title "{title}"
set subject_parity even
set subject_nr 0
set start experiment
set sound_sample_size -16
set sound_freq 48000
set sound_channels 2
set sound_buf_size 1024
set round_decimals 2
set mouse_backend legacy
set keyboard_backend legacy
set color_backend legacy
set canvas_backend legacy
set clock_backend legacy
set sampler_backend legacy
set fullscreen no
set font_size 24
set font_family mono
set font_bold no
set font_italic no
set font_underline no
set foreground black
set background white
set bidi no
set compensation 0
set coordinates relative
set description "{description}"
"""


def block(name, code):
    return "\t__%s__\n%s\n\t__end__\n" % (
        name, "\n".join("\t" + l if l else "" for l in code.strip("\n").split("\n")))


def inline(name, prepare, run, desc):
    return ("define inline_script %s\n\tset description \"%s\"\n" % (name, desc)
            + block("_prepare", prepare) + block("_run", run) + "\n")


def sketchpad(name, text, desc="", duration="keypress"):
    return ("define sketchpad %s\n\tset start_response_interval no\n"
            "\tset duration %s\n\tset description \"%s\"\n"
            "\tdraw textline center=1 color=black font_bold=no font_family=mono "
            "font_italic=no font_size=24 html=yes show_if=True text=\"%s\" x=0 y=0 z_index=0\n\n"
            % (name, duration, desc, text))


def loop(name, item, rows, description="Trials (stimulus table)"):
    cols = list(rows[0].keys())
    s = ("define loop %s\n\tset source_file \"\"\n\tset source table\n\tset skip 0\n"
         "\tset repeat 1\n\tset order random\n\tset offset no\n\tset item %s\n"
         "\tset description \"%s\"\n\tset cycles %d\n\tset continuous no\n"
         "\tset break_if_on_first yes\n\tset break_if False\n"
         "\tset column_order \"%s\"\n" % (name, item, description, len(rows), ";".join(cols)))
    for i, r in enumerate(rows):
        for c in cols:
            s += "\tsetcycle %d %s \"%s\"\n" % (i, c, r[c])
    return s + "\trun %s\n\n" % item


def pygaze_items(drift_x=0):
    return (
        "define pygaze_init pygaze_init\n\tset tracker_type \"Advanced dummy (mouse simulation)\"\n"
        "\tset calibrate yes\n\tset calbeep no\n\tset _logfile automatic\n"
        "\tset sacc_vel_thr 35\n\tset sacc_acc_thr 9500\n"
        "\tset alea_api_key \"Contact Alea for an API key\"\n\tset alea_animated_calibration no\n"
        "\tset eyelink_force_drift_correct yes\n\tset eyelink_pupil_size_mode area\n"
        "\tset smi_ip 127.0.0.1\n\tset smi_send_port 4444\n\tset smi_recv_port 5555\n"
        "\tset tobiiglasses_address 192.168.71.50\n\tset tobiiglasses_udpport 49152\n"
        "\tset description \"Initialize and calibrate the eye tracker (advanced dummy: mouse = gaze)\"\n\n"
        "define pygaze_drift_correct drift_correct\n\tset xpos %d\n\tset ypos 0\n"
        "\tset fixation_triggered no\n\tset target_color \"[foreground]\"\n"
        "\tset target_style default\n\tset draw_target yes\n"
        "\tset description \"Drift correction (click / space on the target)\"\n\n"
        "define pygaze_start_recording start_recording\n\tset status_msg start_trial\n"
        "\tset description \"Start recording\"\n\n"
        "define pygaze_stop_recording stop_recording\n\tset status_msg stop_trial\n"
        "\tset description \"Stop recording\"\n\n"
        "define pygaze_log log_trial\n\tset throttle 2\n\tset auto_log no\n"
        "\tset msg \"TRIALINFO item={item}\"\n\tset description \"Log trial info\"\n\n"
        "define logger logger\n\tset description \"Default logger\"\n\tset auto_log yes\n\n"
        % drift_x)


def experiment(title, description, instructions, rows, trial_inline, drift_x):
    s = HEADER.format(title=title, description=description)
    s += ("define sequence experiment\n\tset flush_keyboard yes\n\tset description \"Main sequence\"\n"
          "\trun pygaze_init always\n\trun instructions always\n\trun trial_loop always\n"
          "\trun goodbye always\n\n")
    s += ("define sequence trial_sequence\n\tset flush_keyboard yes\n\tset description \"One trial\"\n"
          "\trun drift_correct always\n\trun start_recording always\n\trun log_trial always\n"
          "\trun trial_display always\n\trun stop_recording always\n\trun logger always\n\n")
    s += pygaze_items(drift_x)
    s += sketchpad("instructions", instructions, "Instructions")
    s += sketchpad("goodbye", "The experiment is finished.<br />Thank you!", "Goodbye")
    s += loop("trial_loop", "trial_sequence", rows)
    s += trial_inline
    return s


# Shared inline-script helpers (OpenSesame inline scripts are standalone, so the
# few helper lines are repeated in each item).
SETUP = '''
from openexp.canvas import Canvas
from openexp.keyboard import Keyboard
W, H = var.width, var.height
kb = Keyboard(exp, keylist=['space', 'escape'], timeout=1)
LEFT = -W // 2 + 100                      # left edge of text (relative coords)
_probe = Canvas(exp)
CHARW = _probe.text_size('x')[0]          # mono font: constant char width


def text_canvas(txt):
    c = Canvas(exp)
    c.text(txt, center=False, x=LEFT, y=-CHARW, color='black')
    return c


def gaze_char(n):
    """Index of the character currently fixated (gaze in screen px)."""
    gx = eyetracker.sample()[0]
    return int((gx - W / 2 - LEFT) // CHARW)
'''

READING = inline("trial_display", SETUP + '''
sentence_canvas = text_canvas(var.sentence)
''', '''
sentence_canvas.show()
eyetracker.log('STIMONSET')
while True:
    key, _ = kb.get_key(timeout=None)
    if key in ('space', 'escape'):
        break
eyetracker.log('TRIALEND')
''', "Show the sentence until space is pressed")

BOUNDARY = inline("trial_display", SETUP + '''
pre = var.sentence.replace('TARGET', var.preview)
tar = var.sentence.replace('TARGET', var.target)
pre_canvas = text_canvas(pre)
tar_canvas = text_canvas(tar)
boundary_char = var.sentence.index('TARGET') - 1   # the space before the target
''', '''
pre_canvas.show()
eyetracker.log('STIMONSET preview=%s' % var.preview)
changed = False
while True:
    key, _ = kb.get_key(timeout=1)
    if key in ('space', 'escape'):
        break
    if not changed and gaze_char(0) > boundary_char:   # gaze crossed the invisible boundary
        tar_canvas.show()
        eyetracker.log('DISPLAYCHANGE target=%s' % var.target)
        changed = True
var.display_changed = int(changed)
eyetracker.log('TRIALEND changed=%d' % changed)
''', "Boundary paradigm: swap preview for target when gaze crosses the boundary")

MOVINGWINDOW = inline("trial_display", SETUP + '''
window = int(var.window)
sentence = var.sentence


def masked(centre):
    return ''.join(c if c == ' ' or abs(i - centre) <= window else 'x'
                   for i, c in enumerate(sentence))
''', '''
last = None
while True:
    key, _ = kb.get_key(timeout=1)
    if key in ('space', 'escape'):
        break
    char = min(max(gaze_char(0), 0), len(sentence) - 1)
    if char != last:                                   # redraw only when the fixated char changes
        text_canvas(masked(char)).show()
        eyetracker.log('WINDOWMOVE char=%d' % char)
        last = char
eyetracker.log('TRIALEND')
''', "Moving window: only characters near gaze are visible")

VWP = inline("trial_display", '''
import random
from openexp.canvas import Canvas
from openexp.keyboard import Keyboard
from openexp.mouse import Mouse
W, H = var.width, var.height
SIZE = 200
POS = [(-W // 4, -H // 4), (W // 4, -H // 4), (-W // 4, H // 4), (W // 4, H // 4)]
objects = [var.target, var.competitor, var.distractor1, var.distractor2]
random.shuffle(objects)
var.target_position = objects.index(var.target)


def scene(instruction=None):
    c = Canvas(exp)
    for name, (x, y) in zip(objects, POS):
        c.rect(x - SIZE // 2, y - SIZE // 2, SIZE, SIZE, color='black')
        c.text(name, x=x, y=y)           # replace by c.image('name.png', ...) for real pictures
    c.fixdot()
    if instruction:
        c.text(instruction, y=-H // 2 + 40)
    return c


def region(gx, gy):
    for i, (x, y) in enumerate(POS):
        if abs(gx - W / 2 - x) <= SIZE // 2 and abs(gy - H / 2 - y) <= SIZE // 2:
            return i
    return None


preview, spoken = scene(), scene(var.sentence)
kb = Keyboard(exp, keylist=['space', 'escape'], timeout=1)
''', '''
preview.show()
eyetracker.log('PREVIEW_ONSET')
clock.sleep(1000)
spoken.show()
eyetracker.log('SPOKEN_ONSET')              # play a sampler here for real audio
t0 = clock.time()
counts = [0] * 4
while clock.time() - t0 < 4000:
    gx, gy = eyetracker.sample()
    r = region(gx, gy)
    if r is not None:
        counts[r] += 1
    clock.sleep(10)
for name, n in zip(objects, counts):
    eyetracker.log('SAMPLES object=%s n=%d' % (name, n))
var.target_samples = counts[var.target_position]
eyetracker.log('TRIALEND')
''', "Visual world: show 4 objects, play instruction, count gaze samples per object")


def rows(*dicts):
    return list(dicts)


EXPERIMENTS = {
    "reading": experiment(
        "Reading experiment", "Simple sentence reading with PyGaze",
        "Read each sentence silently.<br />Press SPACE when you are done.<br /><br />Press any key to start",
        rows({"item": 1, "condition": "high", "sentence": "The old fisherman repaired his net on the quiet beach."},
             {"item": 2, "condition": "low", "sentence": "The old fisherman repaired his rete on the quiet beach."},
             {"item": 3, "condition": "high", "sentence": "The small child opened the door to see the garden."},
             {"item": 4, "condition": "low", "sentence": "The small child opened the door to see the lawns."}),
        READING, -400),
    "boundary": experiment(
        "Boundary paradigm", "Gaze-contingent display change (Rayner, 1975)",
        "Read each sentence silently.<br />Press SPACE when you are done.<br /><br />Press any key to start",
        rows({"item": 1, "preview": "tabie", "target": "table", "sentence": "The waiter put the TARGET near the window."},
             {"item": 2, "preview": "chorr", "target": "chair", "sentence": "The teacher pulled the TARGET toward the desk."},
             {"item": 3, "preview": "hovse", "target": "house", "sentence": "The family bought the TARGET beside the river."}),
        BOUNDARY, -400),
    "movingwindow": experiment(
        "Moving window paradigm", "Gaze-contingent moving window (McConkie & Rayner, 1975)",
        "Read each sentence silently.<br />Press SPACE when you are done.<br /><br />Press any key to start",
        rows({"item": 1, "window": 5, "sentence": "The explorers crossed the frozen river before sunset and made camp."},
             {"item": 2, "window": 9, "sentence": "A small bakery on the corner sells fresh bread each morning."}),
        MOVINGWINDOW, -400),
    "vwp": experiment(
        "Visual world paradigm", "Four-object visual world with gaze-sample counting",
        "Listen to the instruction and look at the named object.<br /><br />Press any key to start",
        rows({"item": 1, "sentence": "Click on the candle", "target": "candle", "competitor": "candy",
              "distractor1": "chair", "distractor2": "apple"},
             {"item": 2, "sentence": "Click on the beetle", "target": "beetle", "competitor": "beaker",
              "distractor1": "lamp", "distractor2": "shoe"}),
        VWP, 0),
}


def build():
    os.makedirs(OUT, exist_ok=True)
    for name, script in EXPERIMENTS.items():
        # .osexp = gzipped tar with script.opensesame and a pool/ folder
        with tarfile.open(os.path.join(OUT, name + ".osexp"), "w:gz") as tar:
            data = script.encode("utf-8")
            info = tarfile.TarInfo("script.opensesame")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
            d = tarfile.TarInfo("pool")
            d.type = tarfile.DIRTYPE
            d.mode = 0o755
            tar.addfile(d)
        print("wrote", name + ".osexp")


if __name__ == "__main__":
    build()
