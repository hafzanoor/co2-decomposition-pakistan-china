"""
What drives CO2 emissions in Pakistan and China, 1990-2022?

1. Kaya identity:  C = P x (G/P) x (E/G) x (C/E)
       C = fossil-fuel CO2 (coal + oil + gas), Mt
       P = population, G = GDP (int.-$ 2011 prices), E = primary energy (TWh)
2. LMDI-I additive decomposition of the change in C into four effects:
       population, affluence (GDP per person), energy intensity (energy per GDP),
       carbon intensity of energy (CO2 per unit of energy).
3. Tapio decoupling elasticity between GDP growth and CO2 growth.
4. Illustrative scenarios for Pakistan to 2035.

Data: Our World in Data CO2 dataset (Global Carbon Budget 2026, Maddison Project 2023,
      EIA / Energy Institute energy data). GDP ends in 2022, so the analysis ends there.

Output: results/*.csv, results/summary.json, figures/01-06_*.png
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import style

ROOT = Path(__file__).resolve().parents[1]
FIG, RES, PROC = ROOT / "figures", ROOT / "results", ROOT / "data" / "processed"
for p in (FIG, RES, PROC):
    p.mkdir(parents=True, exist_ok=True)
style.apply()

COUNTRIES = ["Pakistan", "China"]
PEERS = ["Pakistan", "China", "India", "Bangladesh"]
START, END = 1990, 2022
PERIODS = [(1990, 1995), (1995, 2000), (2000, 2005), (2005, 2010),
           (2010, 2015), (2015, 2020), (2020, 2022)]
FACTORS = {"pop": "Population", "aff": "Affluence (GDP per person)",
           "ei": "Energy intensity (energy per GDP)", "ci": "Carbon intensity (CO₂ per energy)"}
FACTOR_COLORS = {"pop": style.VIOLET, "aff": style.ORANGE, "ei": style.BLUE, "ci": style.AQUA}
PEER_COLORS = {"Pakistan": style.AQUA, "China": style.ORANGE, "India": style.BLUE, "Bangladesh": style.VIOLET}


# ------------------------------------------------------------------ data
def load():
    d = pd.read_csv(ROOT / "data/raw/owid_co2_subset.csv")
    d["fossil_co2"] = d[["coal_co2", "oil_co2", "gas_co2"]].sum(axis=1, min_count=3)
    d["gdp_per_capita"] = d["gdp"] / d["population"]
    d["co2_per_gdp"] = d["co2"] * 1e9 / d["gdp"]                                     # kg CO2 per $
    return d


def kaya(d, country):
    s = d[(d.country == country) & d.year.between(START, END)].set_index("year")
    k = pd.DataFrame({
        "C": s["fossil_co2"],
        "pop": s["population"],
        "aff": s["gdp"] / s["population"],
        "ei": s["primary_energy_consumption"] / s["gdp"],
        "ci": s["fossil_co2"] / s["primary_energy_consumption"],
        "gdp": s["gdp"],
    })
    assert k.notna().all().all(), f"missing data for {country}"
    # identity check: C must equal the product of the four factors
    prod = k["pop"] * k["aff"] * k["ei"] * k["ci"]
    assert np.allclose(prod, k["C"]), "Kaya identity does not hold"
    return k


# ------------------------------------------------------------------ LMDI
def short(p):
    a, b = p.split("–")
    return f"{a}–{b[2:]}"


def logmean(a, b):
    return (a - b) / (np.log(a) - np.log(b)) if a != b else a


def lmdi(k, y0, y1):
    c0, c1 = k.at[y0, "C"], k.at[y1, "C"]
    w = logmean(c1, c0)
    eff = {f: w * np.log(k.at[y1, f] / k.at[y0, f]) for f in FACTORS}
    eff["total"] = c1 - c0
    eff["residual"] = eff["total"] - sum(eff[f] for f in FACTORS)
    return eff


# ------------------------------------------------------------------ Tapio decoupling
def tapio(dc, dg):
    """dc, dg = relative changes in CO2 and GDP. Returns (elasticity, state)."""
    e = dc / dg if dg != 0 else np.nan
    if dg > 0:
        if dc < 0:
            state = "Strong decoupling"
        elif e < 0.8:
            state = "Weak decoupling"
        elif e <= 1.2:
            state = "Expansive coupling"
        else:
            state = "Expansive negative decoupling"
    else:
        if dc > 0:
            state = "Strong negative decoupling"
        elif e > 1.2:
            state = "Recessive decoupling"
        elif e >= 0.8:
            state = "Recessive coupling"
        else:
            state = "Weak negative decoupling"
    return e, state


# ------------------------------------------------------------------ scenarios (Pakistan)
def scenarios(k, base=2022, horizon=2035, trend_from=2010):
    n = base - trend_from
    g = {f: (k.at[base, f] / k.at[trend_from, f]) ** (1 / n) - 1 for f in FACTORS}
    defs = {
        "Trend (2010–22 rates continue)": dict(g),
        "Efficiency push": {**g, "ei": -0.025},
        "Efficiency + clean energy": {**g, "ei": -0.025, "ci": -0.015},
    }
    years = np.arange(base, horizon + 1)
    out = {}
    for name, rates in defs.items():
        vals = []
        for y in years:
            t = y - base
            vals.append(k.at[base, "C"] * np.prod([(1 + rates[f]) ** t for f in FACTORS]))
        out[name] = pd.Series(vals, index=years)
    return pd.DataFrame(out), g, defs


# ------------------------------------------------------------------ figures
def fig_trends(d):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for c in PEERS:
        s = d[(d.country == c) & d.year.between(START, 2024)]
        axes[0].plot(s.year, s.co2_per_capita, color=PEER_COLORS[c], lw=2 if c in COUNTRIES else 1.3, label=c)
        s2 = s[s.year <= END]
        axes[1].plot(s2.year, s2.co2_per_gdp, color=PEER_COLORS[c], lw=2 if c in COUNTRIES else 1.3, label=c)
    axes[0].set_title("CO₂ per person")
    axes[0].set_ylabel("tonnes CO₂ per person")
    axes[1].set_title("CO₂ per unit of GDP (carbon intensity of the economy)")
    axes[1].set_ylabel("kg CO₂ per international-$ (2011)")
    for ax in axes:
        ax.set_ylim(0, None)
    axes[0].legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(FIG / "01_per_capita_and_intensity.png")
    plt.close(fig)


def fig_indexed(kd):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), sharey=False)
    names = {"C": "Fossil CO₂", "pop": "Population", "aff": "GDP per person",
             "ei": "Energy per GDP", "ci": "CO₂ per energy"}
    cols = {"C": style.TEXT, **FACTOR_COLORS}
    for ax, c in zip(axes, COUNTRIES):
        k = kd[c]
        for f in ["C", "pop", "aff", "ei", "ci"]:
            ax.plot(k.index, k[f] / k[f].iloc[0] * 100, color=cols[f], lw=2.4 if f == "C" else 1.6, label=names[f])
        ax.axhline(100, color=style.TEXT_2, lw=0.8)
        ax.set_title(f"{c}: Kaya factors (1990 = 100)")
        ax.set_yscale("log")
        ax.set_yticks([50, 100, 200, 400, 800])
        ax.set_yticklabels(["50", "100", "200", "400", "800"])
        ax.yaxis.set_minor_formatter(plt.NullFormatter())
    axes[0].set_ylabel("Index, 1990 = 100 (log scale)")
    axes[1].legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(FIG / "02_kaya_factors_indexed.png")
    plt.close(fig)


def fig_lmdi(lm):
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    for ax, c in zip(axes, COUNTRIES):
        t = lm[(lm.country == c) & (lm.period != f"{START}–{END}")].set_index("period")
        x = np.arange(len(t))
        pos = np.zeros(len(t)); neg = np.zeros(len(t))
        for f in FACTORS:
            v = t[f].values
            bottom = np.where(v >= 0, pos, neg)
            ax.bar(x, v, bottom=bottom, color=FACTOR_COLORS[f], width=0.62,
                   edgecolor=style.SURFACE, lw=1.5, label=FACTORS[f])
            pos += np.where(v >= 0, v, 0); neg += np.where(v < 0, v, 0)
        ax.scatter(x, t["total"], color=style.TEXT, zorder=5, s=28, label="Net change in CO₂")
        ax.axhline(0, color=style.TEXT_2, lw=0.8)
        ax.set_xticks(x, [short(p) for p in t.index], fontsize=8.5)
        ax.grid(axis="x", visible=False)
        ax.set_title(f"{c}: what changed fossil CO₂")
        ax.set_ylabel("Change in CO₂ (Mt)")
    h, l = axes[0].get_legend_handles_labels()
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.legend(h, l, loc="lower center", ncol=5, fontsize=8.5)
    fig.savefig(FIG / "03_lmdi_decomposition_by_period.png")
    plt.close(fig)


def fig_lmdi_share(lm):
    full = lm[lm.period == f"{START}–{END}"].set_index("country")
    fig, ax = plt.subplots(figsize=(9, 3.6))
    y = np.arange(len(COUNTRIES))
    for i, c in enumerate(COUNTRIES):
        r = full.loc[c]
        pct = {f: r[f] / r["total"] * 100 for f in FACTORS}
        left_pos, left_neg = 0, 0
        for f in FACTORS:
            v = pct[f]
            start = left_pos if v >= 0 else left_neg + v
            ax.barh(i, abs(v), left=start, color=FACTOR_COLORS[f], height=0.55,
                    edgecolor=style.SURFACE, lw=1.5, label=FACTORS[f] if i == 0 else None)
            if abs(v) >= 12:
                ax.text(start + abs(v) / 2, i, f"{v:+.0f}%", ha="center", va="center", fontsize=8.5, color="white")
            if v >= 0:
                left_pos += v
            else:
                left_neg += v
    ax.axvline(0, color=style.TEXT_2, lw=0.8)
    ax.axvline(100, color=style.TEXT, lw=1, ls="--")
    ax.text(102, 0.5, "net change = 100%", fontsize=8.5, color=style.TEXT_2, va="center")
    ax.set_yticks(y, COUNTRIES)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Contribution to the 1990–2022 change in fossil CO₂ (% of net change)")
    ax.set_title("Wealth drove emissions up; efficiency held them back")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.28), ncol=2, fontsize=8.5)
    fig.savefig(FIG / "04_lmdi_full_period_shares.png")
    plt.close(fig)


def fig_decoupling(dec):
    fig, ax = plt.subplots(figsize=(10, 3.8))
    for c in COUNTRIES:
        t = dec[dec.country == c]
        ax.plot([short(p) for p in t.period], t.elasticity, marker="o", ms=7, color=PEER_COLORS[c], lw=1.8, label=c)
    ax.axhspan(0, 0.8, color=style.GRID, alpha=0.6, lw=0)
    ax.axhline(0.8, color=style.TEXT_2, lw=0.8, ls="--")
    ax.axhline(1.2, color=style.TEXT_2, lw=0.8, ls="--")
    ax.axhline(0, color=style.TEXT_2, lw=0.8)
    ax.text(6.35, 0.4, "weak\ndecoupling", fontsize=8, color=style.TEXT_2, va="center")
    ax.text(6.35, 1.0, "coupling", fontsize=8, color=style.TEXT_2, va="center")
    ax.text(6.35, 1.6, "negative\ndecoupling", fontsize=8, color=style.TEXT_2, va="center")
    ax.set_xlim(-0.3, 7.1)
    ax.set_ylabel("Tapio elasticity\n(% change CO₂ / % change GDP)")
    ax.set_title("Is economic growth decoupling from CO₂?")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left")
    fig.savefig(FIG / "05_tapio_decoupling.png")
    plt.close(fig)


def fig_scenarios(k, sc):
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(k.index, k["C"], color=style.TEXT, lw=2, label="Historical (fossil CO₂)")
    cols = [style.ORANGE, style.BLUE, style.AQUA]
    for (name, s), col in zip(sc.items(), cols):
        ax.plot(s.index, s.values, color=col, lw=2, ls="--", label=name)
        ax.text(s.index[-1] + 0.3, s.values[-1], f"{s.values[-1]:.0f} Mt", va="center", fontsize=8.5, color=style.TEXT)
    ax.set_xlim(START, 2038)
    ax.set_ylim(0, None)
    ax.set_ylabel("Fossil CO₂ (Mt)")
    ax.set_title("Pakistan: illustrative emission pathways to 2035")
    ax.legend(loc="upper left")
    fig.savefig(FIG / "06_pakistan_scenarios_2035.png")
    plt.close(fig)


# ------------------------------------------------------------------ main
def main():
    d = load()
    kd = {c: kaya(d, c) for c in COUNTRIES}
    pd.concat({c: kd[c] for c in COUNTRIES}, names=["country", "year"]).to_csv(PROC / "kaya_factors.csv")

    rows, dec_rows = [], []
    for c in COUNTRIES:
        k = kd[c]
        for y0, y1 in PERIODS + [(START, END)]:
            rows.append({"country": c, "period": f"{y0}–{y1}", **lmdi(k, y0, y1)})
            if (y0, y1) != (START, END):
                dc = k.at[y1, "C"] / k.at[y0, "C"] - 1
                dg = k.at[y1, "gdp"] / k.at[y0, "gdp"] - 1
                e, st = tapio(dc, dg)
                dec_rows.append({"country": c, "period": f"{y0}–{y1}", "co2_change_%": dc * 100,
                                 "gdp_change_%": dg * 100, "elasticity": e, "state": st})
    lm = pd.DataFrame(rows)
    assert lm["residual"].abs().max() < 1e-8, "LMDI is not exact"
    dec = pd.DataFrame(dec_rows)
    lm.round(2).to_csv(RES / "lmdi_decomposition.csv", index=False)
    dec.round(3).to_csv(RES / "tapio_decoupling.csv", index=False)

    sc, rates, defs = scenarios(kd["Pakistan"])
    sc.round(1).to_csv(RES / "pakistan_scenarios.csv", index_label="year")

    fig_trends(d)
    fig_indexed(kd)
    fig_lmdi(lm)
    fig_lmdi_share(lm)
    fig_decoupling(dec)
    fig_scenarios(kd["Pakistan"], sc)

    full = lm[lm.period == f"{START}–{END}"].set_index("country")
    pc = d[d.year == 2024].set_index("country")["co2_per_capita"]
    summary = {
        "fossil_co2_Mt": {c: {str(START): round(kd[c].at[START, "C"], 1), str(END): round(kd[c].at[END, "C"], 1),
                              "ratio": round(kd[c].at[END, "C"] / kd[c].at[START, "C"], 2)} for c in COUNTRIES},
        "lmdi_full_period_Mt": {c: {k: round(float(full.at[c, k]), 1) for k in list(FACTORS) + ["total"]} for c in COUNTRIES},
        "lmdi_full_period_pct_of_net": {c: {k: round(float(full.at[c, k] / full.at[c, "total"] * 100), 1) for k in FACTORS} for c in COUNTRIES},
        "co2_per_capita_2024_t": {c: round(float(pc[c]), 2) for c in PEERS + ["World"]},
        "decoupling": dec[["country", "period", "elasticity", "state"]].round(2).to_dict("records"),
        "pakistan_trend_rates_2010_22_%": {k: round(v * 100, 2) for k, v in rates.items()},
        "pakistan_2035_Mt": {k: round(float(v.iloc[-1]), 1) for k, v in sc.items()},
    }
    (RES / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
