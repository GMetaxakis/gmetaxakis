# Fonts

Subsets embedded (base64 WOFF2) into every panel, so the SVGs render the same on any OS.
All three are SIL Open Font License 1.1 (see the `OFL-*.txt` files).

| File | Font | Glyphs |
|---|---|---|
| `Bangers-Regular.subset.woff2` | [Bangers](https://fonts.google.com/specimen/Bangers) | ASCII + a few symbols |
| `ComicNeue-Bold.subset.woff2` | [Comic Neue](https://fonts.google.com/specimen/Comic+Neue) Bold | ASCII + a few symbols |
| `NotoSansJP-Black.subset.woff2` | [Noto Sans JP](https://fonts.google.com/noto/specimen/Noto+Sans+JP) at weight 900 | only the Japanese used by the panels |

## Adding new Japanese text

Glyphs missing from the subset fall back to the viewer's system font. To re-subset:

```sh
pip install fonttools brotli
curl -LO "https://github.com/google/fonts/raw/main/ofl/notosansjp/NotoSansJP%5Bwght%5D.ttf"
fonttools varLib.instancer "NotoSansJP[wght].ttf" wght=900 -o NotoSansJP-Black.ttf
pyftsubset NotoSansJP-Black.ttf --text="$(python3 scripts/gen_profile.py --jp-chars)" \
  --unicodes="U+0020-007E" --no-hinting --flavor=woff2 \
  --output-file=scripts/fonts/NotoSansJP-Black.subset.woff2
```
