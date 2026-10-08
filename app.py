"""
GFS Dashboard v6 — FastAPI backend

Рендерит прогностические поля NCEP GFS 0.25° по Северной Пацифике
(26–72° с.ш., 117–246° в.д.) в PNG-тайлы в проекции Меркатора плюс
векторную береговую линию Natural Earth.
"""
import os, io, math, logging, time, datetime, tempfile
from contextlib import asynccontextmanager
from typing import Optional

# Метка времени запуска сервера — передаётся клиентам для сброса кэша браузера
# после перезапуска.
_SERVER_START_TS = str(int(time.time()))

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)

import numpy as np
from fastapi import FastAPI, HTTPException, Response, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from auth import get_current_user

DATA_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


@asynccontextmanager
async def lifespan(app):
    # Инициализация пула БД
    try:
        import db as _db
        await _db.init_db()
        logger.info("DB pool initialized")
    except Exception as e:
        logger.warning("DB not available: %s", e)
    # Запуск фонового планировщика
    try:
        from services.scheduler import start_scheduler
        start_scheduler()
        logger.info("Scheduler started")
    except Exception as e:
        logger.warning("Scheduler not started: %s", e)
    yield
    try:
        import db as _db
        await _db.close_db()
    except Exception:
        pass


app = FastAPI(title="GFS Dashboard v6", lifespan=lifespan)

# ── Подключение дополнительных роутеров (с изящной деградацией при отсутствии зависимостей) ──
def _try_include(module_path: str, attr: str):
    try:
        import importlib
        mod = importlib.import_module(module_path)
        router = getattr(mod, attr)
        app.include_router(router)
        logger.info("Router %s included", attr)
    except Exception as e:
        logger.warning("Router %s not loaded: %s", attr, e)

_try_include("auth", "auth_router")
_try_include("routers.stations", "stations_router")
_try_include("routers.forecast", "forecast_router")
_try_include("routers.monitoring", "monitoring_router")
_try_include("routers.requests", "requests_router")
_try_include("routers.calendar_routes", "calendar_router")
_try_include("routers.equipment", "equipment_router")
_try_include("routers.users", "users_router")
_try_include("routers.regions", "regions_router")
_try_include("routers.schedule", "schedule_router")
_try_include("routers.webhooks", "webhooks_router")
_try_include("routers.gfs_forecast", "gfs_router")

# ──────────────────────────────────────────────
# Конфигурация GFS
# ──────────────────────────────────────────────
_GFS_BASE     = os.getenv("GFS_LOCAL_PATH", "/mnt/meteo/data/NOAA/NCEP/FTPPRD/pub/data/nccf/com/gfs/prod0p25.sfc")

# Географический домен (конвенция долготы 0–360°), общий для карт и береговой линии
LON_MIN, LON_MAX = 117.0, 246.0
LAT_MIN, LAT_MAX = 26.0,  72.0

# Сроки прогноза (в часах) для сетки сравнения (6 карт)
GFS_FHOURS = [0, 24, 48, 72, 96, 120]
GFS_FHOUR_LABELS = ["Анализ (+0ч)", "+24ч (+1 сут)", "+48ч (+2 сут)",
                    "+72ч (+3 сут)", "+96ч (+4 сут)", "+120ч (+5 сут)"]

