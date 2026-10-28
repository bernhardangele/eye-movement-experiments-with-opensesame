"""Checks the letter and word boundaries (interest areas) against the pixels.

    python experiments/check_interest_areas.py [--backend legacy|psycho]
        [--font mono] [--font-file FILE.ttf ...] [--size 24] [--bold] [--max-sentences N]

Needs the OpenSesame Python and an X display (like test_headless.py); the
psycho backend also needs OpenGL (Mesa works under Xvfb). Draws text with the
chosen backend and finds where each character really is. --font-file uses a
font that is not installed, e.g. --font "Courier New" --font-file
"examples/Courier New.ttf" "examples/Courier New Bold.ttf". (The files are
registered with Qt directly: OpenSesame 4.1.17 finds "<font>.ttf" in the file
pool but then fails to load it, "Font ... not found", and silently uses
another font.) The script prints the font that Qt really uses.

* Ground truth: in a monospace font every character occupies a cell of the
  same width, and '|' sits in the middle of its cell. Drawing a row of '|'
  gives the cell grid (first cell edge and pitch). The grid is then validated:
  every character of a sample sentence, drawn alone at its position, must be
  centred in its cell (its ink may overhang the cell a little, e.g. serifs).
* For every sentence of the experiments (comas.csv, both versions, and the
  boundary sentences in sentences.csv), the right edge of every character and
  word is computed with three methods and compared with the grid:

    corrected        TEXT_LAYOUT in build_osexp.py (exactly the code that runs
                     in the experiments): text_size(text + '|', center=False)
    anchored |..|    text_size('|' + text + '|') minus two '|', with a left
                     offset estimated from the first letter (the method of
                     examples/EyeLogic_LITE.osexp)
    plain text_size  text_size() of the text up to the end of each word, with
                     the default arguments (a common, naive approach)

Word boundaries are compared in the convention of each method: the first two
include the space after a word, plain text_size() measures up to the last
letter.
"""
import argparse
import csv
import os
import sys
import time
from math import floor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_osexp  # noqa: E402  (for TEXT_LAYOUT)

X = 125                     # screen x at which sentences are drawn (as in the experiments)
W, H = 1920, 1080


