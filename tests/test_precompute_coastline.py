from __future__ import annotations

import os
from unittest.mock import patch

import precompute_coastline


@patch("precompute_coastline.os.path.getsize")
@patch("precompute_coastline.os.path.exists")
@patch("precompute_coastline.os.makedirs")
@patch("precompute_coastline.urllib.request.urlretrieve")
@patch("builtins.print")
def test_main_file_exists(mock_print, mock_urlretrieve, mock_makedirs, mock_exists, mock_getsize):
    mock_exists.return_value = True
    mock_getsize.return_value = 2048 * 1024  # 2048 KB

    precompute_coastline.main()

    mock_makedirs.assert_called_once_with(precompute_coastline.DATA_DIR, exist_ok=True)
    mock_exists.assert_called_once_with(precompute_coastline.GEOJSON_CACHE)
    mock_getsize.assert_called_once_with(precompute_coastline.GEOJSON_CACHE)
    mock_urlretrieve.assert_not_called()
    mock_print.assert_called_once_with(
        f"Already present: {precompute_coastline.GEOJSON_CACHE} (2048 KB)"
    )


@patch("precompute_coastline.os.path.getsize")
@patch("precompute_coastline.os.path.exists")
@patch("precompute_coastline.os.makedirs")
@patch("precompute_coastline.urllib.request.urlretrieve")
@patch("builtins.print")
def test_main_file_not_exists(mock_print, mock_urlretrieve, mock_makedirs, mock_exists, mock_getsize):
    mock_exists.return_value = False
    mock_getsize.return_value = 4096 * 1024  # 4096 KB

    precompute_coastline.main()

    mock_makedirs.assert_called_once_with(precompute_coastline.DATA_DIR, exist_ok=True)
    mock_exists.assert_called_once_with(precompute_coastline.GEOJSON_CACHE)
    mock_urlretrieve.assert_called_once_with(
        precompute_coastline.GEOJSON_URL, precompute_coastline.GEOJSON_CACHE
    )
    mock_getsize.assert_called_once_with(precompute_coastline.GEOJSON_CACHE)

    assert mock_print.call_count == 2
    mock_print.assert_any_call("Downloading Natural Earth 1:10m land polygons …")
    mock_print.assert_any_call(f"Saved: {precompute_coastline.GEOJSON_CACHE} (4096 KB)")
