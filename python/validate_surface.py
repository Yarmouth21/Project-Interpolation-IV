"""
Validation out-of-sample de la surface de volatilite implicite NVDA.

Reproduit le pipeline du README (filtrage qualite + griddata/Delaunay),
puis mesure l'erreur de reconstruction par cross-validation, ainsi que
le temps de construction de la surface complete.
"""
import time
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.interpolate import griddata

from vol_surface import load_clean  # meme filtrage qualite que la surface

ROOT = Path(__file__).parent.parent
RNG = np.random.default_rng(42)


# ------------------------------------------------------------ predicteur
def predict(train, x_test, method):
    """IV interpolee aux points (DTM, Strike) de x_test, entraine sur `train`."""
    pts = train[["Day until Maturity", "Strike"]].to_numpy(float)
    vals = train["Implied Vol"].to_numpy(float)
    return griddata(pts, vals, x_test, method=method)


def metrics(y_true, y_pred, label):
    m = ~np.isnan(y_pred)
    cov = m.mean()
    yt, yp = y_true[m], y_pred[m]
    err = (yp - yt) * 100.0          # points de volatilite
    mae, rmse = np.abs(err).mean(), np.sqrt((err ** 2).mean())
    r2 = 1 - ((yp - yt) ** 2).sum() / ((yt - yt.mean()) ** 2).sum()
    p95 = np.percentile(np.abs(err), 95)
    print(f"  {label:<28} MAE={mae:5.2f} vol pts | RMSE={rmse:5.2f} | "
          f"R2={r2:6.3f} | p95={p95:5.2f} | max={np.abs(err).max():5.2f} | "
          f"couverture={cov:.0%} (n={m.sum()})")
    return dict(label=label, mae=mae, rmse=rmse, r2=r2, p95=p95,
                maxerr=np.abs(err).max(), coverage=cov, n=int(m.sum()))


# ----------------------------------------------------- schemas de holdout
def kfold_random(df, method, k=5, repeats=10):
    yt, yp = [], []
    for _ in range(repeats):
        idx = RNG.permutation(len(df))
        for f in range(k):
            test_i = idx[f::k]
            train_i = np.setdiff1d(idx, test_i)
            te, tr = df.iloc[test_i], df.iloc[train_i]
            yp.append(predict(tr, te[["Day until Maturity", "Strike"]].to_numpy(float), method))
            yt.append(te["Implied Vol"].to_numpy(float))
    return np.concatenate(yt), np.concatenate(yp)


def leave_one_out(df, method):
    yt, yp = [], []
    X = df[["Day until Maturity", "Strike"]].to_numpy(float)
    y = df["Implied Vol"].to_numpy(float)
    for i in range(len(df)):
        tr = df.drop(index=i)
        yp.append(predict(tr, X[i:i + 1], method)[0])
        yt.append(y[i])
    return np.array(yt), np.array(yp)


def baseline_dtm_mean(df):
    """Baseline naive : IV = moyenne du smile de la meme maturite (LOO)."""
    yt, yp = [], []
    for i in range(len(df)):
        row = df.iloc[i]
        same = df.drop(index=i)
        same = same[same["Day until Maturity"] == row["Day until Maturity"]]
        yp.append(same["Implied Vol"].mean())
        yt.append(row["Implied Vol"])
    return np.array(yt), np.array(yp)


# --------------------------------------------------------------- timings
def timings(df, method="linear", n=80, reps=5):
    pts = df[["Day until Maturity", "Strike"]].to_numpy(float)
    vals = df["Implied Vol"].to_numpy(float)
    gd = np.linspace(pts[:, 0].min(), pts[:, 0].max(), n)
    gs = np.linspace(pts[:, 1].min(), pts[:, 1].max(), n)
    GD, GS = np.meshgrid(gd, gs)
    grid = np.column_stack([GD.ravel(), GS.ravel()])

    t = []
    for _ in range(reps):
        t0 = time.perf_counter()
        griddata(pts, vals, grid, method=method)
        t.append(time.perf_counter() - t0)
    vec = min(t)

    # naif : un appel griddata par point (re-triangulation a chaque fois)
    sample = 200
    sub = grid[RNG.choice(len(grid), sample, replace=False)]
    t0 = time.perf_counter()
    for p in sub:
        griddata(pts, vals, p[None, :], method=method)
    naive_per_pt = (time.perf_counter() - t0) / sample

    print(f"\nTemps de calcul (grille {n}x{n} = {n*n} points, method={method})")
    print(f"  Surface complete (vectorisee)     : {vec*1000:7.1f} ms "
          f"({vec/ (n*n) * 1e6:.1f} us/point)")
    print(f"  Naif point par point (extrapole)  : {naive_per_pt*n*n*1000:7.1f} ms "
          f"({naive_per_pt*1e6:.1f} us/point)")
    print(f"  Speedup                           : x{naive_per_pt*n*n/vec:.0f}")


# ------------------------------------------------------------------ main
if __name__ == "__main__":
    df = load_clean()
    print(f"\nGrille : {df['Day until Maturity'].nunique()} maturites, "
          f"{df['Strike'].nunique()} strikes distincts, {len(df)} points")
    print(f"IV : moyenne={df['Implied Vol'].mean():.3f}, "
          f"ecart-type={df['Implied Vol'].std()*100:.2f} vol pts, "
          f"min={df['Implied Vol'].min():.3f}, max={df['Implied Vol'].max():.3f}")

    print("\n=== Leave-one-out (chaque option retiree tour a tour) ===")
    res = []
    for m in ("linear", "cubic"):
        res.append(metrics(*leave_one_out(df, m), f"griddata {m}"))
    res.append(metrics(*baseline_dtm_mean(df), "baseline moy. par maturite"))

    print("\n=== 5-fold x10 (20% des points retires en bloc) ===")
    for m in ("linear", "cubic"):
        metrics(*kfold_random(df, m, k=5, repeats=10), f"griddata {m}")

    timings(df, "linear")
    timings(df, "cubic")


# ---------------------------------------------- ventilation des erreurs
def breakdown(df):
    yt, yp = leave_one_out(df, "linear")
    err = (yp - yt) * 100
    d = df.assign(err=err).dropna(subset=["err"])
    print("\n=== Erreur LOO (linear) par maturite ===")
    g = d.groupby("Day until Maturity")["err"]
    for dtm, s in g:
        print(f"  DTM {dtm:>2} (n={len(s):>2}) : MAE={s.abs().mean():5.2f} | RMSE={np.sqrt((s**2).mean()):5.2f}")
    print("\n=== Erreur LOO (linear) par zone de strike ===")
    bins = pd.cut(d["Strike"], [0, 180, 200, 220, 1e9],
                  labels=["<180 (ITM)", "180-200 (ATM)", "200-220 (OTM)", ">220 (deep OTM)"])
    for z, s in d.groupby(bins, observed=True)["err"]:
        print(f"  {str(z):<16} (n={len(s):>2}) : MAE={s.abs().mean():5.2f} | RMSE={np.sqrt((s**2).mean()):5.2f}")
