import os
import pytest
from unittest.mock import patch

from precompute_coastline import main, GEOJSON_CACHE, GEOJSON_URL, DATA_DIR

@patch("precompute_coastline.os.makedirs")
@patch("precompute_coastline.os.path.exists")
@patch("precompute_coastline.os.path.getsize")
@patch("precompute_coastline.urllib.request.urlretrieve")
@patch("builtins.print")
def test_main_file_already_exists(mock_print, mock_urlretrieve, mock_getsize, mock_exists, mock_makedirs):
    # Setup mock
    mock_exists.return_value = True
    mock_getsize.return_value = 2048 * 1024  # 2048 KB

    # Run function
    main()

    # Verify directory creation
    mock_makedirs.assert_called_once_with(DATA_DIR, exist_ok=True)

    # Verify exists check
    mock_exists.assert_called_once_with(GEOJSON_CACHE)

    # Verify URL is NOT retrieved
    mock_urlretrieve.assert_not_called()

    # Verify output
    mock_print.assert_called_once_with(f"Already present: {GEOJSON_CACHE} (2048 KB)")

@patch("precompute_coastline.os.makedirs")
@patch("precompute_coastline.os.path.exists")
@patch("precompute_coastline.os.path.getsize")
@patch("precompute_coastline.urllib.request.urlretrieve")
@patch("builtins.print")
def test_main_file_does_not_exist(mock_print, mock_urlretrieve, mock_getsize, mock_exists, mock_makedirs):
    # Setup mock
    mock_exists.return_value = False
    mock_getsize.return_value = 1024 * 1024  # 1024 KB

    # Run function
    main()

    # Verify directory creation
    mock_makedirs.assert_called_once_with(DATA_DIR, exist_ok=True)

    # Verify exists check
    mock_exists.assert_called_once_with(GEOJSON_CACHE)

    # Verify URL IS retrieved
    mock_urlretrieve.assert_called_once_with(GEOJSON_URL, GEOJSON_CACHE)

    # Verify output
    mock_print.assert_any_call("Downloading Natural Earth 1:10m land polygons …")
    mock_print.assert_any_call(f"Saved: {GEOJSON_CACHE} (1024 KB)")
