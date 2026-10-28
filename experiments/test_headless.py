"""Runs the workshop experiments headless with a simulated participant.

    python experiments/test_headless.py [reading boundary movingwindow vwp]
        [--subject N] [--max-trials N] [--fake-eyelink]
        [--outdir DIR] [--screenshots DIR [--screenshot-trials 0,1,2]]

Needs an X display (the devcontainer starts Xvfb on :0, or use `xvfb-run`).
The PyGaze "advanced dummy" tracker normally follows the mouse; here its
methods are replaced by a scripted gaze trajectory that reacts to the messages
the experiment logs (GAZE TARGET ON, STIMONSET, ...). Keyboard and mouse input
are simulated as well. After each run the script checks the OpenSesame log file
and the tracker messages and prints PASS/FAIL per check.

The simulated participant also tests the experimenter controls: it ignores
the gaze target in trial 2 (-> 10 s timeout -> drift correction) and the
"experimenter" presses C during the gaze target in trial 3 (-> calibration +
validation).

--fake-eyelink switches on the EyeLink-only items (Host PC drawing, Data
Viewer messages) while still using the dummy tracker; the Host PC commands are
recorded and checked. Without it, the test checks that those items do nothing.

`opensesamerun` is broken in OpenSesame 4.1.17 (its entry point is missing),
so the experiment is run through `libopensesame.experiment.Experiment`.
"""
import argparse
import csv
import math
import os
import random
import re
import sys
import tarfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OSEXP = os.path.join(HERE, "osexp")
ALL = ["reading", "boundary", "movingwindow", "vwp"]

# Simulated reading: fixations of FIX_MS, each placed exactly on a letter
# boundary with the gaze drifting +- DRIFT letters across it, and saccades of
# SACCADE_LETTERS letters taking SACCADE_MS.
FIX_MS = 200
SACCADE_MS = 20
SACCADE_LETTERS = 7
DRIFT = 0.3
VWP_COMPETITOR_MS = 200   # after target-word onset: look at the competitor,
VWP_TARGET_MS = 500       # then at the target,
VWP_CLICK_MS = 900        # then click on it
BLOCK_ORDERS = {1: ["1", "2", "3"], 2: ["2", "3", "1"], 0: ["3", "1", "2"]}
EYELINK_LINE = "EYELINK = items['pygaze_init'].var.tracker_type == 'EyeLink'"


