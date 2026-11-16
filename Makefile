QUARTO ?= quarto
SLIDES_PYTHON ?= /opt/slides-check/bin/python
SLIDES_OUT ?= /tmp/slides
ANIM_TIMES ?= 2,6,12

SLIDE_SRC := slides/workshop.qmd
SLIDE_HTML := slides/workshop.html
SLIDE_DEPS := \
	$(SLIDE_SRC) \
	slides/workshop.css \
	slides/animations.js \
	slides/animations-include.html \
	slides/js/gsap.min.js \
	$(wildcard slides/images/*.png slides/images/vwp/*.png)

.DEFAULT_GOAL := slides

.PHONY: all slides preview check clean help

all: slides

slides: $(SLIDE_HTML)

$(SLIDE_HTML): $(SLIDE_DEPS)
	$(QUARTO) render $(SLIDE_SRC)

preview:
	$(QUARTO) preview $(SLIDE_SRC)

check: $(SLIDE_HTML)
	$(SLIDES_PYTHON) slides/check_slides.py $(SLIDE_HTML) --out $(SLIDES_OUT) --anim-times $(ANIM_TIMES)

clean:
	rm -rf $(SLIDE_HTML) slides/workshop_files slides/.quarto

help:
	@echo "Targets:"
	@echo "  make [slides]   Render $(SLIDE_HTML) with Quarto"
	@echo "  make preview    Live-preview $(SLIDE_SRC) with Quarto"
	@echo "  make check      Render slides and run check_slides.py (out: $(SLIDES_OUT))"
	@echo "  make clean      Remove rendered slide outputs"
