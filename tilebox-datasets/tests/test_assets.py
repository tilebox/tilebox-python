from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from tilebox.datasets import iter_datapoints
from tilebox.datasets.assets import (
    Asset,
    AssetCollection,
    AssetLocation,
    Band,
    MediaType,
)
from tilebox.datasets.datasets.stac.v1.asset_metadata_pb import (
    EOCommonName,
    EOProperties,
    RasterProperties,
)
from tilebox.datasets.datasets.stac.v1.asset_pb import (
    Asset as ProtoAsset,
)
from tilebox.datasets.datasets.stac.v1.asset_pb import (
    AssetAccessProfile,
    Assets,
    DataType,
    KnownAssetRole,
)
from tilebox.datasets.datasets.stac.v1.asset_pb import AssetLocation as ProtoAssetLocation
from tilebox.datasets.datasets.stac.v1.asset_pb import Band as ProtoBand
from tilebox.datasets.datasets.stac.v1.authentication_pb import (
    Authentication,
    AuthenticationFlow,
    AuthenticationParameter,
    OAuth2Flow,
    SignedURLFlow,
)
from tilebox.datasets.datasets.stac.v1.authentication_pb import (
    AuthenticationScheme as AuthenticationSchemeProto,
)
from tilebox.datasets.datasets.stac.v1.core_pb import KnownMediaType
from tilebox.datasets.datasets.stac.v1.core_pb import MediaType as ProtoMediaType
from tilebox.datasets.datasets.stac.v1.sar_pb import (
    SARFrequencyBand,
    SARObservationDirection,
    SARPolarization,
    SARProperties,
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


def test_real_sentinel2_fixture_recompiles_to_identical_optimized_fields() -> None:
    """The public AWS Earth Search fixture retains the Go compiler's canonical layout."""
    assets_message, storage = _read_real_fixture()
    decoded = AssetCollection.from_datapoint(_scalar(assets=assets_message, storage=storage))

    fields = AssetCollection.from_assets(decoded.values()).to_fields()

    assert fields["assets"].to_binary() == assets_message.to_binary()
    assert fields["storage"].to_binary() == storage.to_binary()
    assert len(fields["assets"].access_profiles) == 2
    assert len(fields["assets"].band_profiles) == 12


def test_asset_authoring_compiles_profiles_registries_and_custom_field_names() -> None:
    scheme = StorageScheme(known_type=KnownStorageType.AWS_S3, region="eu-central-1")
    authentication_scheme = AuthenticationSchemeProto(name="signed")
    assets = AssetCollection.from_assets(
        [
            Asset(
                key="red",
                primary=AssetLocation(
                    "https://example.com/item/red.tif",
                    storage_schemes={"main": scheme},
                    authentication_schemes={"signed": authentication_scheme},
                ),
                alternates={
                    "s3": AssetLocation(
                        "s3://bucket/item/red.tif",
                        alternate_name="Amazon S3",
                        storage_schemes={"main": scheme},
                        authentication_schemes={"signed": authentication_scheme},
                    )
                },
                media_type="image/tiff; application=geotiff; profile=cloud-optimized",
                roles=frozenset({"data", "custom-role"}),
            ),
            Asset(
                key="green",
                primary=AssetLocation(
                    "https://example.com/item/green.tif",
                    storage_schemes={"main": scheme},
                    authentication_schemes={"signed": authentication_scheme},
                ),
                alternates={
                    "s3": AssetLocation(
                        "s3://bucket/item/green.tif",
                        alternate_name="Amazon S3",
                        storage_schemes={"main": scheme},
                        authentication_schemes={"signed": authentication_scheme},
                    )
                },
            ),
        ]
    )

    fields = assets.to_fields(fields={"assets": "catalog", "storage": "store", "authentication": "auth"})
    root = fields["catalog"]
    assert isinstance(root, Assets)
    assert root.access_profiles == [
        AssetAccessProfile(base_href="https://example.com/item/", storage_refs=["main"], auth_refs=["signed"]),
        AssetAccessProfile(
            alternate_key="s3",
            default_alternate_name="Amazon S3",
            base_href="s3://bucket/item/",
            storage_refs=["main"],
            auth_refs=["signed"],
        ),
    ]
    assert all(not alternate.has_field("href") for asset in root.assets for alternate in asset.alternates)
    assert fields["store"] == Storage(schemes={"main": scheme})
    assert fields["auth"] == Authentication(schemes={"signed": authentication_scheme})
    compiled_red = next(asset for asset in root.assets if asset.key == "red")
    assert assets["red"].roles == frozenset({KnownAssetRole.DATA, "custom-role"})
    assert compiled_red.roles == [KnownAssetRole.DATA]
    assert compiled_red.custom_roles == ["custom-role"]
    decoded = AssetCollection.from_datapoint(
        _scalar(catalog=root, store=fields["store"], auth=fields["auth"]),
        fields={"assets": "catalog", "storage": "store", "authentication": "auth"},
    )
    assert decoded == assets
    assert decoded["red"] == assets["red"]
    assert decoded["green"] == assets["green"]


def test_media_type_has_string_enum_semantics_and_compact_encoding() -> None:
    assert isinstance(MediaType.CLOUD_OPTIMIZED_GEOTIFF, str)
    assert str(MediaType.CLOUD_OPTIMIZED_GEOTIFF) == ("image/tiff; application=geotiff; profile=cloud-optimized")

    assets = AssetCollection.from_assets(
        [
            Asset(
                key="enum",
                primary=AssetLocation("https://example.com/enum.tif"),
                media_type=MediaType.CLOUD_OPTIMIZED_GEOTIFF,
            ),
            Asset(
                key="known-string",
                primary=AssetLocation("https://example.com/known-string.json"),
                media_type="application/json",
            ),
            Asset(
                key="custom",
                primary=AssetLocation("https://example.com/custom.bin"),
                media_type="application/x-example",
            ),
        ]
    )

    compiled = assets.to_fields()["assets"]
    compiled_by_key = {asset.key: asset for asset in compiled.assets}
    assert compiled_by_key["enum"].media_type == ProtoMediaType(known=KnownMediaType.CLOUD_OPTIMIZED_GEOTIFF)
    assert compiled_by_key["known-string"].media_type == ProtoMediaType(known=KnownMediaType.JSON)
    assert compiled_by_key["custom"].media_type == ProtoMediaType(custom="application/x-example")

    decoded = AssetCollection.from_datapoint(_scalar(assets=compiled))
    assert decoded["enum"].media_type is (MediaType.CLOUD_OPTIMIZED_GEOTIFF)
    assert decoded["known-string"].media_type is MediaType.JSON
    assert decoded["custom"].media_type == "application/x-example"


def test_primary_and_alternate_names_round_trip() -> None:
    assets = AssetCollection.from_assets(
        [
            Asset(
                key="red",
                primary=AssetLocation("https://example.com/red.tif", alternate_name="HTTPS"),
                alternates={
                    "s3": AssetLocation("s3://bucket/red.tif", alternate_name="Amazon S3"),
                },
            ),
            Asset(
                key="green",
                primary=AssetLocation("https://example.com/green.tif", alternate_name="HTTPS"),
                alternates={
                    "s3": AssetLocation("s3://bucket/green.tif", alternate_name="Amazon S3"),
                },
            ),
        ]
    )

    compiled = assets.to_fields()["assets"]
    profiles = {profile.alternate_key: profile for profile in compiled.access_profiles}

    assert profiles[""].default_alternate_name == "HTTPS"
    assert profiles["s3"].default_alternate_name == "Amazon S3"
    assert all(asset.primary is not None and not asset.primary.has_field("alternate_name") for asset in compiled.assets)
    assert AssetCollection.from_datapoint(_scalar(assets=compiled)) == assets

    names_with_no_common_default = AssetCollection.from_assets(
        [
            Asset(
                key="red",
                primary=AssetLocation("https://example.com/red.tif", alternate_name="HTTPS"),
                alternates={"s3": AssetLocation("s3://bucket/red.tif", alternate_name="Amazon S3")},
            ),
            Asset(
                key="green",
                primary=AssetLocation("https://example.com/green.tif"),
                alternates={"s3": AssetLocation("s3://bucket/green.tif", alternate_name="S3 mirror")},
            ),
        ]
    )

    compiled = names_with_no_common_default.to_fields()["assets"]
    assert all(not profile.has_field("default_alternate_name") for profile in compiled.access_profiles)

    decoded = AssetCollection.from_datapoint(_scalar(assets=compiled))
    assert decoded["red"].primary.alternate_name == "HTTPS"
    assert decoded["green"].primary.alternate_name is None
    assert decoded["red"].alternates["s3"].alternate_name == "Amazon S3"
    assert decoded["green"].alternates["s3"].alternate_name == "S3 mirror"


def test_field_names_are_validated_at_runtime() -> None:
    assets = AssetCollection.from_assets([Asset(key="data", primary=AssetLocation("https://example.com/data.tif"))])
    datapoint = _scalar(assets=assets.to_fields()["assets"])

    for fields, error in (
        ({"unknown": "value"}, "unknown asset field names"),
        ({"assets": ""}, "cannot be empty"),
        ({"storage": "assets"}, "must be distinct"),
    ):
        with pytest.raises(ValueError, match=error):
            assets.to_fields(fields=fields)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match=error):
            AssetCollection.from_datapoint(datapoint, fields=fields)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="must be a string"):
        assets.to_fields(fields={"assets": 1})  # type: ignore[typeddict-item]