# Единый источник правды для каждого визуализируемого параметра GFS:
# селекторы GRIB2, единица измерения, цветовая палитра и подпись в интерфейсе.
#   scale       — множитель, применяемый к сырым значениям GRIB
#   to_celsius  — вычитание 273.15 вместо масштабирования
#   wind_speed  — поле рассчитывается как sqrt(u10² + v10²) вместо одного shortName
GFS_PARAMS: dict[str, dict] = {
    "gfs_t": {
        "label": "Темп. поверхности", "unit": "°C", "cmap": "RdYlBu_r",
        "shortName": "t", "typeOfLevel": "surface", "to_celsius": True,
    },
    "gfs_2t": {
        "label": "Темп. воздуха 2м", "unit": "°C", "cmap": "RdYlBu_r",
        "shortName": "2t", "typeOfLevel": "heightAboveGround", "to_celsius": True,
    },
    "gfs_prmsl": {
        "label": "Давление (уровень моря)", "unit": "гПа", "cmap": "Blues",
        "shortName": "prmsl", "typeOfLevel": "meanSea", "scale": 0.01,
    },
    "gfs_wind": {
        "label": "Скорость ветра 10м", "unit": "м/с", "cmap": "Plasma",
        "shortName": "10u", "typeOfLevel": "heightAboveGround", "wind_speed": True,
    },
    "gfs_tcc": {
        "label": "Облачность", "unit": "%", "cmap": "Greys",
        "shortName": "tcc", "typeOfLevel": "atmosphere",
    },
    "gfs_pwat": {
        "label": "Запас воды (PWAT)", "unit": "кг/м²", "cmap": "Greens",
        "shortName": "pwat", "typeOfLevel": "atmosphereSingleLayer",
    },
}


def _param_cfg(param: str) -> dict:
    cfg = GFS_PARAMS.get(param)
    if cfg is None:
        raise HTTPException(404, f"Unknown GFS parameter: {param}")
    return cfg


def _fhour(fhour_idx: int) -> int:
    return GFS_FHOURS[max(0, min(fhour_idx, len(GFS_FHOURS) - 1))]


# ──────────────────────────────────────────────
# Цветовые палитры — Таблица поиска (LUT) на чистом NumPy (256 × 3, uint8)
# ──────────────────────────────────────────────
# имя → [(позиция 0..1, (r, g, b)), …]; промежуточные цвета интерполируются.
_CMAP_STOPS: dict[str, list] = {
    "RdYlBu_r": [
        (0.000, (49,  54,  149)), (0.125, (69,  117, 180)),
        (0.250, (116, 173, 209)), (0.375, (171, 217, 233)),
        (0.500, (255, 255, 191)), (0.625, (254, 224, 144)),
        (0.750, (253, 174, 97)),  (0.875, (244, 109, 67)),
        (1.000, (165, 0,   38)),
    ],
    "Blues": [
        (0.000, (247, 251, 255)), (0.250, (198, 219, 239)),
        (0.500, (107, 174, 214)), (0.750, (33,  113, 181)),
        (1.000, (8,   48,  107)),
    ],
    "Greens": [
        (0.000, (247, 252, 245)), (0.333, (161, 217, 155)),
        (0.667, (49,  163, 84)),  (1.000, (0,   68,  27)),
    ],
    "Plasma": [
        (0.000, (13,  8,   135)), (0.250, (126, 3,   168)),
        (0.500, (204, 71,  120)), (0.750, (248, 149, 64)),
        (1.000, (240, 249, 33)),
    ],
    # Linear black → white ramp (0 % облачности — тёмный, 100 % — белый)
    "Greys": [
        (0.000, (0, 0, 0)), (1.000, (255, 255, 255)),
    ],
}


def _make_lut(stops: list) -> np.ndarray:
    """Создание таблицы поиска 256×3 uint8 с интерполяцией между контрольными точками цвета."""
    pos  = np.array([p for p, _ in stops], dtype=np.float64)
    cols = np.array([c for _, c in stops], dtype=np.float64)
    t    = np.linspace(0.0, 1.0, 256)
    lut  = np.empty((256, 3), dtype=np.uint8)
    for ch in range(3):
        lut[:, ch] = np.clip(np.interp(t, pos, cols[:, ch]), 0, 255).astype(np.uint8)
    return lut


_LUTS = {name: _make_lut(stops) for name, stops in _CMAP_STOPS.items()}


# ──────────────────────────────────────────────
# Отображение процентилей в диапазоны (lo, hi) для отсечения цветовой шкалы
# ──────────────────────────────────────────────
def _pct_bounds(percentile: float) -> tuple[float, float]:
    """Возвращает границы процентилей (lo, hi) для расчета vmin/vmax."""
    p = float(percentile)
    if p >= 100:
        return (0.0, 100.0)
    elif p >= 99.9:
        return (0.1, 99.9)
    else:
        return (1.0, 99.0)


