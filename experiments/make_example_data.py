"""Generate realistic 1000 Hz EyeLink .asc and OpenSesame .csv example datasets.

Runs each experiment in `experiments/osexp/` (`reading`, `boundary`, `movingwindow`,
`vwp`) through OpenSesame for subjects 1-6 (matching the 6-subject boundary
counterbalancing matrix and covering both reading lists and all 4 moving-window
Latin-square lists), with a realistic 1000 Hz simulated EyeLink tracker.

Output layout (committed in git for analysis-script testing):
    experiments/example_data/<experiment>/subject-<1..6>.asc
    experiments/example_data/<experiment>/subject-<1..6>.csv

For `reading` and `boundary`, the loop tables are trimmed to a balanced subset
(2 practice + 12 experimental trials across all blocks, half odd/even item numbers,
including comprehension questions) so the 1000 Hz `.asc` files stay compact.
`movingwindow` (5 trials) and `vwp` (8 trials) run at full length.
"""
import argparse
import csv
import math
import os
import random
import re
import tarfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OSEXP = os.path.join(HERE, "osexp")
OUT_DEFAULT = os.path.join(HERE, "example_data")
ALL = ["reading", "boundary", "movingwindow", "vwp"]
EYELINK_LINE = "EYELINK = items['pygaze_init'].var.tracker_type == 'EyeLink'"

SUBJ_SPEED = {1: 0.94, 2: 1.06, 3: 0.98, 4: 1.09, 5: 0.90, 6: 1.02}
SUBJ_BIAS = {1: (3.2, -1.8), 2: (-2.5, 2.4), 3: (1.8, 3.0),
             4: (-3.6, -1.5), 5: (2.7, 1.2), 6: (-1.4, -2.9)}


def px_to_deg(dx, dy, width_px=1920, screen_cm=53.0, dist_cm=70.0):
    cm = math.hypot(dx, dy) * screen_cm / width_px
    return math.degrees(math.atan2(cm, dist_cm))


