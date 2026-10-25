# grantandassociates.com website

The static website for Grant and Associates. **Not published yet**: this is the private preview build.

- `src/pages/` one Markdown file per page (`__` in a filename stands for `/` in the address)
- `src/insights/` Judy's articles and free guides (imported from the playbook archive by `tools/import_insights.py`, then lightly edited)
- `src/data/` navigation, testimonial quotes, redirects from every old address, site settings (Formspree form ID, phone)
- `src/assets/` stylesheet, logo (SVG redraw of the original GIF), favicon, article images
- `build.py` builds everything into `docs/` (`python3 build.py`; add `--production` when publishing)

Content decisions and the archive of the old site live in the private playbook repo, cellwood/grantandassociates-website-playbook.

## Photo sources

Free-licence photos from Unsplash (no attribution required) unless noted.

| File (src/assets/img/…) | Source |
|---|---|
| insights/all-star.jpg | unsplash.com/photos/AZTpFmYBzzs (Gustavo Xavier) |
| insights/singing-bowl.jpg | unsplash.com/photos/VsI_74zRzAo |
| insights/celebrate.jpg | Pexels 761993 (owner's stock folder) |
| insights/people-conversing.jpg | owner's stock (Storyteller.jpg) |
| pages/presenter.jpg | iStock 507066626, licensed by the owner |
| pages/judy-on-camera.jpg | owner's video still |
| insights/breathe.jpg | unsplash.com/photos/buymYm3RQ3U |
| insights/microphone-crowd.jpg | unsplash.com/photos/LETdkk7wHQk |
| insights/library-overhead.jpg | unsplash.com/photos/1mwPOXb_pB8 |
| insights/presenter-confident.jpg | unsplash.com/photos/Ra23FmCoeiQ |
| insights/meeting-paper.jpg | unsplash.com/photos/O2o1hzDA7iE |
| insights/speed-blur.jpg | unsplash.com/photos/ZbFoi92fyzY |
| insights/video-shoot.jpg | unsplash.com/photos/KieCLNzKoBo |
| insights/mic-stage.jpg | unsplash.com/photos/QrqeusbpFMM |
| insights/football-catch.jpg | unsplash.com/photos/eH1yBJqxNgA |
| insights/mother-daughter.jpg | unsplash.com/photos/zzl7_zgdTm4 |
| insights/library.jpg | unsplash.com/photos/2JIvboGLeho |
| insights/vintage-mic.jpg | unsplash.com/photos/Y20JJ_ddy9M |
| insights/camera-crew.jpg | unsplash.com/photos/fBwNDRgig_w |