def test_band_compilation_lifts_metadata_and_interns_profiles() -> None:
    band = Band(
        name="red",
        data_type=DataType.UINT16,
        nodata=0,
        eo=EOProperties(common_name=EOCommonName.RED, center_wavelength=0.665),
        raster=RasterProperties(scale=0, offset=0, spatial_resolution=10),
    )
    assets = AssetCollection.from_assets(
        Asset(
            key=key,
            primary=AssetLocation(f"https://example.com/{key}.tif"),
            bands=(band,),
        )
        for key in ("red-a", "red-b")
    )

    root = assets.to_fields()["assets"]

    assert len(root.band_profiles) == 1
    assert [asset.band_profile_indices for asset in root.assets] == [[0], [0]]
    assert all(asset.data_type == DataType.UINT16 for asset in root.assets)
    assert all(asset.has_field("nodata") and asset.nodata == 0 for asset in root.assets)
    assert all(asset.raster == RasterProperties(scale=0, offset=0, spatial_resolution=10) for asset in root.assets)
    assert all(asset.eo is None for asset in root.assets)
    assert root.band_profiles[0].eo == band.eo
    decoded = AssetCollection.from_datapoint(_scalar(assets=root))
    assert decoded == assets
    assert decoded["red-a"] == assets["red-a"]
    assert decoded["red-b"] == assets["red-b"]


