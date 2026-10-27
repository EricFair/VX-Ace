# Day/night and time pattern

**Goal:** a time-of-day cycle that tints the screen and gates content, without a heavy always-on parallel process.

## Native-first design

Prefer **event-driven** time over continuous polling. Choose the clock model first:

| Model | Advance trigger | Good for |
|---|---|---|
| Step-based | Steps (Control Variables, Game Data > Steps) | Exploration games |
| Action-based | Events you author (rest, travel, dungeon floor) | Story-driven games, cheapest |
| Real-time-ish | Play Time (Game Data > Play Time, seconds) or a parallel counter | Visible ticking clocks |

Play Time keeps running during menus and message windows, which may or may not be wanted; step/action models avoid that.

## State ownership

| State | Owner | Notes |
|---|---|---|
| Time of day | Variable `VAR[time_phase]` (0 dawn, 1 day, 2 dusk, 3 night) | One common event writes it |
| Day counter | Variable `VAR[day_count]` | Increment only when the phase wraps |
| Tick accumulator | Variable `VAR[time_ticks]` | Only for step/timer models |
| Indoors flag | Switch `SW[map_is_indoors]` | Set by each map's entry logic |
| Derived phase flags | Switches `SW[is_night]` etc. | Written only by the tint common event |
| Current screen tone | Engine screen object | Presentation; re-derive from `VAR[time_phase]`, never the source of truth |

## Step-by-step event layout

1. `CE[time_advance]` (not parallel): add to `VAR[time_ticks]`; when past a threshold, subtract it and add 1 to `VAR[time_phase]`; wrap 4 to 0 and add 1 to `VAR[day_count]`; then Call Common Event `CE[time_apply_tint]`.
2. `CE[time_apply_tint]`: Conditional Branches on `VAR[time_phase]`; each sets the derived switches and uses Tint Screen with fixed values and a fade time (e.g. 60 frames; 0 on map entry). If `SW[map_is_indoors]` is ON, tint to normal instead.
3. **Step/action model:** no parallel event needed. Call `CE[time_advance]` from places that already run: exits, transfers, rest events, battle end.
4. **Parallel model (only if real time is required):** one Parallel common event gated by `SW[time_tick_on]`: Wait 60; add 1 to `VAR[time_ticks]`; one Conditional Branch for the threshold. Short body, always with a Wait.
5. **Map-transfer refresh:** every map's entry logic (an autorun that ends by turning itself off, or the transfer source) calls `CE[time_apply_tint]` with fade 0. Treat the tone as not guaranteed to survive transfers or loads; re-apply it.
6. **Gating content:** page conditions cannot test variable ranges, so use the derived switches (`SW[is_night]`).

## Pitfalls

- A parallel process without a Wait (see `event-performance.md`).
- Tinting indoors or during a cutscene because the tint event ignores `SW[map_is_indoors]` or a cutscene flag.
- Two events both advancing the clock (double increments).
- Treating the screen tone as the state; after load it may not match `VAR[time_phase]`.
- Derived switches drifting when `VAR[time_phase]` is set directly by debug or cutscene events.
- Time passing during cutscenes unless the tick source is disabled by a flag.

## Test checklist

- Each phase's tint, entering the map directly in that phase (fade 0).
- Indoor/outdoor transitions in every phase.
- Phase wrap and day counter increment.
- Battle in each phase; tone afterwards.
- Save at night, load: the next map entry restores the night tint.
- **Old save** with no clock: variables read 0; confirm 0 is a sane default phase and the first map entry applies it.
- Frame rate with the parallel version on a busy map.

## When RGSS3 is justified

- Smooth continuous tint interpolation, weather blending, or a clock HUD. Keep the time value in a game variable (read-only from script) so events still branch on it; see `templates/rgss3/hud_window.rb` for a change-only display.