# ── Константы проекции Меркатора (долгота 117-246°, широта 26-72°) ──
_EARTH_CIRC = 40075016.685578488  # метры, длина экватора WGS-84

def _mercator_extent():
    """Возвращает (x_min, y_min, x_max, y_max) в EPSG:3857 для области данных."""
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    x_min, y_min = tr.transform(LON_MIN, LAT_MIN)
    x_max        = x_min + (LON_MAX - LON_MIN) / 360.0 * _EARTH_CIRC
    _, y_max     = tr.transform(0.0, LAT_MAX)
    return x_min, y_min, x_max, y_max

_MERC_EXTENT = _mercator_extent()   # вычисляется один раз при импорте модуля


# ──────────────────────────────────────────────
# Отрисовка
# ──────────────────────────────────────────────
def _overlay_contours(img, vals: np.ndarray, finite: np.ndarray,
                      vmin: float, vmax: float,
                      show_labels: bool = False,
                      lut: "np.ndarray | None" = None) -> "PIL.Image.Image":
    """Накладывает контуры изолиний (и опциональные подписи значений) на PIL RGBA изображение."""
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

        # CS.collections был удален в matplotlib 3.9; используем CS.get_paths()
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

        # Отрисовка подписей значений — умный цвет текста под цветовую шкалу, без фона
        if show_labels:
            try:
                fmt_comma = lambda x: f"{x:.1f}".replace(".", ",")
                label_texts = ax.clabel(CS, inline=True, fontsize=7, fmt=fmt_comma)
                # Фильтрация перекрывающихся подписей — оставляем только те, расстояние между которыми > MIN_DIST пикселей
                MIN_DIST_SQ = 80 ** 2
                kept = []
                for lt in label_texts:
                    px_l, py_l = lt.get_position()
                    if not any((px_l - k.get_position()[0])**2 +
                               (py_l - k.get_position()[1])**2 < MIN_DIST_SQ
                               for k in kept):
                        kept.append(lt)
                label_texts = kept
                # Использование системного TTF-шрифта без засечек; при отсутствии fallback на шрифт по умолчанию PIL
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
                    # Выбор цвета текста для контраста со значением цветовой шкалы
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

        return _PIL.alpha_composite(img, cont_overlay)

    except Exception as e:
        logger.warning("Contour overlay failed: %s", e)
        return img


