"""
Surface de volatilite implicite NVDA — filtrage qualite et visualisation 3D.

Les options illiquides sont ecartees avant toute interpolation : leur IV est
calculee a partir de prix sans profondeur reelle et fausserait la surface.
La surface est ensuite reconstruite par triangulation de Delaunay
(scipy.interpolate.griddata), qui accepte des donnees non-regulieres — ici
7 maturites inegalement espacees et des strikes differents selon la maturite.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.interpolate import griddata

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
OUTPUT = ROOT / "output"

MAX_SPREAD = 0.50   # (Ask - Bid) / Ask
MIN_OI = 10         # open interest minimal si volume nul
GRID = 80           # resolution de la surface interpolee


def load_clean(verbose=True):
    """Charge le CSV nettoye et retire les options illiquides.

    Trois criteres, dans l'ordre du README :
      - Bid = 0            : aucun acheteur, le prix ne reflete aucun consensus
      - spread relatif >50%: l'IV varie du simple au double selon le cote retenu
      - volume nul et OI<10: contrat fantome, sans activite ni position ouverte
    """
    df = pd.read_csv(DATA / "nvda_calls_clean.csv")
    n0 = len(df)

    no_bid = df["Bid"] == 0
    spread = (df["Ask"] - df["Bid"]) / df["Ask"].replace(0, np.nan)
    wide = spread > MAX_SPREAD
    ghost = (df["Volume"] == 0) & (df["Open Interest"] < MIN_OI)

    kept = df[~(no_bid | wide | ghost)].reset_index(drop=True)

    if verbose:
        print(f"Filtrage qualite : {n0} options -> {len(kept)} conservees")
        print(f"  Bid = 0                    : {no_bid.sum():>3}")
        print(f"  Spread > {MAX_SPREAD:.0%}               : {(wide & ~no_bid).sum():>3}")
        print(f"  Volume = 0 et OI < {MIN_OI}       : {(ghost & ~no_bid & ~wide).sum():>3}")
    return kept


def interpolate(df, method):
    """Interpole l'IV sur une grille reguliere GRID x GRID (DTM, Strike)."""
    pts = df[["Day until Maturity", "Strike"]].to_numpy(float)
    vals = df["Implied Vol"].to_numpy(float)

    dtm = np.linspace(pts[:, 0].min(), pts[:, 0].max(), GRID)
    strike = np.linspace(pts[:, 1].min(), pts[:, 1].max(), GRID)
    DTM, STRIKE = np.meshgrid(dtm, strike)

    IV = griddata(pts, vals, (DTM, STRIKE), method=method)
    return DTM, STRIKE, IV


def plot(df, method, path):
    DTM, STRIKE, IV = interpolate(df, method)

    fig = plt.figure(figsize=(11, 8))
    ax = fig.add_subplot(111, projection="3d")

    surf = ax.plot_surface(DTM, STRIKE, IV * 100, cmap="viridis",
                           edgecolor="none", alpha=0.9, rstride=1, cstride=1)
    # points de marche effectivement utilises
    ax.scatter(df["Day until Maturity"], df["Strike"], df["Implied Vol"] * 100,
               c="crimson", s=8, depthshade=False, label="Options observees")

    ax.set_xlabel("Jours jusqu'a maturite")
    ax.set_ylabel("Strike ($)")
    ax.set_zlabel("Volatilite implicite (%)")
    ax.set_title(f"Surface de volatilite implicite — NVDA calls, 5 mai 2026\n"
                 f"griddata method=\"{method}\" — {len(df)} options")
    ax.view_init(elev=24, azim=-58)
    ax.legend(loc="upper left", framealpha=0.9)
    fig.colorbar(surf, ax=ax, shrink=0.55, aspect=18, label="IV (%)")

    OUTPUT.mkdir(exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)

    covered = np.isfinite(IV).mean()
    print(f"  {method:<7} -> {path.relative_to(ROOT)} "
          f"(IV {np.nanmin(IV)*100:.1f}–{np.nanmax(IV)*100:.1f} %, "
          f"grille couverte a {covered:.0%})")


if __name__ == "__main__":
    df = load_clean()
    print(f"\n{df['Day until Maturity'].nunique()} maturites, "
          f"{df['Strike'].nunique()} strikes distincts, {len(df)} points\n")

    print("Generation des surfaces :")
    for method in ("cubic", "linear"):
        plot(df, method, OUTPUT / f"vol_surface_{method}.png")
