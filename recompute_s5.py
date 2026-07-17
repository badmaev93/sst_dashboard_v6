#!/usr/bin/env python3
"""
Recompute s5.npz with proper month-specific variance trends.

For each month m: extract SST(year, m), compute anomalies from clim mean,
fit trend to squared anomalies (= trend of interannual variance) per pixel.
"""
import os, sys, time
import numpy as np
from scipy import stats
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
NC_FILE  = "/home/oleg/Документы/workother/SST/702f0cf697615aa1590f02162e5df1cc.nc"

print("Loading NetCDF …")
try:
    import netCDF4
    nc      = netCDF4.Dataset(NC_FILE)
    lat     = np.array(nc.variables["latitude"][:])
    lon     = np.array(nc.variables["longitude"][:])
    vt      = np.array(nc.variables["valid_time"][:])
    sst_raw = np.array(nc.variables["sst"][:], dtype=np.float32)
    nc.close()
except Exception as e:
    print(f"ERROR: {e}"); sys.exit(1)

sst = sst_raw - 273.15
sst[np.abs(sst) > 100] = np.nan
NTIME, NLAT, NLON = sst.shape
land_mask = np.all(np.isnan(sst), axis=0)

dates  = [datetime.utcfromtimestamp(int(t)) for t in vt]
years  = np.array([d.year  for d in dates])
months = np.array([d.month for d in dates])

# ESS season assignment
def ess_season(m):
    m0 = m - 1
    if m0 in (11, 0, 1): return 0
    elif m0 in (2, 3, 4): return 1
    elif m0 in (5, 6, 7): return 2
    else: return 3

ess_idx = np.array([ess_season(m) for m in months])


def compute_trend(data_nt, x_years):
    """data: (T, NLAT, NLON). Returns trend per decade, r2, pval."""
    T, NL, NW = data_nt.shape
    trend = np.full((NL, NW), np.nan, dtype=np.float32)
    pval  = np.full((NL, NW), np.nan, dtype=np.float32)
    x = x_years - x_years.mean()
    d2d = data_nt.reshape(T, NL * NW)
    for p in range(NL * NW):
        y = d2d[:, p]
        msk = np.isfinite(y)
        if msk.sum() < 5:
            continue
        xm, ym = x[msk], y[msk]
        sl, _, _, pv, _ = stats.linregress(xm, ym)
        trend.ravel()[p] = sl * 10   # per decade
        pval.ravel()[p]  = pv
    return trend, pval


def variance_trend_monthly(yr0, yr1):
    """
    For each month m (0..11): compute trend of squared SST anomalies over years.
    Returns shape (12, NLAT, NLON) — trend in °C²/decade, masked p>=0.05.
    """
    result = np.full((12, NLAT, NLON), np.nan, dtype=np.float32)
    sel_years = np.unique(years[(years >= yr0) & (years <= yr1)])
    if len(sel_years) < 5:
        return result
    for m in range(12):
        mon_no = m + 1  # 1-based
        # Extract one frame per year for this month
        frames, yrs_used = [], []
        for yr in sel_years:
            idx = np.where((years == yr) & (months == mon_no))[0]
            if len(idx):
                frames.append(sst[idx[0]])
                yrs_used.append(yr)
        if len(frames) < 5:
            continue
        frames = np.array(frames, dtype=np.float32)  # (Ny, NLAT, NLON)
        y_arr  = np.array(yrs_used, dtype=float)
        clim_m = np.nanmean(frames, axis=0)           # climatological mean for this month
        anom   = frames - clim_m[np.newaxis]           # anomalies
        sq_anom = anom ** 2                             # squared anomalies = proxy for variance
        tr, pv = compute_trend(sq_anom, y_arr)
        result[m] = np.where(pv < 0.05, tr, np.nan)
        print(f"  month {mon_no:02d}: valid pixels = {np.isfinite(result[m]).sum()}")
    return result


def variance_trend_ess(yr0, yr1):
    """ESS version: 4 seasons."""
    result = np.full((4, NLAT, NLON), np.nan, dtype=np.float32)
    sel_years = np.unique(years[(years >= yr0) & (years <= yr1)])
    if len(sel_years) < 5:
        return result
    for s in range(4):
        frames, yrs_used = [], []
        for yr in sel_years:
            idx = np.where((years == yr) & (ess_idx == s))[0]
            if len(idx):
                frames.append(np.nanmean(sst[idx], axis=0))
                yrs_used.append(yr)
        if len(frames) < 5:
            continue
        frames = np.array(frames, dtype=np.float32)
        y_arr  = np.array(yrs_used, dtype=float)
        clim_s = np.nanmean(frames, axis=0)
        anom   = frames - clim_s[np.newaxis]
        sq_anom = anom ** 2
        tr, pv = compute_trend(sq_anom, y_arr)
        result[s] = np.where(pv < 0.05, tr, np.nan)
        print(f"  ESS {s}: valid pixels = {np.isfinite(result[s]).sum()}")
    return result


# ── Load existing s5 for pcts (keep them) ──────
existing = np.load(os.path.join(DATA_DIR, "s5.npz"), allow_pickle=True)
s5_pcts  = existing["pcts"]

print("Computing s5 all-period monthly …")
t0 = time.time()
# All-period (1980–2026) as baseline "monthly" and "ess" keys
all_yr0 = int(years.min())
all_yr1 = int(years.max())
s5_monthly = variance_trend_monthly(all_yr0, all_yr1).astype(np.float32)
s5_ess     = variance_trend_ess(all_yr0, all_yr1).astype(np.float32)
print(f"  done in {time.time()-t0:.1f}s")

periods = [
    ("1981_2010", 1981, 2010),
    ("1991_2020", 1991, 2020),
    ("1980_2026", 1980, 9999),
]
results = {}
for name, yr0, yr1 in periods:
    actual_yr1 = all_yr1 if yr1 == 9999 else yr1
    print(f"Computing s5 {name} monthly …")
    t0 = time.time()
    results[f"monthly_{name}"] = variance_trend_monthly(yr0, actual_yr1).astype(np.float32)
    print(f"Computing s5 {name} ESS …")
    results[f"ess_{name}"]     = variance_trend_ess(yr0, actual_yr1).astype(np.float32)
    print(f"  done in {time.time()-t0:.1f}s")

out = os.path.join(DATA_DIR, "s5.npz")
np.savez_compressed(out,
    monthly=s5_monthly, ess=s5_ess, pcts=s5_pcts,
    monthly_1981_2010=results["monthly_1981_2010"], ess_1981_2010=results["ess_1981_2010"],
    monthly_1991_2020=results["monthly_1991_2020"], ess_1991_2020=results["ess_1991_2020"],
    monthly_1980_2026=results["monthly_1980_2026"], ess_1980_2026=results["ess_1980_2026"],
)
print(f"Saved {out}")
