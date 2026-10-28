"""Extracts the sentences of examples/EyeLogic_LITE.osexp into movingwindow.csv.

    /home/ubuntu/venv/bin/python experiments/extract_eyelogic.py

The experiment's file pool contains its practice materials
(sentences_practice.xlsx): 5 items, each with a high- and a low-frequency
version of the sentence and its own comprehension question. Both versions of
every item become rows of movingwindow.csv (10 sentences).

Corrections: item 1005, low-frequency version: the sentence is "No podemos
negar que el supermercado tiene ...", the question "¿Podemos negar que el
supermercado tiene ...?", but the answer key says YES (the parallel
high-frequency question has NO). Corrected to NO; `corrected = 1`.
"""
import csv
import io
import os
import tarfile

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "examples", "EyeLogic_LITE.osexp")

# (item, version): (answer in the source, corrected answer)
CORRECTIONS = {(1005, "low"): ("YES", "NO")}


def main():
    with tarfile.open(SRC) as tar:
        data = tar.extractfile("pool/sentences_practice.xlsx").read()
    ws = openpyxl.load_workbook(io.BytesIO(data)).active
    rows = list(ws.values)
    head = [str(h) for h in rows[0]]
    out = []
    for values in rows[1:]:
        r = dict(zip(head, values))
        for version in ("high", "low"):
            answer = str(r["correct_" + version]).strip()
            fix = CORRECTIONS.get((r["index"], version))
            corrected = 0
            if fix:
                assert answer == fix[0], "source of item %s changed" % r["index"]
                answer, corrected = fix[1], 1
            out.append({
                "item": len(out) + 1,
                "source_item": r["index"],
                "version": version,
                "sentence": str(r["sentence_" + version]).strip(),
                "question": str(r["Q_" + version]).strip()
                if str(r["is_Q"]).strip() == "YES" else "NA",
                "answer": {"YES": "SI", "NO": "NO"}[answer]
                if str(r["is_Q"]).strip() == "YES" else "NA",
                "corrected": corrected,
            })
    with open(os.path.join(HERE, "movingwindow.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print("wrote movingwindow.csv: %d sentences, %d corrected"
          % (len(out), sum(r["corrected"] for r in out)))


if __name__ == "__main__":
    main()
