"""
Hypothesis strategies for generating random granules for testing storage client related functionality.

This module is intentionally not named just 'data', to avoid multiple 'tests.data' modules in our mono-repo, which
can confuse the test runner.
"""

import string
from datetime import datetime
from pathlib import Path

from hypothesis.strategies import DrawFn, booleans, composite, datetimes, integers, just, one_of, text, uuids

from tilebox.storage.granule import ASFStorageGranule, CopernicusStorageGranule, UmbraStorageGranule
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

    return ASFStorageGranule(time, granule_name, level, "ASF", file_size, md5sum, urls)


@composite
def s1_granules(draw: DrawFn) -> ASFStorageGranule:
    """Generate a realistic-looking random Sentinel 1 granule."""
    level = "RAW"
    platform = draw(one_of(just("A"), just("B")))
    acquisition_mode = draw(one_of(*(just(am) for am in ["IW", "EW", *[f"S{i + 1}" for i in range(6)]])))
    start = draw(datetimes(min_value=datetime(2014, 6, 1), max_value=datetime(2050, 1, 1), timezones=just(None)))
    stop = draw(datetimes(min_value=datetime(2014, 6, 1), max_value=datetime(2050, 1, 1), timezones=just(None)))
    orbit = draw(integers(min_value=1, max_value=999_999))
    random_1 = draw(text(alphabet=string.hexdigits, min_size=6, max_size=6)).upper()
    random_2 = draw(text(alphabet=string.hexdigits, min_size=4, max_size=4)).upper()
    file_size = draw(integers(min_value=10_000, max_value=999_999_999))
    md5sum = draw(text(alphabet=string.hexdigits, min_size=32, max_size=32))

    granule_name = (
        f"S1{platform}_{acquisition_mode}_{level}__0SDV_{start:%Y%m%dT%H%M%S}_{stop:%Y%m%dT%H%M%S}_"
        f"{orbit:06d}_S{random_1}_{random_2}"
    )

    urls = StorageURLs(f"{_ASF_URL}/{level}/S{platform}/{granule_name}.zip", None)
    return ASFStorageGranule(start, granule_name, level, "ASF", file_size, md5sum, urls)


@composite
def asf_granules(draw: DrawFn) -> ASFStorageGranule:
    return draw(one_of(ers_granules(), s1_granules()))


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
