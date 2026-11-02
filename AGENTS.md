# Munich Radar illustrated map

The first delivered 75-section painted atlas is the binding visual baseline.
Read `atlas/README.md` and use `python -m src.map_pipeline` for map work.

- Preserve the event app, event datasets and immutable `atlas/baseline/`.
- Preserve the original rich olive/green, terracotta, cream and turquoise palette,
  miniature detail and north-up ground layout. Do not introduce a new style sheet.
- Generate or edit painting pixels using built-in image_gen. The CLI prepares
  prompts, records references and imports outputs; it does not call an external
  generation API or require a key.
- Prefer editing the existing local tile with its original geographic guide and
  direct neighbors. Never use a distant composed neighborhood as a style stamp.
- Keep stable section IDs, native size, geographic registration and overlap.
- New images are candidates until palette, detail, composition and neighboring
  transitions are visually reviewed. Pixel checks do not establish visual quality.
- Activate reviewed candidates explicitly; retain the baseline and successful
  versions so an individual section or whole release can be rolled back.
- Build releases separately and switch the live manifest only after validation.
- Record actual commands, prompts, image hashes, review decisions and checks.
  Do not claim deterministic image generation; deterministic assembly is separate.
