#!/usr/bin/env python3
"""
Gera os SVGs do topo do README a partir do calendário público de
contribuições do GitHub (o mesmo HTML que a página do perfil usa):

    assets/contributions.svg  heatmap animado do último ano
    assets/stats.svg          cards de sequência, totais e barras por mês

Só usa a biblioteca padrão. Roda todo dia pelo
.github/workflows/update-stats.yml.

    python scripts/build_stats.py [usuario]
"""
import datetime as dt
import html
import os
import re
import sys
import urllib.request

USER = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GH_USER", "crispinzz")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MONO = "'JetBrains Mono','SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"

# paleta do GitHub no tema escuro
BG = "#0d1117"
PANEL = "#161b22"
BORDER = "#30363d"
TEXT = "#e6edf3"
MUTED = "#8b949e"
GREEN = "#39d353"
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]

W = 840  # os dois SVGs têm a mesma largura para empilhar alinhados


# ---------------------------------------------------------------- dados

def fetch_days(user):
    req = urllib.request.Request(
        f"https://github.com/users/{user}/contributions",
        headers={"User-Agent": "Mozilla/5.0 (profile-stats)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        page = resp.read().decode("utf-8")

    tips = dict(re.findall(r'<tool-tip[^>]*\bfor="([^"]+)"[^>]*>([^<]*)</tool-tip>', page))

    days = []
    for tag in re.findall(r"<td\b[^>]*ContributionCalendar-day[^>]*>", page):
        date = re.search(r'data-date="([^"]+)"', tag)
        if not date:
            continue
        cid = re.search(r'\bid="([^"]+)"', tag)
        level = re.search(r'data-level="(\d)"', tag)
        # "No contributions on ..." não casa e vira 0
        n = re.match(r"([\d,]+) contributions?", tips.get(cid.group(1), "") if cid else "")
        days.append({
            "date": dt.date.fromisoformat(date.group(1)),
            "count": int(n.group(1).replace(",", "")) if n else 0,
            "level": int(level.group(1)) if level else 0,
        })

    if not days:
        sys.exit("nenhum dia encontrado no calendário: o HTML do GitHub pode ter mudado")
    days.sort(key=lambda d: d["date"])

    shown = re.search(r"([\d,]+)\s+contributions?\s+in the last year", page)
    total = sum(d["count"] for d in days)
    if shown and int(shown.group(1).replace(",", "")) != total:
        print(f"aviso: soma dos dias ({total}) difere do total do GitHub ({shown.group(1)})")
    return days


def runs_of_activity(days):
    """Intervalos [ini, fim] (índices) de dias seguidos com contribuição."""
    runs, start = [], None
    for i, d in enumerate(days):
        if d["count"] and start is None:
            start = i
        elif not d["count"] and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(days) - 1))
    return runs


def compute_stats(days):
    runs = runs_of_activity(days)
    last = len(days) - 1
    # hoje ainda não acabou: um dia zerado hoje não quebra a sequência
    alive = last if days[last]["count"] else last - 1
    current = next((r for r in runs if r[1] == alive), None)
    longest = max(runs, key=lambda r: (r[1] - r[0], r[1]), default=None)

    def span(r):
        if r is None:
            return 0, None, None
        return r[1] - r[0] + 1, days[r[0]]["date"], days[r[1]]["date"]

    months = {}
    for d in days:
        key = d["date"].replace(day=1)
        months[key] = months.get(key, 0) + d["count"]

    total = sum(d["count"] for d in days)
    active = sum(1 for d in days if d["count"])
    best = max(days, key=lambda d: (d["count"], d["date"]))
    return {
        "total": total,
        "active": active,
        "n_days": len(days),
        "best": best,
        "avg": total / active if active else 0.0,
        "current": span(current),
        "longest": span(longest),
        "months": sorted(months.items()),
    }


# ------------------------------------------------------------- formatos

def esc(s):
    return html.escape(str(s), quote=True)


def fmt_int(n):
    return f"{n:,}".replace(",", ".")


def fmt_date(d):
    return f"{d.day} {MESES[d.month - 1]}"


def fmt_range(a, b):
    return fmt_date(a) if a == b else f"{fmt_date(a)} – {fmt_date(b)}"


def plural(n, one, many):
    return one if n == 1 else many


# ---------------------------------------------------------------- render