class Participant:
    """Scripted gaze, keyboard and mouse; state changes on logged messages."""

    def __init__(self, exp, correct_rate=.8):
        self.exp = exp
        self.correct_rate = correct_rate
        self.messages = []        # (trial, time, message)
        self.commands = []        # (trial, Host PC command)
        self.trial = 0
        self.state = "centre"
        self.t0 = 0
        self.point = None
        self.ignore_target_in_trial = 2
        self.plan = None          # fixations of the current sentence
        self.fixations = []       # (trial, start, end, letter index)
        self.recalibrate_in_trial = 3

    @property
    def ws(self):
        return self.exp.python_workspace

    def now(self):
        return self.exp._clock.time()

    def log(self, msg):
        msg = str(msg)
        self.messages.append((self.trial, self.now(), msg))
        if re.match(r"trial \d+/\d+ ", msg):
            self.trial += 1
        for key, state in (("GAZE TARGET ON", "gazetarget"),
                           ("VALIDATION POINT", "validation"),
                           ("STIMONSET", "reading"),
                           ("PREVIEW_ONSET", "centre"),
                           ("AUDIO_ONSET", "vwp"),
                           ("TRIALEND", "centre")):
            if msg.startswith(key):
                self.state = state
                self.t0 = self.now()
        if msg.startswith("VALIDATION POINT"):
            self.point = [int(v) for v in re.findall(r"=(\d+)", msg)]
        if msg == "GAZE TARGET ON" and self.trial == self.ignore_target_in_trial:
            self.state = "away"
            self.ignore_target_in_trial = None

    def sentence_length(self):
        v = self.exp.var
        if "sentence" in v:
            return len(v.sentence)
        return len(" ".join([v.pretarget, v.target, v.posttarget]))

    def object_centre(self, name):
        x, y = self.ws["POS"][self.ws["objects"].index(name)]
        return x, y                                   # canvas coordinates

    def sample(self):
        W, H = self.exp.var.width, self.exp.var.height
        corner = (W * .97, H * .97)
        dt = self.now() - self.t0
        if self.state == "away":
            return 50, 50
        if self.state == "validation":
            return self.point[0] + 3, self.point[1] - 2
        if self.state == "gazetarget":
            return self.ws["GAZE_LEFT"] + self.ws["GAZE_SIZE"] / 2, H / 2
        if self.state == "reading":
            return self.reading_sample(dt, corner, H)
        if self.state == "vwp":
            dt -= int(self.exp.var.target_onset)
            if dt > VWP_TARGET_MS:
                x, y = self.object_centre(self.exp.var.target)
                return x + W / 2, y + H / 2
            if dt > VWP_COMPETITOR_MS:
                x, y = self.object_centre(self.exp.var.competitor)
                return x + W / 2, y + H / 2
        return W / 2, H / 2

    def reading_sample(self, dt, corner, H):
        """Fixations on letter boundaries (with drift) and fast saccades."""
        edges = self.ws["letter_x"]                  # left edge of every character
        if self.plan is None or self.plan[0] != self.t0:
            ks = list(range(1, len(edges) - 1, SACCADE_LETTERS))
            self.plan = (self.t0, ks)
            t = self.t0
            for k in ks:
                self.fixations.append((self.trial, t, t + FIX_MS, k))
                t += FIX_MS + SACCADE_MS
        ks = self.plan[1]
        i, into = divmod(dt, FIX_MS + SACCADE_MS)
        i = int(i)
        if i >= len(ks):
            return corner
        width = (edges[-1] - edges[0]) / (len(edges) - 1)
        if into < FIX_MS:                            # fixation with drift
            x = edges[ks[i]] + DRIFT * width * math.sin(2 * math.pi * dt / 12)
        else:                                        # saccade to the next one
            frac = (into - FIX_MS) / SACCADE_MS
            nxt = edges[ks[i + 1]] if i + 1 < len(ks) else corner[0]
            x = edges[ks[i]] + frac * (nxt - edges[ks[i]])
        return x, H / 2 + 10

    def click(self):
        if self.state != "vwp":
            return None
        if self.now() - self.t0 - int(self.exp.var.target_onset) < VWP_CLICK_MS:
            return None
        return self.object_centre(self.exp.var.target)

    def key(self, keylist, timeout):
        if timeout == 0:
            if (keylist and "c" in keylist and self.state == "gazetarget"
                    and self.trial == self.recalibrate_in_trial):
                self.recalibrate_in_trial = None
                return "c"
            return None
        if keylist and "1" in keylist:
            correct = self.exp.var.get("correct_button", "1")
            if correct not in ("1", "2"):
                correct = "1"
            if random.random() < self.correct_rate:
                return correct
            return "2" if correct == "1" else "1"
        return "space"


def save_screenshots(participant, folder, name, trials=(0, 1, 2), max_per_trial=8):
    """Save the displays of the given trials as PNG (0 = before the first trial)."""
    from openexp._canvas import legacy as canvas_legacy
    import pygame
    os.makedirs(folder, exist_ok=True)
    show = canvas_legacy.Legacy.show
    count = {}

    def show_and_save(self):
        t = show(self)
        trial = participant.trial
        if trial in trials and count.get(trial, 0) < max_per_trial:
            count[trial] = count.get(trial, 0) + 1
            pygame.image.save(self.surface, os.path.join(
                folder, "%s_t%d_%02d.png" % (name, trial, count[trial])))
        return t
    canvas_legacy.Legacy.show = show_and_save


def patch(participant):
    from pygaze._eyetracker import libdummytracker
    from openexp._keyboard import legacy as kb_legacy
    from openexp._mouse import legacy as mouse_legacy
    import pygame

    D = libdummytracker.Dummy
    D.calibrate = lambda self: None
    D.drift_correction = lambda self, pos=None, fix_triggered=False: True
    D.sample = lambda self: participant.sample()
    D.log = lambda self, msg: participant.log(msg)
    D.log_var = lambda self, var, val: None
    D.send_command = lambda self, cmd: participant.commands.append(
        (participant.trial, cmd))

    def _get_key_event(self, event_type):
        pygame.event.pump()
        key = participant.key(self.keylist, self.timeout)
        return key, pygame.time.get_ticks()
    kb_legacy.Legacy._get_key_event = _get_key_event

    def _get_mouse_event(self, event_type):
        pygame.event.pump()
        pos = participant.click()
        return (None if pos is None else 1), pos, pygame.time.get_ticks()
    mouse_legacy.Legacy._get_mouse_event = _get_mouse_event


