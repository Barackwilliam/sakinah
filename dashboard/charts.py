"""Tiny server-side SVG chart helpers, so the dashboard needs no JavaScript chart library."""
from math import log10

def nice_max(v):
    if v <= 0: return 1
    step = 10 ** int(log10(v))
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * step: return m * step
    return 10 * step

def line_chart(labels, series, width=400, height=230, pad_l=40, pad_b=24, pad_t=10, pad_r=10):
    """series: list of (name, color, values). Returns everything the template needs to draw the SVG."""
    top = nice_max(max([max(v) for _, _, v in series if v] + [0]))
    w, h = width - pad_l - pad_r, height - pad_t - pad_b
    n = max(len(labels) - 1, 1)
    x = lambda i: pad_l + w * i / n
    y = lambda v: pad_t + h - h * v / top
    lines = []
    for name, color, values in series:
        pts = [(round(x(i), 1), round(y(v), 1)) for i, v in enumerate(values)]
        line = " ".join(f"{a},{b}" for a, b in pts)
        area = f"{pts[0][0]},{pad_t + h} {line} {pts[-1][0]},{pad_t + h}" if pts else ""
        lines.append({"name": name, "color": color, "line": line, "area": area, "points": pts, "total": sum(values)})
    ticks = [{"y": round(y(top * k / 4), 1), "label": fmt(top * k / 4)} for k in range(5)]
    xl = [{"x": round(x(i), 1), "label": l} for i, l in enumerate(labels)]
    return {"w": width, "h": height, "lines": lines, "ticks": ticks, "xlabels": xl, "left": pad_l, "right": width - pad_r, "base": pad_t + h}

def bar_chart(labels, series, width=320, height=170, pad_l=40, pad_b=22, pad_t=8):
    top = nice_max(max([max(v) for _, _, v in series if v] + [0]))
    w, h = width - pad_l - 6, height - pad_t - pad_b
    group = w / max(len(labels), 1); bw = min(14, group / (len(series) + 1))
    bars = []
    for gi, label in enumerate(labels):
        for si, (name, color, values) in enumerate(series):
            bh = h * values[gi] / top
            bars.append({"x": round(pad_l + gi * group + (group - bw * len(series)) / 2 + si * bw, 1), "y": round(pad_t + h - bh, 1),
                         "w": round(bw - 2, 1), "h": round(bh, 1), "color": color, "title": f"{name}: {values[gi]}"})
    ticks = [{"y": round(pad_t + h - h * k / 4, 1), "label": fmt(top * k / 4)} for k in range(5)]
    xl = [{"x": round(pad_l + gi * group + group / 2, 1), "label": l} for gi, l in enumerate(labels)]
    return {"w": width, "h": height, "bars": bars, "ticks": ticks, "xlabels": xl, "left": pad_l, "right": width - 6, "base": pad_t + h,
            "legend": [(n, c) for n, c, _ in series]}

def donut(parts):
    """parts: list of (label, color, value). Returns conic-gradient stops and percentages."""
    total = sum(v for _, _, v in parts) or 1
    stops, acc, rows = [], 0, []
    for label, color, v in parts:
        pct = v * 100 / total
        stops.append(f"{color} {acc:.2f}% {acc + pct:.2f}%"); acc += pct
        rows.append({"label": label, "color": color, "value": v, "pct": round(pct)})
    return {"gradient": ", ".join(stops) if sum(v for *_, v in parts) else "#eceef3 0 100%", "rows": rows}

def fmt(v):
    if v >= 1_000_000: return f"{v / 1_000_000:g}M"
    if v >= 1000: return f"{v:,.0f}"
    return f"{v:g}"