def _render_mercator(field: np.ndarray, lat_arr: np.ndarray, lon_arr: np.ndarray,
                     cmap: str, vmin: float, vmax: float,
                     width: int = 1200, height: int = 550,
                     scale: int = 1,
                     blur: bool = True,
                     contours: bool = True,
                     contour_labels: bool = False) -> bytes:
    """Рендеринг прямоугольного 2D поля GFS в RGBA PNG в проекции Меркатора.

    field    : 2D (nlat × nlon), NaN = нет данных
    lat_arr  : 1-D, может убывать
    lon_arr  : 1-D, конвенция 0-360
    scale    : коэффициент увеличения (1=1200×550, 2=2400×1100 и т.д.)
    """
    from pyproj import Transformer
    from scipy.interpolate import RegularGridInterpolator
    from PIL import Image as _PIL, ImageEnhance as _IE, ImageFilter as _IF

    W = width  * scale
    H = height * scale

    x_min, y_min, x_max, y_max = _MERC_EXTENT

    xs = np.linspace(x_min, x_max, W)
    ys = np.linspace(y_max, y_min, H)
    X, Y = np.meshgrid(xs, ys)

    inv = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    lons_grid, lats_grid = inv.transform(X, Y)
    lons_grid = lons_grid % 360.0

    # Обеспечение возрастающей оси широты
    if lat_arr[0] > lat_arr[-1]:
        lat_inc  = lat_arr[::-1]
        field_rc = field[::-1, :]
    else:
        lat_inc  = lat_arr
        field_rc = field

    interp = RegularGridInterpolator(
        (lat_inc, lon_arr), field_rc,
        method="linear", bounds_error=False, fill_value=np.nan)

    pts  = np.stack([lats_grid.ravel(), lons_grid.ravel()], axis=1)
    vals = interp(pts).reshape(H, W)

    # Nullify pixels within 5 grid cells of the domain boundary. The sharp
    # data→NaN transition at the rectangular domain edge creates a visible
    # coloured fringe after Gaussian blur; trimming a small margin removes it.
    lat_step = float(abs(lat_arr[1] - lat_arr[0]))
    lon_step = float(abs(lon_arr[1] - lon_arr[0]))
    edge_mask = ((lats_grid < float(lat_arr.min()) + lat_step * 5) |
                 (lats_grid > float(lat_arr.max()) - lat_step * 5) |
                 (lons_grid < float(lon_arr.min()) + lon_step * 5) |
                 (lons_grid > float(lon_arr.max()) - lon_step * 5))
    vals[edge_mask] = np.nan

    # Окрашивание — пиксели NaN остаются идентифицированными
    lut    = _LUTS[cmap]
    finite = np.isfinite(vals)
    safe   = np.where(finite, vals, vmin)
    norm   = np.clip((safe - vmin) / (vmax - vmin + 1e-10), 0.0, 1.0)
    idx    = (norm * 255).astype(np.uint8)

    rgba = np.zeros((H, W, 4), dtype=np.uint8)
    rgba[:, :, :3] = lut[idx]
    rgba[~finite, 3] = 0   # Пиксели NaN: альфа=0 (RGB пока сохраняет цвет lut[0] = vmin)

    # Опциональное гауссово размытие (сглаживает границы пикселей)
    if blur:
        from scipy.ndimage import distance_transform_edt
        # Заполнение только ВНУТРЕННИХ пикселей NaN — исключая edge_mask.
        # Краевые пиксели сохраняют RGB=0, чтобы размытие не распространяло цвет на валидные пиксели.
        nf_interior = ~finite & ~edge_mask
        if nf_interior.any() and finite.any():
            # Источник EDT: только конечные некраевые пиксели
            _, nn = distance_transform_edt(~finite | edge_mask, return_indices=True)
            rgba[nf_interior, :3] = rgba[nn[0][nf_interior], nn[1][nf_interior], :3]
        rgb_arr = _PIL.fromarray(rgba[:, :, :3], "RGB")
        rgb_arr = rgb_arr.filter(_IF.GaussianBlur(radius=1.2))
        rgba[:, :, :3] = np.asarray(rgb_arr)

    rgba[finite, 3] = 255

    img = _PIL.fromarray(rgba, "RGBA")
    r, g, b, a = img.split()
    rgb = _PIL.merge("RGB", (r, g, b))
    rgb = _IE.Color(rgb).enhance(1.3)
    r2, g2, b2 = rgb.split()
    img = _PIL.merge("RGBA", (r2, g2, b2, a))

    # Наложение контуров изолиний (пропускается, если contours=False)
    if contours:
        img = _overlay_contours(img, vals, finite, vmin, vmax,
                                show_labels=contour_labels, lut=lut)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    return buf.getvalue()


# ──────────────────────────────────────────────
# Доступ к данным GFS (локальные файлы GRIB2)
# ──────────────────────────────────────────────
_gfs_png_cache: dict = {}
_gfs_data_cache: dict = {}   # кэш сырых полей (массивы широты, долготы и данных)


def _find_latest_gfs_00z_file(fhour: int = 0) -> tuple[Optional[str], str]:
    """Возвращает (path, run_label) для последнего доступного файла GFS 00Z для fhour."""
    today = datetime.date.today()
    fname = f"gfs.t00z.pgrb2.0p25.f{fhour:03d}.grb2"
    for delta in range(8):
        d = today - datetime.timedelta(days=delta)
        path = os.path.join(_GFS_BASE,
                            f"{d.year:04d}", f"{d.month:02d}", f"{d.day:02d}",
                            "00", fname)
        if os.path.exists(path):
            return path, f"{d.year:04d}-{d.month:02d}-{d.day:02d} 00Z +{fhour}ч"
    return None, "—"