def window(h, title, cmd, desc, css, body):
    """Moldura de terminal com barra de título e a linha de comando."""
    prompt = (
        f'<tspan fill="{GREEN}">{esc(USER)}@github</tspan>'
        f'<tspan fill="{MUTED}">:~$ </tspan>'
        f'<tspan fill="{TEXT}">{esc(cmd)} </tspan>'
        f'<tspan class="cur" fill="{TEXT}">█</tspan>'
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" aria-labelledby="t">
<title id="t">{esc(desc)}</title>
<style>
text{{font-family:{MONO}}}
.cur{{animation:blink 1s steps(1) infinite}}
@keyframes blink{{50%{{fill-opacity:0}}}}
{css}
</style>
<rect x=".5" y=".5" width="{W - 1}" height="{h - 1}" rx="10" fill="{BG}" stroke="{BORDER}"/>
<circle cx="20" cy="16" r="6" fill="#ff5f57"/>
<circle cx="40" cy="16" r="6" fill="#febc2e"/>
<circle cx="60" cy="16" r="6" fill="#28c840"/>
<text x="{W / 2}" y="20" text-anchor="middle" font-size="12" fill="{MUTED}">{esc(title)}</text>
<line x1="1" y1="32.5" x2="{W - 1}" y2="32.5" stroke="{BORDER}"/>
<text x="24" y="62" font-size="14" xml:space="preserve">{prompt}</text>
{body}
</svg>
"""


def render_heatmap(days, stats):
    step, cell = 14, 11
    first = days[0]["date"]
    origin = first - dt.timedelta(days=(first.weekday() + 1) % 7)  # domingo da 1ª coluna

    def pos(d):
        off = (d - origin).days
        return off // 7, off % 7

    ncols = pos(days[-1]["date"])[0] + 1
    gw = ncols * step - (step - cell)
    gx = (W - gw) // 2 + 14  # +14 compensa os rótulos dos dias à esquerda
    gy = 104
    out = []

    # meses: rótulo na primeira coluna cujo domingo cai num mês novo
    labels, prev = [], None
    for c in range(ncols):
        m = (origin + dt.timedelta(weeks=c)).month
        if m != prev:
            labels.append((c, m))
            prev = m
    # como o GitHub, some com o rótulo que ficaria colado no seguinte
    labels = [l for i, l in enumerate(labels) if i + 1 == len(labels) or labels[i + 1][0] - l[0] >= 3]
    for c, m in labels:
        out.append(f'<text x="{gx + c * step}" y="{gy - 10}" font-size="12" fill="{MUTED}">{MESES[m - 1]}</text>')

    for r, name in ((1, "seg"), (3, "qua"), (5, "sex")):
        out.append(f'<text x="{gx - 8}" y="{gy + r * step + 9}" text-anchor="end" font-size="11" fill="{MUTED}">{name}</text>')

    for d in days:
        c, r = pos(d["date"])
        out.append(
            f'<rect class="c" x="{gx + c * step}" y="{gy + r * step}" width="{cell}" height="{cell}" rx="2" '
            f'fill="{LEVELS[d["level"]]}" style="animation-delay:{c * 0.025 + r * 0.012:.3f}s"/>'
        )

    fy = gy + 7 * step - (step - cell) + 30
    total = stats["total"]
    out.append(
        f'<text class="f" x="{gx}" y="{fy}" font-size="13" xml:space="preserve">'
        f'<tspan fill="{TEXT}" font-weight="700">{fmt_int(total)}</tspan>'
        f'<tspan fill="{MUTED}"> {plural(total, "contribuição", "contribuições")} no último ano</tspan></text>'
    )
    right = gx + gw
    box0 = right - 34 - 5 * step
    out.append(f'<text class="f" x="{box0 - 6}" y="{fy}" text-anchor="end" font-size="11" fill="{MUTED}">menos</text>')
    for i, color in enumerate(LEVELS):
        out.append(f'<rect class="f" x="{box0 + i * step}" y="{fy - 10}" width="{cell}" height="{cell}" rx="2" fill="{color}"/>')
    out.append(f'<text class="f" x="{right}" y="{fy}" text-anchor="end" font-size="11" fill="{MUTED}">mais</text>')

    css = (
        ".c{opacity:0;transform-box:fill-box;transform-origin:center;animation:pop .35s ease-out forwards}"
        "@keyframes pop{from{opacity:0;transform:scale(.3)}to{opacity:1;transform:scale(1)}}"
        ".f{opacity:0;animation:fade .5s ease-out 1.5s forwards}"
        "@keyframes fade{to{opacity:1}}"
        "@media (prefers-reduced-motion:reduce){.c,.f{animation:none;opacity:1;transform:none}}"
    )
    desc = f"Gráfico de contribuições de {USER} no GitHub: {fmt_int(total)} no último ano"
    return window(fy + 24, f"{USER}@github: ~/contributions", "./contributions.sh", desc, css, "\n".join(out))


def card(x, y, w, h, label, value, unit, sub, delay, accent=False):
    unit_t = f'<tspan font-size="14" font-weight="400" fill="{MUTED}">{esc(unit)}</tspan>' if unit else ""
    return (
        f'<g class="card" style="animation-delay:{delay:.2f}s">'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{PANEL}" stroke="{BORDER}"/>'
        f'<text x="{x + 16}" y="{y + 26}" font-size="13" fill="{MUTED}">$ {esc(label)}</text>'
        f'<text x="{x + 16}" y="{y + 62}" font-size="30" font-weight="700" fill="{GREEN if accent else TEXT}" '
        f'xml:space="preserve">{esc(value)}{unit_t}</text>'
        f'<text x="{x + 16}" y="{y + 84}" font-size="12" fill="{MUTED}">{esc(sub)}</text>'
        "</g>"
    )


def render_stats(stats):
    pad, gap = 24, 12
    cw, ch = (W - 2 * pad - 2 * gap) // 3, 96
    cur_n, cur_a, cur_b = stats["current"]
    lon_n, lon_a, lon_b = stats["longest"]
    best = stats["best"]
    pct = round(100 * stats["active"] / stats["n_days"])

    cards = [
        ("sequência atual", cur_n, plural(cur_n, " dia", " dias"),
         fmt_range(cur_a, cur_b) if cur_n else "nenhuma em andamento", cur_n > 0),
        ("maior sequência", lon_n, plural(lon_n, " dia", " dias"),
         fmt_range(lon_a, lon_b) if lon_n else "ainda não começou", False),
        ("contribuições", fmt_int(stats["total"]), "", "no último ano", False),
        ("dias ativos", stats["active"], f" / {stats['n_days']}", f"{pct}% do ano", False),
        ("melhor dia", best["count"], "", fmt_date(best["date"]) if best["count"] else "—", False),
        ("média por dia ativo", f"{stats['avg']:.1f}".replace(".", ","), "", "contribuições", False),
    ]
    out = []
    for i, (label, value, unit, sub, accent) in enumerate(cards):
        x = pad + (i % 3) * (cw + gap)
        y = 80 + (i // 3) * (ch + gap)
        out.append(card(x, y, cw, ch, label, value, unit, sub, 0.1 + i * 0.08, accent))

    # barras por mês
    bx, by, bw_, bh = pad, 80 + 2 * (ch + gap), W - 2 * pad, 184
    out.append(f'<g class="card" style="animation-delay:.6s">'
               f'<rect x="{bx}" y="{by}" width="{bw_}" height="{bh}" rx="8" fill="{PANEL}" stroke="{BORDER}"/>'
               f'<text x="{bx + 16}" y="{by + 26}" font-size="13" fill="{MUTED}">$ contribuições / mês</text></g>')
    months = stats["months"]
    left, right = bx + 24, bx + bw_ - 24
    slot = (right - left) / len(months)
    bar = min(32, slot * 0.55)
    base = by + bh - 34
    tallest = bh - 96
    peak = max(v for _, v in months)
    for i, (m, v) in enumerate(months):
        h = max(3, round(v / peak * tallest)) if v else 2
        x = round(left + i * slot + (slot - bar) / 2, 1)
        mid = round(x + bar / 2, 1)
        top = v == peak and v > 0
        fill = GREEN if top else LEVELS[3] if v else BORDER
        delay = 0.8 + i * 0.05
        out.append(f'<rect class="b" x="{x}" y="{base - h}" width="{bar}" height="{h}" rx="3" fill="{fill}" '
                   f'style="animation-delay:{delay:.2f}s"/>')
        if v:
            weight = "700" if top else "400"
            out.append(f'<text class="v" x="{mid}" y="{base - h - 7}" text-anchor="middle" font-size="11" '
                       f'fill="{TEXT if top else MUTED}" font-weight="{weight}" '
                       f'style="animation-delay:{delay + 0.5:.2f}s">{fmt_int(v)}</text>')
        out.append(f'<text x="{mid}" y="{base + 20}" text-anchor="middle" font-size="11" fill="{MUTED}" '
                   f'class="v" style="animation-delay:{delay:.2f}s">{MESES[m.month - 1]}</text>')

    css = (
        ".card{opacity:0;animation:rise .5s ease-out forwards}"
        "@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}"
        ".b{transform-box:fill-box;transform-origin:50% 100%;transform:scaleY(0);"
        "animation:grow .7s cubic-bezier(.2,.8,.2,1) forwards}"
        "@keyframes grow{to{transform:scaleY(1)}}"
        ".v{opacity:0;animation:fade .4s ease-out forwards}"
        "@keyframes fade{to{opacity:1}}"
        "@media (prefers-reduced-motion:reduce){.card,.b,.v{animation:none;opacity:1;transform:none}}"
    )
    desc = (f"Estatísticas de {USER}: sequência atual de {cur_n} {plural(cur_n, 'dia', 'dias')}, "
            f"{fmt_int(stats['total'])} contribuições no último ano")
    return window(by + bh + 24, f"{USER}@github: ~/stats", "./stats.sh", desc, css, "\n".join(out))


# ------------------------------------------------------------------ main

def write(name, svg):
    with open(os.path.join(ASSETS, name), "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)


def main():
    days = fetch_days(USER)
    stats = compute_stats(days)
    os.makedirs(ASSETS, exist_ok=True)
    write("contributions.svg", render_heatmap(days, stats))
    write("stats.svg", render_stats(stats))
    print(f"{USER}: {stats['total']} contribuições, {stats['active']} dias ativos, "
          f"sequência atual {stats['current'][0]}, maior {stats['longest'][0]}")


if __name__ == "__main__":
    main()
