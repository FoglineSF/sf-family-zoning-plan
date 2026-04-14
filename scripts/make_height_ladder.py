#!/usr/bin/env python3
"""
Draw the SF building-height ladder as a single wide image:
small bungalow -> 3-story rowhouse -> RH-1 max -> FZP bonus heights ->
downtown spike, with a human figure at the base of each for scale.

Designed to be usable inline in a Fogline article AND as a YouTube B-roll
still. Tall skinny aspect works better for mobile/article; wide for YT.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

OUT = Path(__file__).resolve().parent.parent / "maps" / "03_height_ladder.png"
OUT.parent.mkdir(exist_ok=True)

# (height_ft, label_short, stories_text, style_family, color, annotation_text,
#  annotation_offset_ft, city_tag)
# style_family: "sf" = earth-tone, "paris" = blue, "miami" = teal
BUILDINGS = [
    (33,  "33 ft",   "~3 stories",  "sf",    "#b7a189", "Typical Richmond\nEdwardian",                    18, "SF"),
    (40,  "40 ft",   "~4 stories",  "sf",    "#9c886f", "RH-1/RH-2 max\n(Richmond & Sunset\nzoning limit)", 22, "SF"),
    (65,  "65 ft",   "~6 stories",  "sf",    "#eb9449", "Ocean Beach\nSafeway: FZP base",                 22, "SF"),
    (85,  "85 ft",   "~8 stories",  "sf",    "#e67727", "Ocean Beach Safeway:\nas built (+density bonus)", 22, "SF"),
    (121, "121 ft",  "~12 stories", "paris", "#4a6fa0", "Paris city center\nheight limit (37m)",           22, "Paris"),
    (140, "140 ft",  "~14 stories", "sf",    "#c7451c", "Geary + Arguello\n(FZP max)",                    22, "SF"),
    (250, "250 ft",  "~25 stories", "sf",    "#9e1f0c", "Geary + Masonic\n(tallest SF FZP block)\n↓ currently a parking lot", 22, "SF"),
    (641, "641 ft",  "~60 stories", "miami", "#1d5570", "Porsche Design Tower\nSunny Isles, Miami",       22, "Miami"),
    (673, "673 ft",  "~51 stories", "miami", "#1d5570", "Estates at Acqualina\nSunny Isles, Miami",       22, "Miami"),
    (749, "749 ft",  "~62 stories", "miami", "#1d5570", "Bentley Residences\nSunny Isles, Miami",         22, "Miami"),
]

# style
FIG_W = 22
FIG_H = 18
MARGIN = 0.5  # feet of padding in the y axis

# Pill colors per city (for annotation bubbles)
CITY_PILL = {
    "SF":    dict(fc="#fff3e6", ec="#d68a5a", text="#5a1500"),
    "Paris": dict(fc="#e8eef7", ec="#4a6fa0", text="#1c3c78"),
    "Miami": dict(fc="#e3f0f2", ec="#1d5570", text="#0c3847"),
}


def draw_building(ax, x_center, width, height_ft, style_family, color, label, stories_text, annotation, ann_offset, city):
    """Draw a rectangular building with floor lines. Paris buildings get a mansard hint."""
    left = x_center - width / 2
    body_top = height_ft

    # Paris buildings: leave a little room for a mansard roof cap
    if style_family == "paris":
        mansard_h = min(5.0, height_ft * 0.08)
        body_top = height_ft - mansard_h
    else:
        mansard_h = 0

    # main body
    rect = mpatches.Rectangle((left, 0), width, body_top, facecolor=color, edgecolor="#111", linewidth=0.8)
    ax.add_patch(rect)

    # mansard roof for Paris (darker trapezoid)
    if style_family == "paris" and mansard_h > 0:
        inset = width * 0.15
        dark = "#2f4a73"
        mansard = mpatches.Polygon(
            [
                (left, body_top),
                (left + width, body_top),
                (left + width - inset, body_top + mansard_h),
                (left + inset, body_top + mansard_h),
            ],
            closed=True, facecolor=dark, edgecolor="#111", linewidth=0.8,
        )
        ax.add_patch(mansard)

    # horizontal floor lines every ~11 ft
    story = 11.0
    n_floors = int(body_top / story)
    for i in range(1, n_floors):
        y = i * story
        ax.plot([left + 0.25, left + width - 0.25], [y, y], color="#111", linewidth=0.3, alpha=0.5)

    # window grid hint
    for i in range(n_floors):
        y = i * story + story * 0.55
        for wx_frac in (0.28, 0.5, 0.72):
            ax.plot(left + wx_frac * width, y, marker="s", markersize=1.6, color="#111", alpha=0.55)

    # roof tick
    ax.plot([left, left + width], [height_ft, height_ft], color="#111", linewidth=1.3)

    # label block below the ground line
    ax.text(x_center, -14, label, ha="center", va="top",
            fontsize=12, fontweight="bold", color="#111")
    ax.text(x_center, -28, stories_text, ha="center", va="top",
            fontsize=9, color="#555")
    # city tag
    city_color = {"SF": "#5a1500", "Paris": "#1c3c78", "Miami": "#0c3847"}.get(city, "#444")
    ax.text(x_center, -42, city, ha="center", va="top",
            fontsize=9, fontweight="bold", color=city_color)

    # annotation above building, pill color keyed to city
    if annotation:
        pill = CITY_PILL.get(city, CITY_PILL["SF"])
        ax.annotate(
            annotation,
            xy=(x_center, height_ft + 1),
            xytext=(x_center, height_ft + ann_offset),
            ha="center",
            va="bottom",
            fontsize=9,
            color=pill["text"],
            fontweight="bold",
            arrowprops=dict(arrowstyle="-", color=pill["ec"], lw=0.7, alpha=0.7),
            bbox=dict(boxstyle="round,pad=0.3", fc=pill["fc"], ec=pill["ec"], lw=0.6, alpha=0.96),
        )


def draw_person(ax, x_center, scale_ft=6.0):
    """Stick figure at human scale (6 ft)."""
    head_r = 0.55
    body_top = scale_ft - 2 * head_r
    # head
    ax.add_patch(mpatches.Circle((x_center, scale_ft - head_r), head_r,
                                  facecolor="#222", edgecolor="none"))
    # body
    ax.plot([x_center, x_center], [0, body_top], color="#222", linewidth=1.5)
    # arms
    ax.plot([x_center - 1.2, x_center + 1.2], [body_top - 1, body_top - 1],
            color="#222", linewidth=1.3)
    # legs
    ax.plot([x_center, x_center - 0.8], [0, 1.8], color="#222", linewidth=1.3)
    ax.plot([x_center, x_center + 0.8], [0, 1.8], color="#222", linewidth=1.3)


def render(buildings: list, out_path: Path, title: str, subtitle: str,
           y_top_override: float | None = None, show_miami_callout: bool = True,
           fig_w: float = FIG_W, fig_h: float = FIG_H) -> None:
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    spacing = 70
    width = 26
    x_positions = [i * spacing + spacing for i in range(len(buildings))]
    max_h = max(b[0] for b in buildings)

    # ground line
    ax.axhline(0, color="#444", linewidth=1.4, zorder=1)
    ax.axhspan(-6, 0, facecolor="#dcd3c2", edgecolor="none", zorder=0)

    for (h, lbl, st, style, color, ann, ann_off, city), x in zip(buildings, x_positions):
        draw_building(ax, x, width, h, style, color, lbl, st, ann, ann_off, city)
        draw_person(ax, x - width / 2 - 5, scale_ft=6.0)

    # Reference lines removed — explained in article text instead

    # Miami side-callout removed — explained in article text instead

    # Geary + Masonic callout removed — explained in article text instead

    # title
    y_top = y_top_override if y_top_override is not None else max_h + 130
    title_y = y_top - 35
    title_x = (x_positions[0] + x_positions[-1]) / 2
    ax.text(title_x, title_y,
            title, fontsize=26, fontweight="bold", color="#111", ha="center")
    ax.text(title_x, title_y - 22,
            subtitle, fontsize=13, color="#555", ha="center")
    ax.text(title_x, title_y - 42,
            "~6 ft human figure at the base of each building for scale",
            fontsize=10, color="#777", ha="center", style="italic")

    # footer
    ax.text(x_positions[0] - 35, -80,
            "Data: SF Planning Department · Paris PLU Bioclimatique (2023) · Sunny Isles Beach tallest buildings   ·   Fogline · foglinesf.com",
            fontsize=9, color="#777")

    # axes cleanup
    ax.set_xlim(x_positions[0] - 45, x_positions[-1] + 50)
    ax.set_ylim(-95, y_top)
    ax.set_aspect("equal")
    ax.set_axis_off()

    plt.tight_layout()
    plt.savefig(out_path, dpi=180, bbox_inches="tight", facecolor="white")
    print(f"wrote {out_path}")
    plt.close(fig)


def main() -> None:
    out_dir = Path(__file__).resolve().parent.parent / "maps"

    # Full version — all buildings including the Miami tower
    render(
        buildings=BUILDINGS,
        out_path=out_dir / "03_height_ladder_full.png",
        title="How tall is \"too tall\" in San Francisco?",
        subtitle="Building heights in the Family Zoning Plan debate  ·  with Paris & Miami for reference",
        show_miami_callout=True,
    )

    # Zoomed version — drops the Miami tower so Paris/SF comparison reads clearly
    zoomed = [b for b in BUILDINGS if b[0] <= 260]
    render(
        buildings=zoomed,
        out_path=out_dir / "03_height_ladder_zoomed.png",
        title="San Francisco's Family Zoning Plan  vs.  Paris height limits",
        subtitle="Everything the FZP allows fits inside what Paris already builds  ·  human figure at base for scale",
        y_top_override=380,
        show_miami_callout=False,
        fig_w=22,
        fig_h=14,
    )


if __name__ == "__main__":
    main()