class AscSession:
    """1000 Hz EyeLink `.asc` generator synced to a running OpenSesame Experiment."""

    def __init__(self, exp, name, subject):
        self.exp = exp
        self.name = name
        self.subject = subject
        self.rng = random.Random(1000 * subject + ALL.index(name) * 97 + 13)
        self.speed = SUBJ_SPEED[subject]
        self.bias_x, self.bias_y = SUBJ_BIAS[subject]
        self.base_pupil = 1350.0 + (subject % 3) * 140.0
        self.accuracy = 0.85 + 0.02 * (subject % 3)

        self.t = 10000
        self.last_polled_t = -1
        self.last_sample_t = -1
        self.recording = False
        self.trial = 0

        self.W = 1920
        self.H = 1080
        self.cur_x = self.W / 2.0
        self.cur_y = self.H / 2.0

        self.segments = []          # queue of [kind, t0, dur, sx, sy, ex, ey]
        self.active_seg = None
        self.hold = None            # (x, y) when queue is empty
        self.open_evt = None        # accumulator for current EFIX/ESACC/EBLINK
        self.sac_peak_v = 0.0

        self.vwp_clicked_pos = None
        self.vwp_click_t = None
        self.vwp_mouse_resets = []

        self.asc = [
            "** CONVERTED FROM S%d_%s.EDF using edfapi 4.1 Linux64 (simulated 1000 Hz EyeLink Portable Duo)" % (subject, name.upper()[:4]),
            "** DATE: Sun Nov 15 21:50:00 2026",
            "** TYPE: EDF_FILE BINARY EVENT SAMPLE TAGGED",
            "** VERSION: EYELINK II 1",
            "** SOURCE: EYELINK CL",
            "** EYELINK II CL v5.15 Jan 24 2018 (EyeLink Portable Duo)",
            "** CAMERA: EyeLink CL Version 1.2 Sensor=AI7",
            "** SERIAL NUMBER: CLU-12345",
            "** CAMERA_CONFIG: CLU-12345",
            "**",
        ]

    @property
    def ws(self):
        return self.exp.python_workspace

    # ---- Virtual clock ---------------------------------------------------
    def time(self):
        return float(self.t)

    def ticks(self):
        return int(self.t)

    def sleep(self, ms):
        self.advance(max(0, int(round(ms))))

    def advance(self, ms):
        for _ in range(ms):
            self.t += 1
            if self.recording:
                self._emit_sample()

    # ---- Gaze trajectories -----------------------------------------------
    def _set_hold(self, x, y):
        self.hold = (float(x), float(y))

    def _push(self, kind, dur, sx, sy, ex, ey):
        self.segments.append([kind, None, max(1, int(dur)),
                              float(sx), float(sy), float(ex), float(ey)])

    def _saccade_to(self, ex, ey, cur_pos=None):
        sx, sy = cur_pos if cur_pos is not None else (self.cur_x, self.cur_y)
        dist = math.hypot(ex - sx, ey - sy)
        dur = max(18, min(68, int(round(18 + dist / 14.0))))
        self._push("sac", dur, sx, sy, ex, ey)
        return dur

    def _start_new_event(self, kind, sx, sy, ex, ey):
        self._close_open_event()
        if kind == "fix":
            self.asc.append("SFIX R   \t%d" % self.t)
            self.open_evt = ["fix", self.t, 0.0, 0.0, 0.0, 0]
        elif kind == "sac":
            self.asc.append("SSACC R  \t%d" % self.t)
            self.open_evt = ["sac", self.t, sx, sy, ex, ey, 0.0]
        elif kind == "blink":
            self.asc.append("SBLINK R \t%d" % self.t)
            self.open_evt = ["blink", self.t]

    def _close_open_event(self):
        if self.open_evt is None:
            return
        t_end = self.last_sample_t
        kind = self.open_evt[0]
        if kind == "fix":
            _, t_st, sx, sy, sp, n = self.open_evt
            if n > 0 and t_end >= t_st:
                dur = t_end - t_st + 1
                self.asc.append(
                    "EFIX R   \t%d\t%d\t%d\t%7.1f\t%7.1f\t%7d"
                    % (t_st, t_end, dur, sx / n, sy / n, int(round(sp / n)))
                )
        elif kind == "sac":
            _, t_st, sx, sy, ex, ey, max_v = self.open_evt
            if t_end >= t_st:
                dur = t_end - t_st + 1
                amp = px_to_deg(ex - sx, ey - sy)
                pv = int(round(px_to_deg(max_v, 0) * 1000.0))
                self.asc.append(
                    "ESACC R  \t%d\t%d\t%d\t%7.1f\t%7.1f\t%7.1f\t%7.1f\t%6.2f\t%6d"
                    % (t_st, t_end, dur, sx, sy, ex, ey, amp, max(35, pv))
                )
        elif kind == "blink":
            _, t_st = self.open_evt
            if t_end >= t_st:
                dur = t_end - t_st + 1
                self.asc.append("EBLINK R \t%d\t%d\t%d" % (t_st, t_end, dur))
        self.open_evt = None

    def _emit_sample(self):
        # Fetch or advance segment queue
        while self.active_seg is not None:
            kind, t0, dur, sx, sy, ex, ey = self.active_seg
            if self.t - t0 >= dur:
                self.active_seg = None
                break
            break
        if self.active_seg is None:
            if self.segments:
                seg = self.segments.pop(0)
                seg[1] = self.t
                self.active_seg = seg
                self._start_new_event(seg[0], seg[3], seg[4], seg[5], seg[6])
            else:
                hx, hy = self.hold if self.hold is not None else (self.cur_x, self.cur_y)
                if self.open_evt is None or self.open_evt[0] != "fix":
                    self._start_new_event("fix", hx, hy, hx, hy)

        if self.active_seg is not None:
            kind, t0, dur, sx, sy, ex, ey = self.active_seg
            if kind == "sac":
                u = min(1.0, (self.t - t0 + 1) / float(dur))
                du = 30 * (u ** 2) - 60 * (u ** 3) + 30 * (u ** 4)
                f = 10 * (u ** 3) - 15 * (u ** 4) + 6 * (u ** 5)
                x = sx + (ex - sx) * f
                y = sy + (ey - sy) * f
                vel = math.hypot(ex - sx, ey - sy) * (du / dur)
                if self.open_evt and self.open_evt[0] == "sac":
                    self.open_evt[4], self.open_evt[5] = x, y
                    if vel > self.open_evt[6]:
                        self.open_evt[6] = vel
                pupil = self.base_pupil + 20.0 * math.sin(self.t / 190.0)
                self.cur_x, self.cur_y = x, y
                self.asc.append("%d\t%7.1f\t%7.1f\t%7.1f\t..." % (self.t, x, y, pupil))
                self.last_sample_t = self.t
                return
            if kind == "blink":
                self.cur_x, self.cur_y = -32768.0, -32768.0
                self.asc.append("%d\t   .\t   .\t    0.0\t..." % self.t)
                self.last_sample_t = self.t
                return
            # Timed fixation
            ax, ay = sx, sy
        else:
            ax, ay = self.hold if self.hold is not None else (self.cur_x, self.cur_y)

        # Gentle physiological drift + micro-tremor (stays < ~2.5 px so movingwindow
        # lock stays completely stable during fixations).
        jitter_x = 1.2 * math.sin(self.t / 47.0) + self.rng.gauss(0, 0.55)
        jitter_y = 0.9 * math.cos(self.t / 61.0) + self.rng.gauss(0, 0.45)
        x = max(0.0, min(self.W - 1.0, ax + jitter_x))
        y = max(0.0, min(self.H - 1.0, ay + jitter_y))
        pupil = self.base_pupil + 25.0 * math.sin(self.t / 240.0) + self.rng.gauss(0, 2.0)
        self.cur_x, self.cur_y = x, y
        if self.open_evt and self.open_evt[0] == "fix":
            self.open_evt[2] += x
            self.open_evt[3] += y
            self.open_evt[4] += pupil
            self.open_evt[5] += 1
        self.asc.append("%d\t%7.1f\t%7.1f\t%7.1f\t..." % (self.t, x, y, pupil))
        self.last_sample_t = self.t

    # ---- Experiment / Tracker callbacks ----------------------------------
    def start_recording(self):
        self.recording = True
        self.segments.clear()
        self.active_seg = None
        self.open_evt = None
        self.asc.append("START\t%d \tRIGHT\tSAMPLES\tEVENTS" % self.t)
        self.asc.append("PRESCALER\t1")
        self.asc.append("VPRESCALER\t1")
        self.asc.append("PUPIL\tAREA")
        self.asc.append("EVENTS\tGAZE\tRIGHT\tRATE\t1000.00\tTRACKING\tCR\tFILTER\t2")
        self.asc.append("SAMPLES\tGAZE\tRIGHT\tRATE\t1000.00\tTRACKING\tCR\tFILTER\t2")
        self._set_hold(self.cur_x, self.cur_y)
        self.advance(1)

    def stop_recording(self):
        if self.last_sample_t < self.t:
            self.advance(1)
        self._close_open_event()
        self.recording = False
        self.segments.clear()
        self.active_seg = None
        self.asc.append("END\t%d \tSAMPLES\tEVENTS\tRES\t  34.12\t  34.12" % self.t)

    def calibrate(self):
        self.advance(2500)
        self.asc.append("MSG\t%d !CAL " % self.t)
        self.asc.append(">>>>>>> CALIBRATION (HV9,P-CR) FOR RIGHT: <<<<<<<<<")
        self.asc.append("MSG\t%d !CAL VALIDATION HV9 R RIGHT GOOD AVG 0.28 deg  MAX 0.44 deg OFFSET" % self.t)

    def drift_correction(self, pos=None, fix_triggered=False):
        self.advance(350)
        px, py = pos if pos is not None else (self.W // 2, self.H // 2)
        dx = self.rng.uniform(-4.0, 4.0)
        dy = self.rng.uniform(-4.0, 4.0)
        deg = px_to_deg(dx, dy)
        self.asc.append(
            "MSG\t%d DRIFTCORRECT LR RIGHT at %d,%d OFFSET %.2f deg. (%.1f,%.1f px)"
            % (self.t, int(px), int(py), deg, dx, dy)
        )
        return True

    def log(self, msg):
        msg = str(msg)
        self.asc.append("MSG\t%d %s" % (self.t, msg))
        if re.match(r"trial \d+/\d+ ", msg):
            self.trial += 1
        elif msg.startswith("VALIDATION POINT"):
            vx, vy = [int(v) for v in re.findall(r"=(\d+)", msg)]
            tx, ty = vx + self.bias_x, vy + self.bias_y
            self.segments.clear()
            self.active_seg = None
            self._saccade_to(tx, ty)
            self._set_hold(tx, ty)
        elif msg == "GAZE TARGET ON":
            tx = self.ws["GAZE_LEFT"] + self.ws["GAZE_SIZE"] / 2.0 + self.rng.uniform(-5, 5)
            ty = self.H / 2.0 + self.rng.uniform(-4, 4)
            self.segments.clear()
            self.active_seg = None
            self._saccade_to(tx, ty)
            self._set_hold(tx, ty)
        elif msg.startswith("STIMONSET"):
            self._plan_reading()
        elif msg == "PREVIEW_ONSET":
            self._plan_vwp_preview()
        elif msg.startswith("AUDIO_ONSET"):
            self._plan_vwp_audio()
        elif msg == "TRIALEND":
            self.segments.clear()
            self.active_seg = None
            self._set_hold(self.cur_x, self.cur_y)

    def sample(self):
        if self.t == self.last_polled_t:
            self.advance(1)
        self.last_polled_t = self.t
        return self.cur_x, self.cur_y

    # ---- Experiment-specific eye-movement planners -----------------------
    def _plan_reading(self):
        self.segments.clear()
        self.active_seg = None
        ias = self.ws["interest_areas"]     # [(word, left, top, right, bottom), ...]
        v = self.exp.var
        H = self.H
        n_words = len(ias)

        target_wi = None
        if self.name == "boundary" and "target_word_nr" in v:
            target_wi = int(v.target_word_nr) - 1

        # Build sequence of word indices with realistic skips, refixations, regressions.
        seq = []
        wi = 0 if self.rng.random() < 0.7 else 1
        while wi < n_words:
            word = ias[wi][0]
            # Never skip pre-target or target word in boundary so every trial crosses cleanly.
            force_fix = (target_wi is not None and wi in (target_wi - 1, target_wi))
            if wi > 0 and not force_fix and wi < n_words - 1:
                skip_p = 0.35 if len(word) <= 3 else (0.14 if len(word) <= 5 else 0.04)
                if self.name == "movingwindow" and str(v.get("window", "")) == "4":
                    skip_p *= 0.35
                if self.rng.random() < skip_p:
                    wi += 1
                    continue
            seq.append(wi)
            # Refixation on long words
            if len(word) >= 7 and self.rng.random() < 0.14:
                seq.append(wi)
            # Occasional short regressive saccade (not past pre-target in boundary to keep boundary clean)
            if (wi >= 3 and wi < n_words - 1 and self.rng.random() < 0.08
                    and not (target_wi is not None and wi == target_wi)):
                seq.append(wi - 1)
                seq.append(wi)
            wi += 1

        # Ensure pre-boundary -> post-boundary jump happens cleanly once in boundary.
        cx, cy = self.cur_x, self.cur_y
        # Natural blink on 1 trial per subject (non-critical middle transition).
        do_blink_at = (len(seq) // 2) if (self.trial == 4 and len(seq) >= 6) else None

        crossed = False
        for step_idx, wi in enumerate(seq):
            word, left, _, right, _ = ias[wi]
            ink_w = max(14.0, (right - left) - (14.4 if wi < n_words - 1 else 0.0))
            lx = left + ink_w * self.rng.uniform(0.35, 0.58)
            if target_wi is not None:
                bnd = float(v.boundary)
                if wi < target_wi:
                    lx = min(lx, bnd - 18.0)
                elif wi == target_wi and not crossed:
                    # Guarantee landing clearly inside target word past boundary.
                    lx = max(lx, bnd + 16.0)
                    crossed = True
            lx = max(left + 4.0, min(max(left + 6.0, right - 12.0), lx))
            ly = H / 2.0 + self.rng.gauss(0, 4.5)

            if do_blink_at is not None and step_idx == do_blink_at:
                blink_dur = self.rng.randint(85, 115)
                self._push("blink", blink_dur, cx, cy, cx, cy)

            # Fixation duration with paradigm-realistic condition effects
            base = 205.0 * self.speed
            if len(word) >= 7:
                base += 20.0
            if self.name == "reading" and str(v.condition) == "comma" and "," in word:
                base += 22.0
            elif self.name == "boundary" and wi == target_wi:
                base += 42.0 if str(v.condition) == "dissimilar" else -10.0
            elif self.name == "movingwindow":
                if str(v.get("window", "")) == "4":
                    base += 28.0
                if str(v.get("version", "")) == "low" and wi >= n_words // 2:
                    base += 25.0

            fix_dur = max(115, min(420, int(round(self.rng.gauss(base, 32.0)))))
            if step_idx > 0 and wi != target_wi and abs(lx - cx) < 28.0:
                # Avoid tiny < 2-letter hops that behave as microsaccades in movingwindow
                continue
            self._saccade_to(lx, ly, (cx, cy))
            self._push("fix", fix_dur, lx, ly, lx, ly)
            cx, cy = lx, ly

        # Final saccade to the bottom-right corner square (must dwell >= 100 ms in >0.9*W, >0.9*H)
        corner_x = self.W * 0.94 + self.rng.uniform(-4.0, 4.0)
        corner_y = self.H * 0.94 + self.rng.uniform(-4.0, 4.0)
        self._saccade_to(corner_x, corner_y, (cx, cy))
        self._set_hold(corner_x, corner_y)

    def _obj_centre(self, name):
        cx, cy = self.ws["POS"][self.ws["objects"].index(name)]
        return cx + self.W / 2.0, cy + self.H / 2.0

    def _plan_vwp_preview(self):
        self.segments.clear()
        self.active_seg = None
        objs = list(self.ws["objects"])
        pick = self.rng.choice(objs)
        ox, oy = self._obj_centre(pick)
        ox += self.rng.gauss(0, 12.0)
        oy += self.rng.gauss(0, 12.0)
        self._push("fix", 240, self.cur_x, self.cur_y, self.cur_x, self.cur_y)
        self._saccade_to(ox, oy, (self.cur_x, self.cur_y))
        self._push("fix", 410, ox, oy, ox, oy)
        cx, cy = self.W / 2.0 + self.rng.gauss(0, 8.0), self.H / 2.0 + self.rng.gauss(0, 8.0)
        self._saccade_to(cx, cy, (ox, oy))
        self._set_hold(cx, cy)

    def _plan_vwp_audio(self):
        self.segments.clear()
        self.active_seg = None
        onset = int(self.exp.var.target_onset)
        cx, cy = self.cur_x, self.cur_y

        # Wait through carrier + saccadic latency after target_onset
        lat = self.rng.randint(175, 235)
        pre_dur = max(120, onset + lat)
        self._push("fix", pre_dur, cx, cy, cx, cy)

        # Cohort competitor looks on 75% of trials before shifting to target
        tx, ty = self._obj_centre(self.exp.var.target)
        tx += self.rng.gauss(0, 14.0)
        ty += self.rng.gauss(0, 14.0)
        if self.rng.random() < 0.75:
            kx, ky = self._obj_centre(self.exp.var.competitor)
            kx += self.rng.gauss(0, 14.0)
            ky += self.rng.gauss(0, 14.0)
            sd1 = self._saccade_to(kx, ky, (cx, cy))
            comp_dur = self.rng.randint(230, 320)
            self._push("fix", comp_dur, kx, ky, kx, ky)
            if self.trial == 3:
                self._push("blink", 90, kx, ky, kx, ky)
            sd2 = self._saccade_to(tx, ty, (kx, ky))
            to_target_ms = lat + sd1 + comp_dur + sd2
        else:
            sd = self._saccade_to(tx, ty, (cx, cy))
            to_target_ms = lat + sd

        self._set_hold(tx, ty)
        click_delay = max(to_target_ms + 220, self.rng.randint(860, 1180))
        self.vwp_click_t = self.t + onset + click_delay
        # Canvas coordinates for mouse.get_click()
        ctx, cty = self.ws["POS"][self.ws["objects"].index(self.exp.var.target)]
        self.vwp_clicked_pos = (int(ctx + self.rng.gauss(0, 10)),
                                int(cty + self.rng.gauss(0, 10)))

    def click(self):
        if self.vwp_click_t is not None and self.t >= self.vwp_click_t:
            pos = self.vwp_clicked_pos
            self.vwp_click_t = None
            return pos
        return None

    def key(self, keylist, timeout):
        if timeout == 0:
            return None
        if keylist and "1" in keylist:
            self.advance(self.rng.randint(950, 1950))
            correct = self.exp.var.get("correct_button", "1")
            if correct not in ("1", "2"):
                correct = "1"
            if self.rng.random() < self.accuracy:
                return correct
            return "2" if correct == "1" else "1"
        self.advance(450)
        return "space"


def run_one(name, subject, outdir):
    from libopensesame.experiment import Experiment
    from pygaze._eyetracker import libdummytracker
    from openexp._clock import legacy as clock_legacy, psycho as clock_psycho
    from openexp._canvas import legacy as canvas_legacy, psycho as canvas_psycho
    from openexp._keyboard import legacy as kb_legacy, psycho as kb_psycho
    from openexp._mouse import legacy as mouse_legacy, psycho as mouse_psycho
    import pygame

    osexp_name = {"reading": "reading_short", "boundary": "boundary_short"}.get(name, name)
    tmp = tempfile.mkdtemp(prefix="osexp-gen-")
    with tarfile.open(os.path.join(OSEXP, osexp_name + ".osexp")) as tar:
        tar.extractall(tmp, filter="data")
    with open(os.path.join(tmp, "script.opensesame"), encoding="utf-8") as f:
        script = f.read()

    assert EYELINK_LINE in script
    script = script.replace(EYELINK_LINE, "EYELINK = True  # example_data 1000 Hz EyeLink simulation")

    exp_dir = os.path.join(outdir, name)
    os.makedirs(exp_dir, exist_ok=True)
    csv_path = os.path.join(exp_dir, "subject-%d.csv" % subject)
    asc_path = os.path.join(exp_dir, "subject-%d.asc" % subject)

    exp = Experiment(string=script, experiment_path=OSEXP, logfile=csv_path,
                     subject_nr=subject, pool_folder=os.path.join(tmp, "pool"))
    sess = AscSession(exp, name, subject)

    # Save originals so repeated runs leave no stale monkey-patches.
    D = libdummytracker.Dummy
    orig = {
        "calibrate": D.calibrate,
        "drift": D.drift_correction,
        "sample": D.sample,
        "log": D.log,
        "log_var": D.log_var,
        "send_cmd": D.send_command,
        "start_rec": D.start_recording,
        "stop_rec": D.stop_recording,
        "cl_time": clock_legacy.Legacy.time,
        "cl_sleep": clock_legacy.Legacy.sleep,
        "cp_time": clock_psycho.Psycho.time,
        "cp_sleep": clock_psycho.Psycho.sleep,
        "pg_ticks": pygame.time.get_ticks,
        "c_leg_show": canvas_legacy.Legacy.show,
        "c_psy_show": canvas_psycho.Psycho.show,
        "kb_leg": kb_legacy.Legacy._get_key_event,
        "kb_psy": kb_psycho.Psycho.get_key,
        "ms_leg_ev": mouse_legacy.Legacy._get_mouse_event,
        "ms_leg_pos": mouse_legacy.Legacy.set_pos,
        "ms_psy": mouse_psycho.Psycho.get_click,
    }

    D.calibrate = lambda self: sess.calibrate()
    D.drift_correction = lambda self, pos=None, fix_triggered=False: sess.drift_correction(pos, fix_triggered)
    D.sample = lambda self: sess.sample()
    D.log = lambda self, msg: sess.log(msg)
    D.log_var = lambda self, var, val: sess.log("var %s %s" % (var, val))
    D.send_command = lambda self, cmd: sess.asc.append("MSG\t%d !CMD %s" % (sess.t, cmd))
    D.start_recording = lambda self: sess.start_recording()
    D.stop_recording = lambda self: sess.stop_recording()

    clock_legacy.Legacy.time = lambda self: sess.time()
    clock_legacy.Legacy.sleep = lambda self, ms: sess.sleep(ms)
    clock_psycho.Psycho.time = lambda self: sess.time()
    clock_psycho.Psycho.sleep = lambda self, ms: sess.sleep(ms)
    pygame.time.get_ticks = lambda: sess.ticks()

    def leg_show(self):
        sess.advance(2)
        return orig["pg_ticks"]() if False else sess.time()

    def psy_show(self):
        sess.advance(sess.rng.randint(2, 4))
        return sess.time()

    canvas_legacy.Legacy.show = leg_show
    canvas_psycho.Psycho.show = psy_show

    def _kb_leg(self, event_type):
        return sess.key(self.keylist, self.timeout), sess.ticks()

    kb_legacy.Legacy._get_key_event = _kb_leg

    # OpenSesame Psycho keyboard/mouse decorators expect `(self)` -> `(val, t)`.
    from openexp.backend import configurable

    @configurable
    def _kb_psy(self):
        return sess.key(self.keylist, self.timeout), sess.time()

    kb_psycho.Psycho.get_key = _kb_psy

    def _ms_leg(self, event_type):
        pos = sess.click()
        return (None if pos is None else 1), pos, sess.ticks()

    def _ms_set_pos(self, pos=(0, 0)):
        sess.vwp_mouse_resets.append((sess.trial, pos))
        return orig["ms_leg_pos"](self, pos=pos)

    @configurable
    def _ms_psy(self):
        pos = sess.click()
        return (None if pos is None else 1), pos, sess.time()

    mouse_legacy.Legacy._get_mouse_event = _ms_leg
    mouse_legacy.Legacy.set_pos = _ms_set_pos
    mouse_psycho.Psycho.get_click = _ms_psy

    try:
        exp.run()
    finally:
        D.calibrate = orig["calibrate"]
        D.drift_correction = orig["drift"]
        D.sample = orig["sample"]
        D.log = orig["log"]
        D.log_var = orig["log_var"]
        D.send_command = orig["send_cmd"]
        D.start_recording = orig["start_rec"]
        D.stop_recording = orig["stop_rec"]
        clock_legacy.Legacy.time = orig["cl_time"]
        clock_legacy.Legacy.sleep = orig["cl_sleep"]
        clock_psycho.Psycho.time = orig["cp_time"]
        clock_psycho.Psycho.sleep = orig["cp_sleep"]
        pygame.time.get_ticks = orig["pg_ticks"]
        canvas_legacy.Legacy.show = orig["c_leg_show"]
        canvas_psycho.Psycho.show = orig["c_psy_show"]
        kb_legacy.Legacy._get_key_event = orig["kb_leg"]
        kb_psycho.Psycho.get_key = orig["kb_psy"]
        mouse_legacy.Legacy._get_mouse_event = orig["ms_leg_ev"]
        mouse_legacy.Legacy.set_pos = orig["ms_leg_pos"]
        mouse_psycho.Psycho.get_click = orig["ms_psy"]

    with open(asc_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(sess.asc) + "\n")
    return csv_path, asc_path


def verify_pair(name, subject, csv_path, asc_path):
    """Validate structural, EyeLink, and experimental consistency of an (.asc, .csv) pair."""
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    with open(asc_path, encoding="utf-8") as f:
        lines = [line.rstrip("\n") for line in f]

    want_n = {"reading": 14, "boundary": 14, "movingwindow": 5, "vwp": 8}[name]
    assert len(rows) == want_n, "%s s%d: expected %d csv rows, got %d" % (name, subject, want_n, len(rows))
    assert all(r["trial_aborted"] == "0" for r in rows)

    trial_starts = [i for i, l in enumerate(lines) if re.match(r"MSG\t\d+ TRIALID \d+$", l)]
    trial_ends = [i for i, l in enumerate(lines) if re.match(r"MSG\t\d+ TRIAL_RESULT 0$", l)]
    assert len(trial_starts) == want_n and len(trial_ends) == want_n

    # Verify strict 1 ms sample timestamps inside every START..END block, zero open events,
    # zero aborted/timeout flags, and paradigm-specific guarantees.
    in_rec = False
    prev_t = None
    open_kinds = set()
    cur_fix = None
    n_fix = n_sac = n_blink = 0
    bad_mw_lock = 0
    hook_trials = []
    cur_trial = 0
    boundary_changed = set()
    for line in lines:
        if line.startswith("START\t"):
            assert not in_rec
            in_rec = True
            prev_t = None
        elif line.startswith("END\t"):
            assert in_rec and not open_kinds, "%s s%d open_kinds=%s" % (name, subject, open_kinds)
            in_rec = False
        elif line.startswith("SFIX "):
            open_kinds.add("fix")
            cur_fix = int(line.split("\t")[1])
        elif line.startswith("EFIX "):
            open_kinds.remove("fix")
            n_fix += 1
            parts = line.split("\t")
            st, en, dur = int(parts[1]), int(parts[2]), int(parts[3])
            assert en - st + 1 == dur and dur > 0
            cur_fix = None
        elif line.startswith("SSACC "):
            open_kinds.add("sac")
        elif line.startswith("ESACC "):
            open_kinds.remove("sac")
            n_sac += 1
        elif line.startswith("SBLINK "):
            open_kinds.add("blink")
        elif line.startswith("EBLINK "):
            open_kinds.remove("blink")
            n_blink += 1
        elif line.startswith("MSG\t"):
            ts_str, msg = line[4:].split(" ", 1)
            if msg.startswith("TRIALID "):
                cur_trial = int(msg.split()[1])
            elif msg.startswith("WINDOWMOVE ") and cur_fix is not None:
                # Ignore first 20 ms settling before initial lock right at STIMONSET
                if int(ts_str) - cur_fix >= 25:
                    bad_mw_lock += 1
            elif msg.startswith("DISPLAYCHANGE "):
                boundary_changed.add(cur_trial)
                # Ensure DISPLAYCHANGE occurs strictly inside a saccade, never during fixation
                if cur_fix is not None:
                    hook_trials.append(cur_trial)
            assert "TIMEOUT" not in msg and "TRIAL ABORTED" not in msg, msg
        elif re.match(r"^\d+\t", line):
            t = int(line.split("\t", 1)[0])
            if prev_t is not None:
                assert t == prev_t + 1, "%s s%d sample gap %d -> %d" % (name, subject, prev_t, t)
            prev_t = t

    assert not bad_mw_lock, "%s s%d had %d WINDOWMOVE during fixations" % (name, subject, bad_mw_lock)
    assert not hook_trials, "%s s%d had hook trials %s" % (name, subject, hook_trials)
    if name == "boundary":
        assert len(boundary_changed) == want_n
    return n_fix, n_sac, n_blink


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--outdir", default=OUT_DEFAULT)
    a = ap.parse_args()
    os.environ.setdefault("DISPLAY", ":0")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    total_bytes = 0
    for name in ALL:
        for subject in range(1, 7):
            csv_path, asc_path = run_one(name, subject, a.outdir)
            n_fix, n_sac, n_blink = verify_pair(name, subject, csv_path, asc_path)
            sz = os.path.getsize(asc_path) + os.path.getsize(csv_path)
            total_bytes += sz
            print("%-12s s%d: fix=%4d sac=%4d blink=%d  (%5.1f KB)  OK"
                  % (name, subject, n_fix, n_sac, n_blink, sz / 1024.0))
    print("Total size: %.2f MB across 24 .asc + 24 .csv files" % (total_bytes / (1024.0 * 1024.0)))


if __name__ == "__main__":
    main()
