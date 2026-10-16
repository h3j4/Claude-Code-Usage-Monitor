"""Reapply this fork's built-in theme changes to upstream theme files.

Run after rebasing onto a new upstream release, on files taken from upstream:

    git checkout upstream/main -- src/themes/classic-usage-widget.json src/themes/compact-fluent-quad.json
    python scripts/fork_theme_patches.py

The script rewrites the theme files in place and refuses to run twice.

1. Value columns widen by 18px while reset countdowns show minutes
   (`display.minutes`), so `100% · 4h 59m` fits.
2. Classic gets a strip for the auto-hidden taskbar: each provider's 5-hour
   gauge and, 6px to its right, its weekly gauge 30% darker, drawn into the
   rows the hidden taskbar leaves on screen (`taskbar.peek_y`/`peek_height`).
"""

import copy
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THEMES = ROOT / "src" / "themes"
MINUTES = " + display.minutes * 18"
SEGMENTS = "ceil(10 / max(1, providers.count)) * 11 - 1"
PROVIDERS = ["claude", "codex", "antigravity", "opencode", "cursor", "grok", "copilot"]


def darker(color, factor=0.7):
    value = color.lstrip("#")
    red, green, blue = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    alpha = value[6:8] or "FF"
    return "#%02X%02X%02X%s" % (
        round(red * factor),
        round(green * factor),
        round(blue * factor),
        alpha,
    )


def widen_for_minutes(main):
    if "display.minutes" in main["width"]:
        raise SystemExit("theme already has the minutes widths")
    width, columns = re.subn(r"(\+ 4 \+ 62)\)", rf"\1{MINUTES})", main["width"])
    if columns != 1:
        raise SystemExit("unexpected surface width: " + main["width"])
    # The optional Fable column reserves its own width.
    main["width"] = re.sub(
        r"(fable\.available \* )(\d+)", rf"\1(\2{MINUTES})", width
    )
    for layer in main["children"]:
        width = str(layer.get("width", ""))
        content = layer.get("content") or {}
        is_value = content.get("type") == "text" and ":usage_line}" in content.get(
            "template", ""
        )
        is_column = layer["id"].endswith("-provider") and (
            re.search(r"\+ 4 \+ \d+$", width) or re.fullmatch(r"\d+", width)
        )
        if (is_value and re.fullmatch(r"\d+", width)) or is_column:
            layer["width"] = width + MINUTES


def peek_layer(source, gauge_id, x, factor):
    layer = copy.deepcopy(source)
    layer["id"] = gauge_id + "-peek"
    layer["name"] = source["name"] + " (hidden taskbar strip)"
    layer["render"] = f"taskbar.hidden * ({source.get('render', '1')})"
    layer["y"] = "taskbar.peek_y"
    layer["height"] = "taskbar.peek_height"
    layer.pop("corner_radius", None)
    layer.pop("x", None)
    if x:
        layer["x"] = x
    layer["content"].pop("corner_radius", None)
    if factor != 1:
        layer["content"]["fill"]["color"] = darker(layer["content"]["fill"]["color"])
    return layer


def add_hidden_taskbar_strip(main):
    layers = main["children"]
    if any(layer["id"].endswith("-peek") for layer in layers):
        raise SystemExit("theme already has the hidden-taskbar strip")
    by_id = {layer["id"]: layer for layer in layers}
    strip = []
    for provider in PROVIDERS:
        for row in ("session", "weekly", "pool"):
            for mode in ("dark", "light"):
                gauge_id = f"{provider}-{row}-segments-{mode}"
                if gauge_id in by_id:
                    session = row == "session"
                    strip.append(
                        peek_layer(
                            by_id[gauge_id],
                            gauge_id,
                            None if session else f"{SEGMENTS} + 6",
                            1 if session else 0.7,
                        )
                    )
    # Fable only has a weekly gauge, so it fills its own column.
    for mode in ("dark", "light"):
        gauge_id = f"fable-weekly-segments-{mode}"
        if gauge_id in by_id:
            strip.append(peek_layer(by_id[gauge_id], gauge_id, None, 0.7))
    layers.extend(strip)
    return len(strip)


def rewrite(name, patch):
    path = THEMES / name
    raw = path.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")
    theme = json.loads(text)
    result = patch(theme["surfaces"][0])
    output = json.dumps(theme, indent=2, ensure_ascii=False)
    if text.endswith("\n"):
        output += "\n"
    path.write_bytes(output.replace("\n", newline).encode("utf-8"))
    print(f"{name}: {result}")


def classic(main):
    widen_for_minutes(main)
    return f"{add_hidden_taskbar_strip(main)} strip layers"


def compact(main):
    widen_for_minutes(main)
    return "minutes widths"


if __name__ == "__main__":
    rewrite("classic-usage-widget.json", classic)
    rewrite("compact-fluent-quad.json", compact)
