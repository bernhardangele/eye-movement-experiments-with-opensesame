"""Checks the rendered slides in a headless browser.

    /opt/slides-check/bin/python slides/check_slides.py [slides/workshop.html]
        [--out DIR] [--anim-times 1,4,8,12] [--only fixations,boundary]

Render first (quarto render slides/workshop.qmd). For every slide, this script
reports content that does not fit on the 1920 x 1080 slide (OVERFLOW), boxes
with their own scrollbar (INNER-SCROLL, e.g. code that is cut off), and
JavaScript errors, and saves a screenshot. For slides with an animation it also
saves screenshots at the given times (seconds after the slide appears), so the
animations can be checked frame by frame. Exit code 1 if anything is wrong.

Needs Playwright with Chromium; the devcontainer installs both in
/opt/slides-check (see .devcontainer/Dockerfile).
"""
import argparse
import os
import sys
import tempfile

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))

GOTO = '''i => { const s = Reveal.getSlides()[i]; const x = Reveal.getIndices(s);
                 Reveal.slide(x.h, x.v); }'''
INFO = '''() => { const s = Reveal.getCurrentSlide(); const h = s.querySelector('h1, h2');
  let inner = 0;
  s.querySelectorAll('pre, code, table, div').forEach(e => {
    if (e.scrollHeight > e.clientHeight + 4 && getComputedStyle(e).overflowY !== 'visible') inner++; });
  const a = s.querySelector('.anim');
  return {title: h ? h.textContent.trim() : '', height: s.scrollHeight, inner: inner,
          anim: a ? a.dataset.anim : null}; }'''


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html", nargs="?", default=os.path.join(HERE, "workshop.html"))
    ap.add_argument("--out", default=None, help="folder for the screenshots")
    ap.add_argument("--anim-times", default="1,4,8,12")
    ap.add_argument("--only", default=None, help="only these animations (comma-separated)")
    ap.add_argument("--width", type=int, default=1600, help="browser window (16:9)")
    a = ap.parse_args()
    out = a.out or tempfile.mkdtemp(prefix="slides-")
    os.makedirs(out, exist_ok=True)
    times = [float(t) for t in a.anim_times.split(",") if t]
    only = set(a.only.split(",")) if a.only else None

    problems = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": a.width, "height": a.width * 9 // 16})
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto("file://" + os.path.abspath(a.html))
        page.wait_for_timeout(1500)
        cfg = page.evaluate("({w: Reveal.getConfig().width, h: Reveal.getConfig().height,"
                            " n: Reveal.getTotalSlides()})")
        print("%d slides, %d x %d" % (cfg["n"], cfg["w"], cfg["h"]))
        for i in range(cfg["n"]):
            page.evaluate(GOTO, i)
            page.wait_for_timeout(300)
            info = page.evaluate(INFO)
            flags = []
            if info["height"] > cfg["h"] + 2:
                flags.append("OVERFLOW (%d px)" % info["height"])
            if info["inner"]:
                flags.append("INNER-SCROLL")
            problems += bool(flags)
            if flags or (info["anim"] and (not only or info["anim"] in only)):
                print("%3d %-60s %s %s" % (i + 1, info["title"][:60], " ".join(flags),
                                           "[animation: %s]" % info["anim"] if info["anim"] else ""))
            page.screenshot(path=os.path.join(out, "slide%02d.png" % (i + 1)))
            if info["anim"] and (not only or info["anim"] in only):
                # restart the animation from 0, as a click by the presenter does
                page.evaluate("Reveal.getCurrentSlide().querySelector('.anim').click()")
                prev = 0
                for t in times:
                    page.wait_for_timeout(int((t - prev) * 1000))
                    prev = t
                    page.screenshot(path=os.path.join(
                        out, "slide%02d_%s_%04.1fs.png" % (i + 1, info["anim"], t)))
        browser.close()
    for e in errors:
        print("JavaScript error:", e)
    problems += len(errors)
    print("screenshots in", out)
    print("OK" if not problems else "%d PROBLEM(S)" % problems)
    sys.exit(bool(problems))


if __name__ == "__main__":
    main()