def _gfs_subset(arr: np.ndarray, lat: np.ndarray, lon: np.ndarray):
    """Обрезает массив и оси до домена Северной Пацифики."""
    lat_m = (lat >= LAT_MIN) & (lat <= LAT_MAX)
    lon_m = (lon >= LON_MIN) & (lon <= LON_MAX)
    return arr[np.ix_(lat_m, lon_m)], lat[lat_m], lon[lon_m]


def _open_grib(path: str, short_name: str, level_type: str, idx_path: str):
    """Открывает один набор сообщений GRIB2 и возвращает (values, lat, lon) с возрастающей широтой."""
    import cfgrib
    try:
        ds = cfgrib.open_dataset(
            path,
            filter_by_keys={"shortName": short_name, "typeOfLevel": level_type},
            indexpath=idx_path)
    except Exception as e:
        raise HTTPException(500, f"Failed to read GFS {short_name}: {e}")

    var_name = short_name if short_name in ds else list(ds.data_vars.keys())[0]
    arr = np.asarray(ds[var_name].values, dtype=np.float32)
    lat = np.asarray(ds.latitude.values,  dtype=np.float64)
    lon = np.asarray(ds.longitude.values, dtype=np.float64)
    if lat[0] > lat[-1]:
        lat = lat[::-1]
        arr = arr[::-1, :]
    return arr, lat, lon


def _load_gfs_field(param: str, fhour: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray, str]:
    """Загружает поле GFS из GRIB2 и обрезает до Северной Пацифики.
    Возвращает (field, lat_arr_inc, lon_arr_0_360, run_label)."""
    cache_key = (param, fhour)
    if cache_key in _gfs_data_cache:
        return _gfs_data_cache[cache_key]

    try:
        import cfgrib  # noqa: F401  — импортируется только для проверки доступности
    except ImportError:
        raise HTTPException(500, "cfgrib not installed — pip install cfgrib")

    cfg = _param_cfg(param)
    path, label = _find_latest_gfs_00z_file(fhour)
    if path is None:
        raise HTTPException(503, f"GFS +{fhour}h data not available")

    with tempfile.TemporaryDirectory() as tmpdir:
        idx = os.path.join(tmpdir, "gfs.idx")

        if cfg.get("wind_speed"):
            # Скорость ветра = sqrt(u² + v²) из составляющих u и v на высоте 10м
            u, lat, lon = _open_grib(path, "10u", "heightAboveGround", idx + "u")
            v, _,   _   = _open_grib(path, "10v", "heightAboveGround", idx + "v")
            raw = np.sqrt(u ** 2 + v ** 2).astype(np.float32)
        else:
            raw, lat, lon = _open_grib(path, cfg["shortName"], cfg["typeOfLevel"], idx)

    raw_s, lat_s, lon_s = _gfs_subset(raw, lat, lon)
    if cfg.get("to_celsius"):
        field = (raw_s - 273.15).astype(np.float32)
    elif cfg.get("scale", 1.0) != 1.0:
        field = (raw_s * cfg["scale"]).astype(np.float32)
    else:
        field = raw_s

    logger.info("GFS %s +%dh loaded: shape=%s label=%s", param, fhour, field.shape, label)
    result = (field, lat_s, lon_s, label)
    _gfs_data_cache[cache_key] = result
    return result


def _get_gfs_wind_vectors(fhour: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, str]:
    """Возвращает (u, v, lat, lon, label) для ветра 10m на заданный срок прогноза."""
    cache_key = ("wind_uv", fhour)
    if cache_key in _gfs_data_cache:
        return _gfs_data_cache[cache_key]

    try:
        import cfgrib  # noqa: F401
    except ImportError:
        raise HTTPException(500, "cfgrib not installed")

    path, label = _find_latest_gfs_00z_file(fhour)
    if path is None:
        raise HTTPException(503, f"GFS +{fhour}h data not available")

    with tempfile.TemporaryDirectory() as tmpdir:
        idx = os.path.join(tmpdir, "gfs.idx")
        u, lat, lon = _open_grib(path, "10u", "heightAboveGround", idx + "u")
        v, _,   _   = _open_grib(path, "10v", "heightAboveGround", idx + "v")

    # Прореживание до каждой 4-й точки сетки для ответа JSON
    u_s, lat_s, lon_s = _gfs_subset(u, lat, lon)
    v_s, _,     _     = _gfs_subset(v, lat, lon)
    step = 4
    result = (u_s[::step, ::step], v_s[::step, ::step],
              lat_s[::step], lon_s[::step], label)
    _gfs_data_cache[cache_key] = result
    return result


