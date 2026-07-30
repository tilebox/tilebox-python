from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from tilebox.datasets import iter_datapoints
from tilebox.datasets.assets import AssetCollection
from tilebox.datasets.datasets.stac.v1.asset_metadata_pb import (
    EOCommonName,
    EOProperties,
    RasterProperties,
)
from tilebox.datasets.datasets.stac.v1.asset_pb import (
    Asset,
    AssetAccessProfile,
    AssetLocation,
    Assets,
    Band,
    DataType,
    KnownAssetRole,
)
from tilebox.datasets.datasets.stac.v1.authentication_pb import (
    Authentication,
    AuthenticationFlow,
    AuthenticationParameter,
    SignedURLFlow,
)
from tilebox.datasets.datasets.stac.v1.authentication_pb import (
    AuthenticationScheme as AuthenticationSchemeProto,
)
from tilebox.datasets.datasets.stac.v1.storage_pb import KnownStorageType, Storage, StorageScheme

TESTDATA = Path(__file__).parent / "testdata"


def _scalar(**variables: object) -> xr.Dataset:
    return xr.Dataset({name: xr.DataArray(np.array(value, dtype=object)) for name, value in variables.items()})


def _read_real_fixture() -> tuple[Assets, Storage]:
    """Read real Sentinel-2 metadata captured from the public Tilebox dataset.

    These raw protobuf messages are the first result returned on 2026-07-29 by
    ``tilebox dataset query open_data.aws_earth.sentinel2 --last 10Y --limit 1``.
    The datapoint's STAC ID is ``S2A_T33TWM_20161102T100149_L2A``. It has no
    authentication metadata, so no synthetic Authentication fixture is stored.
    """
    assets = Assets.from_binary((TESTDATA / "sentinel2_assets.binpb").read_bytes())
    storage = Storage.from_binary((TESTDATA / "sentinel2_storage.binpb").read_bytes())
    return assets, storage


def test_real_sentinel2_fixture_decodes_to_self_contained_assets() -> None:
    assets_message, storage = _read_real_fixture()
    assets = AssetCollection.from_datapoint(_scalar(catalog=assets_message, storage=storage))

    assert len(assets) == 23
    red = assets["red"]
    assert red.primary.href.endswith("/S2A_T33TWM_20161102T100149_L2A/B04.tif")
    assert red.alternates["s3"].href == (
        "s3://e84-earth-search-sentinel-data/sentinel-2-c1-l2a/33/T/WM/2016/11/S2A_T33TWM_20161102T100149_L2A/B04.tif"
    )
    assert red.alternates["s3"].storage_schemes["earth-search"].region == "us-west-2"
    assert red.media_type == "image/tiff; application=geotiff; profile=cloud-optimized"
    assert red.roles == frozenset({KnownAssetRole.DATA, KnownAssetRole.REFLECTANCE})
    assert red.raster == RasterProperties(scale=0.0001, offset=-0.1, spatial_resolution=10)
    assert red.bands[0].data_type == DataType.UINT16
    assert red.bands[0].nodata == 0
    assert red.bands[0].raster == red.raster
    assert red.bands[0].eo == EOProperties(
        common_name=EOCommonName.RED,
        center_wavelength=0.665,
        full_width_half_max=0.038,
    )


def test_discovery_uses_descriptor_type_and_supports_overrides() -> None:
    root = Assets(
        access_profiles=[AssetAccessProfile(base_href="https://example.com/")],
        assets=[Asset(key="data", primary=AssetLocation(access_profile_index=0, href="data.tif"))],
    )
    datapoint = _scalar(not_named_assets=root, other=root)
    with pytest.raises(ValueError, match=r"ambiguous datasets\.stac\.v1\.Assets"):
        AssetCollection.from_datapoint(datapoint)

    decoded = AssetCollection.from_datapoint(datapoint, fields={"assets": "other"})
    assert decoded["data"].primary.href == "https://example.com/data.tif"
    with pytest.raises(ValueError, match="not present"):
        AssetCollection.from_datapoint(datapoint, fields={"assets": "missing"})


def test_context_ambiguity_and_explicit_override() -> None:
    root = Assets(
        access_profiles=[AssetAccessProfile(base_href="s3://bucket/", storage_refs=["main"])],
        assets=[Asset(key="data", primary=AssetLocation(access_profile_index=0, href="data.tif"))],
    )
    first = Storage(schemes={"main": StorageScheme(region="eu-west-1")})
    second = Storage(schemes={"main": StorageScheme(region="us-west-2")})
    datapoint = _scalar(root=root, first=first, second=second)
    with pytest.raises(ValueError, match=r"ambiguous datasets\.stac\.v1\.Storage"):
        AssetCollection.from_datapoint(datapoint)
    decoded = AssetCollection.from_datapoint(datapoint, fields={"storage": "second"})
    assert decoded["data"].primary.storage_schemes["main"].region == "us-west-2"


