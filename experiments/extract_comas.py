"""Extracts the stimuli of the comma study into `comas.csv`.

    python experiments/extract_comas.py

Source: `examples/frases-comas/frases_comas.script` (UMass EyeTrack script of
the published experiment). Trial names encode the design:

    P1I<n>D0   practice sentence n
    E1I<n>D0   item n, with comma(s)       E2I<n>D0   item n, without commas
    F11I<n>D1  question after item n, correct answer: left button (SÍ)
    F12I<n>D1  question after item n, correct answer: right button (NO)

The sentence type (adversativa, concesiva, ...) comes from
`examples/frases-comas/frases.csv` or, for sentences missing there, from
`words_statistics_for_manuscript.csv`, matched on the letters of the sentence.

Corrections: in the source script, the comma version of item 19 has no comma
(it is identical to the no-comma version; `frases.csv` has the same error).
The manuscript's word table marks "deliciosa" as the pre-comma word and "aun"
as the immediate post-comma word, so the comma is restored after "deliciosa".
Corrected items have `corrected = 1` in comas.csv.
"""
import csv
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "examples", "frases-comas")

# item: (sentence as in the source script, corrected comma version)
CORRECTIONS = {
    19: ("Su comida estaba deliciosa aun llevando muy pocas especias y sal.",
         "Su comida estaba deliciosa, aun llevando muy pocas especias y sal."),
}


def main():
    with open(os.path.join(SRC, "frases_comas.script"), encoding="utf-8") as f:
        script = f.read()
    trials = {}
    for m in re.finditer(r"^trial (\S+)\n(.*?)^end \1", script, re.M | re.S):
        trials[m.group(1)] = re.search(r"inline =\s+\|(.*)", m.group(2)).group(1).strip()

    def letters(text):
        return re.sub(r"\W", "", text).lower()

    types = {}
    with open(os.path.join(SRC, "frases.csv"), encoding="utf-8-sig") as f:
        for sentence_type, sentence in csv.reader(f):
            types[letters(sentence)] = sentence_type
    # Fallback: the word table of the manuscript also has the sentence type.
    words = {}
    with open(os.path.join(SRC, "words_statistics_for_manuscript.csv"),
              encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            key = (r["sentence_type"], r["sentence_number"], r["condition"])
            words.setdefault(key, []).append(r["word"])
    for (sentence_type, _, _), ws in words.items():
        types.setdefault(letters("".join(ws)), sentence_type)

    rows = []
    for name, text in trials.items():
        m = re.fullmatch(r"P1I(\d+)D0", name)
        if m:
            rows.append({"block": "practice", "item": 900 + int(m.group(1)),
                         "sentence_type": "practice", "comma": text,
                         "no_comma": text, "question": "NA", "answer": "NA",
                         "corrected": 0})
    items = sorted(int(m) for m in re.findall(r"^trial E1I(\d+)D0", script, re.M))
    for n in items:
        question, answer = "NA", "NA"
        for code, ans in (("F11", "SI"), ("F12", "NO")):
            if "%sI%dD1" % (code, n) in trials:
                question = trials["%sI%dD1" % (code, n)].split("\\n")[0].strip()
                answer = ans
        comma = trials["E1I%dD0" % n]
        sentence_type = types.get(letters(comma), "NA")
        corrected = n in CORRECTIONS
        if corrected:
            assert comma == CORRECTIONS[n][0], "source of item %d changed" % n
            comma = CORRECTIONS[n][1]
        rows.append({"block": "", "item": n, "sentence_type": sentence_type,
                     "comma": comma, "no_comma": trials["E2I%dD0" % n],
                     "question": question, "answer": answer,
                     "corrected": int(corrected)})
        assert comma != trials["E2I%dD0" % n], \
            "item %d: comma and no-comma versions are identical" % n
        assert letters(comma) == letters(trials["E2I%dD0" % n]), \
            "item %d: versions differ in more than punctuation" % n
    # Two blocks of equal size, in item order.
    exp = [r for r in rows if r["block"] != "practice"]
    for i, r in enumerate(exp):
        r["block"] = 1 + 2 * i // len(exp)

    with open(os.path.join(HERE, "comas.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("wrote comas.csv: %d practice, %d items, %d with a question, %d without a type"
          % (len(rows) - len(exp), len(exp),
             sum(r["question"] != "NA" for r in exp),
             sum(r["sentence_type"] == "NA" for r in exp)))
    print("corrected items:", [r["item"] for r in exp if r["corrected"]])


if __name__ == "__main__":
    main()