def sentences():
    out = []
    with open(os.path.join(HERE, "comas.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.append(r["comma"])
            if r["no_comma"] != r["comma"]:
                out.append(r["no_comma"])
    with open(os.path.join(HERE, "sentences.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            end = r["posttarget"] if r["posttarget"].endswith(".") else r["posttarget"] + "."
            out.append(" ".join([r["pretarget"], r["target"], end]))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", default="legacy", choices=["legacy", "psycho"])
    ap.add_argument("--font", default="mono")
    ap.add_argument("--font-file", nargs="+", default=[],
                    help="TrueType file(s) of --font, e.g. regular and bold")
    ap.add_argument("--size", type=int, default=24)
    ap.add_argument("--bold", action="store_true")
    ap.add_argument("--max-sentences", type=int, default=0)
    a = ap.parse_args()
    os.environ.setdefault("DISPLAY", ":0")

    import pygame
    from libopensesame.experiment import Experiment
    exp = Experiment(string=(
        "set width %d\nset height %d\nset font_family \"%s\"\nset font_size %d\n"
        "set font_bold %s\nset canvas_backend {b}\nset keyboard_backend {b}\n"
        "set mouse_backend {b}\nset sampler_backend legacy\nset clock_backend {b}\n"
        "set color_backend {b}\nset uniform_coordinates yes\nset fullscreen no\n"
        "set psychopy_screen 0\nset start s\ndefine sequence s\n").replace("{b}", a.backend)
        % (W, H, a.font, a.size, "yes" if a.bold else "no"))
    exp.init_display()
    exp.init_clock()
    from openexp.canvas import Canvas
    Canvas(exp).text_size("x")                  # initialises Qt and its fonts
    from qtpy.QtGui import QFont, QFontDatabase, QFontInfo
    for path in a.font_file:
        if QFontDatabase.addApplicationFont(os.path.abspath(path)) < 0:
            sys.exit("could not load %s" % path)
    qf = QFont(a.font)
    qf.setPixelSize(a.size)
    qf.setBold(a.bold)
    used = QFontInfo(qf)
    print("Qt draws '%s' with: %s%s" % (a.font, used.family(), " (bold)" if used.bold() else ""))

    def screen_after_show(c):
        """The displayed image as an (x, y) array of summed RGB values."""
        if a.backend == "legacy":
            c.show()
            return pygame.surfarray.array3d(pygame.display.get_surface()).sum(axis=2)
        # psycho: grab the back buffer just before the flip
        win, grab, flip = exp.window, {}, exp.window.flip

        def grab_and_flip(*args, **kwargs):
            grab["img"] = np.array(win._getFrame(buffer="back"))
            win.flip = flip
            return flip(*args, **kwargs)
        win.flip = grab_and_flip
        c.show()
        return grab["img"].astype(int).sum(axis=2).T

    def inked_columns(text):
        c = Canvas(exp, background_color="white")
        c.text(text, center=False, x=X - W // 2, y=-20, color="black", html=False)
        a_ = screen_after_show(c)
        return np.nonzero((a_ < 600).any(axis=1))[0]

    def runs(cols):
        out, start = [], None
        for i, c in enumerate(cols):
            if start is None:
                start = c
            if i + 1 == len(cols) or cols[i + 1] != c + 1:
                out.append((start, c + 1))
                start = None
        return out

    # --- ground truth: the cell grid -------------------------------------
    n_bars = 80
    centres = np.array([(s + e - 1) / 2 for s, e in runs(inked_columns("|" * n_bars))])
    if len(centres) != n_bars:
        sys.exit("could not separate the %d bars (%d found)" % (n_bars, len(centres)))
    pitch, first = np.polyfit(np.arange(n_bars), centres, 1)
    origin = first - pitch / 2
    print("backend %s, font %s %d px%s: pitch %.3f px, first cell starts at x = %.2f (text drawn at x = %d)"
          % (a.backend, a.font, a.size, " bold" if a.bold else "", pitch, origin, X))

    all_sentences = sentences()
    if a.max_sentences:
        all_sentences = all_sentences[:a.max_sentences]
    # Validate the grid: every character, drawn alone at its position, must be
    # centred in its cell (ink may overhang a little, e.g. serifs in Courier).
    sample = all_sentences[0]
    off_centre = overhang = 0
    for k, ch in enumerate(sample):
        if ch == " ":
            continue
        cols = inked_columns("".join(c if i == k else " " for i, c in enumerate(sample)))
        centre = (cols[0] + cols[-1]) / 2
        cell_centre = origin + (k + 0.5) * pitch
        if abs(centre - cell_centre) > pitch / 4:
            off_centre += 1
        if cols[0] < origin + k * pitch - 1 or cols[-1] + 1 > origin + (k + 1) * pitch + 1:
            overhang += 1
    print("grid check: %d of %d characters not centred in their cell (must be 0); "
          "%d overhang their cell by > 1 px (allowed)"
          % (off_centre, sum(c != " " for c in sample), overhang))
    if off_centre:
        sys.exit("not a monospace font? the ground truth does not apply")

    # --- the three methods -------------------------------------------------
    probe = Canvas(exp)
    ns = {"_probe": probe, "SENTENCE_LEFT": X, "W": W}
    exec(build_osexp.TEXT_LAYOUT, ns)
    letter_edges = ns["letter_edges"]

    def ts(t, **kw):
        return probe.text_size(t, **kw)[0]

    def anchored_method(s):
        anchor = ts("|", html=False)

        def anchored(t):
            return ts("|" + t + "|", html=False) - 2 * anchor
        corr = ts("X", html=False) * 0.01
        left = X + (ts(s[0] + "|", html=False) - anchor) - anchored(s[0])
        chars = [floor(left + anchored(s[:k + 1]) - corr) for k in range(len(s))]
        words, cur = [], ""
        ws = s.split(" ")
        for i, w in enumerate(ws):
            cur += w + (" " if i < len(ws) - 1 else "")
            words.append(floor(left + anchored(cur) - corr))
        return floor(left), chars, words

    def plain_text_size(s):
        ws = s.split(" ")
        words = [ts(" ".join(ws[:i + 1])) + X for i in range(len(ws))]
        return words

    methods = ("corrected", "anchored |..|", "plain text_size")
    stats = {m: {"left": [], "char": [], "word": []} for m in methods}
    t_ours = []
    for s in all_sentences:
        truth_char = [origin + (k + 1) * pitch for k in range(len(s))]
        ends, pos = [], 0                  # index of the last letter of each word
        for w in s.split(" "):
            ends.append(pos + len(w) - 1)
            pos += len(w) + 1
        with_space = [min(e + 1, len(s) - 1) for e in ends]

        t0 = time.time()
        edges = letter_edges(s)
        t_ours.append(time.time() - t0)
        st = stats["corrected"]
        st["left"].append(edges[0] - origin)
        st["char"] += [edges[k + 1] - truth_char[k] for k in range(len(s)) if s[k] != " "]
        st["word"] += [edges[e + 1] - truth_char[e] for e in with_space]

        left, chars, words = anchored_method(s)
        st = stats["anchored |..|"]
        st["left"].append(left - origin)
        st["char"] += [chars[k] - truth_char[k] for k in range(len(s)) if s[k] != " "]
        st["word"] += [words[i] - truth_char[e] for i, e in enumerate(with_space)]

        st = stats["plain text_size"]
        st["left"].append(0 - origin + X)
        st["word"] += [w - truth_char[e] for w, e in zip(plain_text_size(s), ends)]

    print("%d sentences, %d letters, %d words\n" % (
        len(all_sentences), len(stats["corrected"]["char"]), len(stats["corrected"]["word"])))
    print("error = computed - true position, in px (one letter = %.1f px)" % pitch)
    print("%-16s %-22s %-22s %-22s" % ("method", "sentence left edge", "letter right edges",
                                       "word right edges"))
    for m, st in stats.items():
        cells = []
        for key in ("left", "char", "word"):
            e = np.array(st[key])
            cells.append("n/a" if not len(e) else "%+5.1f .. %+5.1f (%.2f L)"
                         % (e.min(), e.max(), np.abs(e).max() / pitch))
        print("%-16s %-22s %-22s %-22s" % (m, *cells))
    print("\ncorrected method: %.0f ms per sentence (prepare phase)" % (1000 * np.mean(t_ours)))
    worst = max(np.abs(stats["corrected"][k]).max() for k in ("left", "char", "word"))
    print("RESULT: the boundaries used in the experiments are %s (max error %.1f px)"
          % ("CORRECT" if worst <= 1.5 else "WRONG", worst))
    sys.exit(int(worst > 1.5))


if __name__ == "__main__":
    main()
