"""Net-worth chart renderers for the menu spike.

Discord-dark-theme matplotlib PNGs. Palette validated (dataviz six checks,
dark surface #313338): Radiant #3BA55D / Dire #ED4245, neutral inks.
Pure functions: data in, PNG bytes out.
"""

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SURFACE = "#313338"  # Discord dark message surface
INK = "#DBDEE1"  # primary text
MUTED = "#949BA4"  # secondary text / axes
GRID = "#3F4147"
RADIANT = "#3BA55D"
DIRE = "#ED4245"


def _style(ax, fig):
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.grid(True, color=GRID, linewidth=0.8, alpha=0.6)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color(MUTED)


def _fmt_gold(v, _pos=None):
    a = abs(v)
    return f"{'-' if v < 0 else ''}{a / 1000:.0f}k" if a >= 1000 else f"{v:.0f}"


def networth_lead_png(leads: list[int], title: str = "Net Worth Lead") -> bytes:
    """Diverging-around-zero lead chart: green above (Radiant), red below (Dire)."""
    mins = list(range(len(leads)))
    fig, ax = plt.subplots(figsize=(7.2, 3.4), dpi=144)
    _style(ax, fig)

    ax.axhline(0, color=MUTED, linewidth=1)
    ax.fill_between(mins, leads, 0, where=[v >= 0 for v in leads],
                    color=RADIANT, alpha=0.35, interpolate=True)
    ax.fill_between(mins, leads, 0, where=[v <= 0 for v in leads],
                    color=DIRE, alpha=0.35, interpolate=True)
    ax.plot(mins, leads, color=INK, linewidth=2)

    # Direct labels on the extremes only (selective, not every point)
    hi_i = max(mins, key=lambda i: leads[i])
    lo_i = min(mins, key=lambda i: leads[i])
    for i, va in ((hi_i, "bottom"), (lo_i, "top")):
        if abs(leads[i]) > 500:
            ax.annotate(_fmt_gold(leads[i]), (i, leads[i]),
                        textcoords="offset points", xytext=(0, 6 if va == "bottom" else -6),
                        ha="center", va=va, color=INK, fontsize=9, fontweight="bold")

    ax.set_title(title, color=INK, fontsize=11, loc="left", pad=10)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(_fmt_gold))
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    ax.set_xlabel("minute", color=MUTED, fontsize=9)
    ax.margins(x=0.01)
    # Legend-as-caption: two poles, labeled once
    ax.text(1.0, 1.02, "▲ Radiant   ▼ Dire", transform=ax.transAxes,
            ha="right", color=MUTED, fontsize=9)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight",
                facecolor=SURFACE, edgecolor="none")
    plt.close(fig)
    return buf.getvalue()


def sparkline_png(leads: list[int]) -> bytes:
    """Tiny 400x100 lead sparkline for list-row thumbnails."""
    mins = list(range(len(leads)))
    fig, ax = plt.subplots(figsize=(2.8, 0.7), dpi=144)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    ax.axis("off")
    ax.axhline(0, color=GRID, linewidth=0.8)
    ax.fill_between(mins, leads, 0, where=[v >= 0 for v in leads],
                    color=RADIANT, alpha=0.5, interpolate=True)
    ax.fill_between(mins, leads, 0, where=[v <= 0 for v in leads],
                    color=DIRE, alpha=0.5, interpolate=True)
    ax.margins(x=0, y=0.1)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.02,
                facecolor=SURFACE, edgecolor="none")
    plt.close(fig)
    return buf.getvalue()


def thumb_spark_png(leads: list[int]) -> bytes:
    """Small 2:1 diverging lead chart for Section thumbnail accessories."""
    mins = list(range(len(leads)))
    fig, ax = plt.subplots(figsize=(2.2, 1.1), dpi=144)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    ax.axis("off")
    ax.axhline(0, color=MUTED, linewidth=1)
    ax.fill_between(mins, leads, 0, where=[v >= 0 for v in leads],
                    color=RADIANT, alpha=0.75, interpolate=True)
    ax.fill_between(mins, leads, 0, where=[v <= 0 for v in leads],
                    color=DIRE, alpha=0.75, interpolate=True)
    ax.margins(x=0, y=0.08)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.02,
                facecolor=SURFACE, edgecolor="none")
    plt.close(fig)
    return buf.getvalue()


if __name__ == "__main__":
    # ponytail: self-check — a throw-shaped curve must render both poles
    demo = [0, 600, 1500, 2800, 4200, 6100, 8000, 9500, 8100, 6000,
            3500, 900, -1800, -4200, -7600, -11000, -14500, -13000, -16000, -21000]
    png = networth_lead_png(demo, "Match 8875698195 — Net Worth Lead")
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 10_000
    open("out/demo_lead.png", "wb").write(png)
    spark = sparkline_png(demo)
    assert spark[:8] == b"\x89PNG\r\n\x1a\n"
    open("out/demo_spark.png", "wb").write(spark)
    print(f"ok: lead {len(png)}B, spark {len(spark)}B -> out/")
