"""Builds the workshop experiments as OpenSesame .osexp files.

Run `python experiments/build_osexp.py` (any Python 3). Every experiment is
generated from the script text below, so the .osexp files can be re-created and
diffed easily; open them in OpenSesame as usual.

The boundary experiment is modelled on `examples/ella_experiment_A.osexp`
(gaze-contingent display change; the published experiment) and uses the real
Spanish sentences extracted from that file into `sentences.csv`. Counter-
balancing is simplified: preview validity is assigned from subject parity
instead of rotating three counterbalanced blocks.

All experiments use the same trial skeleton:

    drift correction -> start recording -> gaze target at sentence start
    -> sentence / scene -> look at bottom-right corner to end the trial
    -> yes/no comprehension question -> stop recording

The experiments use the PyGaze plugin items (pygaze_init, pygaze_drift_correct,
pygaze_start_recording, pygaze_log, pygaze_stop_recording) and inline_script
items that only use the tracker-independent `eyetracker` object.
Change the tracker in the pygaze_init item to run on real hardware.
"""
import csv
import io
import os
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "osexp")
SENTENCES_CSV = os.path.join(HERE, "sentences.csv")

# Geometry from the published experiment: a 50 px gaze target at x=100..150,
# the sentence starts in the middle of that target, and the trial ends when the
# bottom-right 10% x 10% corner is fixated for 100 ms.
HEADER = """---
API: 3
Title: {title}
Description: {description}
OpenSesame: 4.1.0
Platform: posix
---
set width 1920
set height 1080
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


def q(value):
    """Escape a value for a quoted .osexp attribute/setcycle value."""
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def block(name, code):
    return "\t__%s__\n%s\n\t__end__\n" % (
        name, "\n".join("\t" + l if l else "" for l in code.strip("\n").split("\n")))


def inline(name, prepare, run, desc):
    return ("define inline_script %s\n\tset description \"%s\"\n" % (name, q(desc))
            + block("_prepare", prepare) + block("_run", run) + "\n")


def sketchpad(name, text, desc="", duration="keypress"):
    return ("define sketchpad %s\n\tset start_response_interval no\n"
            "\tset duration %s\n\tset description \"%s\"\n"
            "\tdraw textline center=1 color=black font_bold=no font_family=mono "
            "font_italic=no font_size=24 html=yes show_if=True text=\"%s\" x=0 y=0 z_index=0\n\n"
            % (name, duration, q(desc), q(text)))


def empty_sketchpad(name, desc=""):
    return ("define sketchpad %s\n\tset start_response_interval no\n"
            "\tset duration 0\n\tset description \"%s\"\n\n" % (name, q(desc)))


def loop(name, item, rows, description="Trials (stimulus table)", order="random"):
    cols = list(rows[0].keys())
    s = ("define loop %s\n\tset source_file \"\"\n\tset source table\n\tset skip 0\n"
         "\tset repeat 1\n\tset order %s\n\tset offset no\n\tset item %s\n"
         "\tset description \"%s\"\n\tset cycles %d\n\tset continuous no\n"
         "\tset break_if_on_first yes\n\tset break_if False\n"
         "\tset column_order \"%s\"\n" % (name, order, item, q(description),
                                         len(rows), ";".join(cols)))
    for i, r in enumerate(rows):
        for c in cols:
            s += "\tsetcycle %d %s \"%s\"\n" % (i, c, q(r[c]))
    return s + "\trun %s\n\n" % item


def pygaze_items():
    return (
        "define pygaze_init pygaze_init\n\tset tracker_type \"Advanced dummy (mouse simulation)\"\n"
        "\tset calibrate yes\n\tset calbeep no\n\tset _logfile automatic\n"
        "\tset sacc_vel_thr 35\n\tset sacc_acc_thr 9500\n"
        "\tset alea_api_key \"Contact Alea for an API key\"\n\tset alea_animated_calibration no\n"
        "\tset eyelink_force_drift_correct yes\n\tset eyelink_pupil_size_mode area\n"
        "\tset smi_ip 127.0.0.1\n\tset smi_send_port 4444\n\tset smi_recv_port 5555\n"
        "\tset tobiiglasses_address 192.168.71.50\n\tset tobiiglasses_udpport 49152\n"
        "\tset description \"Initialize and calibrate the eye tracker (advanced dummy: mouse = gaze)\"\n\n"
        "define pygaze_drift_correct drift_correct\n\tset xpos 0\n\tset ypos 0\n"
        "\tset fixation_triggered no\n\tset target_color \"[foreground]\"\n"
        "\tset target_style default\n\tset draw_target yes\n"
        "\tset description \"Drift correction at screen centre\"\n\n"
        "define pygaze_start_recording start_recording\n\tset status_msg \"start_trial [count_trial_sequence]\"\n"
        "\tset description \"Start recording\"\n\n"
        "define pygaze_stop_recording stop_recording\n\tset status_msg stop_trial\n"
        "\tset description \"Stop recording\"\n\n"
        "define pygaze_log log_trial\n\tset throttle 2\n\tset auto_log no\n"
        "\tset msg \"TRIALINFO item={item}\"\n\tset description \"Log trial info\"\n\n"
        "define logger logger\n\tset description \"Default logger\"\n\tset auto_log yes\n\n")


# Shared geometry and gaze helpers. These are defined once, after pygaze_init
# has created the display, and are used by all trial inline scripts.
HELPERS = r'''
from openexp.canvas import Canvas
from openexp.keyboard import Keyboard

W, H = var.width, var.height

GAZE_SIZE = 50
GAZE_LEFT = 100
SENTENCE_LEFT = GAZE_LEFT + GAZE_SIZE // 2   # sentence starts in the target
CORNER_X = int(W * .9)
CORNER_Y = int(H * .9)
CORNER_SIZE = max(6, int(W * .005))

_probe = Canvas(exp)
CHARW = _probe.text_size('x')[0]             # monospace: constant char width

kb = Keyboard(exp, keylist=['escape'], timeout=0)


def add_corner(c):
    """Draw the small square that participants fixate to end the trial."""
    c.rect(int(W * .94) - W // 2, int(H * .94) - H // 2,
           CORNER_SIZE, CORNER_SIZE, fill=True, color='black')


def text_canvas(txt):
    """Left-aligned sentence at the published position, vertically centred."""
    c = Canvas(exp)
    c.text(txt, center=False, x=SENTENCE_LEFT - W // 2, color='black')
    add_corner(c)
    return c


def gaze_char(x):
    """Character index at an absolute gaze x coordinate."""
    return int((x - SENTENCE_LEFT) // CHARW)


def on_gaze_target(x, y):
    return (GAZE_LEFT <= x <= GAZE_LEFT + GAZE_SIZE and
            H / 2 - GAZE_SIZE / 2 <= y <= H / 2 + GAZE_SIZE / 2)


def on_corner(x, y):
    return x > CORNER_X and y > CORNER_Y


def wait_for_fixation(region, duration=250, timeout=None):
    """Wait until gaze stays inside `region` for `duration` ms.

    Returns True on success, False on timeout or when Escape is pressed.
    """
    t0 = clock.time()
    since = None
    while True:
        x, y = eyetracker.sample()
        if region(x, y):
            if since is None:
                since = clock.time()
            elif clock.time() - since >= duration:
                return True
        else:
            since = None
        key, _ = kb.get_key(timeout=0)
        if key == 'escape':
            return False
        if timeout is not None and clock.time() - t0 >= timeout:
            return False
        clock.sleep(5)


def gaze_target_canvas():
    c = Canvas(exp)
    c.rect(GAZE_LEFT - W // 2, -GAZE_SIZE // 2, GAZE_SIZE, GAZE_SIZE,
           fill=True, color='black')
    return c
'''

SETUP_CONDITION = r'''
if var.answer == 'SI':
    var.correct_button = '1'
elif var.answer == 'NO':
    var.correct_button = '2'
else:
    var.correct_button = 'NA'
# Avoid stale values from the previous trial when the question is skipped.
var.response = 'NA'
var.correct = 'NA'
var.response_time = 'NA'
var.trial_aborted = 0
'''

SHOW_GAZE_TARGET_PREPARE = r'''
gazetarget_canvas = gaze_target_canvas()
'''

SHOW_GAZE_TARGET_RUN = r'''
gazetarget_canvas.show()
eyetracker.log('GAZE TARGET ON')
if wait_for_fixation(on_gaze_target, duration=250, timeout=10000):
    var.trial_aborted = 0
else:
    var.trial_aborted = 1
    eyetracker.log('GAZE TARGET TIMEOUT/ABORT')
'''

READING_PREPARE = r'''
sentence_canvas = text_canvas(var.sentence)
'''

READING_RUN = r'''
if var.trial_aborted:
    eyetracker.log('TRIAL ABORTED')
else:
    sentence_canvas.show()
    eyetracker.log('STIMONSET')
    if not wait_for_fixation(on_corner, duration=100, timeout=60000):
        eyetracker.log('CORNER TIMEOUT')
    eyetracker.log('TRIALEND')
'''

BOUNDARY_PREPARE = r'''
# Simplify the published counterbalancing: practice is always identical, and
# experimental items alternate preview validity with subject parity.
sentence_number = int(var.sentence_number)
if var.block == 'practice':
    var.preview_condition = 'identical'
elif var.subject_parity == 'odd':
    var.preview_condition = 'dissimilar' if sentence_number % 2 == 0 else 'identical'
else:
    var.preview_condition = 'identical' if sentence_number % 2 == 0 else 'dissimilar'

posttarget = var.posttarget
if not posttarget.endswith('.'):
    posttarget += '.'

preview_word = var.changed if var.preview_condition == 'dissimilar' else var.target
pre_sentence = ' '.join([var.pretarget, preview_word, posttarget])
tar_sentence = ' '.join([var.pretarget, var.target, posttarget])

pre_canvas = text_canvas(pre_sentence)
tar_canvas = text_canvas(tar_sentence)

# Invisible boundary: right edge of the pre-target word + 0.4 character.
var.target_word_nr = len(var.pretarget.split())
var.boundary = SENTENCE_LEFT + pre_canvas.text_size(var.pretarget)[0] + 0.4 * CHARW
eyetracker.log('BOUNDARY x=%d target_word=%d' % (var.boundary, var.target_word_nr))
'''

BOUNDARY_RUN = r'''
if var.trial_aborted:
    eyetracker.log('TRIAL ABORTED')
else:
    pre_canvas.show()
    eyetracker.log('STIMONSET preview=%s' % var.preview_condition)
    changed = False
    t0 = clock.time()
    while not changed:
        x, y = eyetracker.sample()
        if x > var.boundary:
            t_pre = clock.time()
            t_post = tar_canvas.show()
            eyetracker.log('DISPLAYCHANGE latency=%d' % (t_post - t_pre))
            changed = True
        key, _ = kb.get_key(timeout=0)
        if key == 'escape':
            var.trial_aborted = 1
            break
        if clock.time() - t0 > 60000:
            eyetracker.log('BOUNDARY TIMEOUT')
            break
        clock.sleep(5)
    var.display_changed = int(changed)
    if not var.trial_aborted:
        if not wait_for_fixation(on_corner, duration=100, timeout=60000):
            eyetracker.log('CORNER TIMEOUT')
    eyetracker.log('TRIALEND changed=%d' % changed)
'''

MOVINGWINDOW_PREPARE = r'''
window = int(var.window)
sentence = var.sentence


def masked(centre):
    return ''.join(c if c == ' ' or abs(i - centre) <= window else 'x'
                   for i, c in enumerate(sentence))


masked_canvas = text_canvas(masked(0))
'''

MOVINGWINDOW_RUN = r'''
if var.trial_aborted:
    eyetracker.log('TRIAL ABORTED')
else:
    masked_canvas.show()
    eyetracker.log('STIMONSET')
    last = 0
    corner_since = None
    t0 = clock.time()
    while True:
        x, y = eyetracker.sample()
        if on_corner(x, y):
            if corner_since is None:
                corner_since = clock.time()
            elif clock.time() - corner_since >= 100:
                break
        else:
            corner_since = None
            char = min(max(gaze_char(x), 0), len(sentence) - 1)
            if char != last:
                text_canvas(masked(char)).show()
                eyetracker.log('WINDOWMOVE char=%d' % char)
                last = char
        key, _ = kb.get_key(timeout=0)
        if key == 'escape':
            var.trial_aborted = 1
            break
        if clock.time() - t0 > 60000:
            eyetracker.log('CORNER TIMEOUT')
            break
        clock.sleep(5)
    eyetracker.log('TRIALEND')
'''

VWP_PREPARE = r'''
import random

SIZE = 200
POS = [(-W // 4, -H // 4), (W // 4, -H // 4), (-W // 4, H // 4), (W // 4, H // 4)]
objects = [var.target, var.competitor, var.distractor1, var.distractor2]
random.shuffle(objects)
var.target_position = objects.index(var.target)


def scene(instruction=None):
    c = Canvas(exp)
    for name, (x, y) in zip(objects, POS):
        c.rect(x - SIZE // 2, y - SIZE // 2, SIZE, SIZE, color='black')
        c.text(name, x=x, y=y)       # replace by c.image('name.png', ...) for pictures
    add_corner(c)
    if instruction:
        c.text(instruction, y=-H // 2 + 40)
    return c


def region(gx, gy):
    for i, (x, y) in enumerate(POS):
        if abs(gx - W / 2 - x) <= SIZE // 2 and abs(gy - H / 2 - y) <= SIZE // 2:
            return i
    return None


preview = scene()
spoken = scene(var.sentence)
'''

VWP_RUN = r'''
if var.trial_aborted:
    eyetracker.log('TRIAL ABORTED')
else:
    preview.show()
    eyetracker.log('PREVIEW_ONSET')
    clock.sleep(1000)
    spoken.show()
    eyetracker.log('SPOKEN_ONSET')          # play a sampler here for real audio
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
    if not wait_for_fixation(on_corner, duration=100, timeout=60000):
        eyetracker.log('CORNER TIMEOUT')
    eyetracker.log('TRIALEND')
'''

QUESTION_ITEMS = (
    "define sketchpad comprehension_question\n"
    "\tset start_response_interval no\n"
    "\tset duration 0\n"
    "\tset description \"Comprehension question\"\n"
    "\tdraw textline center=1 color=black font_bold=no font_family=mono font_italic=no font_size=24 html=yes show_if=always text=\"[question]\" x=0 y=-64 z_index=0\n"
    "\tdraw textline center=1 color=black font_bold=no font_family=mono font_italic=no font_size=24 html=yes show_if=always text=\"SI\" x=-128 y=64 z_index=0\n"
    "\tdraw textline center=1 color=black font_bold=no font_family=mono font_italic=no font_size=24 html=yes show_if=always text=\"NO\" x=128 y=64 z_index=0\n"
    "\tdraw textline center=1 color=black font_bold=no font_family=mono font_italic=no font_size=24 html=yes show_if=always text=\"1 = SI&nbsp;&nbsp;&nbsp;2 = NO\" x=0 y=160 z_index=0\n\n"
    "define keyboard_response keyboard_response\n"
    "\tset timeout infinite\n\tset flush yes\n\tset event_type keypress\n"
    "\tset duration keypress\n\tset description \"Collects the yes/no response\"\n"
    "\tset correct_response \"[correct_button]\"\n\tset allowed_responses \"1;2\"\n\n"
)


TRIAL_SEQUENCE = (
    "define sequence trial_sequence\n\tset flush_keyboard yes\n"
    "\tset description \"One trial\"\n"
    "\trun setup_condition always\n"
    "\trun prepare_trial always\n"
    "\trun drift_correct always\n"
    "\trun start_recording always\n"
    "\trun log_trial always\n"
    "\trun show_gaze_target always\n"
    "\trun trial_display always\n"
    "\trun comprehension_question \"[question] != \\\"NA\\\" and [trial_aborted] == 0\"\n"
    "\trun keyboard_response \"[question] != \\\"NA\\\" and [trial_aborted] == 0\"\n"
    "\trun clear_screen always\n"
    "\trun logger always\n"
    "\trun stop_recording always\n\n"
)


def experiment(title, description, instructions, prepare, run, *,
               practice_rows=None, blocks=None, rows=None):
    s = HEADER.format(title=title, description=description)

    s += ("define sequence experiment\n\tset flush_keyboard yes\n"
          "\tset description \"Main sequence\"\n"
          "\trun pygaze_init always\n"
          "\trun setup_helpers always\n"
          "\trun instructions always\n")
    if practice_rows:
        s += ("\trun practice_loop always\n"
              "\trun end_of_practice always\n")
        for i in range(1, len(blocks) + 1):
            s += "\trun experimental_loop_%d always\n" % i
            if i < len(blocks):
                s += "\trun break_instr always\n"
    else:
        s += "\trun trial_loop always\n"
    s += "\trun goodbye always\n\n"

    s += TRIAL_SEQUENCE
    s += pygaze_items()
    s += inline("setup_helpers", "", HELPERS,
                "Define shared geometry and gaze helpers")
    s += sketchpad("instructions", instructions, "Instructions")
    s += sketchpad("goodbye", "The experiment is finished.<br />Thank you!", "Goodbye")
    s += QUESTION_ITEMS
    s += empty_sketchpad("clear_screen", "Blank screen after the response")

    if practice_rows:
        s += sketchpad(
            "end_of_practice",
            "You have finished the practice block.<br /><br />"
            "If you have any questions, ask the experimenter now.<br /><br />"
            "Press any key to start the experiment.",
            "End of practice")
        s += sketchpad(
            "break_instr",
            "You can take a short break.<br /><br />"
            "Press any key to continue.",
            "Break")
        s += loop("practice_loop", "trial_sequence", practice_rows,
                  "Practice trials", order="sequential")
        for i, block in enumerate(blocks, 1):
            s += loop("experimental_loop_%d" % i, "trial_sequence", block,
                      "Experimental block %d" % i, order="random")
    else:
        s += loop("trial_loop", "trial_sequence", rows, "Trials")

    s += inline("setup_condition", SETUP_CONDITION, "",
                "Set the correct response button")
    s += inline("prepare_trial", prepare, "",
                "Prepare the trial canvases")
    s += inline("show_gaze_target", SHOW_GAZE_TARGET_PREPARE, SHOW_GAZE_TARGET_RUN,
                "Show the gaze-contingent target and wait for fixation")
    s += inline("trial_display", "", run,
                "Show the stimulus and end the trial at the corner")
    return s


def load_sentences():
    with open(SENTENCES_CSV, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def boundary_rows(raw):
    rows = []
    for r in raw:
        rows.append({
            "item": r["sentence_number"],
            "block": r["block"],
            "sentence_number": r["sentence_number"],
            "pretarget": r["pretarget"],
            "target": r["target"],
            "posttarget": r["posttarget"],
            "changed": r["changed"],
            "question": r["question"],
            "answer": r["answer"],
        })
    return rows


def build_experiments():
    sentences = load_sentences()
    practice = boundary_rows([r for r in sentences if r["block"] == "practice"])
    blocks = [boundary_rows([r for r in sentences if r["block"] == str(i)])
              for i in (1, 2, 3)]

    reading_rows = [
        {"item": 1, "condition": "high",
         "sentence": "The old fisherman repaired his net on the quiet beach.",
         "question": "Did the fisherman repair his net?", "answer": "SI"},
        {"item": 2, "condition": "low",
         "sentence": "The old fisherman repaired his rete on the quiet beach.",
         "question": "Did the fisherman repair his net?", "answer": "SI"},
        {"item": 3, "condition": "high",
         "sentence": "The small child opened the door to see the garden.",
         "question": "Did the child open the door?", "answer": "SI"},
        {"item": 4, "condition": "low",
         "sentence": "The small child opened the door to see the lawns.",
         "question": "Did the child open the door?", "answer": "SI"},
    ]
    movingwindow_rows = [
        {"item": 1, "window": 5,
         "sentence": "The explorers crossed the frozen river before sunset and made camp.",
         "question": "Did the explorers cross the river?", "answer": "SI"},
        {"item": 2, "window": 9,
         "sentence": "A small bakery on the corner sells fresh bread each morning.",
         "question": "Does the bakery sell bread?", "answer": "SI"},
    ]
    vwp_rows = [
        {"item": 1, "sentence": "Click on the candle", "target": "candle",
         "competitor": "candy", "distractor1": "chair", "distractor2": "apple",
         "question": "Did you look at the candle?", "answer": "SI"},
        {"item": 2, "sentence": "Click on the beetle", "target": "beetle",
         "competitor": "beaker", "distractor1": "lamp", "distractor2": "shoe",
         "question": "Did you look at the beetle?", "answer": "SI"},
    ]

    return {
        "reading": experiment(
            "Reading experiment",
            "Simple sentence reading with PyGaze, gaze target and comprehension questions",
            "Read each sentence silently.<br /><br />"
            "Keep your eyes on the black square at the start of the sentence; "
            "the sentence appears once you fixate it.<br /><br />"
            "When you have finished reading, look at the small black square "
            "in the bottom-right corner.<br /><br />"
            "Then answer the yes/no question: press 1 for SI, 2 for NO.<br /><br />"
            "Press any key to start.",
            READING_PREPARE, READING_RUN, rows=reading_rows),
        "boundary": experiment(
            "Boundary paradigm",
            "Gaze-contingent display change with the published Spanish sentences",
            "Read each sentence silently.<br /><br />"
            "Keep your eyes on the black square at the start of the sentence; "
            "the sentence appears once you fixate it.<br /><br />"
            "When you have finished reading, look at the small black square "
            "in the bottom-right corner.<br /><br />"
            "Then answer the yes/no question in Spanish: press 1 for SI, 2 for NO.<br /><br />"
            "Press any key to start.",
            BOUNDARY_PREPARE, BOUNDARY_RUN,
            practice_rows=practice, blocks=blocks),
        "movingwindow": experiment(
            "Moving window paradigm",
            "Gaze-contingent moving window with comprehension questions",
            "Read each sentence silently.<br /><br />"
            "Keep your eyes on the black square at the start of the sentence; "
            "the sentence appears once you fixate it.<br /><br />"
            "When you have finished reading, look at the small black square "
            "in the bottom-right corner.<br /><br />"
            "Then answer the yes/no question: press 1 for SI, 2 for NO.<br /><br />"
            "Press any key to start.",
            MOVINGWINDOW_PREPARE, MOVINGWINDOW_RUN, rows=movingwindow_rows),
        "vwp": experiment(
            "Visual world paradigm",
            "Four-object visual world with gaze target and comprehension questions",
            "Look at the black square at the start of each trial.<br /><br />"
            "Then look at the object named in the instruction.<br /><br />"
            "When the trial is over, look at the small black square in the "
            "bottom-right corner.<br /><br />"
            "Then answer the yes/no question: press 1 for SI, 2 for NO.<br /><br />"
            "Press any key to start.",
            VWP_PREPARE, VWP_RUN, rows=vwp_rows),
    }


def build():
    os.makedirs(OUT, exist_ok=True)
    for name, script in build_experiments().items():
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
