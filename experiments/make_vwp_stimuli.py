"""Creates the pictures and spoken instructions for vwp.osexp.

    /home/ubuntu/venv/bin/python experiments/make_vwp_stimuli.py \
        [--piper PATH --voice MODEL.onnx]

Pictures: simple line drawings made with PIL (240 x 240 px PNG).

Sound: "Click on the" + target word, synthesised with Piper
(https://github.com/rhasspy/piper; voice en_US-ljspeech-high, trained on the
public-domain LJ Speech data set). The carrier phrase and the word are
synthesised separately, trimmed, and spliced, so the onset of the target word
in each file is known exactly; it is written to `stimuli.csv`. Without
`--piper` only the pictures are (re)drawn and the existing audio is kept.

Everything is written to `experiments/vwp_pool/`; build_osexp.py copies it
into the file pool of vwp.osexp.
"""
import argparse
import csv
import math
import os
import subprocess
import tempfile
import wave

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
POOL = os.path.join(HERE, "vwp_pool")
SIZE = 240
RATE = 48000                       # matches sound_freq in the experiments
CARRIER = "Click on the"

# Each display: two words with the same onset (target and competitor) plus two
# unrelated distractors. Every display is used twice, once with each of the
# two onset-overlapping words as the target.
DISPLAYS = [
    ("candle", "candy", "chair", "apple"),
    ("bell", "belt", "fish", "key"),
    ("cat", "cap", "tree", "cup"),
    ("star", "stairs", "moon", "heart"),
]

INK = (0, 0, 0)
W = 6                              # line width


def candle(d):
    d.rectangle((95, 100, 145, 215), fill=(245, 240, 220), outline=INK, width=W)
    d.line((120, 100, 120, 80), fill=INK, width=4)
    d.polygon([(120, 25), (138, 62), (120, 80), (102, 62)], fill=(255, 150, 0), outline=INK)


def candy(d):
    d.polygon([(70, 120), (25, 85), (25, 155)], fill=(230, 60, 60), outline=INK)
    d.polygon([(170, 120), (215, 85), (215, 155)], fill=(230, 60, 60), outline=INK)
    d.ellipse((65, 85, 175, 155), fill=(230, 60, 60), outline=INK, width=W)
    for x in (95, 120, 145):
        d.line((x, 90, x - 10, 150), fill=(255, 255, 255), width=5)


def chair(d):
    brown = (140, 85, 40)
    d.rectangle((75, 25, 165, 115), outline=brown, width=10)          # backrest
    d.line((75, 70, 165, 70), fill=brown, width=8)
    d.rectangle((60, 115, 180, 140), fill=brown, outline=INK, width=3)  # seat
    for x in (70, 170):
        d.line((x, 140, x, 220), fill=brown, width=10)               # legs


def apple(d):
    d.ellipse((55, 70, 135, 200), fill=(210, 30, 30), outline=INK, width=W)
    d.ellipse((105, 70, 185, 200), fill=(210, 30, 30), outline=INK, width=W)
    d.rectangle((90, 90, 150, 190), fill=(210, 30, 30))
    d.line((120, 85, 128, 40), fill=(100, 60, 20), width=7)
    d.ellipse((130, 35, 175, 60), fill=(60, 160, 60), outline=INK, width=3)


def bell(d):
    d.chord((60, 30, 180, 150), 180, 360, fill=(230, 190, 40), outline=INK, width=W)
    d.polygon([(60, 90), (180, 90), (205, 185), (35, 185)], fill=(230, 190, 40), outline=INK)
    d.line((35, 185, 205, 185), fill=INK, width=W)
    d.ellipse((105, 180, 135, 210), fill=INK)
    d.ellipse((112, 15, 128, 31), outline=INK, width=4)


def belt(d):
    d.rounded_rectangle((15, 100, 225, 140), radius=8, fill=(120, 70, 30), outline=INK, width=4)
    d.rectangle((40, 88, 85, 152), outline=(200, 170, 60), width=8)
    for x in (130, 160, 190):
        d.ellipse((x - 5, 115, x + 5, 125), fill=INK)


def fish(d):
    d.polygon([(165, 120), (220, 75), (220, 165)], fill=(60, 140, 220), outline=INK)
    d.ellipse((25, 75, 180, 165), fill=(60, 140, 220), outline=INK, width=W)
    d.ellipse((55, 105, 72, 122), fill=INK)


def key(d):
    d.ellipse((20, 80, 100, 160), outline=(180, 150, 40), width=14)
    d.line((98, 120, 215, 120), fill=(180, 150, 40), width=14)
    for x in (170, 200):
        d.line((x, 120, x, 155), fill=(180, 150, 40), width=12)


