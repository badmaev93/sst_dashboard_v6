#!/usr/bin/env python3
"""
Download the Natural Earth 1:10m land polygons used by the coastline endpoints
(`/api/coastline.svg`, `/api/coastline.geojson`).

The clipping and Mercator projection happen at request time in `app.py`; this
script only makes sure `data/ne_10m_land.geojson` exists locally.

Run once:
    python precompute_coastline.py
"""
import os, urllib.request

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

GEOJSON_URL   = ("https://raw.githubusercontent.com/nvkelso/"
                 "natural-earth-vector/master/geojson/ne_10m_land.geojson")
GEOJSON_CACHE = os.path.join(DATA_DIR, "ne_10m_land.geojson")


def main() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(GEOJSON_CACHE):
        print(f"Already present: {GEOJSON_CACHE} "
              f"({os.path.getsize(GEOJSON_CACHE) // 1024} KB)")
        return
    print("Downloading Natural Earth 1:10m land polygons …")
    urllib.request.urlretrieve(GEOJSON_URL, GEOJSON_CACHE)
    print(f"Saved: {GEOJSON_CACHE} ({os.path.getsize(GEOJSON_CACHE) // 1024} KB)")


if __name__ == "__main__":
    main()
