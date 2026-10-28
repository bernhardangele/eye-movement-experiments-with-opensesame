"""Builds the workshop experiments as OpenSesame .osexp files.

Run `python experiments/build_osexp.py` (any Python 3). Every experiment is
generated from the script text below, so the .osexp files can be re-created and
diffed easily; open them in OpenSesame as usual.

Experiments and their materials:

    reading       the published comma study (Spanish sentences with and
                  without commas), `comas.csv`, extracted from the EyeTrack
                  script in examples/frases-comas by extract_comas.py
    boundary      gaze-contingent display change, modelled on
                  examples/ella_experiment_A.osexp, `sentences.csv`
    movingwindow  gaze-contingent moving window, `movingwindow.csv`: the
                  sentences of examples/EyeLogic_LITE.osexp (extract_eyelogic.py)
    vwp           visual world: pictures + spoken instruction + mouse click,
                  `vwp_pool/` (made by make_vwp_stimuli.py)

All experiments use the same trial skeleton:

    drift correction -> start recording -> gaze target
    -> sentence / scene -> look at bottom-right corner to end the trial
    -> yes/no comprehension question -> stop recording

(the visual world trial ends with a mouse click instead). If the gaze target is
not fixated within 10 s, a drift correction is run and the target is shown
again; the experimenter can press C to re-calibrate. After the initial
calibration (and every re-calibration) a tracker-independent validation
measures the accuracy in degrees.

The experiments use the PyGaze plugin items (pygaze_init, pygaze_drift_correct,
pygaze_start_recording, pygaze_log, pygaze_stop_recording) and inline_script
items that only use the tracker-independent `eyetracker` object. The only
exception are the items `eyelink_setup`, `eyelink_trial_start` and
`eyelink_trial_end`: they draw on the EyeLink Host PC and write Data Viewer
messages, and do nothing with any other tracker.
Change the tracker in the pygaze_init item to run on real hardware.

After changing this file, run `python experiments/test_headless.py` to run
every experiment with a simulated participant.
"""
import csv
import io
import os
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "osexp")
SENTENCES_CSV = os.path.join(HERE, "sentences.csv")
COMAS_CSV = os.path.join(HERE, "comas.csv")
MOVINGWINDOW_CSV = os.path.join(HERE, "movingwindow.csv")
VWP_POOL = os.path.join(HERE, "vwp_pool")