def limit_trials(script, max_trials):
    """Keep only the first `max_trials` cycles of every loop table."""
    out = []
    for line in script.split("\n"):
        m = re.match(r"\tsetcycle (\d+) ", line)
        if m and int(m.group(1)) >= max_trials:
            continue
        m = re.match(r"\tset cycles (\d+)$", line)
        if m:
            line = "\tset cycles %d" % min(int(m.group(1)), max_trials)
        out.append(line)
    return "\n".join(out)


def run(name, subject, max_trials, outdir, fake_eyelink=False, screenshots=None,
        screenshot_trials=(0, 1, 2)):
    from libopensesame.experiment import Experiment
    tmp = tempfile.mkdtemp(prefix="osexp-")
    with tarfile.open(os.path.join(OSEXP, name + ".osexp")) as tar:
        tar.extractall(tmp, filter="data")
    with open(os.path.join(tmp, "script.opensesame"), encoding="utf-8") as f:
        script = f.read()
    if max_trials:
        script = limit_trials(script, max_trials)
    if fake_eyelink:
        assert EYELINK_LINE in script
        script = script.replace(EYELINK_LINE, "EYELINK = True  # test_headless --fake-eyelink")
    logfile = os.path.join(outdir, "%s-subject-%d.csv" % (name, subject))
    exp = Experiment(string=script, experiment_path=OSEXP, logfile=logfile,
                     subject_nr=subject, pool_folder=os.path.join(tmp, "pool"))
    participant = Participant(exp)
    patch(participant)
    if screenshots:
        save_screenshots(participant, screenshots, name, screenshot_trials)
    exp.run()
    with open(logfile, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows, participant, script


class Checker:
    def __init__(self, name):
        self.name = name
        self.failed = 0

    def __call__(self, label, ok, detail=""):
        print("  %s %s%s" % ("PASS" if ok else "FAIL", label,
                             (" (%s)" % detail) if detail else ""))
        self.failed += not ok


def by_trial(messages):
    trials = {}
    for trial, t, msg in messages:
        trials.setdefault(trial, []).append((t, msg))
    return trials


def expected_condition(row, subject, yes, no):
    """Two-list counterbalancing of reading.osexp (list A = even subjects)."""
    first = (int(row["item"]) % 2 == 1) == (subject % 2 == 0)
    return yes if first else no


def check(name, rows, participant, script, subject, fake_eyelink):
    messages = participant.messages
    c = Checker(name)
    n_cycles = sum(int(m) for m in re.findall(r"\tset cycles (\d+)", script))
    c("one logged row per trial", len(rows) == n_cycles,
      "%d rows, %d cycles" % (len(rows), n_cycles))
    c("no aborted trials", all(r["trial_aborted"] == "0" for r in rows))
    trials = by_trial(messages)

    # Validation at the start of the experiment.
    first = trials.get(0, [])
    c("calibration validated and accepted before the first trial",
      any(m.startswith("VALIDATION RESULT") and m.endswith("accepted=1")
          for _, m in first) and
      sum(m.startswith("VALIDATION ERROR") for _, m in first) == 5)
    c("validation error logged in degrees",
      all(float(r["validation_max_error"]) < 0.5 for r in rows),
      "max %s deg" % rows[0]["validation_max_error"])

    status = [m for _, _, m in messages if re.match(r"trial \d+/\d+ ", m)]
    c("status message: trial n/N item condition",
      [s.split()[3] for s in status] == [r["item"] for r in rows]
      and all(s.split()[4] == r["condition"] for s, r in zip(status, rows)),
      status[0] if status else "")
    stim = "PREVIEW_ONSET" if name == "vwp" else "STIMONSET"
    order = ["trial ", "TRIALINFO item=", "GAZE TARGET ON", stim, "TRIALEND",
             "stop_trial"]
    bad = []
    for i in range(1, len(rows) + 1):
        msgs = [m for _, m in trials.get(i - 1, [])[-1:]] + \
            [m for _, m in trials.get(i, [])]
        pos = [next((j for j, m in enumerate(msgs) if m.startswith(o)), None)
               for o in order]
        if None in pos or pos != sorted(pos):
            bad.append(i)
    c("tracker messages in trial order", not bad, "bad trials: %s" % bad[:5])
    timeouts = ["trial %d: %s" % (t, m) for t, _, m in messages
                if m.startswith(("CORNER TIMEOUT", "BOUNDARY TIMEOUT", "CLICK TIMEOUT"))]
    c("no corner/boundary/click timeouts", not timeouts, "; ".join(timeouts))
    recov = [t for t, _, m in messages if m.startswith("GAZE TARGET TIMEOUT")]
    c("ignored gaze target -> drift correction, trial continues",
      len(rows) < 2 or recov == [2], "timeouts in trials %s" % recov)
    recal = [t for t, _, m in messages if m == "GAZE TARGET RECALIBRATION"]
    revalid = [t for t, _, m in messages if m.startswith("VALIDATION RESULT")]
    c("experimenter key C -> calibration + validation, trial continues",
      len(rows) < 3 or (recal == [3] and 3 in revalid),
      "recalibrations in trials %s" % recal)

    n_regions = [sum(m.startswith("REGION n=") for _, m in trials.get(i, []))
                 for i in range(1, len(rows) + 1)]
    if name == "vwp":
        want = [4] * len(rows)
    else:
        want = [len(r["sentence"].split(" ")) if "sentence" in r else
                len(" ".join([r["pretarget"], r["target"], r["posttarget"]]).split(" "))
                for r in rows]
    c("one interest area (REGION) per word / object", n_regions == want,
      str(n_regions[:4]))
    if name != "vwp":
        def fields(m):
            return dict(f.split("=", 1) for f in m.split()[1:])
        gaps = 0
        n_letters = []
        for i in range(1, len(rows) + 1):
            regions = [fields(m) for _, m in trials.get(i, []) if m.startswith("REGION n=")]
            gaps += sum(int(a["right"]) != int(b["left"]) for a, b in zip(regions, regions[1:]))
            n_letters.append(sum(m.startswith("LETTER ") for _, m in trials.get(i, [])))
        c("word areas touch (the space after a word belongs to it)", gaps == 0,
          "%d gaps" % gaps)
        want_letters = [len(r["sentence"].replace(" ", "")) for r in rows]
        c("one LETTER message per letter", n_letters == want_letters,
          str(n_letters[:4]))
    items = [m.split("=", 1)[1] for _, _, m in messages
             if m.startswith("TRIALINFO item=")]
    c("TRIALINFO message carries the item number",
      items == [r["item"] for r in rows], "first: %s" % items[:3])
    q_rows = [r for r in rows if r["question"] != "NA"]
    if q_rows:
        c("response collected only when there is a question",
          all(r["response"] in ("1", "2") for r in q_rows)
          and all(r["response"] == "NA" for r in rows if r["question"] == "NA"))
        c("correct is scored against the answer column",
          all(r["correct"] == str(int(r["response"] == r["correct_button"]))
              for r in q_rows))

    # EyeLink-only items.
    trialids = [t for t, _, m in messages if m.startswith("TRIALID")]
    if fake_eyelink:
        c("EyeLink: DISPLAY_COORDS once",
          sum(m.startswith("DISPLAY_COORDS") for _, _, m in messages) == 1)
        c("EyeLink: one TRIALID and TRIAL_RESULT per trial",
          trialids == list(range(len(rows))) and
          sum(m == "TRIAL_RESULT 0" for _, _, m in messages) == len(rows))
        n_iarea = [sum(m.startswith("!V IAREA") for _, m in trials.get(i - 1, [])
                       if True) for i in range(1, len(rows) + 1)]
        c("EyeLink: one !V IAREA per interest area", n_iarea == want, str(n_iarea[:4]))
        c("EyeLink: TRIAL_VAR item and condition every trial",
          sum(m.startswith("!V TRIAL_VAR item ") for _, _, m in messages) == len(rows)
          and sum(m.startswith("!V TRIAL_VAR condition ") for _, _, m in messages)
          == len(rows))
        boxes = sum(cmd.startswith("draw_box") for _, cmd in participant.commands)
        c("EyeLink: interest areas drawn on the Host PC", boxes >= sum(want),
          "%d boxes" % boxes)
        lines = sum(cmd.startswith("draw_line") for _, cmd in participant.commands)
        c("EyeLink: boundary line drawn on the Host PC only in boundary.osexp",
          (lines >= len(rows)) if name == "boundary" else lines == 0,
          "%d lines" % lines)
    else:
        c("EyeLink-only items do nothing with another tracker",
          not participant.commands and not trialids and
          not any(m.startswith(("!V ", "TRIAL_RESULT", "DISPLAY_COORDS"))
                  for _, _, m in messages))

    if name == "reading":
        exp_rows = [r for r in rows if r["block"] != "practice"]
        c("list A for even, list B for odd subject numbers",
          all(r["item_list"] == ("A" if subject % 2 == 0 else "B") for r in rows))
        c("comma / no comma by item and list",
          all(r["condition"] == expected_condition(r, subject, "comma", "no_comma")
              and r["sentence"] == r[r["condition"]] for r in exp_rows))
        c("every comma version has more commas than its no-comma version",
          all(r["comma"].count(",") > r["no_comma"].count(",") for r in exp_rows))
        if len(exp_rows) == 130:
            n_comma = sum(r["condition"] == "comma" for r in exp_rows)
            c("half of the items with commas (65 / 130)", n_comma == 65, str(n_comma))
        c("practice first, then block 1 and block 2",
          [r["block"] for r in rows] == sorted([r["block"] for r in rows],
                                               key=lambda b: (b != "practice", b)))
    if name == "boundary":
        c("every trial has a display change",
          all(r["display_changed"] == "1" for r in rows))
        lat = [float(r["display_change_latency"]) for r in rows]
        c("display-change latency logged",
          len([m for _, _, m in messages if m.startswith("DISPLAYCHANGE")])
          == len(rows), "max %.0f ms in this environment" % max(lat))
        with open(os.path.join(HERE, "sentences.csv"), encoding="utf-8") as f:
            table = {r["sentence_number"]: r for r in csv.DictReader(f)}
        c("logged `changed` column is the preview word",
          all(r["changed"] == table[r["sentence_number"]]["changed"]
              for r in rows))
        exp_rows = [r for r in rows if r["block"] != "practice"]
        c("practice is always identical",
          all(r["preview_condition"] == "identical"
              for r in rows if r["block"] == "practice"))
        parity = "odd" if subject % 2 else "even"
        want_cond = [("identical" if (int(r["sentence_number"]) % 2 == 0)
                      == (parity == "even") else "dissimilar") for r in exp_rows]
        c("preview condition follows subject parity",
          [r["preview_condition"] for r in exp_rows] == want_cond)
        seen = []
        for r in exp_rows:
            if not seen or seen[-1] != r["block"]:
                seen.append(r["block"])
        c("block order rotates with subject_nr % 3",
          seen == BLOCK_ORDERS[subject % 3] and
          exp_rows[0]["block_order"] == "-".join(BLOCK_ORDERS[subject % 3]),
          "-".join(seen))
        # The boundary must lie in the space between the last letter of the
        # pre-target word and the first letter of the target (LETTER messages).
        ok = []
        for i, r in enumerate(rows, 1):
            letters = [dict(f.split("=", 1) for f in m.split()[1:])
                       for _, m in trials.get(i, []) if m.startswith("LETTER ")]
            k = int(r["target_word_nr"])
            last_pre = [l for l in letters if int(l["word"]) == k - 1][-1]
            first_target = [l for l in letters if int(l["word"]) == k][0]
            ok.append(int(last_pre["right"]) <= float(r["boundary"])
                      <= int(first_target["left"]))
        c("boundary lies in the space before the target word", all(ok))
    if name == "movingwindow":
        moves = [(t, tm, int(m.split("=")[1])) for t, tm, m in messages
                 if m.startswith("WINDOWMOVE")]
        last = {}
        for t, _, c_ in moves:
            last[t] = c_
        fix = {}
        for t, start, end, k in participant.fixations:
            fix.setdefault(t, []).append((start, end, k))
        # Window at the end of the last fixation (afterwards the eyes move on to
        # the corner square, and the window may follow them past the text).
        at_end, want = [], []
        for i in range(1, len(rows) + 1):
            start, end, k = fix[i][-1]
            at_end.append(([c_ for t, tm, c_ in moves if t == i and tm <= end] or [None])[-1])
            want.append(k)
        c("window followed the gaze to the last fixation",
          all(w in (k - 1, k) for w, k in zip(at_end, want)),
          "window %s, fixated letter %s" % (at_end[:3], want[:3]))
        n_sacc = sum(len(f) for f in fix.values())
        c("about one window change per letter passed in a saccade, no more",
          len(moves) <= n_sacc * (SACCADE_LETTERS + 1), "%d changes, %d saccades" % (len(moves), n_sacc))
        # During a fixation (after 40 ms for landing) the gaze drifts back
        # and forth across a letter boundary: the window must not change.
        during = sum(1 for t, tm, _ in moves for start, end, _ in fix.get(t, [])
                     if start + 40 <= tm <= end)
        c("no window changes while the gaze drifts during a fixation",
          during == 0, "%d changes during fixations, %d in total" % (during, len(moves)))
        c("window sizes by item and list (4 / 12)",
          all(r["window"] == ("4" if expected_condition(r, subject, True, False) else "12")
              for r in rows))
    if name == "vwp":
        c("clicked the target in every trial",
          all(r["clicked"] == r["target"] and r["click_correct"] == "1"
              for r in rows))
        c("click RT measured from target-word onset",
          all(VWP_CLICK_MS <= float(r["click_rt"]) < VWP_CLICK_MS + 100
              for r in rows), str([r["click_rt"] for r in rows[:4]]))
        delays = []
        for i in range(1, len(rows) + 1):
            t = dict((m.split()[0], tt) for tt, m in trials.get(i, []))
            delays.append(t["TARGET_ONSET"] - t["AUDIO_ONSET"]
                          - int(rows[i - 1]["target_onset"]))
        c("TARGET_ONSET logged at audio onset + target_onset (+- 10 ms)",
          all(0 <= d <= 10 for d in delays), "%s ms late" % delays[:4])
        c("gaze on the target after target onset",
          all(int(r["target_samples"]) > 0 for r in rows))
    return c.failed


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("experiments", nargs="*", default=ALL,
                    help="any of: %s (default: all)" % " ".join(ALL))
    ap.add_argument("--subject", type=int, default=1)
    ap.add_argument("--max-trials", type=int, default=0,
                    help="cycles per loop (0 = all); speeds up boundary/reading")
    ap.add_argument("--fake-eyelink", action="store_true",
                    help="switch on the EyeLink-only items and check them")
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--screenshots", default=None,
                    help="save the displays of some trials as PNG")
    ap.add_argument("--screenshot-trials", default="0,1,2",
                    help="trial numbers for --screenshots (0 = before the first trial)")
    a = ap.parse_args()
    outdir = a.outdir or tempfile.mkdtemp(prefix="osexp-test-")
    os.makedirs(outdir, exist_ok=True)
    os.environ.setdefault("DISPLAY", ":0")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    failed = 0
    for name in a.experiments:
        if name not in ALL:
            ap.error("unknown experiment %r" % name)
    for name in a.experiments:
        print("%s (subject %d%s)" % (name, a.subject,
                                     ", fake EyeLink" if a.fake_eyelink else ""))
        try:
            rows, participant, script = run(name, a.subject, a.max_trials, outdir,
                                            a.fake_eyelink, a.screenshots,
                                            [int(t) for t in a.screenshot_trials.split(",")])
        except Exception as e:
            print("  FAIL experiment crashed: %s" % str(e).strip().split("\n")[-1])
            failed += 1
            continue
        failed += check(name, rows, participant, script, a.subject, a.fake_eyelink)
    print("logs in", outdir)
    print("ALL PASSED" if not failed else "%d CHECK(S) FAILED" % failed)
    sys.exit(bool(failed))


if __name__ == "__main__":
    main()
