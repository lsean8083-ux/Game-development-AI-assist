# Stardust Harbor · 星尘港湾

**English** | [中文](README.zh-CN.md)

A calm 2D side-scrolling space game about gliding, threading rings and gathering stardust.
**No dependencies, no install, no network** — just double-click `index.html`.

> Glide · thread the rings · gather stardust — no failure, only sectors slowly waking to light.

![Title screen](preview/04-title-en.jpg)

---

## How to play

| Input | Action |
|---|---|
| Hold left mouse and move | Thrust toward the cursor |
| Release the mouse | Coast with gentle damping (no hard stop) |
| `W A S D` / arrow keys | Keyboard thrust |
| `1` `2` `3` | Switch palette (Aurora Cyan / Crimson Pulse / Amber Ember) |
| `L` | Switch language (English / 中文) |
| `M` | Mute / unmute |
| `P` / `Esc` | Pause / resume |
| `R` | Back to title (restart) |
| `Space` | Start from the title screen |

### Goal

- **Gather stardust** — each mote adds +1 light and plays an ascending note (pentatonic, so collecting runs naturally fall into a melody).
- **Thread the rings** — fly inside the halo; each ring adds +3.5 light with a shockwave and bloom.
- Fill the bar to **46** and the sector lights up: the counter advances and the sky keeps getting brighter. Endless, with **no losing condition**.

---

## Design notes

**Feel first**
- No health, no timer, no death. The only "penalty" is that you keep drifting after you let go.
- Inertial handling: 980 px/s² thrust, 1.35/s damping, 780 px/s cap — like sliding on ice.
- Generous hitboxes (motes +30 px, rings at 86% of the inner radius) so casual passes still feel rewarded.

**Art — 100% procedural, no image assets**
- Probe: layered gradient hull, inset armour plates, glowing core, engine flame, wingtip lights and a ribbon trail; three palettes switch live.
- Background: pre-baked base layer + half-resolution nebula composited once at 4× upscale + three parallax star layers + speed lines.
- Feedback: particle bursts, ring shockwaves, full-screen bloom, sector-lit toast.

**Audio — synthesized at runtime with Web Audio, no audio files**
- Ambient bed: 55 Hz fundamental plus five overtones through a low-pass, breathing at 0.045 Hz.
- Collect: ascending pentatonic notes, three overtones, procedural convolution reverb.
- Ring pass: sustained major triad. Sector cleared: ascending arpeggio.

**Performance**
- Background and vignette are pre-baked and only redrawn when the window size or palette changes.
- Nebulas are composited on a 1/4-resolution canvas and upscaled once, which removes most of the fill cost.
- Measured in headless Chrome on pure software rasterization at 1440×900: **59.3 fps / p50 16.7 ms** (empty-canvas baseline in the same environment: 60 fps).
- Entities recycle at the view radius and respawn on an off-screen band with a fade-in, keeping density stable.

---

## Files

```
index.html            # everything: HTML + CSS + JS (~1.6k lines), no external deps
README.md             # this file (English)
README.zh-CN.md       # Chinese version
preview/              # screenshots
```

## Debug URL parameters

| Parameter | Effect |
|---|---|
| `?autostart` | Skip the title screen |
| `?palette=2` | Start with the second palette |
| `?lang=en` | Start in English (`zh` for Chinese) |

The page also exposes `window.__stardust` (state, player, input, audio, entity arrays, `startGame()`, `setLang()`, …) for automated testing only; it does not affect normal play.

## Browser support

Desktop browsers (current Chrome / Edge / Safari / Firefox). Uses Canvas 2D, Web Audio and Pointer Events; no build step.