def test_sar_metadata_is_lifted_field_by_field_and_round_trips() -> None:
    def sar_properties(resolution_range: float | None = None) -> SARProperties:
        return SARProperties(
            polarizations=[SARPolarization.VV],
            instrument_mode="IW",
            frequency_band=SARFrequencyBand.C,
            center_frequency=5.405,
            resolution_range=resolution_range,
            looks_range=0,
            observation_direction=SARObservationDirection.RIGHT,
            beam_ids=["beam"],
        )

    assets = AssetCollection.from_assets(
        [
            Asset(
                key="data",
                primary=AssetLocation("https://example.com/data.tif"),
                bands=(
                    Band(name="vv-near", sar=sar_properties(10)),
                    Band(name="vv-far", sar=sar_properties(20)),
                ),
            )
        ]
    )

    root = assets.to_fields()["assets"]
    compiled = root.assets[0]

    assert compiled.sar == sar_properties()
    sar_profiles = [profile.sar for profile in root.band_profiles]
    assert all(profile is not None for profile in sar_profiles)
    assert [profile.resolution_range for profile in sar_profiles if profile is not None] == [20, 10]
    assert all(profile.has_field("resolution_range") for profile in sar_profiles if profile is not None)
    assert all(not profile.has_field("center_frequency") for profile in sar_profiles if profile is not None)
    assert AssetCollection.from_datapoint(_scalar(assets=root)) == assets


def test_asset_authoring_validation_and_registry_merge() -> None:
    location = AssetLocation("https://example.com/data.tif")
    with pytest.raises(ValueError, match="asset key cannot be empty"):
        AssetCollection.from_assets([Asset(key="", primary=location)])
    with pytest.raises(ValueError, match="duplicate asset key"):
        AssetCollection.from_assets([Asset(key="data", primary=location), Asset(key="data", primary=location)])

    scheme = StorageScheme(region="eu-west-1")
    assets = AssetCollection.from_assets(
        [Asset(key="data", primary=AssetLocation(location.href, storage_schemes={"main": scheme}))]
    )
    fields = assets.to_fields(storage=Storage(schemes={"link-only": StorageScheme(region="us-west-2")}))
    assert set(fields["storage"].schemes) == {"main", "link-only"}
    with pytest.raises(ValueError, match="conflicting scheme"):
        assets.to_fields(storage=Storage(schemes={"main": StorageScheme(region="different")}))
    with pytest.raises(ValueError, match="field names must be distinct"):
        assets.to_fields(fields={"storage": "assets"})

    first_auth = AuthenticationSchemeProto(flows=[AuthenticationFlow(oauth2=OAuth2Flow(scopes={"a": "A", "b": "B"}))])
    equal_auth = AuthenticationSchemeProto(flows=[AuthenticationFlow(oauth2=OAuth2Flow(scopes={"b": "B", "a": "A"}))])
    assets_with_auth = AssetCollection.from_assets(
        [
            Asset(
                key="data",
                primary=AssetLocation(location.href, authentication_schemes={"oauth": first_auth}),
            )
        ]
    )
    assert (
        assets_with_auth.to_fields(authentication=Authentication(schemes={"oauth": equal_auth}))[
            "authentication"
        ].schemes["oauth"]
        == equal_auth
    )


