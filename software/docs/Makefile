# Minimal Sphinx makefile for the fishing-robot workspace docs.
# CI passes a stricter SPHINXOPTS="-W --keep-going" to fail on warnings.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

.PHONY: help html clean linkcheck export-diagrams

help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

html:
	@$(SPHINXBUILD) -b html "$(SOURCEDIR)" "$(BUILDDIR)/html" $(SPHINXOPTS) $(O)
	@echo "Build finished. Open $(BUILDDIR)/html/index.html"

clean:
	rm -rf "$(BUILDDIR)" _generated

export-diagrams:
	@mkdir -p exports
	@command -v mmdc >/dev/null 2>&1 || { echo "Install: npm i -g @mermaid-js/mermaid-cli" >&2; exit 1; }
	@for f in diagrams/*.mmd; do \
	  mmdc -i "$$f" -o "exports/$$(basename "$${f%.mmd}").svg"; \
	  echo "  exports/$$(basename "$${f%.mmd}").svg"; \
	done

linkcheck:
	@$(SPHINXBUILD) -b linkcheck "$(SOURCEDIR)" "$(BUILDDIR)/linkcheck" $(O)
