from __future__ import annotations
"""
SST Dashboard v5 — SST router
"""
import os, io, math, logging, time
from typing import Optional

_SERVER_START_TS = str(int(time.time()))

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)

import numpy as np
from scipy.ndimage import zoom as nd_zoom
from PIL import Image
from fastapi import APIRouter, HTTPException, Response

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

sst_router = APIRouter()

# ──────────────────────────────────────────────
# Lazy-load precomputed data
# ──────────────────────────────────────────────
_cache: dict = {}

def _load(name: str) -> dict:
    if name not in _cache:
        path = os.path.join(DATA_DIR, f"{name}.npz")
        if not os.path.exists(path):
            raise HTTPException(500, f"Data not precomputed: {name}.npz — run precompute.py first.")
        _cache[name] = dict(np.load(path, allow_pickle=True))
    return _cache[name]

# ──────────────────────────────────────────────
# Colormaps — pure-numpy LUT (256 × 3, uint8)
# ──────────────────────────────────────────────
def _make_lut(name: str) -> np.ndarray:
    n   = 256
    lut = np.zeros((n, 3), dtype=np.uint8)
    t   = np.linspace(0, 1, n)

    def c(v): return int(np.clip(v, 0, 255))

    if name == "RdYlBu_r":
        colors = [
            (0.000, (49,  54,  149)),
            (0.125, (69,  117, 180)),
            (0.250, (116, 173, 209)),
            (0.375, (171, 217, 233)),
            (0.500, (255, 255, 191)),
            (0.625, (254, 224, 144)),
            (0.750, (253, 174, 97)),
            (0.875, (244, 109, 67)),
            (1.000, (165, 0,   38)),
        ]
        for i, v in enumerate(t):
            for k in range(len(colors) - 1):
                v0, c0 = colors[k]
                v1, c1 = colors[k + 1]
                if v0 <= v <= v1:
                    f = (v - v0) / (v1 - v0)
                    lut[i] = [c(c0[j] + f * (c1[j] - c0[j])) for j in range(3)]
                    break
    elif name == "RdBu_r":
        colors = [
            (0.000, (5,   48,  97)),
            (0.250, (33,  102, 172)),
            (0.375, (103, 169, 207)),
            (0.450, (209, 229, 240)),
            (0.500, (247, 247, 247)),
            (0.550, (253, 219, 199)),
            (0.625, (239, 138, 98)),
            (0.750, (178, 24,  43)),
            (1.000, (103, 0,   31)),
        ]
        for i, v in enumerate(t):
            for k in range(len(colors) - 1):
                v0, c0 = colors[k]
                v1, c1 = colors[k + 1]
                if v0 <= v <= v1:
                    f = (v - v0) / (v1 - v0)
                    lut[i] = [c(c0[j] + f * (c1[j] - c0[j])) for j in range(3)]
                    break
    elif name == "Viridis":
        colors = [
            (0.000, (68,  1,   84)),
            (0.250, (59,  82,  139)),
            (0.500, (33,  145, 140)),
            (0.750, (94,  201, 98)),
            (1.000, (253, 231, 37)),
        ]
        for i, v in enumerate(t):
            for k in range(len(colors) - 1):
                v0, c0 = colors[k]
                v1, c1 = colors[k + 1]
                if v0 <= v <= v1:
                    f = (v - v0) / (v1 - v0)
                    lut[i] = [c(c0[j] + f * (c1[j] - c0[j])) for j in range(3)]
                    break
    elif name == "YlOrRd":
        colors = [
            (0.000, (255, 255, 204)),
            (0.250, (254, 217, 118)),
            (0.500, (253, 141, 60)),
            (0.750, (227, 26,  28)),
            (1.000, (128, 0,   38)),
        ]
        for i, v in enumerate(t):
            for k in range(len(colors) - 1):
                v0, c0 = colors[k]
                v1, c1 = colors[k + 1]
                if v0 <= v <= v1:
                    f = (v - v0) / (v1 - v0)
                    lut[i] = [c(c0[j] + f * (c1[j] - c0[j])) for j in range(3)]
                    break
    elif name == "Hot_r":
        colors = [
            (0.000, (255, 255, 255)),
            (0.333, (255, 255, 0)),
            (0.667, (255, 0,   0)),
            (1.000, (0,   0,   0)),
        ]
        for i, v in enumerate(t):
            for k in range(len(colors) - 1):
                v0, c0 = colors[k]
                v1, c1 = colors[k + 1]
                if v0 <= v <= v1:
                    f = (v - v0) / (v1 - v0)
                    lut[i] = [c(c0[j] + f * (c1[j] - c0[j])) for j in range(3)]
                    break
    else:
        lut[:, 0] = lut[:, 1] = lut[:, 2] = np.arange(n, dtype=np.uint8)
    return lut


COLORMAPS = {
    "s1": ("RdYlBu_r", False),
    "s2": ("RdBu_r",   True),
    "s3": ("Viridis",  False),
    "s4": ("YlOrRd",   False),
    "s5": ("RdBu_r",   True),
    "s6": ("Hot_r",    False),
    "s7": ("RdBu_r",   True),
}

_LUTS = {nm: _make_lut(nm) for nm in set(n for n, _ in COLORMAPS.values())}

# ──────────────────────────────────────────────
# Section metadata
# ──────────────────────────────────────────────
SECTIONS = [
    {"id": "s1", "label": "Климатологическое среднее ТПО",          "unit": "°C",              "symmetric": False},
    {"id": "s2", "label": "Линейный тренд ТПО (p<0.05)",            "unit": "°C/дек",          "symmetric": True},
    {"id": "s3", "label": "Коэффициент детерминации тренда (R²)",   "unit": "",                "symmetric": False},
    {"id": "s4", "label": "Дисперсия ТПО",                          "unit": "°C²",             "symmetric": False},
    {"id": "s5", "label": "Тренд дисперсии ТПО",                    "unit": "°C²/дек",         "symmetric": True},
    {"id": "s7", "label": "Аномалии ТПО",                           "unit": "°C",              "symmetric": True},
]

MON_LABELS = ["Январь","Февраль","Март","Апрель","Май","Июнь",
              "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"]

# ──────────────────────────────────────────────
# Percentile → (lo, hi) mapping for colorscale clipping
# ──────────────────────────────────────────────
def _pct_bounds(percentile: float) -> tuple[float, float]:
    """Return (lo, hi) percentile bounds for vmin/vmax computation."""
    p = float(percentile)
    if p >= 100:
        return (0.0, 100.0)
    elif p >= 99.9:
        return (0.1, 99.9)
    else:
        return (1.0, 99.0)

