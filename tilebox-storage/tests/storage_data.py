"""
Hypothesis strategies for generating random granules for testing storage client related functionality.

This module is intentionally not named just 'data', to avoid multiple 'tests.data' modules in our mono-repo, which
can confuse the test runner.
"""

import string
from datetime import datetime
from pathlib import Path

from hypothesis.strategies import DrawFn, booleans, composite, datetimes, integers, just, one_of, text, uuids

from tilebox.storage.granule import (
    ASFStorageGranule,
    CopernicusStorageGranule,
    UmbraStorageGranule,
    USGSLandsatStorageGranule,
)
from tilebox.storage.providers import _ASF_URL, StorageURLs


@composite
def ers_granules(draw: DrawFn, ensure_quicklook: bool = False) -> ASFStorageGranule:
    """Generate a realistic-looking random ERS granule."""
    level = "L0"
    time = draw(datetimes(min_value=datetime(1990, 1, 1), max_value=datetime(2015, 1, 1), timezones=just(None)))
    platform = draw(integers(min_value=1, max_value=2))
    orbit = draw(integers(min_value=1, max_value=99_999))
    frame = draw(integers(min_value=1, max_value=999))
    granule_name = f"E{platform}_{orbit:05d}_STD_F{frame:03d}"
    file_size = draw(integers(min_value=10_000, max_value=999_999_999))
    md5sum = draw(text(alphabet=string.hexdigits, min_size=32, max_size=32))

    file_name = f"E{platform}_{orbit:05d}_STD_{level}_F{frame:03d}"
    quicklook_available = draw(booleans()) if not ensure_quicklook else True
    quicklook = None
    if quicklook_available:
        quicklook = f"{_ASF_URL}/BROWSE/E{platform}/{granule_name}.jpg"
    urls = StorageURLs(f"{_ASF_URL}/{level}/E{platform}/{file_name}.zip", quicklook)

    return ASFStorageGranule(time, granule_name, file_size, md5sum, urls)


@composite
def alphanumerical_text(draw: DrawFn, min_size: int = 1, max_size: int = 100) -> str:
    # the text() strategy gets a bit crazy with utf codepoints, so lets restrict it a bit
    return draw(text(alphabet=string.ascii_letters + string.digits + "-_", min_size=min_size, max_size=max_size))


@composite
def umbra_granules(draw: DrawFn) -> UmbraStorageGranule:
    """Generate a realistic-looking random Umbra granule."""
    level = "L0"
    time = draw(datetimes(min_value=datetime(1990, 1, 1), max_value=datetime(2025, 1, 1), timezones=just(None)))
    number = draw(integers(min_value=1, max_value=2))
    text_location = draw(alphanumerical_text(min_size=1, max_size=20))
    granule_id = str(draw(uuids(version=4)))
    granule_name = f"{time:%Y-%m-%d-%H-%M-%S}_UMBRA-{number:02d}"
    location = str(Path(text_location) / granule_id / granule_name)

    return UmbraStorageGranule(time, granule_name, level, location)


@composite
def s5p_granules(draw: DrawFn) -> CopernicusStorageGranule:
    """Generate a realistic-looking random Sentinel 5P granule."""
    mission = "S5P"
    processing_stream = draw(one_of(just("NRTI"), just("OFFL"), just("RPRO")))
    product_type = draw(text(alphabet=string.ascii_uppercase + "_", min_size=1, max_size=20))
    start = draw(datetimes(min_value=datetime(2017, 1, 1), max_value=datetime(2025, 1, 1), timezones=just(None)))
    end = draw(datetimes(min_value=datetime(2017, 1, 1), max_value=datetime(2025, 1, 1), timezones=just(None)))
    orbit = draw(integers(min_value=1, max_value=99_999))
    collection = draw(integers(min_value=1, max_value=99))
    processor_version = draw(integers(min_value=1, max_value=999_999))
    processing = draw(datetimes(min_value=datetime(2017, 1, 1), max_value=datetime(2025, 1, 1), timezones=just(None)))

    # S5P_NRTI_L2__AER_LH_20240415T055540_20240415T060040_33707_03_020600_20240415T063447.nc
    granule_name = (
        f"{mission}_{processing_stream}_{product_type}_{start:%Y%m%dT%H%M%S}_{end:%Y%m%dT%H%M%S}_"
        f"{orbit:05d}_{collection:02d}_{processor_version:06d}_{processing:%Y%m%dT%H%M%S}.nc"
    )

    instrument = "TROPOMI"
    # /eodata/Sentinel-5P/TROPOMI/L2__AER_LH/2024/04/15/S5P_NRTI_L2__AER_LH_20240415T055540_20240415T060040_33707_03_020600_20240415T063447
    location = f"/eodata/Sentinel-5P/{instrument}/{product_type}/{start:%Y}/{start:%m}/{start:%d}/{granule_name.removesuffix('.nc')}"

    file_size = draw(integers(min_value=10_000, max_value=999_999_999))
    return CopernicusStorageGranule(start, granule_name, location, file_size)


@composite
def landsat_granules(draw: DrawFn) -> USGSLandsatStorageGranule:
    """Generate a realistic-looking random USGS Landsat granule."""
    time = draw(datetimes(min_value=datetime(1990, 1, 1), max_value=datetime(2025, 1, 1), timezones=just(None)))
    landsat_mission = draw(integers(min_value=1, max_value=9))

    path = draw(integers(min_value=1, max_value=999))
    row = draw(integers(min_value=1, max_value=999))

    granule_name = f"LC{landsat_mission:02d}_L1GT_{path:03d}{row:03d}_{time:%Y%m%d}_{time:%Y%m%d}_02_T1"
    location = f"s3://usgs-landsat/collection02/level-1/standard/oli-tirs/{time:%Y}/{path:03d}/{row:03d}/{granule_name}"
    thumbnail = draw(one_of(just(f"{granule_name}_thumb_small.jpeg"), just(None)))
    return USGSLandsatStorageGranule(
        time,
        granule_name,
        location,
        thumbnail,
    )
