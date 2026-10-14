# Scene and Window Lifecycle

Use this reference for menu systems, custom screens, HUDs, modal flows, and UI debugging.

## Scene control

`SceneManager` owns:

- the current scene;
- a stack used for call/return navigation;
- direct transitions;
- application exit;
- background snapshots used by menu-like scenes.

### `goto` versus `call`

Conceptually:

- **goto** — replace the current flow with another scene;
- **call** — push the current scene and open another scene that can return;
- **return** — pop back to the caller.

Use stack semantics for submenus and modal screens that should return to their origin.

## Base scene lifecycle

The default `Scene_Base` lifecycle is approximately:

```text
start
post_start
update loop until scene changes
pre_terminate
terminate
```

The base update path also updates Graphics, Input, and window instances.

This creates several important extension rules:

- allocate windows/sprites in `start` or a method called from it;
- do per-frame control logic in `update` or narrower update methods;
- release resources in `terminate` if they are not automatically disposed;
- avoid allocating new bitmaps/windows every frame;
- do not keep stale references to disposed windows after a scene transition.

## Window hierarchy and responsibilities

### `Window_Base`

Provides common window setup and drawing utilities: contents bitmap creation, padding, line height, tone, open/close behavior, text colors, gauges, icons, actor info, and related helpers.

Use it for informational windows that do not need cursor selection.

### `Window_Selectable`

Adds cursor/index selection, scrolling, handlers, help-window integration, and input-driven selection behavior.

Use it when the player moves a cursor among items/rows.

### `Window_Command`

Builds on selectable behavior with a command list made from symbols, names, enabled states, and optional ext data.

Use it for command menus rather than reimplementing cursor/input logic from scratch.

## Scene owns orchestration; window owns presentation/input surface

A common architecture mistake is placing business flow inside a window class.

Prefer:

```text
Scene
  creates windows
  registers handlers
  decides what happens next

Window
  displays state
  collects selection/input
  calls registered handlers
```

This keeps UI reusable and reduces script collisions.

## Resource lifetime

Native graphics resources need deliberate disposal.

Watch for:

- `Bitmap` created manually;
- `Sprite` / `Viewport` created outside standard scene/spriteset ownership;
- cached versus non-cached graphics;
- windows whose `contents` bitmap is recreated after resize.

Symptoms of bad lifetime management include memory growth, disposed bitmap errors, invisible sprites after returning to a scene, and crashes in long sessions.

## UI modification routing

| Request | Likely owner |
|---|---|
| Add text to an existing menu | relevant window |
| Add a new selectable menu command | command window + scene handler |
| Add a full new screen | new `Scene_*` + windows |
| Change battle command sequence | battle command windows + `Scene_Battle`/`BattleManager` |
| Draw actor stat differently everywhere | shared draw helper or targeted windows |
| Add a map HUD | map scene/spriteset/HUD window, depending design |

## Compatibility hotspots

Many UI frameworks replace or heavily modify:

- `Scene_MenuBase`;
- `Scene_Menu`;
- `Scene_Battle`;
- `Window_Base` drawing helpers;
- `Window_Selectable` input/handler behavior;
- command list construction.

Before injecting a menu or battle command, inspect all scripts reopening the relevant classes.

## UI test plan

For a custom screen/window test:

1. open from every supported caller;
2. cancel/return repeatedly;
3. test disabled commands;
4. test empty lists;
5. test long lists/scrolling;
6. test party sizes 1 and max supported;
7. change resolution/window size only if the project runtime supports it;
8. save/load if the UI reflects persistent custom state;
9. open/close repeatedly to catch disposal/leak problems.