# ──────────────────────────────────────────────
# Core field renderer → PNG bytes
# ──────────────────────────────────────────────
def _render(field: np.ndarray, cmap: str, land_mask: np.ndarray,
            vmin_ov=None, vmax_ov=None, symmetric: bool = False,
            percentile: float = 99) -> tuple[bytes, float, float]:
    lut   = _LUTS[cmap]
    valid = field[~land_mask & np.isfinite(field)]

    if valid.size == 0:
        vmin, vmax = 0.0, 1.0
    elif vmin_ov is not None:
        vmin, vmax = float(vmin_ov), float(vmax_ov)
    elif symmetric:
        lo, hi = _pct_bounds(percentile)
        if hi >= 100:
            vm = float(np.max(np.abs(valid)))
        else:
            vm = float(np.percentile(np.abs(valid), hi))
        vmin, vmax = -vm, vm
    else:
        lo, hi = _pct_bounds(percentile)
        if lo <= 0 and hi >= 100:
            vmin = float(np.min(valid))
            vmax = float(np.max(valid))
        else:
            vmin = float(np.percentile(valid, lo))
            vmax = float(np.percentile(valid, hi))

    if vmax == vmin:
        vmax = vmin + 1.0

    NLAT, NLON = field.shape
    img  = np.zeros((NLAT, NLON, 4), dtype=np.uint8)
    norm = np.where(np.isfinite(field),
                    np.clip((field - vmin) / (vmax - vmin), 0, 1), 0.0)
    idx  = (norm * 255).astype(np.uint8)

    ocean = ~land_mask & np.isfinite(field)
    img[ocean, :3] = lut[idx[ocean]]
    img[ocean, 3]  = 255

    # NaN ocean → translucent dark
    img[~land_mask & ~np.isfinite(field)] = [20, 20, 30, 80]
    # land stays transparent

    pil = Image.fromarray(img, "RGBA")
    # Smooth: 2× upscale for nicer appearance
    ow, oh = pil.size
    pil = pil.resize((ow * 2, oh * 2), Image.Resampling.BILINEAR)
    buf = io.BytesIO()
    pil.save(buf, format="PNG", optimize=False)
    return buf.getvalue(), vmin, vmax


def _compute_s7_field(season_type: str, season_idx: int,
                      year: int, clim_period: str) -> np.ndarray:
    meta      = _load("meta")
    years_a   = meta["years"]
    months_a  = meta["months"]
    land_mask = meta["land_mask"]
    raw_sst   = _load("sst_raw")["sst"]
    s7        = _load("s7")
    clim_key  = f"clim_{clim_period}"
    if clim_key not in s7:
        raise HTTPException(400, f"Unknown clim_period: {clim_period}")
    clim = s7[clim_key]

    idx = np.where((years_a == year) & (months_a - 1 == season_idx))[0]
    if len(idx) == 0:
        return np.full(land_mask.shape, np.nan, dtype=np.float32)
    field = raw_sst[idx[0]].astype(np.float32) - clim[season_idx]

    field[land_mask] = np.nan
    return field.astype(np.float32)


# ── S5 per-month on-the-fly cache ──
_s5_monthly_cache: dict = {}

