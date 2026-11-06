# Stardust Harbor

**English** | [中文](README.zh-CN.md)

A 2D sci-fi relaxation game that runs in one file. **No dependencies, no install, no network** — just open `index.html`.

> Glide · thread rings · gather stardust · shoot down intruders — no failure, only sectors waking to light.

![Title screen](preview/04-title-en.jpg)

---

## How to play

| Input | Action |
|---|---|
| Hold left mouse button | Thrust toward the cursor |
| Release | Coast on inertia (gentle damping, no hard stop) |
| `W A S D` / arrow keys | Keyboard thrust |
| `1` `2` `3` | Switch theme — which also switches your weapon and your foes |
| `L` | Switch language (中文 / English) |
| `M` | Mute / unmute |
| `P` / `Esc` | Pause / resume |
| `R` | Back to title (restart) |
| `Space` | Start from the title screen |

**Your weapon fires automatically** — you only have to fly beautifully. Where you go, what you gather, who you shoot is left to feel and a little luck.

### Goals
- **Gather stardust** — +10 points each, plus an ascending note (pentatonic, so chains turn into tunes).
- **Thread the rings** — fly into the hoop, +50 points.
- **Shoot down intruders** — 30 / 60 / 80 points depending on the foe; kills can drop extra stardust.
- Fill the bar to **46** to light a sector: +500 points, then the next sector begins. Endless loop, **no failure state and no health bar**.

---

## Three themes = three weapons + three foes

Switching theme swaps your weapon, your enemies, and the colour of the whole sector.

| Theme | Weapon | Feel | Foe |
|---|---|---|---|
| **AURORA CYAN** | **ION BURST** | Rapid bolts; the faster you fly, the faster it fires | Drifter — hex hull, tanky |
| **CRIMSON PULSE** | **PHASE RAM** | No gun at all: builds speed, grows a blade, and shatters foes by flying through them. Few foes on purpose — every hit should feel earned | Prism — splits into two smaller shards |
| **AMBER EMBER** | **BROOD CARRIER** | Never fires itself: a big, heavy hull (drawn 1.8× and slow) with escort gunships you can watch orbiting it | Swarm — fast and numerous |

![Aurora Cyan](preview/02-play-cyan.jpg)
![Crimson Pulse](preview/05-play-pink.jpg)

### Ramming with CRIMSON PULSE

Hold the cursor far ahead and commit to a line. Your probe is the fastest of the three themes
(top speed 889 vs 780) and the slipperiest, so a straight run keeps building momentum. Once you pass
**300 px/s** the blade arms — the HUD reads `RAM READY` and a glowing wedge grows out of the nose.
Touching a foe then destroys it instantly: **screen shake, impact ring, sparks, `RAM +n`**, and
+70 px/s of momentum out of the hit, so each kill feeds the next one. Bumping a foe below the
threshold does nothing but shove it — fly faster.

### Higher score → stronger weapon

Crossing a score threshold upgrades the weapon automatically. The HUD shows five level pips, and a "LV.n + weapon name" banner flashes on each upgrade.

| Level | Score needed | Effect |
|---|---|---|
| LV.1 | 0 | Base form |
| LV.2 | 800 | Faster fire rate |
| LV.3 | 2,200 | ION BURST twin shot; one more escort gunship |
| LV.4 | 4,200 | More bullets, more escorts |
| LV.5 | 7,000 | ION BURST triple shot; the carrier runs a full wing of six |

Enemies cannot hurt you — there is no health and no game over. They approach, drift, and get shot down.

---

## Design notes

**Feel first (it is a relaxation game)**
- No health, no timer, no death; the only "penalty" is drifting while you coast.
- Inertia tuning: 980 px/s² acceleration and exponential damping, like gliding on ice. Each theme has its own cap, grip and hull size — cyan 780 px/s @1.35 (1.18× hull), crimson 889 @1.12 (1.08×), amber 655 @1.52 (1.82×, an actual carrier: bigger, slower, so the escorts read clearly).
- Foe density is per theme too: crimson deliberately runs sparse (2 / 3 / 4 … by sector instead of 5 / 6 / 7 …).
- Generous pickup radii (stardust +30px, ring inner 86%) so a casual pass still rewards you.
- Auto-fire with predictive aim: enemies pop even if you never aim.

**Art — everything generated at runtime, zero assets**
- The probe is layered: gradient hull, inset armour plates, glowing core, engine flame, wingtip lights, ribbon trail.
- Each theme brings its own foe silhouette (hex / diamond / triangle) in a hue that contrasts with the palette, so friend and foe never blur together.
- Background: a baked base image, half-resolution nebula compositing upscaled 4×, three parallax star layers, and speed lines.
- Feedback: particle bursts, shockwaves, floating score numbers, screen bloom, sector-lit banner.

**Audio — synthesised live with Web Audio, no files**
- Bed: 55Hz fundamental plus five partials through a low-pass, breathing at 0.045Hz.
- Pickups: pentatonic ascending notes with three partials into a generated convolution reverb.
- Shots, explosions, the beam, and level-ups each get their own restrained voice.

**Performance**
- Base image and vignette are pre-baked; they only redraw on resize or palette change.
- Nebulae composite into a quarter-resolution canvas and get upscaled once, cutting fill-rate dramatically.
- Measured (Chrome headless, software rasteriser, 1440×900): 59.3 fps / p50 16.7 ms, against a 60 fps empty-canvas baseline in the same environment.
- Entities recycle by view radius and respawn just off-screen with a fade-in, keeping density stable.

---

## Files

```
index.html            # everything: HTML + CSS + JS (~2k lines), no external dependencies
py/combat_model.py    # readable Python copy of the combat maths (not used at runtime)
README.md             # this file
README.zh-CN.md       # Chinese version
preview/              # screenshots
```

## Python mechanics model

`py/combat_model.py` restates the tuning — speeds, damping, level thresholds, fire intervals,
ram reach and bonuses, escort counts — as small pure functions plus a printed report.
Run it to read or experiment with the numbers:

```bash
python3 py/combat_model.py
```

It is a reference document, not part of the build: editing it does **not** change the game.


## Dev parameters (optional)

| Param | Effect |
|---|---|
| `?autostart` | Skip the title screen |
| `?palette=2` | Start with theme 2 (1 / 2 / 3) |
| `?lang=en` | Start in English (`zh` for Chinese) |

The page also exposes `window.__stardust` (state, player, input, audio, enemies, bullets, drones, `startGame()`, `setLang()`, …) for automated testing only.

## Browser support

Desktop browsers (current Chrome / Edge / Safari / Firefox). Uses Canvas 2D, Web Audio and Pointer Events; no build step.
