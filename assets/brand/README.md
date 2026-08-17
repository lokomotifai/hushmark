# Hushmark brand assets

`hushmark-logo.svg` is the project mark: three lines of text on a dark tile, the middle line
replaced by a masked span between bracket ticks. It is the product in one glyph—something is still
there, it is still positioned in the sentence, and its value is not readable.

## Palette

| Token          | Value                 | Use                                              |
| -------------- | --------------------- | ------------------------------------------------ |
| Ink            | `#111111`             | Tile, headings, primary marks                    |
| Ground         | `#FBFAF8`             | Page and diagram canvas                          |
| Signal         | `#D11F26`             | One meaningful accent per view, never decoration |
| Signal, strong | `#B3171D`             | Accent text on a tinted ground                   |
| Meta           | `#7C7A76`             | Labels, axis text, secondary lines               |
| Hairline       | `#E7E5DF` / `#D6D3CC` | Borders and dividers                             |

Typeface is Inter with a system sans fallback, and a system monospace stack for identifiers,
placeholders, and entity type names. Headings are sentence case with negative tracking; uppercase
appears only in wide-tracked meta labels.

## Diagrams

The README diagrams in [`../readme/`](../readme/) follow the same system and ship in English and
Turkish variants (`name.svg` and `name.tr.svg`). They are plain SVG with `<title>` and `<desc>` for
accessibility, no external font or image references, and an explicit background so they stay legible
when a viewer renders them on a dark surface.

Update a diagram by editing the SVG or regenerating it, then keep both language variants in sync.
If the underlying numbers change—benchmark results, taxonomy counts—update the diagram, the README
table, and `README.tr.md` in the same change.

## Using the mark

The Apache-2.0 licence covers the source code. It does not grant rights to the Hushmark name or
logo. Truthful, nominative use is fine; use that implies endorsement, certification, or official
status is not. See [TRADEMARKS.md](../../TRADEMARKS.md).

Do not recolor the mark, stretch it, place it on a busy background, or combine it with another logo
in a way that suggests a partnership that does not exist. If a fork or modified distribution needs
branding, use your own.