def cat(d):
    d.polygon([(55, 95), (70, 30), (105, 75)], fill=(160, 160, 160), outline=INK)
    d.polygon([(185, 95), (170, 30), (135, 75)], fill=(160, 160, 160), outline=INK)
    d.ellipse((45, 60, 195, 200), fill=(160, 160, 160), outline=INK, width=W)
    d.ellipse((85, 105, 105, 125), fill=INK)
    d.ellipse((135, 105, 155, 125), fill=INK)
    d.polygon([(112, 145), (128, 145), (120, 155)], fill=(230, 120, 140))
    for dy in (-8, 8):
        d.line((20, 150 + dy, 95, 150), fill=INK, width=3)
        d.line((220, 150 + dy, 145, 150), fill=INK, width=3)


def cap(d):
    d.chord((45, 50, 195, 200), 180, 360, fill=(40, 90, 200), outline=INK, width=W)
    d.polygon([(150, 125), (230, 125), (225, 150), (150, 140)], fill=(40, 90, 200), outline=INK)
    d.line((45, 125, 195, 125), fill=INK, width=W)
    d.ellipse((112, 42, 128, 58), fill=(40, 90, 200), outline=INK, width=3)


def tree(d):
    d.rectangle((105, 140, 135, 220), fill=(120, 70, 30), outline=INK, width=4)
    d.ellipse((45, 20, 195, 160), fill=(60, 160, 60), outline=INK, width=W)


def cup(d):
    d.arc((140, 90, 200, 160), 270, 90, fill=INK, width=10)
    d.rectangle((50, 70, 160, 200), fill=(250, 250, 250), outline=INK, width=W)
    d.line((70, 40, 75, 60), fill=(150, 150, 150), width=4)
    d.line((100, 35, 105, 60), fill=(150, 150, 150), width=4)


def star(d):
    pts = []
    for i in range(10):
        r = 105 if i % 2 == 0 else 45
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((120 + r * math.cos(a), 125 + r * math.sin(a)))
    d.polygon(pts, fill=(250, 210, 30), outline=INK, width=W)


def stairs(d):
    pts = [(20, 220)]
    x, y = 20, 220
    for _ in range(5):
        y -= 38
        pts.append((x, y))
        x += 40
        pts.append((x, y))
    pts += [(x, 220)]
    d.polygon(pts, fill=(170, 170, 170), outline=INK, width=W)


def moon(d):
    d.ellipse((40, 30, 200, 190), fill=(250, 220, 80), outline=INK, width=W)
    d.ellipse((90, 10, 240, 160), fill=(255, 255, 255))


def heart(d):
    d.ellipse((35, 45, 125, 135), fill=(220, 30, 60))
    d.ellipse((115, 45, 205, 135), fill=(220, 30, 60))
    d.polygon([(40, 105), (200, 105), (120, 210)], fill=(220, 30, 60))


def draw_pictures():
    for name in sorted({n for disp in DISPLAYS for n in disp}):
        img = Image.new("RGB", (SIZE, SIZE), "white")
        globals()[name](ImageDraw.Draw(img))
        img.save(os.path.join(POOL, name + ".png"))


def synthesise(piper, voice, text):
    """Synthesise `text`; returns (mono float array at RATE, silence trimmed)."""
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "out.wav")
        subprocess.run([piper, "-m", voice, "-f", out], input=text.encode(),
                       check=True, capture_output=True)
        with wave.open(out) as w:
            sr = w.getframerate()
            x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16) / 32768
    t_new = np.arange(int(len(x) * RATE / sr)) / RATE
    x = np.interp(t_new, np.arange(len(x)) / sr, x)
    loud = np.nonzero(np.abs(x) > .02)[0]
    return x[max(0, loud[0] - 240):loud[-1] + 240]      # keep 5 ms margins


def write_wav(path, x):
    x = np.concatenate([np.zeros(RATE // 20), x, np.zeros(RATE // 5)])   # 50 ms lead-in
    stereo = np.repeat((np.clip(x, -1, 1) * 32767).astype(np.int16)[:, None], 2, axis=1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(stereo.tobytes())
    return 1000 * (RATE // 20) / RATE                   # lead-in in ms


def make_sounds(piper, voice):
    carrier = synthesise(piper, voice, CARRIER)
    rows = []
    for disp in DISPLAYS:
        for target, competitor in ((disp[0], disp[1]), (disp[1], disp[0])):
            word = synthesise(piper, voice, target)
            lead = write_wav(os.path.join(POOL, "click_%s.wav" % target),
                             np.concatenate([carrier, word]))
            rows.append({
                "target": target, "competitor": competitor,
                "distractor1": disp[2], "distractor2": disp[3],
                "sound": "click_%s.wav" % target,
                "target_onset": round(lead + 1000 * len(carrier) / RATE),
                "sound_duration": round(lead + 1000 * (len(carrier) + len(word)) / RATE),
            })
    with open(os.path.join(POOL, "stimuli.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--piper", help="piper executable")
    ap.add_argument("--voice", help="piper voice model (.onnx)")
    a = ap.parse_args()
    os.makedirs(POOL, exist_ok=True)
    draw_pictures()
    if a.piper:
        make_sounds(a.piper, a.voice)
    print("wrote", POOL)


if __name__ == "__main__":
    main()