def test_nan_and_empty_band_extensions_round_trip_semantically() -> None:
    assets = AssetCollection.from_assets(
        [
            Asset(
                key="data",
                primary=AssetLocation("https://example.com/data.tif"),
                bands=(Band(name="band", nodata=float("nan"), eo=EOProperties()),),
            )
        ]
    )

    packed = assets.to_fields()["assets"]
    reparsed = Assets.from_binary(packed.to_binary())
    decoded = AssetCollection.from_datapoint(_scalar(assets=reparsed))

    assert packed.assets[0].has_field("nodata")
    assert not packed.band_profiles[0].has_field("nodata")
    assert decoded == assets


@pytest.mark.parametrize(
    ("root", "error"),
    [
        (
            Assets(
                access_profiles=[AssetAccessProfile(base_href="https://example.com/")],
                assets=[ProtoAsset(primary=ProtoAssetLocation(access_profile_index=0, href="data.tif"))],
            ),
            "asset key cannot be empty",
        ),
        (
            Assets(
                access_profiles=[AssetAccessProfile(alternate_key="s3", base_href="s3://bucket/")],
                assets=[ProtoAsset(key="data", primary=ProtoAssetLocation(access_profile_index=0, href="data.tif"))],
            ),
            "primary location uses alternate profile",
        ),
        (
            Assets(
                access_profiles=[AssetAccessProfile()],
                assets=[ProtoAsset(key="data", primary=ProtoAssetLocation(access_profile_index=0, href=""))],
            ),
            "primary location href cannot be empty",
        ),
        (
            Assets(
                access_profiles=[AssetAccessProfile(base_href="https://example.com/")],
                assets=[
                    ProtoAsset(
                        key="data",
                        primary=ProtoAssetLocation(access_profile_index=0, href="data.tif"),
                        roles=[KnownAssetRole.UNSPECIFIED],
                    )
                ],
            ),
            "invalid role",
        ),
    ],
)
def test_malformed_assets_messages_are_rejected(root: Assets, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        AssetCollection.from_datapoint(_scalar(assets=root))


@pytest.mark.parametrize(
    "media_type",
    [
        ProtoMediaType(),
        ProtoMediaType(known=KnownMediaType.JSON, custom="application/custom"),
        ProtoMediaType(known=KnownMediaType.UNSPECIFIED),
        ProtoMediaType(custom=""),
    ],
)
def test_malformed_media_types_are_rejected(media_type: ProtoMediaType) -> None:
    root = Assets(
        access_profiles=[AssetAccessProfile(base_href="https://example.com/")],
        assets=[
            ProtoAsset(
                key="data",
                primary=ProtoAssetLocation(access_profile_index=0, href="data.tif"),
                media_type=media_type,
            )
        ],
    )
    with pytest.raises(ValueError, match="media type"):
        AssetCollection.from_datapoint(_scalar(assets=root))


def test_discovery_uses_descriptor_type_and_supports_overrides() -> None:
    root = Assets(
        access_profiles=[AssetAccessProfile(base_href="https://example.com/")],
        assets=[ProtoAsset(key="data", primary=ProtoAssetLocation(access_profile_index=0, href="data.tif"))],
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
        assets=[ProtoAsset(key="data", primary=ProtoAssetLocation(access_profile_index=0, href="data.tif"))],
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
        assets=[ProtoAsset(key="data", primary=ProtoAssetLocation(access_profile_index=0, href="data.tif"))],
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
            ProtoAsset(
                key="data",
                primary=ProtoAssetLocation(access_profile_index=0, href="file.tif"),
                alternates=[
                    ProtoAssetLocation(access_profile_index=1),
                    ProtoAssetLocation(access_profile_index=2, href=""),
                    ProtoAssetLocation(access_profile_index=3, href="different.tif"),
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
        band_profiles=[ProtoBand(name="red", raster=RasterProperties(scale=2))],
        assets=[
            ProtoAsset(
                key="data",
                primary=ProtoAssetLocation(access_profile_index=0, href="tmp/data.tif"),
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
        assets=[ProtoAsset(key="data", primary=ProtoAssetLocation(access_profile_index=0, href="data.tif"))],
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
