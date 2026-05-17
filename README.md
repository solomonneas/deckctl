# streamdeck-as-code

Cross-platform declarative Stream Deck driver. YAML config compiles to a live daemon (later phases); this Phase 1 build supports schema validation and offline icon preview.

See [docs/superpowers/specs/2026-05-17-streamdeck-as-code-design.md](docs/superpowers/specs/2026-05-17-streamdeck-as-code-design.md) for the full design.

## Status

Phase 1 (current): config schema + preview. No USB device required.

## Quick start (Phase 1)

```bash
pipx install streamdeck-as-code
sdac --version
sdac validate path/to/config.yaml
sdac preview path/to/config.yaml --out preview.png
```