def _get_s5_monthly_field(month_idx: int, meta: dict) -> np.ndarray:
    """Trend of interannual variance for a specific calendar month (10-year rolling window).
    Gives per-month variation instead of the precomputed annual-only trend."""
    if month_idx in _s5_monthly_cache:
        return _s5_monthly_cache[month_idx]

    raw       = _load("sst_raw")["sst"]
    years_a   = meta["years"]
    months_a  = meta["months"]
    land_mask = meta["land_mask"]
    NLAT, NLON = land_mask.shape

    # Collect one frame per year for this calendar month
    all_years = sorted(set(int(y) for y in years_a))
    frames, yr_list = [], []
    for yr in all_years:
        ix = np.where((years_a == yr) & (months_a - 1 == month_idx))[0]
        if len(ix):
            frames.append(raw[ix[0]].astype(np.float32))
            yr_list.append(float(yr))

    if len(frames) < 10:
        result = np.full((NLAT, NLON), np.nan, dtype=np.float32)
        _s5_monthly_cache[month_idx] = result
        return result

    stack  = np.stack(frames)            # (N, NLAT, NLON)
    yr_arr = np.array(yr_list)
    N      = len(yr_list)
    W      = 10                          # 10-year rolling window

    # Compute rolling variance
    rv_list, ry_list = [], []
    for start in range(N - W + 1):
        rv_list.append(np.nanvar(stack[start:start + W], axis=0))   # (NLAT, NLON)
        ry_list.append(yr_arr[start + W // 2])

    rv    = np.stack(rv_list)            # (n_win, NLAT, NLON)
    ry    = np.array(ry_list, dtype=np.float64)
    ry_c  = ry - ry.mean()
    sx2   = float(np.dot(ry_c, ry_c))

    if sx2 == 0:
        result = np.full((NLAT, NLON), np.nan, dtype=np.float32)
        _s5_monthly_cache[month_idx] = result
        return result

    n_win  = len(ry)
    rv_2d  = rv.reshape(n_win, NLAT * NLON)
    valid  = np.sum(np.isfinite(rv_2d), axis=0)                     # (NLAT*NLON,)
    filled = np.where(np.isfinite(rv_2d), rv_2d, 0.0)

    # Vectorised OLS slope (×10 for per-decade)
    slopes = (np.dot(ry_c, filled) / sx2).reshape(NLAT, NLON).astype(np.float32)
    slopes[valid.reshape(NLAT, NLON) < 5] = np.nan
    slopes[land_mask] = np.nan
    result = (slopes * 10.0).astype(np.float32)

    _s5_monthly_cache[month_idx] = result
    logger.info("s5_monthly[%d] computed: finite=%d", month_idx, int(np.sum(np.isfinite(result))))
    return result


# ── Mercator constants (lon 117-246°, lat 26-72°) ──
_EARTH_CIRC = 40075016.685578488  # meters, WGS-84 equatorial circumference

def _mercator_extent():
    """Return (x_min, y_min, x_max, y_max) in EPSG:3857 for the data domain."""
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    x_min, y_min = tr.transform(117.0, 26.0)
    x_max         = x_min + (246.0 - 117.0) / 360.0 * _EARTH_CIRC
    _, y_max      = tr.transform(0.0, 72.0)
    return x_min, y_min, x_max, y_max

_MERC_EXTENT = _mercator_extent()   # computed once at import time

# ── Ocean mask — loaded from precomputed Natural Earth rasterization ──
_ocean_mask: Optional[np.ndarray] = None

def _load_ocean_mask(width: int = 1200, height: int = 550) -> Optional[np.ndarray]:
    """Load precomputed Natural Earth ocean mask (data/ocean_mask.npy).

    Returns bool array True=ocean, False=land, shape (height, width).
    Returns None if the file hasn't been generated yet (run precompute_coastline.py).
    """
    global _ocean_mask
    if _ocean_mask is not None:
        return _ocean_mask
    path = os.path.join(DATA_DIR, "ocean_mask.npy")
    if not os.path.exists(path):
        logger.warning("ocean_mask.npy not found — run precompute_coastline.py")
        return None
    mask = np.load(path)
    if mask.shape != (height, width):
        logger.warning("ocean_mask.npy shape %s != (%d,%d)", mask.shape, height, width)
        return None
    _ocean_mask = mask.astype(bool)
    logger.info("Natural Earth ocean mask loaded: %d ocean pixels", int(_ocean_mask.sum()))
    return _ocean_mask


def _fill_land_nans(field: np.ndarray, land_mask: Optional[np.ndarray] = None) -> np.ndarray:
    """Fill NaN land pixels with nearest ocean values for smooth coastline extrapolation.

    Only land pixels (land_mask=True) are filled.  Ocean NaN pixels (e.g.
    trend p>=0.05, insufficient data) remain NaN so they render as transparent.
    If land_mask is None, fills all NaN pixels (backward-compat fallback).
    """
    from scipy.ndimage import distance_transform_edt
    nan_mask = ~np.isfinite(field)
    if not nan_mask.any():
        return field

    # Determine which pixels to fill
    if land_mask is not None:
        fill_target = nan_mask & land_mask     # only land NaN pixels
    else:
        fill_target = nan_mask                 # all NaN (fallback)

    # Do NOT fill pixels at the domain boundary rows/cols — they cause
    # colour-bleed lines along the rectangular AOI edge after Mercator projection.
    # Extrapolation is only needed for coastal land pixels in the interior.
    fill_target[[0, -1], :] = False
    fill_target[:, [0, -1]] = False

    if not fill_target.any():
        return field                           # nothing to fill

    # Background for EDT = finite ocean pixels (source of fill values)
    bg = np.isfinite(field) & (True if land_mask is None else ~land_mask)
    if not bg.any():
        bg = np.isfinite(field)               # fallback: any finite pixel
    if not bg.any():
        filled = field.copy()
        filled[fill_target] = 0.0
        return filled

    _, indices = distance_transform_edt(~bg, return_distances=True, return_indices=True)
    r = np.clip(indices[0], 0, field.shape[0] - 1)
    c = np.clip(indices[1], 0, field.shape[1] - 1)
    filled = field.copy()
    filled[fill_target] = field[r, c][fill_target]
    return filled


def _overlay_contours(img, vals: np.ndarray, finite: np.ndarray,
                      vmin: float, vmax: float, ocean_mask_s,
                      show_labels: bool = False,
                      lut: "np.ndarray | None" = None) -> "PIL.Image.Image":
    """Overlay isoline contours (and optional value labels) on a PIL RGBA image."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib.figure import Figure
        import matplotlib.path as mpath
        from PIL import Image as _PIL, ImageDraw, ImageFont

        H, W = vals.shape
        n_levels = 8
        levels = np.linspace(vmin, vmax, n_levels + 2)[1:-1]

        vals_c = np.where(finite, vals, np.nan)

        fig = Figure()
        ax  = fig.add_axes([0, 0, 1, 1])
        CS  = ax.contour(vals_c, levels=levels)

        cont_overlay = _PIL.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(cont_overlay, "RGBA")
        CONT_COLOR = (20, 30, 60, 55)

        MOVETO    = mpath.Path.MOVETO
        CLOSEPOLY = mpath.Path.CLOSEPOLY

        for path in CS.get_paths():
            verts = path.vertices
            codes = path.codes
            if codes is None:
                codes = [MOVETO] + [mpath.Path.LINETO] * (len(verts) - 1)
            seg = []
            for (x, y), code in zip(verts, codes):
                if code == MOVETO:
                    if len(seg) >= 2:
                        draw.line(seg, fill=CONT_COLOR, width=2)
                    seg = [(float(x), float(y))]
                elif code == CLOSEPOLY:
                    if seg:
                        seg.append(seg[0])
                        draw.line(seg, fill=CONT_COLOR, width=2)
                    seg = []
                else:
                    seg.append((float(x), float(y)))
            if len(seg) >= 2:
                draw.line(seg, fill=CONT_COLOR, width=2)

        # Draw value labels — smart text colour matching the colourscale, no background
        if show_labels:
            try:
                fmt_comma = lambda x: f"{x:.1f}".replace(".", ",")
                label_texts = ax.clabel(CS, inline=True, fontsize=7, fmt=fmt_comma)
                # Filter overlapping labels — keep only those > MIN_DIST pixels apart
                MIN_DIST_SQ = 80 ** 2
                kept = []
                for lt in label_texts:
                    px_l, py_l = lt.get_position()
                    if not any((px_l - k.get_position()[0])**2 +
                               (py_l - k.get_position()[1])**2 < MIN_DIST_SQ
                               for k in kept):
                        kept.append(lt)
                label_texts = kept
                _FONT_CANDIDATES = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
                    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                ]
                font = None
                for _fp in _FONT_CANDIDATES:
                    if os.path.exists(_fp):
                        try:
                            font = ImageFont.truetype(_fp, size=12)
                        except Exception:
                            pass
                        break
                if font is None:
                    try:
                        font = ImageFont.load_default(size=12)
                    except TypeError:
                        font = ImageFont.load_default()
                for lt in label_texts:
                    lx, ly = lt.get_position()
                    text = lt.get_text().strip()
                    try:
                        bb = draw.textbbox((0, 0), text, font=font)
                        tw, th = bb[2] - bb[0], bb[3] - bb[1]
                    except AttributeError:
                        tw, th = len(text) * 6, 9
                    px, py = int(lx) - tw // 2, int(ly) - th // 2
                    if lut is not None:
                        try:
                            lv = float(text.replace(',', '.'))
                        except ValueError:
                            lv = (vmin + vmax) / 2
                        norm_v = np.clip((lv - vmin) / (vmax - vmin + 1e-10), 0, 1)
                        bg_rgb = lut[int(norm_v * 255)]
                        lum = (0.299 * bg_rgb[0] + 0.587 * bg_rgb[1] + 0.114 * bg_rgb[2]) / 255
                        fg = (30, 30, 30, 240) if lum > 0.45 else (230, 230, 230, 240)
                    else:
                        fg = (30, 30, 30, 240)
                    draw.text((px, py), text, fill=fg, font=font)
            except Exception as le:
                logger.debug("Contour label drawing failed: %s", le)

        fig.clf()
        del fig

        # Mask contour overlay over land / outside domain
        if ocean_mask_s is not None:
            cont_arr = np.asarray(cont_overlay).copy()
            cont_arr[~ocean_mask_s, 3] = 0
            cont_overlay = _PIL.fromarray(cont_arr, "RGBA")

        return _PIL.alpha_composite(img, cont_overlay)

    except Exception as e:
        logger.warning("Contour overlay failed: %s", e)
        return img


def _render_mercator(field: np.ndarray, lat_arr: np.ndarray, lon_arr: np.ndarray,
                     cmap: str, vmin: float, vmax: float,
                     land_mask: Optional[np.ndarray] = None,
                     width: int = 1200, height: int = 550,
                     scale: int = 1,
                     blur: bool = True,
                     contours: bool = True,
                     contour_labels: bool = False) -> bytes:
    """Render a 2D SST field to a Mercator-projected RGBA PNG."""
    from pyproj import Transformer
    from scipy.interpolate import RegularGridInterpolator

    W = width  * scale
    H = height * scale

    x_min, y_min, x_max, y_max = _MERC_EXTENT

    xs = np.linspace(x_min, x_max, W)
    ys = np.linspace(y_max, y_min, H)
    X, Y = np.meshgrid(xs, ys)

    inv = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    lons_grid, lats_grid = inv.transform(X, Y)
    lons_grid = lons_grid % 360.0

    # Ensure increasing lat axis
    if lat_arr[0] > lat_arr[-1]:
        lat_inc   = lat_arr[::-1]
        field_rc  = field[::-1, :]
        lm_rc     = land_mask[::-1, :] if land_mask is not None else None
    else:
        lat_inc   = lat_arr
        field_rc  = field
        lm_rc     = land_mask

    # Fill only land NaN pixels → data extends to Natural Earth coastline
    # Ocean NaN pixels (e.g. trend p>=0.05) stay NaN → rendered transparent
    field_filled = _fill_land_nans(field_rc, lm_rc)

    interp = RegularGridInterpolator(
        (lat_inc, lon_arr), field_filled,
        method="linear", bounds_error=False, fill_value=np.nan)

    pts  = np.stack([lats_grid.ravel(), lons_grid.ravel()], axis=1)
    vals = interp(pts).reshape(H, W)

    # Nullify pixels within 3 ERA5 grid cells of the domain boundary.
    lat_step = float(abs(lat_arr[1] - lat_arr[0]))
    lon_step = float(abs(lon_arr[1] - lon_arr[0]))
    _lat_lo  = float(lat_arr.min()) + lat_step * 5
    _lat_hi  = float(lat_arr.max()) - lat_step * 5
    _lon_lo  = float(lon_arr.min()) + lon_step * 5
    _lon_hi  = float(lon_arr.max()) - lon_step * 5
    edge_mask = ((lats_grid < _lat_lo) | (lats_grid > _lat_hi) |
                 (lons_grid < _lon_lo) | (lons_grid > _lon_hi))
    vals[edge_mask] = np.nan

    # Colorize — NaN pixels remain identified
    lut      = _LUTS[cmap]
    finite   = np.isfinite(vals)
    safe     = np.where(finite, vals, vmin)
    norm     = np.clip((safe - vmin) / (vmax - vmin + 1e-10), 0.0, 1.0)
    idx      = (norm * 255).astype(np.uint8)

    rgba = np.zeros((H, W, 4), dtype=np.uint8)
    rgba[:, :, :3] = lut[idx]
    rgba[~finite, 3] = 0

    from PIL import Image as _PIL, ImageEnhance as _IE, ImageFilter as _IF

    # Optional Gaussian blur (smooths pixel edges, e.g. for trend maps)
    if blur:
        from scipy.ndimage import distance_transform_edt
        nf = ~finite
        nf_interior = nf & ~edge_mask
        if nf_interior.any() and finite.any():
            _, nn = distance_transform_edt(~finite | edge_mask, return_indices=True)
            rgba[nf_interior, :3] = rgba[nn[0][nf_interior], nn[1][nf_interior], :3]
        rgb_arr = _PIL.fromarray(rgba[:, :, :3], "RGB")
        rgb_arr = rgb_arr.filter(_IF.GaussianBlur(radius=1.2))
        rgba[:, :, :3] = np.asarray(rgb_arr)

    # Hard-zero edge pixels after blur
    rgba[edge_mask, 3] = 0
    rgba[edge_mask, :3] = 0

    # Apply Natural Earth coastline mask: land → transparent
    ocean_mask_data = _load_ocean_mask(width, height)
    ocean_mask_s    = None
    if ocean_mask_data is not None:
        if scale > 1:
            om_img = _PIL.fromarray(ocean_mask_data.astype(np.uint8) * 255)
            om_img = om_img.resize((W, H), resample=_PIL.NEAREST)
            ocean_mask_s = np.asarray(om_img) > 127
        else:
            ocean_mask_s = ocean_mask_data
        rgba[ ocean_mask_s, 3]  = np.where(finite[ocean_mask_s], 255, 0)
        rgba[~ocean_mask_s, 3]  = 0
        rgba[~ocean_mask_s, :3] = 0
    else:
        rgba[finite, 3] = 255

    # Project ERA5 land mask onto Mercator grid
    if lm_rc is not None:
        interp_lm = RegularGridInterpolator(
            (lat_inc, lon_arr), lm_rc.astype(np.float32),
            method="nearest", bounds_error=False, fill_value=1.0)
        land_merc = interp_lm(pts).reshape(H, W) > 0.5
        rgba[land_merc, 3] = 0
        rgba[land_merc, :3] = 0

    # Final hard-zero of edge pixels
    rgba[edge_mask, 3] = 0
    rgba[edge_mask, :3] = 0

    img = _PIL.fromarray(rgba, "RGBA")
    r, g, b, a = img.split()
    rgb = _PIL.merge("RGB", (r, g, b))
    rgb = _IE.Color(rgb).enhance(1.3)
    r2, g2, b2 = rgb.split()
    img = _PIL.merge("RGBA", (r2, g2, b2, a))

    # Overlay isoline contours (skipped when contours=False)
    if contours:
        img = _overlay_contours(img, vals, finite, vmin, vmax, ocean_mask_s,
                                show_labels=contour_labels, lut=lut)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    return buf.getvalue()


# ── PNG cache ──
_png_cache: dict = {}

def _compute_full_field(section: str, season_type: str, season_idx: int,
                        year: Optional[int], clim_period: str,
                        meta: dict) -> tuple[np.ndarray, Optional[float], Optional[float]]:
    """Compute a 2D field. Returns (field, vmin_override, vmax_override)."""
    land_mask = meta["land_mask"]
    cmap, sym = COLORMAPS[section]

    if section == "s7":
        years_a = meta["years"]
        if year is None:
            year = int(years_a[-1])
        s7 = _load("s7")
        anom_vm = float(s7.get("anom_vm_99", s7["anom_vm"]))

        if season_type == "monthly":
            field = _compute_s7_field(season_type, season_idx, year, clim_period)
        else:
            raw_sst  = _load("sst_raw")["sst"]
            months_a = meta["months"]
            clim     = s7[f"clim_{clim_period}"]
            frames, clim_frames = [], []
            for mo1 in range(1, 13):
                ix = np.where((years_a == year) & (months_a == mo1))[0]
                if len(ix):
                    frames.append(raw_sst[ix[0]].astype(np.float32))
                    clim_frames.append(clim[mo1 - 1].astype(np.float32))
            if not frames:
                field = np.full(land_mask.shape, np.nan, dtype=np.float32)
            else:
                field = np.nanmean(frames, axis=0) - np.nanmean(clim_frames, axis=0)
            field[land_mask] = np.nan
        return field, -anom_vm, anom_vm

    elif season_type == "annual":
        data    = _load(section)
        mon_key = f"monthly_{clim_period}" if f"monthly_{clim_period}" in data else "monthly"
        fields  = [data[mon_key][m].astype(np.float32) for m in range(12)]
        field   = np.nanmean(fields, axis=0)
        field[land_mask] = np.nan
        return field, None, None

    elif section == "s5" and season_type == "monthly":
        # Use period-specific precomputed data when available
        data_s5   = _load("s5")
        period_key = f"monthly_{clim_period}"
        if period_key in data_s5:
            field = data_s5[period_key][season_idx].astype(np.float32)
            field[land_mask] = np.nan
        else:
            field = _get_s5_monthly_field(season_idx, meta)
        return field, None, None
    else:
        data       = _load(section)
        key2       = "monthly"
        period_key = f"{key2}_{clim_period}"
        field = data[period_key][season_idx].astype(np.float32) if period_key in data else data[key2][season_idx].astype(np.float32)
        return field, None, None


def _get_field_png(section: str, season_type: str, season_idx: int,
                   year: Optional[int] = None,
                   clim_period: str = "1991_2020",
                   percentile: float = 99,
                   half: Optional[str] = None,
                   scale: int = 1,
                   blur: bool = True,
                   contours: bool = True,
                   contour_labels: bool = False) -> tuple[bytes, float, float]:
    key = (section, season_type, season_idx, year, clim_period, percentile, half, scale, blur,
           contours, contour_labels)
    if key in _png_cache:
        return _png_cache[key]

    meta      = _load("meta")
    lat_arr   = np.asarray(meta["lat"]).ravel()
    lon_arr   = np.asarray(meta["lon"]).ravel()
    land_mask = meta["land_mask"]
    cmap, sym = COLORMAPS[section]

    field, vmin_ov, vmax_ov = _compute_full_field(
        section, season_type, season_idx, year, clim_period, meta)

    # For s7, select anom_vm based on percentile parameter
    if section == "s7" and vmin_ov is not None:
        s7 = _load("s7")
        pct = float(percentile)
        if pct >= 100:
            anom_vm = float(s7.get("anom_vm_100", s7["anom_vm"]))
        elif pct >= 99.9:
            anom_vm = float(s7.get("anom_vm_999", s7["anom_vm"]))
        else:
            anom_vm = float(s7.get("anom_vm_99", s7["anom_vm"]))
        vmin_ov, vmax_ov = -anom_vm, anom_vm

    # Compute vmin/vmax from FULL field
    if vmin_ov is None:
        valid = field[~land_mask & np.isfinite(field)]
        if valid.size == 0:
            vmin_ov, vmax_ov = 0.0, 1.0
        elif sym:
            lo, hi = _pct_bounds(percentile)
            vm = float(np.max(np.abs(valid))) if hi >= 100 else float(np.percentile(np.abs(valid), hi))
            vmin_ov, vmax_ov = -vm, vm
        else:
            lo, hi = _pct_bounds(percentile)
            vmin_ov = float(np.min(valid)) if lo <= 0 else float(np.percentile(valid, lo))
            vmax_ov = float(np.max(valid)) if hi >= 100 else float(np.percentile(valid, hi))
    if vmax_ov == vmin_ov:
        vmax_ov = vmin_ov + 1.0

    logger.info("field.shape=%s vmin=%.3f vmax=%.3f", field.shape, vmin_ov, vmax_ov)

    png = _render_mercator(field, lat_arr, lon_arr, cmap, float(vmin_ov), float(vmax_ov),
                          land_mask=land_mask, scale=scale, blur=blur,
                          contours=contours, contour_labels=contour_labels)
    result = (png, float(vmin_ov), float(vmax_ov))
    _png_cache[key] = result
    return result


def _get_tick_values(section: str) -> np.ndarray:
    """Return precomputed percentile tick values for legend."""
    data = _load(section)
    if "pcts" in data:
        return data["pcts"].astype(np.float64)
    return np.array([])


def _fmt_tick_prec(v: float, prec: int) -> str:
    """Format tick value with given decimal places, using comma as decimal separator."""
    s = f"{v:.{prec}f}"
    return s.replace('.', ',')


# ──────────────────────────────────────────────
# API Routes
# ──────────────────────────────────────────────

@sst_router.get("/api/meta")
def api_meta():
    try:
        meta = _load("meta")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to load meta.npz: %s", e, exc_info=True)
        raise HTTPException(500, f"Failed to load meta.npz: {e}")

    try:
        lat_arr = np.asarray(meta["lat"]).ravel()
        lon_arr = np.asarray(meta["lon"]).ravel()
    except Exception as e:
        logger.error("Cannot read lat/lon from meta: %s", e, exc_info=True)
        raise HTTPException(500, f"Cannot read lat/lon: {e}")

    # Antimeridian split
    try:
        lon_split_idx = int(np.searchsorted(lon_arr, 180.0))
        lon_split_val = float(lon_arr[lon_split_idx]) if lon_split_idx < len(lon_arr) else 180.0
    except Exception as e:
        logger.warning("lon split computation failed: %s", e)
        lon_split_idx = int(len(lon_arr) // 2)
        lon_split_val = 180.0

    # date_strings
    try:
        if "date_strings" in meta:
            dates = []
            for d in meta["date_strings"]:
                dates.append(d.decode("utf-8") if isinstance(d, (bytes, np.bytes_)) else str(d))
        else:
            years_a  = np.asarray(meta["years"]).ravel()
            months_a = np.asarray(meta["months"]).ravel()
            dates = [f"{int(y):04d}-{int(m):02d}-01" for y, m in zip(years_a, months_a)]
    except Exception as e:
        logger.warning("date_strings fallback failed: %s", e)
        dates = []

    # years
    try:
        years = sorted(set(int(y) for y in np.asarray(meta["years"]).ravel()))
    except Exception as e:
        logger.warning("years extraction failed: %s", e)
        years = []

    # last complete year (has all 12 months in the data)
    try:
        from collections import Counter as _Counter
        yr_count = _Counter(int(y) for y in np.asarray(meta["years"]).ravel())
        complete_yrs = sorted(y for y, c in yr_count.items() if c == 12)
        last_complete_year = int(complete_yrs[-1]) if complete_yrs else (years[-1] if years else None)
    except Exception as e:
        logger.warning("last_complete_year failed: %s", e)
        last_complete_year = years[-1] if years else None

    # anom_vm
    anom_vm = 2.6
    try:
        if "anom_vm" in meta:
            anom_vm = float(np.asarray(meta["anom_vm"]).flat[0])
        else:
            s7 = _load("s7")
            for key in ("anom_vm_99", "anom_vm", "anom_vm_999", "anom_vm_100"):
                if key in s7:
                    anom_vm = float(np.asarray(s7[key]).flat[0])
                    break
    except Exception as e:
        logger.warning("anom_vm fallback, using 2.6: %s", e)

    lat = lat_arr.tolist()
    lon = lon_arr.tolist()
    x_min, y_min, x_max, y_max = _MERC_EXTENT
    logger.info("api_meta: lat %s..%s  lon %s..%s  years %s  dates %d",
                lat[0], lat[-1], lon[0], lon[-1],
                f"{years[0]}–{years[-1]}" if years else "?", len(dates))
    return {
        "lat":                {"min": float(min(lat)), "max": float(max(lat)), "n": len(lat)},
        "lon":                {"min": float(min(lon)), "max": float(max(lon)), "n": len(lon)},
        "lon_split_idx":      lon_split_idx,
        "lon_split_val":      lon_split_val,
        "dates":              dates,
        "years":              years,
        "last_complete_year": last_complete_year,
        "sections":           SECTIONS,
        "monthly_labels":     MON_LABELS,
        "anom_vm":            anom_vm,
        "mercator_extent":    [x_min, y_min, x_max, y_max],
        "server_ts":          _SERVER_START_TS,
    }


@sst_router.get("/api/map/{section}/{season_type}/{season_idx}.png")
def api_map_png(section: str, season_type: str, season_idx: int,
                year: Optional[int] = None,
                clim_period: str = "1991_2020",
                percentile: float = 99,
                half: Optional[str] = None,
                scale: int = 1,
                blur: bool = True,
                contours: bool = True,
                contour_labels: bool = False):
    if section not in COLORMAPS:
        raise HTTPException(404, "Unknown section")
    if season_type not in ("monthly", "annual"):
        raise HTTPException(400, "season_type must be monthly|annual")
    if half not in (None, "west", "east"):
        raise HTTPException(400, "half must be west|east or omitted")
    scale = max(1, min(scale, 3))
    logger.info("map %s/%s/%s half=%s year=%s pct=%s scale=%s blur=%s contours=%s labels=%s",
                section, season_type, season_idx, half, year, percentile, scale, blur, contours, contour_labels)
    try:
        png, _, _ = _get_field_png(section, season_type, season_idx, year, clim_period,
                                   percentile, half, scale, blur, contours, contour_labels)
    except HTTPException:
        raise
    except Exception as e:
        import traceback as _tb
        logger.error("Map error %s/%s/%s half=%s: %s\n%s",
                     section, season_type, season_idx, half, e, _tb.format_exc())
        raise HTTPException(500, str(e))
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "no-store"})


_coastline_cache: dict = {}

# ── shared helpers for both coastline endpoints ────────────────────────────
_COAST_LON_MIN, _COAST_LON_MAX = 117.0, 246.0
_COAST_LAT_MIN, _COAST_LAT_MAX = 26.0,  72.0
_COAST_W, _COAST_H             = 1200,  550
_EARTH_CIRC_COAST               = 40075016.685578488

def _coast_boxes():
    from shapely.geometry import box as _box
    M      = 1.0
    M_ANTI = 5.0
    return (
        _box(_COAST_LON_MIN - M, _COAST_LAT_MIN - M, 180.0 + M_ANTI, _COAST_LAT_MAX + M),
        _box(-180.0 - M_ANTI,    _COAST_LAT_MIN - M, -(360.0 - _COAST_LON_MAX) - M, _COAST_LAT_MAX + M),
    )

def _coast_projection():
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    x0, _ = tr.transform(_COAST_LON_MIN, _COAST_LAT_MIN)
    x1    = x0 + (_COAST_LON_MAX - _COAST_LON_MIN) / 360.0 * _EARTH_CIRC_COAST
    _, y1 = tr.transform(0.0, _COAST_LAT_MAX)
    _, y0 = tr.transform(0.0, _COAST_LAT_MIN)
    return tr, x0, x1, y0, y1

def _coast_to_px(lon_std, lat, east, tr, x0, x1, y0, y1):
    mx, my = tr.transform(lon_std, lat)
    if east:
        mx += _EARTH_CIRC_COAST
    px = (mx - x0) / (x1 - x0) * _COAST_W
    py = (y1 - my) / (y1 - y0) * _COAST_H
    return px, py

def _load_coast_geojson():
    import json
    path = os.path.join(DATA_DIR, "ne_10m_land.geojson")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@sst_router.get("/api/coastline.svg")
def api_coastline_svg():
    """Vector coastline pre-projected to 1200x550 Mercator pixel space."""
    if "svg" in _coastline_cache:
        return Response(content=_coastline_cache["svg"], media_type="image/svg+xml",
                        headers={"Cache-Control": "public, max-age=86400"})
    from shapely.geometry import shape
    from shapely.validation import make_valid

    geo = _load_coast_geojson()
    if geo is None:
        raise HTTPException(404, "ne_10m_land.geojson not found — run precompute_coastline.py")

    BOX_W, BOX_E = _coast_boxes()
    tr, x0, x1, y0, y1 = _coast_projection()

    def ring_to_path(coords, east):
        pts = []
        prev_px = None
        for lon, lat in coords:
            try:
                px, py = _coast_to_px(lon, lat, east, tr, x0, x1, y0, y1)
            except Exception:
                continue
            if prev_px is not None and abs(px - prev_px) > _COAST_W * 0.3:
                pts.append(None)
            pts.append((px, py))
            prev_px = px
        if not pts:
            return ""
        segments, cur = [], []
        for p in pts:
            if p is None:
                if len(cur) >= 2:
                    segments.append(cur)
                cur = []
            else:
                cur.append(p)
        if len(cur) >= 2:
            segments.append(cur)
        d = ""
        for seg in segments:
            d += f"M{seg[0][0]:.1f},{seg[0][1]:.1f}"
            for px, py in seg[1:]:
                d += f"L{px:.1f},{py:.1f}"
        return d

    def geom_to_path(geom, east):
        polys = [geom] if geom.geom_type == "Polygon" else (
            [g for g in geom.geoms if g.geom_type == "Polygon"]
            if geom.geom_type in ("MultiPolygon", "GeometryCollection") else [])
        d = ""
        for poly in polys:
            if poly.is_empty:
                continue
            d += ring_to_path(poly.exterior.coords, east)
            for hole in poly.interiors:
                d += ring_to_path(hole.coords, east)
        return d

    all_d = ""
    for feat in geo["features"]:
        geom = shape(feat["geometry"])
        if not geom.is_valid:
            geom = make_valid(geom)
        geom = geom.simplify(0.08, preserve_topology=True)
        w = geom.intersection(BOX_W)
        if not w.is_empty:
            all_d += geom_to_path(w, False)
        e = geom.intersection(BOX_E)
        if not e.is_empty:
            all_d += geom_to_path(e, True)

    W, H = _COAST_W, _COAST_H
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">'
        f'<defs>'
        f'<filter id="bf" x="-2%" y="-2%" width="104%" height="104%">'
        f'<feGaussianBlur stdDeviation="0.7"/>'
        f'</filter>'
        f'</defs>'
        f'<path d="{all_d}" fill="none" filter="url(#bf)" '
        f'stroke="rgba(20,30,60,0.18)" stroke-width="2.5" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
        f'<path d="{all_d}" fill="none" '
        f'stroke="rgba(15,25,55,0.52)" stroke-width="0.7" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
        f'</svg>'
    )
    data = svg.encode("utf-8")
    _coastline_cache["svg"] = data
    return Response(content=data, media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=86400"})


@sst_router.get("/api/coastline.geojson")
def api_coastline_geojson():
    """Natural Earth land polygons clipped to domain, split west/east for OL rendering."""
    if "geojson" in _coastline_cache:
        return Response(content=_coastline_cache["geojson"],
                        media_type="application/geo+json",
                        headers={"Cache-Control": "public, max-age=86400"})
    import json
    from shapely.geometry import shape, mapping
    from shapely.validation import make_valid

    geo = _load_coast_geojson()
    if geo is None:
        raise HTTPException(404, "ne_10m_land.geojson not found")

    BOX_W, BOX_E = _coast_boxes()
    features = []
    for feat in geo["features"]:
        geom = shape(feat["geometry"])
        if not geom.is_valid:
            geom = make_valid(geom)
        geom = geom.simplify(0.08, preserve_topology=True)
        w = geom.intersection(BOX_W)
        if not w.is_empty:
            features.append({"type": "Feature", "geometry": mapping(w),
                              "properties": {"half": "west"}})
        e = geom.intersection(BOX_E)
        if not e.is_empty:
            features.append({"type": "Feature", "geometry": mapping(e),
                              "properties": {"half": "east"}})

    data = json.dumps({"type": "FeatureCollection", "features": features},
                      separators=(',', ':')).encode()
    _coastline_cache["geojson"] = data
    return Response(content=data, media_type="application/geo+json",
                    headers={"Cache-Control": "public, max-age=86400"})


@sst_router.get("/api/colorscale/{section}")
def api_colorscale(section: str,
                   season_type: str = "monthly",
                   season_idx: int = 0,
                   year: Optional[int] = None,
                   clim_period: str = "1991_2020",
                   percentile: float = 99,
                   half: Optional[str] = None):
    if section not in COLORMAPS:
        raise HTTPException(404, "Unknown section")
    _, vmin, vmax = _get_field_png(section, season_type, season_idx, year, clim_period, percentile, half)
    cmap, _  = COLORMAPS[section]
    unit     = next((s["unit"] for s in SECTIONS if s["id"] == section), "")
    rng      = vmax - vmin

    import math as _math
    tick_vals = _get_tick_values(section)
    # First pass: filter ticks by norm dedup
    filtered_vals, filtered_norms = [], []
    for v in tick_vals:
        v_f  = float(v)
        norm = (v_f - vmin) / rng if rng != 0 else 0.5
        norm = max(0.0, min(1.0, norm))
        if filtered_norms and abs(norm - filtered_norms[-1]) < 0.02:
            continue
        filtered_vals.append(v_f)
        filtered_norms.append(norm)

    # Compute optimal precision from minimum step between adjacent values
    if len(filtered_vals) >= 2:
        steps = [abs(filtered_vals[i+1] - filtered_vals[i])
                 for i in range(len(filtered_vals) - 1)]
        min_step = min(s for s in steps if s > 0) if any(s > 0 for s in steps) else rng
    else:
        min_step = rng if rng > 0 else 1.0
    if min_step > 0:
        prec = max(0, min(4, _math.ceil(-_math.log10(min_step))))
    else:
        prec = 2

    ticks = [
        {
            "value": round(v_f, 4),
            "label": _fmt_tick_prec(v_f, prec),
            "norm":  round(norm, 4),
        }
        for v_f, norm in zip(filtered_vals, filtered_norms)
    ]

    return {
        "vmin":  round(vmin, 4),
        "vmax":  round(vmax, 4),
        "unit":  unit,
        "cmap":  cmap,
        "lut":   _LUTS[cmap].tolist(),
        "ticks": ticks,
    }


@sst_router.get("/api/timeseries")
def api_timeseries(lat: float, lon: float):
    meta    = _load("meta")
    lat_arr = meta["lat"]
    lon_arr = meta["lon"]
    i = int(np.argmin(np.abs(lat_arr - lat)))
    j = int(np.argmin(np.abs(lon_arr - lon)))
    sst     = _load("sst_raw")["sst"]
    ts      = sst[:, i, j].tolist()
    dates   = [str(d) for d in meta["date_strings"]]
    return {
        "lat":   float(lat_arr[i]),
        "lon":   float(lon_arr[j]),
        "dates": dates,
        "sst":   [round(float(v), 3) if math.isfinite(float(v)) else None for v in ts],
    }


@sst_router.get("/api/anomaly/{year}/{month}")
def api_anomaly(year: int, month: int, clim_period: str = "1991_2020"):
    meta      = _load("meta")
    years_a   = meta["years"]
    months_a  = meta["months"]
    land_mask = meta["land_mask"]
    raw_sst   = _load("sst_raw")["sst"]
    s7        = _load("s7")
    clim_key  = f"clim_{clim_period}"
    if clim_key not in s7:
        raise HTTPException(400, f"Unknown clim_period: {clim_period}")
    clim = s7[clim_key]
    idx  = np.where((years_a == year) & (months_a == month))[0]
    if len(idx) == 0:
        raise HTTPException(404, f"No data for {year}-{month:02d}")
    field = raw_sst[idx[0]].astype(np.float32) - clim[month - 1]
    field[land_mask] = np.nan
    valid = field[np.isfinite(field)]
    return {
        "year": year, "month": month,
        "clim_period": clim_period,
        "mean":    round(float(np.nanmean(valid)), 3),
        "max":     round(float(np.nanmax(valid)),  3),
        "min":     round(float(np.nanmin(valid)),  3),
        "anom_vm": float(meta["anom_vm"]),
    }


@sst_router.get("/api/field_value")
def api_field_value(section: str, lat: float, lon: float,
                    season_type: str = "monthly", season_idx: int = 0,
                    year: Optional[int] = None,
                    clim_period: str = "1991_2020"):
    meta      = _load("meta")
    lat_arr   = meta["lat"]
    lon_arr   = meta["lon"]
    land_mask = meta["land_mask"]
    i = int(np.argmin(np.abs(lat_arr - lat)))
    j = int(np.argmin(np.abs(lon_arr - lon)))
    unit = next((s["unit"] for s in SECTIONS if s["id"] == section), "")
    if land_mask[i, j]:
        return {"value": None, "unit": unit}
    if section == "s7":
        if year is None:
            year = int(meta["years"][-1])
        field = _compute_s7_field(season_type, season_idx, year, clim_period)
        value = float(field[i, j])
    elif section == "s5" and season_type == "monthly":
        meta_s5 = _load("meta")
        field   = _get_s5_monthly_field(season_idx, meta_s5)
        value   = float(field[i, j])
    elif season_type == "monthly":
        data  = _load(section)
        arr   = data["monthly"]
        value = float(arr[season_idx][i, j])
    else:
        data  = _load(section)
        value = float(data["monthly"][season_idx][i, j])
    if not math.isfinite(value):
        return {"value": None, "unit": unit}
    return {"value": round(value, 3), "unit": unit}


@sst_router.get("/api/point_stats")
def api_point_stats(lat: float, lon: float):
    meta      = _load("meta")
    lat_arr   = meta["lat"]
    lon_arr   = meta["lon"]
    land_mask = meta["land_mask"]
    i = int(np.argmin(np.abs(lat_arr - lat)))
    j = int(np.argmin(np.abs(lon_arr - lon)))
    if land_mask[i, j]:
        return {"land": True}
    s2 = _load("s2")
    s3 = _load("s3")
    trends = [float(s2["monthly"][m][i, j]) for m in range(12)]
    r2s    = [float(s3["monthly"][m][i, j]) for m in range(12)]
    valid_t = [v for v in trends if math.isfinite(v)]
    valid_r = [v for v in r2s    if math.isfinite(v)]
    return {
        "lat":          round(float(lat_arr[i]), 3),
        "lon":          round(float(lon_arr[j]), 3),
        "trend_per_dec": round(float(np.mean(valid_t)) if valid_t else 0.0, 4),
        "r2":            round(float(np.mean(valid_r)) if valid_r else 0.0, 4),
    }


@sst_router.get("/api/point_series")
def api_point_series(section: str, lat: float, lon: float,
                     clim: str = "1991_2020"):
    """Return a time-series for the nearest grid point suitable for Chart.js."""
    meta      = _load("meta")
    lat_arr   = meta["lat"]
    lon_arr   = meta["lon"]
    land_mask = meta["land_mask"]
    i = int(np.argmin(np.abs(lat_arr - lat)))
    j = int(np.argmin(np.abs(lon_arr - lon)))

    if land_mask[i, j]:
        return {"labels": [], "values": [], "unit": "", "chart_type": "line"}

    def _safe(v: float) -> Optional[float]:
        return round(v, 4) if math.isfinite(v) else None

    if section == "s1":
        data   = _load("s1")
        values = [_safe(float(data["monthly"][m][i, j])) for m in range(12)]
        return {"labels": MON_LABELS, "values": values, "unit": "°C", "chart_type": "line"}

    elif section == "s2":
        data   = _load("s2")
        values = [_safe(float(data["monthly"][m][i, j])) for m in range(12)]
        return {"labels": MON_LABELS, "values": values, "unit": "°C/дек", "chart_type": "bar"}

    elif section == "s3":
        data   = _load("s3")
        values = [_safe(float(data["monthly"][m][i, j])) for m in range(12)]
        return {"labels": MON_LABELS, "values": values, "unit": "R²", "chart_type": "line"}

    elif section == "s4":
        # Annual variance time series
        raw     = _load("sst_raw")["sst"]
        years_a = meta["years"]
        all_yrs = sorted(set(int(y) for y in years_a))
        values  = []
        for yr in all_yrs:
            ix = np.where(years_a == yr)[0]
            v  = float(np.nanvar(raw[ix, i, j])) if len(ix) else float("nan")
            values.append(_safe(v))
        return {"labels": [str(y) for y in all_yrs], "values": values,
                "unit": "°C²", "chart_type": "line"}

    elif section == "s5":
        # Per-month trend of rolling variance (one value per month)
        values = []
        for m in range(12):
            f = _get_s5_monthly_field(m, meta)
            values.append(_safe(float(f[i, j])))
        return {"labels": MON_LABELS, "values": values,
                "unit": "°C²/дек", "chart_type": "bar"}

    elif section == "s7":
        # Full monthly anomaly time series
        raw      = _load("sst_raw")["sst"]
        s7       = _load("s7")
        clim_key = f"clim_{clim}"
        if clim_key not in s7:
            raise HTTPException(400, f"Unknown clim period: {clim}")
        clim_data = s7[clim_key]
        years_a   = meta["years"]
        months_a  = meta["months"]
        labels, values = [], []
        for k in range(len(years_a)):
            yr, mo = int(years_a[k]), int(months_a[k])
            labels.append(f"{yr}-{mo:02d}")
            raw_v  = float(raw[k, i, j])
            clim_v = float(clim_data[mo - 1, i, j])
            values.append(_safe(raw_v - clim_v))
        return {"labels": labels, "values": values, "unit": "°C", "chart_type": "line"}

    raise HTTPException(404, f"No point_series for section {section}")


@sst_router.get("/api/point_annual")
def api_point_annual(section: str, lat: float, lon: float,
                     clim: str = "1991_2020",
                     month: Optional[int] = None):
    """Annual time series for a point: raw SST (s1) or anomaly (s7), by year."""
    meta      = _load("meta")
    lat_arr   = meta["lat"]
    lon_arr   = meta["lon"]
    land_mask = meta["land_mask"]
    i = int(np.argmin(np.abs(lat_arr - lat)))
    j = int(np.argmin(np.abs(lon_arr - lon)))
    if land_mask[i, j]:
        return {"labels": [], "values": [], "unit": ""}

    raw_sst = _load("sst_raw")["sst"]
    years_a  = meta["years"]
    months_a = meta["months"]
    all_years = sorted(set(int(y) for y in years_a))

    def _safe(v: float):
        return round(float(v), 3) if math.isfinite(float(v)) else None

    def _get_indices(yr: int):
        """Return time indices for a given year and selected month."""
        if month is not None:
            return np.where((years_a == yr) & (months_a - 1 == month))[0]
        else:
            return np.where(years_a == yr)[0]

    if section == "s1":
        labels, values = [], []
        for yr in all_years:
            ix = _get_indices(yr)
            v  = np.nanmean(raw_sst[ix, i, j]) if len(ix) else float("nan")
            labels.append(str(yr))
            values.append(_safe(v))
        return {"labels": labels, "values": values, "unit": "°C"}

    elif section == "s7":
        s7       = _load("s7")
        clim_key = f"clim_{clim}"
        if clim_key not in s7:
            raise HTTPException(400, f"Unknown clim: {clim}")
        clim_data = s7[clim_key]   # (12, NLAT, NLON)

        labels, values = [], []
        for yr in all_years:
            ix = _get_indices(yr)
            if not len(ix):
                labels.append(str(yr)); values.append(None); continue
            raw_vals  = [float(raw_sst[k, i, j]) for k in ix]
            clim_vals = [float(clim_data[int(months_a[k]) - 1, i, j]) for k in ix]
            anoms     = [r - c for r, c in zip(raw_vals, clim_vals)
                         if math.isfinite(r) and math.isfinite(c)]
            v = float(np.mean(anoms)) if anoms else float("nan")
            labels.append(str(yr))
            values.append(_safe(v))
        return {"labels": labels, "values": values, "unit": "°C"}

    raise HTTPException(404, f"point_annual not supported for {section}")