def test_locations_reuse_generated_storage_and_authentication_messages() -> None:
    root = Assets(
        access_profiles=[AssetAccessProfile(base_href="s3://bucket/", storage_refs=["main"], auth_refs=["signed"])],
        assets=[Asset(key="data", primary=AssetLocation(access_profile_index=0, href="data.tif"))],
    )
    scheme_message = StorageScheme(
        known_type=KnownStorageType.CUSTOM_S3,
        bucket="bucket",
        account="account",
    )
    storage = Storage(schemes={"main": scheme_message})
    signed_url = SignedURLFlow(parameters={"token": AuthenticationParameter(required=True)})
    authentication_scheme = AuthenticationSchemeProto(
        flows=[AuthenticationFlow(key="authorizationCode", signed_url=signed_url)]
    )
    authentication = Authentication(schemes={"signed": authentication_scheme})

    location = AssetCollection.from_datapoint(_scalar(root=root, storage=storage, authentication=authentication))[
        "data"
    ].primary
    scheme = location.storage_schemes["main"]
    assert scheme is scheme_message
    assert scheme.bucket == "bucket"
    assert scheme.account == "account"
    assert location.authentication_schemes["signed"] is authentication_scheme
    assert location.authentication_schemes["signed"].flows[0].signed_url == signed_url
    with pytest.raises(TypeError):
        location.storage_schemes["new"] = scheme  # type: ignore[index]


def test_alternate_href_absent_empty_and_nonempty_are_distinct() -> None:
    root = Assets(
        access_profiles=[
            AssetAccessProfile(base_href="https://primary/"),
            AssetAccessProfile(alternate_key="inherited", base_href="https://inherited/"),
            AssetAccessProfile(alternate_key="empty", base_href="https://empty/"),
            AssetAccessProfile(alternate_key="other", base_href="https://other/"),
        ],
        assets=[
            Asset(
                key="data",
                primary=AssetLocation(access_profile_index=0, href="file.tif"),
                alternates=[
                    AssetLocation(access_profile_index=1),
                    AssetLocation(access_profile_index=2, href=""),
                    AssetLocation(access_profile_index=3, href="different.tif"),
                ],
            )
        ],
    )
    decoded = AssetCollection.from_datapoint(_scalar(root=root))["data"]
    assert decoded.alternates["inherited"].href == "https://inherited/file.tif"
    assert decoded.alternates["empty"].href == "https://empty/"
    assert decoded.alternates["other"].href == "https://other/different.tif"


def test_band_inheritance_is_field_by_field() -> None:
    root = Assets(
        access_profiles=[AssetAccessProfile(base_href="file:///")],
        band_profiles=[Band(name="red", raster=RasterProperties(scale=2))],
        assets=[
            Asset(
                key="data",
                primary=AssetLocation(access_profile_index=0, href="tmp/data.tif"),
                band_profile_indices=[0],
                data_type=DataType.UINT16,
                nodata=-1,
                raster=RasterProperties(offset=3, spatial_resolution=10),
            )
        ],
    )
    band = AssetCollection.from_datapoint(_scalar(root=root))["data"].bands[0]
    assert band.data_type == DataType.UINT16
    assert band.nodata == -1
    assert band.raster == RasterProperties(scale=2, offset=3, spatial_resolution=10)


def test_missing_referenced_context_is_rejected() -> None:
    root = Assets(
        access_profiles=[AssetAccessProfile(base_href="s3://bucket/", storage_refs=["missing"])],
        assets=[Asset(key="data", primary=AssetLocation(access_profile_index=0, href="data.tif"))],
    )
    with pytest.raises(ValueError, match="missing storage scheme 'missing'"):
        AssetCollection.from_datapoint(_scalar(root=root))


def test_iter_datapoints_and_multi_datapoint_error() -> None:
    data = xr.Dataset({"value": ("time", [1, 2, 3])})
    assert [datapoint.value.item() for datapoint in iter_datapoints(data)] == [1, 2, 3]
    with pytest.raises(ValueError, match=r"(?s)received 3.*dimension 'time'"):
        AssetCollection.from_datapoint(data)
    with pytest.raises(ValueError, match=r"'sample'.*not present"):
        list(iter_datapoints(data, dimension="sample"))


def test_decoded_collections_are_deeply_immutable() -> None:
    assets_message, storage = _read_real_fixture()
    assets = AssetCollection.from_datapoint(_scalar(root=assets_message, storage=storage))
    with pytest.raises(TypeError):
        assets._assets["new"] = assets["red"]  # type: ignore[index]
    with pytest.raises(TypeError):
        assets["red"].alternates["new"] = assets["red"].primary  # type: ignore[index]
