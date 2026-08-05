# Minimal Sphinx makefile for the fishing-robot workspace docs.
# CI passes a stricter SPHINXOPTS="-W --keep-going" to fail on warnings.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build
SKIP_DIAGRAM_PDF ?=

MMD_SOURCES   := $(wildcard diagrams/*.mmd)
PDF_TARGETS   := $(patsubst diagrams/%.mmd,exports/pdf/%.pdf,$(MMD_SOURCES))
SVG_TARGETS   := $(patsubst diagrams/%.mmd,exports/svg/%.svg,$(MMD_SOURCES))

SITE_PDF       ?= exports/fishing-robot-ros2-codebase.pdf
SOURCE_PDF    ?= exports/fishing-robot-ros2-source.pdf
SOURCE_HTML   ?= _build/source_code/index.html

.PHONY: help html singlehtml site-pdf source-pdf clean linkcheck export-diagrams export-diagrams-pdf export-diagrams-svg diagrams-pdf diagrams-svg

help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
	@echo ""
	@echo "Diagram export targets:"
	@echo "  make diagrams-pdf   Incrementally export diagrams/*.mmd → exports/pdf/*.pdf"
	@echo "  make diagrams-svg   Incrementally export diagrams/*.mmd → exports/svg/*.svg"

html:
ifneq ($(SKIP_DIAGRAM_PDF),1)
	@$(MAKE) diagrams-pdf
endif
	@$(SPHINXBUILD) -b html "$(SOURCEDIR)" "$(BUILDDIR)/html" $(SPHINXOPTS) $(O)
	@echo "Build finished. Open $(BUILDDIR)/html/index.html"
	@echo "Diagram PDFs: exports/pdf/"

singlehtml:
ifneq ($(SKIP_DIAGRAM_PDF),1)
	@$(MAKE) diagrams-pdf
endif
	@$(SPHINXBUILD) -b singlehtml "$(SOURCEDIR)" "$(BUILDDIR)/singlehtml" $(SPHINXOPTS) $(O)
	@echo "Single-page HTML: $(BUILDDIR)/singlehtml/index.html"

site-pdf: singlehtml
	@node scripts/export_site_pdf.js "$(BUILDDIR)/singlehtml/index.html" "$(SITE_PDF)"
	@echo "Codebase PDF: $(SITE_PDF)"

source-pdf:
	@bash export_source_code_pdf.sh --output "$(SOURCE_PDF)"

clean:
	rm -rf "$(BUILDDIR)" _generated

clean-diagrams:
	rm -rf exports/pdf exports/svg

# Incremental PDF export (preferred for LaTeX \includegraphics).
diagrams-pdf export-diagrams-pdf:
	@bash scripts/export_diagram_pdfs.sh

# Incremental SVG export (one file per target; `make diagrams-svg` builds all).
diagrams-svg export-diagrams-svg: $(SVG_TARGETS)
	@for pdf in exports/svg/*.svg; do \
	  [ -f "$$pdf" ] && cp -f "$$pdf" _static/diagrams/; \
	done 2>/dev/null || true
	@echo "Diagram SVGs: exports/svg/"

exports/svg/%.svg: diagrams/%.mmd
	@mkdir -p exports/svg _static/diagrams
	@if [ -x node_modules/.bin/mmdc ]; then \
	  node_modules/.bin/mmdc -i $< -o $@; \
	elif command -v mmdc >/dev/null 2>&1; then \
	  mmdc -i $< -o $@; \
	else \
	  npx --yes @mermaid-js/mermaid-cli -i $< -o $@; \
	fi
	@cp -f $@ _static/diagrams/

# Backward-compatible alias (SVG).
export-diagrams: diagrams-svg

linkcheck:
	@$(SPHINXBUILD) -b linkcheck "$(SOURCEDIR)" "$(BUILDDIR)/linkcheck" $(O)
