# grantandassociates.com website

The static website for Grant and Associates. **Not published yet**: this is the private preview build.

- `src/pages/` one Markdown file per page (`__` in a filename stands for `/` in the address)
- `src/insights/` Judy's articles and free guides (imported from the playbook archive by `tools/import_insights.py`, then lightly edited)
- `src/data/` navigation, testimonial quotes, redirects from every old address, site settings (Formspree form ID, phone)
- `src/assets/` stylesheet, logo (SVG redraw of the original GIF), favicon, article images
- `build.py` builds everything into `docs/` (`python3 build.py`; add `--production` when publishing)

Content decisions and the archive of the old site live in the private playbook repo, cellwood/grantandassociates-website-playbook.