def _get_gfs_png(param: str, fhour: int = 0, scale: int = 1, blur: bool = True,
                 contours: bool = True, contour_labels: bool = False,
                 percentile: float = 99) -> tuple[bytes, float, float, str]:
    """Рендерит PNG для параметра GFS. Возвращает (png_bytes, vmin, vmax, run_label)."""
    key = (param, fhour, scale, blur, contours, contour_labels, percentile)
    if key in _gfs_png_cache:
        return _gfs_png_cache[key]

    cfg = _param_cfg(param)
    field, lat_arr, lon_arr, label = _load_gfs_field(param, fhour)

    valid  = field[np.isfinite(field)]
    lo, hi = _pct_bounds(percentile)
    if valid.size == 0:
        vmin, vmax = 0.0, 1.0
    elif lo <= 0 and hi >= 100:
        vmin, vmax = float(np.min(valid)), float(np.max(valid))
    else:
        vmin, vmax = float(np.percentile(valid, lo)), float(np.percentile(valid, hi))
    if vmax == vmin:
        vmax = vmin + 1.0

    png = _render_mercator(field, lat_arr, lon_arr, cfg["cmap"], vmin, vmax,
                           scale=scale, blur=blur,
                           contours=contours, contour_labels=contour_labels)
    result = (png, vmin, vmax, label)
    _gfs_png_cache[key] = result
    return result


def _fmt_tick_prec(v: float, prec: int) -> str:
    """Форматирует значение деления шкалы с заданным количеством знаков после запятой (разделитель — запятая)."""
    return f"{v:.{prec}f}".replace('.', ',')


# ──────────────────────────────────────────────
# Маршруты API GFS
# ──────────────────────────────────────────────
@app.get("/api/gfs/meta")
def api_gfs_meta(user=Depends(get_current_user)):
    """Возвращает информацию о последнем доступном прогоне GFS 00Z."""
    path, label = _find_latest_gfs_00z_file(0)
    available_fhours = []
    if path is not None:
        run_dir = os.path.dirname(path)
        for fh in GFS_FHOURS:
            fp = os.path.join(run_dir, f"gfs.t00z.pgrb2.0p25.f{fh:03d}.grb2")
            if os.path.exists(fp):
                available_fhours.append(fh)
    x_min, y_min, x_max, y_max = _MERC_EXTENT
    return {
        "available":        path is not None,
        "run_label":        label.split(" +")[0] if " +" in label else label,
        "fhours":           GFS_FHOURS,
        "fhour_labels":     GFS_FHOUR_LABELS,
        "available_fhours": available_fhours,
        "lat":              {"min": LAT_MIN, "max": LAT_MAX},
        "lon":              {"min": LON_MIN, "max": LON_MAX},
        "mercator_extent":  [x_min, y_min, x_max, y_max],
        "server_ts":        _SERVER_START_TS,
        "params": [
            {"id": pid, "label": cfg["label"], "unit": cfg["unit"]}
            for pid, cfg in GFS_PARAMS.items()
        ],
    }


@app.get("/api/gfs/map/{param}/{fhour_idx}.png")
def api_gfs_map_png(param: str, fhour_idx: int,
                    percentile: float = 99,
                    scale: int = 1,
                    blur: bool = True,
                    contours: bool = True,
                    contour_labels: bool = False):
    _param_cfg(param)
    scale = max(1, min(scale, 3))
    fhour = _fhour(fhour_idx)
    logger.info("GFS map %s +%dh scale=%s blur=%s contours=%s labels=%s",
                param, fhour, scale, blur, contours, contour_labels)
    try:
        png, _, _, _ = _get_gfs_png(param, fhour, scale, blur,
                                    contours, contour_labels, percentile)
    except HTTPException:
        raise
    except Exception as e:
        import traceback as _tb
        logger.error("GFS map error %s +%dh: %s\n%s", param, fhour, e, _tb.format_exc())
        raise HTTPException(500, str(e))
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "no-store"})