# Geometry from the published experiment: a 50 px gaze target at x=100..150,
# the sentence starts in the middle of that target, and the trial ends when the
# bottom-right 10% x 10% corner is fixated for 100 ms.
#
# Lab settings at the end of the header: measure the screen and the viewing
# distance in your lab; they are used to express the validation error in
# degrees of visual angle.
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
set n_trials {n_trials}
set gaze_target_left {gaze_target_left}
set yes_label "{yes_label}"
set no_label "{no_label}"
set screen_width_cm 53
set viewing_distance_cm 70
set validation_threshold 1.0
set fixation_triggered_drift_check no
"""

TEXTS = {
    "en": {
        "yes": "YES", "no": "NO",
        "goodbye": "The experiment is finished.<br />Thank you!",
        "end_of_practice": "You have finished the practice block.<br /><br />"
                           "If you have any questions, ask the experimenter now.<br /><br />"
                           "Press any key to start the experiment.",
        "break": "You can take a short break.<br /><br />Press any key to continue.",
        "reading": "Read each sentence silently.<br /><br />"
                   "Keep your eyes on the black square at the start of the sentence; "
                   "the sentence appears once you fixate it.<br /><br />"
                   "When you have finished reading, look at the small black square "
                   "in the bottom-right corner.<br /><br />"
                   "Then answer the yes/no question: press 1 for YES, 2 for NO.<br /><br />"
                   "Press any key to start.",
    },
    "es": {
        "yes": "SÍ", "no": "NO",
        "goodbye": "El experimento ha concluido.<br />Gracias por su participación.",
        "end_of_practice": "Has llegado al final de la práctica.<br /><br />"
                           "Si tienes alguna duda, puedes preguntar ahora al/a la investigador/a.<br /><br />"
                           "Pulsa cualquier tecla para iniciar el experimento.",
        "break": "Ahora puedes hacer una pausa.<br /><br />Pulsa cualquier tecla para continuar.",
        "reading": "En este experimento leerás frases cortas.<br /><br />"
                   "Mira el cuadrado negro a la izquierda; la frase aparece "
                   "cuando lo fijas con la mirada.<br /><br />"
                   "Lee la frase con atención. Cuando hayas terminado, mira el "
                   "pequeño cuadrado en la esquina inferior derecha.<br /><br />"
                   "Después de algunas frases habrá una pregunta:<br />"
                   "pulsa 1 para SÍ y 2 para NO.<br /><br />"
                   "Pulsa cualquier tecla para empezar.",
    },
}


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


# The status message of start_recording is also shown on the EyeLink Host PC
# (other trackers print it to the console).
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
        "\tset fixation_triggered \"{fixation_triggered_drift_check}\"\n\tset target_color black\n"
        "\tset target_style default\n\tset draw_target yes\n"
        "\tset description \"Drift correction at screen centre (fixation-triggered if "
        "fixation_triggered_drift_check = yes)\"\n\n"
        "define pygaze_start_recording start_recording\n"
        "\tset status_msg \"trial {count_trial_sequence + 1}/{n_trials} item {item} {condition}\"\n"
        "\tset description \"Start recording; the status message is shown on the EyeLink Host PC\"\n\n"
        "define pygaze_stop_recording stop_recording\n\tset status_msg stop_trial\n"
        "\tset description \"Stop recording\"\n\n"
        "define pygaze_log log_trial\n\tset throttle 2\n\tset auto_log no\n"
        "\tset msg \"TRIALINFO item={item}\"\n\tset description \"Log trial info\"\n\n"
        "define logger logger\n\tset description \"Default logger\"\n\tset auto_log yes\n\n")


# Where is every letter on the screen? Used for interest areas, the boundary
# and the moving window. Kept separate so that check_interest_areas.py can test
# exactly this code against the rendered pixels. Needs `_probe` (a Canvas) and
# `SENTENCE_LEFT` (screen x at which sentences are drawn).
TEXT_LAYOUT = r'''
# Canvas.text_size() does NOT return the space that a text takes up on the
# screen: OpenSesame renders the text and returns the size of the *inked*
# pixels only. So
#   - trailing spaces are not counted: text_size('El ') == text_size('El');
#   - with center=True (the default) the empty pixels left of the first letter
#     and right of the last letter are not counted either, so the width
#     depends on which letters a text starts and ends with.
# Measuring prefixes of a sentence with text_size() therefore puts letter and
# word boundaries several pixels (up to ~0.7 letter) too far to the left.
# The correct measurement:
#   - center=False: measure from the drawing position, not from the first ink;
#   - add a '|' at the end and subtract the width of '|' alone: the empty
#     pixels after the last letter (and any spaces) are then counted exactly.
#   - give max_width = screen width: otherwise text wider than half the screen is
#     wrapped onto a second line and measured as two short lines.
# Qt draws text a few pixels to the right of the x you give it (the margin of
# its text document); the first letter starts there.
from qtpy.QtGui import QTextDocument

TEXT_MARGIN = QTextDocument().documentMargin()


def _inked_width(txt):
    return _probe.text_size(txt, center=False, html=False, max_width=W)[0]


_BAR = _inked_width('|')


def text_width(txt):
    """Horizontal space that `txt` takes up on the screen, in pixels."""
    return _inked_width(txt + '|') - _BAR


def letter_edges(sentence):
    """Screen x of the left edge of every character of `sentence`, followed
    by the right edge of the last character (len(sentence) + 1 values)."""
    left = SENTENCE_LEFT + TEXT_MARGIN
    return [left] + [left + text_width(sentence[:k])
                     for k in range(1, len(sentence) + 1)]
'''

# Shared geometry and gaze helpers. These are defined once, after pygaze_init
# has created the display, and are used by all trial inline scripts.
#
# NB: in OpenSesame 4, global variables in inline scripts *are* experimental
# variables (`x = 1` is the same as `var.x = 1`) and end up in the log file.
# Never reuse a loop-table column name for a helper variable, or the logged
# value is overwritten.
HELPERS = r'''
import bisect
import math
from openexp.canvas import Canvas
from openexp.keyboard import Keyboard

W, H = var.width, var.height

GAZE_SIZE = 50
GAZE_LEFT = int(var.gaze_target_left)
SENTENCE_LEFT = GAZE_LEFT + GAZE_SIZE // 2   # sentence starts in the target
CORNER_X = int(W * .9)
CORNER_Y = int(H * .9)
CORNER_SIZE = max(6, int(W * .005))

_probe = Canvas(exp)                         # for measuring text
TEXT_H = _probe.text_size('x')[1]
TEXT_TOP = -TEXT_H // 2                      # vertically centre the line
''' + TEXT_LAYOUT + r'''

# Experimenter keys while waiting for gaze: Escape = pause, C = re-calibrate.
kb = Keyboard(exp, keylist=['escape', 'c'], timeout=0)

# Interest areas of the current trial: (label, left, top, right, bottom) in
# screen pixels, and the x of every letter edge (see letter_edges()). Every
# prepare_trial script sets them.
interest_areas = []
letter_x = []


def ascii_safe(text):
    """Tracker data files (EDF) do not like non-ASCII characters."""
    return str(text).encode('ascii', 'replace').decode().replace(' ', '_')


def add_corner(c):
    """Draw the small square that participants fixate to end the trial."""
    c.rect(int(W * .94) - W // 2, int(H * .94) - H // 2,
           CORNER_SIZE, CORNER_SIZE, fill=True, color='black')


def text_canvas(txt):
    """Left-aligned sentence starting inside the gaze target, vertically centred."""
    c = Canvas(exp)
    c.text(txt, center=False, x=SENTENCE_LEFT - W // 2, y=TEXT_TOP,
           color='black', html=False)
    add_corner(c)
    return c


def gaze_char(x):
    """Index of the character at screen x (uses letter_x of this trial)."""
    i = bisect.bisect_right(letter_x, x) - 1
    return min(max(i, 0), len(letter_x) - 2)


def word_areas(sentence, edges):
    """One interest area per word, one text line above and below; `edges`
    comes from letter_edges(sentence). The areas touch: the space after a
    word belongs to that word."""
    areas = []
    start = 0
    for word in sentence.split(' '):
        end = min(start + len(word) + 1, len(sentence))   # incl. the space
        areas.append((word, round(edges[start]), H // 2 - TEXT_H,
                      round(edges[end]), H // 2 + TEXT_H))
        start += len(word) + 1
    return areas


def log_interest_areas():
    """Write the interest areas (words or pictures) and, for sentences, the
    position of every letter to the tracker data file."""
    for n, (label, left, top, right, bottom) in enumerate(interest_areas, 1):
        eyetracker.log('REGION n=%d label=%s left=%d top=%d right=%d bottom=%d'
                       % (n, ascii_safe(label), left, top, right, bottom))
    word, n = 1, 0
    for k, ch in enumerate(var.get('sentence', '') if letter_x else ''):
        if ch == ' ':
            word, n = word + 1, 0
            continue
        n += 1
        eyetracker.log('LETTER word=%d n=%d char=%s left=%d right=%d'
                       % (word, n, ascii_safe(ch), round(letter_x[k]),
                          round(letter_x[k + 1])))


def on_gaze_target(x, y):
    return (GAZE_LEFT <= x <= GAZE_LEFT + GAZE_SIZE and
            H / 2 - GAZE_SIZE / 2 <= y <= H / 2 + GAZE_SIZE / 2)


def on_corner(x, y):
    return x > CORNER_X and y > CORNER_Y


def wait_for_fixation(region, duration, timeout=None, keys=('escape',)):
    """Wait until gaze stays inside `region` for `duration` ms.

    Returns 'fixated', 'timeout', or the key in `keys` that was pressed.
    Escape first shows OpenSesame's pause screen (Space = resume, Q = quit);
    'escape' is returned after the experimenter resumes.
    """
    t0 = clock.time()
    since = None
    while True:
        x, y = eyetracker.sample()
        if region(x, y):
            if since is None:
                since = clock.time()
            elif clock.time() - since >= duration:
                return 'fixated'
        else:
            since = None
        key, _ = kb.get_key(keylist=list(keys), timeout=0)
        if key is not None:
            return key
        if timeout is not None and clock.time() - t0 >= timeout:
            return 'timeout'
        clock.sleep(5)


def end_trial_at_corner():
    """End the trial when the corner square is fixated for 100 ms.

    Escape aborts the trial (the comprehension question is then skipped).
    """
    result = wait_for_fixation(on_corner, duration=100, timeout=60000)
    if result == 'escape':
        var.trial_aborted = 1
        eyetracker.log('TRIAL ABORTED')
    elif result == 'timeout':
        eyetracker.log('CORNER TIMEOUT')
    eyetracker.log('TRIALEND')


def gaze_target_canvas():
    c = Canvas(exp)
    c.rect(GAZE_LEFT - W // 2, -GAZE_SIZE // 2, GAZE_SIZE, GAZE_SIZE,
           fill=True, color='black')
    return c


# Validation: works with every tracker. Five dots; for each, the median gaze
# position over 500 ms is compared with the dot. The error is converted to
# degrees of visual angle with screen_width_cm and viewing_distance_cm.
VALIDATION_POINTS = [(.5, .5), (.2, .2), (.8, .2), (.2, .8), (.8, .8)]


def px_to_deg(px):
    cm = px * float(var.screen_width_cm) / W
    return math.degrees(math.atan2(cm, float(var.viewing_distance_cm)))


def validate():
    """Show the validation dots; returns the error per dot in degrees."""
    eyetracker.start_recording()
    errors = []
    for fx, fy in VALIDATION_POINTS:
        x, y = int(fx * W), int(fy * H)
        c = Canvas(exp)
        c.fixdot(x - W // 2, y - H // 2)
        c.show()
        eyetracker.log('VALIDATION POINT x=%d y=%d' % (x, y))
        clock.sleep(1000)                 # time to move the eyes to the dot
        xs, ys = [], []
        t0 = clock.time()
        while clock.time() - t0 < 500:
            gx, gy = eyetracker.sample()
            xs.append(gx)
            ys.append(gy)
            clock.sleep(5)
        gx, gy = sorted(xs)[len(xs) // 2], sorted(ys)[len(ys) // 2]
        errors.append(px_to_deg(math.hypot(gx - x, gy - y)))
        eyetracker.log('VALIDATION ERROR x=%d y=%d deg=%.2f' % (x, y, errors[-1]))
    eyetracker.stop_recording()
    return errors


def calibrate_and_validate():
    """Validate until the experimenter accepts (Space) or re-calibrate (C).

    Call this only while the tracker is not recording.
    """
    while True:
        errors = validate()
        mean_error, max_error = sum(errors) / len(errors), max(errors)
        good = max_error <= float(var.validation_threshold)
        c = Canvas(exp)
        c.text('Validation: mean error %.2f°, max %.2f° (%s)<br /><br />'
               'Experimenter: Space = continue, C = calibrate again'
               % (mean_error, max_error,
                  'good' if good else 'above %s°' % var.validation_threshold))
        c.show()
        key, _ = Keyboard(exp, keylist=['space', 'c'], timeout=None).get_key()
        eyetracker.log('VALIDATION RESULT mean=%.2f max=%.2f accepted=%d'
                       % (mean_error, max_error, key == 'space'))
        if key == 'space':
            var.validation_mean_error = round(mean_error, 2)
            var.validation_max_error = round(max_error, 2)
            return
        eyetracker.calibrate()
'''

# ---------------------------------------------------------------------------
# EyeLink-only extras. Everything below talks to the EyeLink Host PC (the
# experimenter's screen) or writes messages for EyeLink Data Viewer. These
# commands do not exist on other trackers, so with any other tracker (and with
# the dummy) the three eyelink_* items do nothing.
# ---------------------------------------------------------------------------
EYELINK_SETUP = r'''
# EYELINK ONLY. Drawing on the experimenter's screen (Host PC) and the
# Data Viewer messages only work with an SR Research EyeLink. With any other
# tracker this item and eyelink_trial_start/eyelink_trial_end do nothing.
EYELINK = items['pygaze_init'].var.tracker_type == 'EyeLink'
if not EYELINK:
    print('EyeLink extras are off (tracker: %s)'
          % items['pygaze_init'].var.tracker_type)

# Trial variables that Data Viewer shows (!V TRIAL_VAR), if they exist.
EYELINK_TRIAL_VARS = ['item', 'condition', 'response', 'correct',
                      'trial_aborted', 'display_change_latency', 'clicked',
                      'click_rt']

# EyeLink Host PC colours: 0 black, 2 green, 4 red, 7 light grey, 15 white.


def eyelink_draw_host():
    """EyeLink only: draw the trial layout on the Host PC screen.

    Gaze target (grey), interest areas (white boxes), boundary (red line,
    boundary experiment only) and the corner square. The Host PC screen is
    cleared by calibration and drift correction, so call this again after them.
    """
    if not EYELINK:
        return
    eyetracker.send_command('clear_screen 0')
    eyetracker.send_command('draw_filled_box %d %d %d %d 7' % (
        GAZE_LEFT, H // 2 - GAZE_SIZE // 2,
        GAZE_LEFT + GAZE_SIZE, H // 2 + GAZE_SIZE // 2))
    for label, left, top, right, bottom in interest_areas:
        eyetracker.send_command('draw_box %d %d %d %d 15'
                                % (left, top, right, bottom))
    if 'boundary' in var:
        eyetracker.send_command('draw_line %d 0 %d %d 4'
                                % (var.boundary, var.boundary, H))
    eyetracker.send_command('draw_filled_box %d %d %d %d 2' % (
        int(W * .94), int(H * .94), int(W * .94) + CORNER_SIZE,
        int(H * .94) + CORNER_SIZE))


if EYELINK:
    # Data Viewer: screen size, needed to show fixations on the stimulus.
    eyetracker.log('DISPLAY_COORDS 0 0 %d %d' % (W - 1, H - 1))
'''

EYELINK_TRIAL_START = r'''
# EYELINK ONLY (does nothing with other trackers). Runs after the drift
# correction and before recording starts: marks the trial for Data Viewer,
# defines the interest areas, and draws the layout on the Host PC.
if EYELINK:
    eyetracker.log('TRIALID %d' % (var.count_trial_sequence + 1))
    for n, (label, left, top, right, bottom) in enumerate(interest_areas, 1):
        eyetracker.log('!V IAREA RECTANGLE %d %d %d %d %d %s'
                       % (n, left, top, right, bottom, ascii_safe(label)))
    eyelink_draw_host()
'''

EYELINK_TRIAL_END = r'''
# EYELINK ONLY (does nothing with other trackers). Trial variables for
# Data Viewer, then the end-of-trial marker.
if EYELINK:
    for name in EYELINK_TRIAL_VARS:
        if name in var:
            eyetracker.log('!V TRIAL_VAR %s %s' % (name, ascii_safe(var.get(name))))
    eyetracker.log('TRIAL_RESULT 0')
'''

VALIDATE_CALIBRATION = r'''
# pygaze_init has calibrated; check the accuracy before the experiment starts.
calibrate_and_validate()
'''

SETUP_CONDITION = r'''
if var.answer in ('SI', 'YES'):
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

# The stimulus only appears once the gaze target has been fixated for 250 ms.
# If that does not happen within 10 s (or the experimenter presses Escape and
# resumes), the calibration has probably drifted: run a drift correction and
# show the target again, as in the published experiment. The experimenter can
# also press C for a full re-calibration followed by a validation.
SHOW_GAZE_TARGET_RUN = r'''
while True:
    gazetarget_canvas.show()
    eyetracker.log('GAZE TARGET ON')
    result = wait_for_fixation(on_gaze_target, duration=250, timeout=10000,
                               keys=('escape', 'c'))
    if result == 'fixated':
        break
    eyetracker.stop_recording()          # (re)calibration needs recording off
    if result == 'c':
        eyetracker.log('GAZE TARGET RECALIBRATION')
        eyetracker.calibrate()
        calibrate_and_validate()
    else:
        eyetracker.log('GAZE TARGET %s: drift correction' % result.upper())
        eyetracker.drift_correction(
            fix_triggered=var.fixation_triggered_drift_check == 'yes')
    eyelink_draw_host()                  # EyeLink only; nothing otherwise
    eyetracker.start_recording()
'''

# Counterbalancing with two lists. Every participant reads every item once,
# half of the items with commas and half without:
#   list A (even subject numbers): odd items with commas, even items without
#   list B (odd subject numbers):  odd items without commas, even items with
# So across every pair of participants (one A, one B), every item is read in
# both conditions. Practice sentences are always shown as they are.
# (Not called `list`: that would hide Python's list() in all inline scripts.)
READING_PREPARE = r'''
var.item_list = 'A' if var.subject_parity == 'even' else 'B'
if var.block == 'practice':
    var.condition = 'practice'
    var.sentence = var.comma
else:
    odd_item = int(var.item) % 2 == 1
    with_comma = odd_item if var.item_list == 'A' else not odd_item
    var.condition = 'comma' if with_comma else 'no_comma'
    var.sentence = var.comma if with_comma else var.no_comma
sentence_canvas = text_canvas(var.sentence)
letter_x = letter_edges(var.sentence)
interest_areas = word_areas(var.sentence, letter_x)
'''

READING_RUN = r'''
sentence_canvas.show()
eyetracker.log('STIMONSET')
log_interest_areas()
end_trial_at_corner()
'''

BOUNDARY_PREPARE = r'''
# Practice is always identical. Experimental items alternate preview validity
# with subject parity (the block order is set by `counterbalance`).
sentence_number = int(var.sentence_number)
if var.block == 'practice':
    var.preview_condition = 'identical'
elif var.subject_parity == 'odd':
    var.preview_condition = 'dissimilar' if sentence_number % 2 == 0 else 'identical'
else:
    var.preview_condition = 'identical' if sentence_number % 2 == 0 else 'dissimilar'
var.condition = var.preview_condition

# Every sentence ends with a full stop.
ending = var.posttarget if var.posttarget.endswith('.') else var.posttarget + '.'

# Before the boundary the target position shows the preview: the target word
# itself (identical) or the `changed` word (dissimilar).
preview_word = var.changed if var.preview_condition == 'dissimilar' else var.target
pre_sentence = ' '.join([var.pretarget, preview_word, ending])
tar_sentence = ' '.join([var.pretarget, var.target, ending])

pre_canvas = text_canvas(pre_sentence)
tar_canvas = text_canvas(tar_sentence)
var.sentence = tar_sentence
letter_x = letter_edges(tar_sentence)
interest_areas = word_areas(tar_sentence, letter_x)

# Invisible boundary: right edge of the last letter of the pre-target word
# (= left edge of the space before the target) + 0.4 of the width of an X.
var.target_word_nr = len(var.pretarget.split()) + 1
var.boundary = letter_x[len(var.pretarget)] + 0.4 * text_width('X')
eyetracker.log('BOUNDARY x=%d target_word=%d' % (var.boundary, var.target_word_nr))
'''

# Poll the gaze as fast as possible (no sleep): the display change has to
# be completed during the saccade that crosses the boundary.
BOUNDARY_RUN = r'''
pre_canvas.show()
eyetracker.log('STIMONSET preview=%s' % var.preview_condition)
log_interest_areas()
# Not called `changed`: that is the loop column with the preview word.
var.display_changed = 0
var.display_change_latency = 'NA'
t0 = clock.time()
while True:
    x, y = eyetracker.sample()
    if x > var.boundary:
        t_pre = clock.time()
        t_post = tar_canvas.show()
        var.display_change_latency = t_post - t_pre
        eyetracker.log('DISPLAYCHANGE latency=%d' % var.display_change_latency)
        var.display_changed = 1
        break
    key, _ = kb.get_key(keylist=['escape'], timeout=0)
    if key == 'escape':
        var.trial_aborted = 1
        eyetracker.log('TRIAL ABORTED')
        break
    if clock.time() - t0 > 60000:
        eyetracker.log('BOUNDARY TIMEOUT')
        break
if var.trial_aborted:
    eyetracker.log('TRIALEND')
else:
    end_trial_at_corner()
'''

# Full counterbalancing as in the published experiment: the order of the three
# experimental blocks rotates with subject_nr % 3. Together with the parity
# rule for the preview condition, subject numbers 1-6 cover all combinations.
COUNTERBALANCE = r'''
orders = {1: (1, 2, 3), 2: (2, 3, 1), 0: (3, 1, 2)}
var.block_at_1, var.block_at_2, var.block_at_3 = orders[var.subject_nr % 3]
var.block_order = '%d-%d-%d' % orders[var.subject_nr % 3]
print('Block order: %s, preview rule: %s subject number'
      % (var.block_order, var.subject_parity))
'''

# `window` = number of characters visible on each side of the fixated
# character (window 5 -> 11 visible characters). One canvas per character
# position is prepared in advance, so that updating the window during reading
# only takes a `show()`.
MOVINGWINDOW_PREPARE = r'''
# Two lists, as in the reading experiment: list A (even subject numbers)
# reads the odd items with the small window, list B with the large one.
var.item_list = 'A' if var.subject_parity == 'even' else 'B'
odd_item = int(var.item) % 2 == 1
small = odd_item if var.item_list == 'A' else not odd_item
var.window = var.window_small if small else var.window_large
var.condition = 'window_%s' % var.window


def masked(centre):
    half = int(var.window)
    return ''.join(c if c == ' ' or abs(i - centre) <= half else 'x'
                   for i, c in enumerate(var.sentence))


window_canvases = [text_canvas(masked(i)) for i in range(len(var.sentence))]
letter_x = letter_edges(var.sentence)
interest_areas = word_areas(var.sentence, letter_x)
'''

# Like wait_for_fixation(on_corner, ...), but the window follows the gaze
# while the participant reads.
#
# The window must not flicker when a fixation lies on a letter boundary and the
# gaze drifts (or the tracker's noise wobbles) across it. So the window is
# *locked* during a fixation and only moves after a saccade:
#   - locked: the window stays, until the gaze is at least
#     `min_saccade_letters` away from where it was locked (= a saccade);
#   - following: during the saccade the window follows the gaze, until the
#     gaze has stayed within half that distance for 20 ms (= the new
#     fixation); then it is locked again at the landing position. While
#     following, the window only moves when the gaze is more than half a
#     letter past the edge of the current letter, so that it does not flicker
#     while the eyes land on a letter boundary.
# (Simply ignoring changes of less than min_saccade_letters would not work:
# a saccade is sampled many times in flight, each step is small, and the
# window could stop short of the landing position.)
MOVINGWINDOW_RUN = r'''
window_canvases[0].show()
eyetracker.log('STIMONSET')
log_interest_areas()
letter_w = (letter_x[-1] - letter_x[0]) / len(var.sentence)
min_shift = float(var.min_saccade_letters) * letter_w
dead_zone = 0.5 * letter_w
current = 0
following = True            # until the first fixation has settled
locked_x = None
settle_x = settle_t = None
corner_since = None
t0 = clock.time()
while True:
    x, y = eyetracker.sample()
    now = clock.time()
    if on_corner(x, y):
        if corner_since is None:
            corner_since = now
        elif now - corner_since >= 100:
            break
    else:
        corner_since = None
        if not following and abs(x - locked_x) >= min_shift:
            following = True                       # a saccade started
            settle_x = settle_t = None
        if following and not (letter_x[current] - dead_zone <= x
                              <= letter_x[current + 1] + dead_zone):
            char = min(max(gaze_char(x), 0), len(var.sentence) - 1)
            if char != current:
                window_canvases[char].show()
                eyetracker.log('WINDOWMOVE char=%d' % char)
                current = char
        if following:
            if settle_x is None or abs(x - settle_x) > min_shift / 2:
                settle_x, settle_t = x, now        # still moving
            elif now - settle_t >= 20:
                following = False                  # fixation: lock the window
                locked_x = settle_x
    key, _ = kb.get_key(keylist=['escape'], timeout=0)
    if key == 'escape':
        var.trial_aborted = 1
        eyetracker.log('TRIAL ABORTED')
        break
    if clock.time() - t0 > 60000:
        eyetracker.log('CORNER TIMEOUT')
        break
eyetracker.log('TRIALEND')
'''

# Pictures and sound come from the file pool (`pool[...]` gives the path).
# Objects are placed in the four quadrants in a new random order every trial.
VWP_PREPARE = r'''
import random
from openexp.sampler import Sampler
from openexp.mouse import Mouse

SIZE = 240
POS = [(-W // 4, -H // 4), (W // 4, -H // 4), (-W // 4, H // 4), (W // 4, H // 4)]
objects = [var.target, var.competitor, var.distractor1, var.distractor2]
random.shuffle(objects)
var.target_position = objects.index(var.target)
var.object_order = ';'.join(objects)          # top-left, top-right, ...
var.condition = var.target

scene = Canvas(exp)
for name, (x, y) in zip(objects, POS):
    scene.image(pool[name + '.png'], x=x, y=y)
interest_areas = [(name, x + W // 2 - SIZE // 2, y + H // 2 - SIZE // 2,
                   x + W // 2 + SIZE // 2, y + H // 2 + SIZE // 2)
                  for name, (x, y) in zip(objects, POS)]

instruction = Sampler(exp, pool[var.sound_file])     # loaded now, played later
mouse = Mouse(exp, visible=True)


def object_at(x, y):
    """Index of the object at screen position (x, y), or None."""
    for i, (name, left, top, right, bottom) in enumerate(interest_areas):
        if left <= x <= right and top <= y <= bottom:
            return i
    return None
'''

# Preview the objects for 1 s, play the spoken instruction ("Click on the
# candle") and wait for a click on one of the objects. The target word starts
# `target_onset` ms after the sound starts (known from make_vwp_stimuli.py);
# TARGET_ONSET is time 0 for the analysis. Gaze samples on each object after
# target onset are counted as a quick check; the real analysis uses the
# samples in the tracker file.
#
# AUDIO_ONSET is logged right after play() returns. The sound reaches the
# loudspeakers a little later (sound card buffer: sound_buf_size / sound_freq
# = 21 ms, plus the driver). Measure this delay in the lab (microphone +
# photodiode) and correct for it in the analysis.
VWP_RUN = r'''
scene.show()
eyetracker.log('PREVIEW_ONSET')
log_interest_areas()
clock.sleep(1000)
instruction.play()
t_audio = clock.time()
eyetracker.log('AUDIO_ONSET file=%s target_onset=%d'
               % (var.sound_file, int(var.target_onset)))
t_target = t_audio + int(var.target_onset)
target_logged = False
counts = [0] * 4
clicked_index = None
while True:
    now = clock.time()
    if not target_logged and now >= t_target:
        eyetracker.log('TARGET_ONSET')
        target_logged = True
    gx, gy = eyetracker.sample()
    looked_at = object_at(gx, gy)
    if target_logged and looked_at is not None:
        counts[looked_at] += 1
    button, position, t_click = mouse.get_click(timeout=0)
    if button is not None:
        # The mouse uses canvas coordinates: (0, 0) is the screen centre.
        clicked_index = object_at(position[0] + W // 2, position[1] + H // 2)
        if clicked_index is not None:
            break
    key, _ = kb.get_key(keylist=['escape'], timeout=0)
    if key == 'escape':
        var.trial_aborted = 1
        eyetracker.log('TRIAL ABORTED')
        break
    if now - t_audio > 10000:
        eyetracker.log('CLICK TIMEOUT')
        break
    clock.sleep(5)
mouse.show_cursor(False)
var.clicked = objects[clicked_index] if clicked_index is not None else 'NA'
var.click_correct = int(var.clicked == var.target)
var.click_rt = t_click - t_target if clicked_index is not None else 'NA'
var.target_samples = counts[var.target_position]
eyetracker.log('CLICK object=%s rt=%s' % (var.clicked, var.click_rt))
eyetracker.log('TRIALEND')
'''

QUESTION_ITEMS = (
    "define sketchpad comprehension_question\n"
    "\tset start_response_interval no\n"
    "\tset duration 0\n"
    "\tset description \"Comprehension question\"\n"
    "\tdraw textline center=1 color=black font_bold=no font_family=mono font_italic=no font_size=24 html=yes show_if=always text=\"{question}\" x=0 y=-64 z_index=0\n"
    "\tdraw textline center=1 color=black font_bold=no font_family=mono font_italic=no font_size=24 html=yes show_if=always text=\"{yes_label}\" x=-128 y=64 z_index=0\n"
    "\tdraw textline center=1 color=black font_bold=no font_family=mono font_italic=no font_size=24 html=yes show_if=always text=\"{no_label}\" x=128 y=64 z_index=0\n"
    "\tdraw textline center=1 color=black font_bold=no font_family=mono font_italic=no font_size=24 html=yes show_if=always text=\"1 = {yes_label}&nbsp;&nbsp;&nbsp;2 = {no_label}\" x=0 y=160 z_index=0\n\n"
    "define keyboard_response keyboard_response\n"
    "\tset timeout infinite\n\tset flush yes\n\tset event_type keypress\n"
    "\tset duration keypress\n\tset description \"Collects the yes/no response\"\n"
    "\tset correct_response \"{correct_button}\"\n\tset allowed_responses \"1;2\"\n\n"
)


TRIAL_SEQUENCE = (
    "define sequence trial_sequence\n\tset flush_keyboard yes\n"
    "\tset description \"One trial\"\n"
    "\trun setup_condition always\n"
    "\trun prepare_trial always\n"
    "\trun drift_correct always\n"
    "\trun eyelink_trial_start always\n"
    "\trun start_recording always\n"
    "\trun log_trial always\n"
    "\trun show_gaze_target always\n"
    "\trun trial_display always\n"
    "\trun comprehension_question \"question != 'NA' and trial_aborted == 0\"\n"
    "\trun keyboard_response \"question != 'NA' and trial_aborted == 0\"\n"
    "\trun clear_screen always\n"
    "\trun logger always\n"
    "\trun stop_recording always\n"
    "\trun eyelink_trial_end always\n\n"
)


def experiment(title, description, instructions, prepare, run, *, lang="en",
               practice_rows=None, blocks=None, rows=None, rotate_blocks=False,
               gaze_target_left=100, extra_vars=None):
    texts = TEXTS[lang]
    n_trials = (len(practice_rows) + sum(len(b) for b in blocks)
                if practice_rows else len(rows))
    s = HEADER.format(title=title, description=description, n_trials=n_trials,
                      gaze_target_left=gaze_target_left,
                      yes_label=texts["yes"], no_label=texts["no"])
    for name, value in (extra_vars or {}).items():
        s += "set %s %s\n" % (name, value)

    s += ("define sequence experiment\n\tset flush_keyboard yes\n"
          "\tset description \"Main sequence\"\n"
          "\trun pygaze_init always\n"
          "\trun setup_helpers always\n"
          "\trun eyelink_setup always\n"
          "\trun validate_calibration always\n"
          "\trun instructions always\n")
    if practice_rows:
        # Variables must exist before the first trial is logged: OpenSesame
        # fixes the columns of the log file at the first `logger` call.
        if rotate_blocks:
            s += "\trun counterbalance always\n"
        s += ("\trun practice_loop always\n"
              "\trun end_of_practice always\n")
        n = len(blocks)
        for position in range(1, n + 1):
            if rotate_blocks:
                # The block at this position depends on the subject number.
                for b in range(1, n + 1):
                    s += ("\trun experimental_loop_%d \"block_at_%d == %d\"\n"
                          % (b, position, b))
            else:
                s += "\trun experimental_loop_%d always\n" % position
            if position < n:
                s += "\trun break_instr always\n"
    else:
        s += "\trun trial_loop always\n"
    s += "\trun goodbye always\n\n"

    s += TRIAL_SEQUENCE
    s += pygaze_items()
    s += inline("setup_helpers", "", HELPERS,
                "Define shared geometry, gaze and validation helpers")
    s += inline("eyelink_setup", "", EYELINK_SETUP,
                "EYELINK ONLY: Host PC drawing + Data Viewer messages (nothing on other trackers)")
    s += inline("eyelink_trial_start", "", EYELINK_TRIAL_START,
                "EYELINK ONLY: TRIALID, interest areas, draw on Host PC (nothing on other trackers)")
    s += inline("eyelink_trial_end", "", EYELINK_TRIAL_END,
                "EYELINK ONLY: TRIAL_VAR and TRIAL_RESULT messages (nothing on other trackers)")
    s += inline("validate_calibration", "", VALIDATE_CALIBRATION,
                "Validate the calibration (any tracker); C = calibrate again")
    s += sketchpad("instructions", instructions, "Instructions")
    s += sketchpad("goodbye", texts["goodbye"], "Goodbye")
    s += QUESTION_ITEMS
    s += empty_sketchpad("clear_screen", "Blank screen after the response")

    if practice_rows:
        s += sketchpad("end_of_practice", texts["end_of_practice"], "End of practice")
        s += sketchpad("break_instr", texts["break"], "Break")
        s += loop("practice_loop", "trial_sequence", practice_rows,
                  "Practice trials", order="sequential")
        for i, rows_i in enumerate(blocks, 1):
            s += loop("experimental_loop_%d" % i, "trial_sequence", rows_i,
                      "Experimental block %d" % i, order="random")
        if rotate_blocks:
            s += inline("counterbalance", "", COUNTERBALANCE,
                        "Block order from subject_nr % 3")
    else:
        s += loop("trial_loop", "trial_sequence", rows, "Trials")

    s += inline("setup_condition", SETUP_CONDITION, "",
                "Set the correct response button")
    s += inline("prepare_trial", prepare, "",
                "Prepare the trial canvases and interest areas")
    s += inline("show_gaze_target", SHOW_GAZE_TARGET_PREPARE, SHOW_GAZE_TARGET_RUN,
                "Show the gaze-contingent target; C = re-calibrate")
    s += inline("trial_display", "", run, "Show the stimulus and end the trial")
    return s


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def boundary_rows(raw):
    return [{
        "item": r["sentence_number"],
        "block": r["block"],
        "sentence_number": r["sentence_number"],
        "pretarget": r["pretarget"],
        "target": r["target"],
        "posttarget": r["posttarget"],
        "changed": r["changed"],
        "question": r["question"],
        "answer": r["answer"],
    } for r in raw]


def comas_rows(raw):
    return [{k: r[k] for k in ("item", "block", "sentence_type", "comma",
                               "no_comma", "corrected", "question",
                               "answer")} for r in raw]


def vwp_rows():
    rows = []
    for i, r in enumerate(read_csv(os.path.join(VWP_POOL, "stimuli.csv")), 1):
        rows.append({"item": i, "target": r["target"], "competitor": r["competitor"],
                     "distractor1": r["distractor1"], "distractor2": r["distractor2"],
                     "sound_file": r["sound"], "target_onset": r["target_onset"],
                     "question": "NA", "answer": "NA"})
    return rows


def build_experiments():
    """Returns {name: (script, [pool files])}."""
    sentences = read_csv(SENTENCES_CSV)
    practice = boundary_rows([r for r in sentences if r["block"] == "practice"])
    blocks = [boundary_rows([r for r in sentences if r["block"] == str(i)])
              for i in (1, 2, 3)]
    comas = read_csv(COMAS_CSV)

    # Sentences of examples/EyeLogic_LITE.osexp (extract_eyelogic.py).
    movingwindow_rows = [{k: r[k] for k in ("item", "source_item", "version", "sentence",
                                            "corrected", "question", "answer")}
                         for r in read_csv(MOVINGWINDOW_CSV)]
    vwp_pool = sorted(os.path.join(VWP_POOL, f) for f in os.listdir(VWP_POOL)
                      if f.endswith((".png", ".wav")))

    return {
        "reading": (experiment(
            "Reading with and without commas",
            "Sentence reading: the published comma study (Angele et al.)",
            TEXTS["es"]["reading"], READING_PREPARE, READING_RUN, lang="es",
            practice_rows=comas_rows([r for r in comas if r["block"] == "practice"]),
            blocks=[comas_rows([r for r in comas if r["block"] == b])
                    for b in ("1", "2")]), []),
        "boundary": (experiment(
            "Boundary paradigm",
            "Gaze-contingent display change with the published Spanish sentences",
            TEXTS["es"]["reading"], BOUNDARY_PREPARE, BOUNDARY_RUN, lang="es",
            practice_rows=practice, blocks=blocks, rotate_blocks=True), []),
        "movingwindow": (experiment(
            "Moving window paradigm",
            "Gaze-contingent moving window, sentences of the EyeLogic experiment",
            TEXTS["es"]["reading"], MOVINGWINDOW_PREPARE, MOVINGWINDOW_RUN, lang="es",
            rows=movingwindow_rows,
            # letters visible on each side of the fixated letter, and the
            # smallest gaze movement (in letters) that moves the window
            extra_vars={"window_small": 4, "window_large": 12,
                        "min_saccade_letters": 1.5}), []),
        "vwp": (experiment(
            "Visual world paradigm",
            "Pictures, a spoken instruction, and a mouse click (Allopenna et al., 1998)",
            "Look at the black square in the middle of the screen.<br /><br />"
            "Then you will see four pictures and hear an instruction.<br />"
            "Click on the picture that you hear as quickly as possible.<br /><br />"
            "Press any key to start.",
            VWP_PREPARE, VWP_RUN, rows=vwp_rows(), gaze_target_left=1920 // 2 - 25),
            vwp_pool),
    }


def build():
    os.makedirs(OUT, exist_ok=True)
    for name, (script, pool_files) in build_experiments().items():
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
            for path in pool_files:
                tar.add(path, arcname="pool/" + os.path.basename(path))
        print("wrote", name + ".osexp", "(%d pool files)" % len(pool_files))


if __name__ == "__main__":
    build()