@app.get("/api/gfs/colorscale/{param}")
def api_gfs_colorscale(param: str, fhour_idx: int = 0, percentile: float = 99):
    cfg   = _param_cfg(param)
    fhour = _fhour(fhour_idx)
    try:
        _, vmin, vmax, label = _get_gfs_png(param, fhour, percentile=percentile)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

    rng     = vmax - vmin
    n_ticks = 10
    step    = rng / (n_ticks + 1)
    prec    = max(0, min(2, math.ceil(-math.log10(step + 1e-10))))
    ticks = [
        {"value": round(float(v), 4),
         "label": _fmt_tick_prec(float(v), prec),
         "norm":  round((float(v) - vmin) / rng, 4)}
        for v in np.linspace(vmin, vmax, n_ticks + 2)[1:-1]
    ]
    return {
        "vmin":      round(vmin, 4),
        "vmax":      round(vmax, 4),
        "unit":      cfg["unit"],
        "cmap":      cfg["cmap"],
        "lut":       _LUTS[cfg["cmap"]].tolist(),
        "ticks":     ticks,
        "run_label": label,
    }


@app.get("/api/gfs/wind/{fhour_idx}")
def api_gfs_wind_vectors(fhour_idx: int):
    """Возвращает векторное поле ветра u/v в формате JSON для анимации частиц ветра."""
    fhour = _fhour(fhour_idx)
    try:
        u, v, lat, lon, label = _get_gfs_wind_vectors(fhour)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    return {
        "fhour":     fhour,
        "run_label": label,
        "lat":       lat.tolist(),
        "lon":       lon.tolist(),
        "u":         u.tolist(),
        "v":         v.tolist(),
    }


# ──────────────────────────────────────────────
# Береговая линия (Natural Earth)
# ──────────────────────────────────────────────
_coastline_cache: dict = {}

_COAST_W, _COAST_H = 1200, 550

def _coast_boxes():
    from shapely.geometry import box as _box
    # Внешний отступ (широта/долгота) для обрезки полигонов. Большое перекрытие
    # антимеридиана (M_ANTI = 5°) гарантирует, что полигоны, пересекающие 180°,
    # рендерятся ОБЕИМИ проекциями (западной и восточной), устраняя видимый шов на 180°.
    M      = 1.0   # отступ внешнего края
    M_ANTI = 5.0   # перекрытие антимеридиана — достаточно широкое, чтобы перекрыть шов обрезки
    return (
        _box(LON_MIN - M, LAT_MIN - M, 180.0 + M_ANTI, LAT_MAX + M),
        _box(-180.0 - M_ANTI, LAT_MIN - M, -(360.0 - LON_MAX) - M, LAT_MAX + M),
    )

def _coast_projection():
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    x0, _ = tr.transform(LON_MIN, LAT_MIN)
    x1    = x0 + (LON_MAX - LON_MIN) / 360.0 * _EARTH_CIRC
    _, y1 = tr.transform(0.0, LAT_MAX)
    _, y0 = tr.transform(0.0, LAT_MIN)
    return tr, x0, x1, y0, y1

def _coast_to_px(lon_std, lat, east, tr, x0, x1, y0, y1):
    mx, my = tr.transform(lon_std, lat)
    if east:
        mx += _EARTH_CIRC
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


@app.get("/api/coastline.svg")
def api_coastline_svg():
    """Векторная береговая линия, спроецированная в пиксельное пространство Меркатора 1200×550."""
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
                pts.append(None)   # разрыв на антимеридиане
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


@app.get("/api/coastline.geojson")
def api_coastline_geojson():
    """Полигоны суши Natural Earth, обрезанные по домену и разделенные на запад/восток для рендеринга в OpenLayers."""
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


# ──────────────────────────────────────────────
# Статические файлы и главная страница
# ──────────────────────────────────────────────
@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
