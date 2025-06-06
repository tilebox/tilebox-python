#!/usr/bin/env python

"""
A small utility helper script for publishing our packages to a private PyPi server.

Usage:

First, build the packages:
./build.sh

Then publish them (this script):
./publish.py publish-private-packages https://pypi.tilebox.com YOUR_TILEBOX_API_KEY dist/

(Optional) Then remove the private packages from the dists directory which we just uploaded:
./publish.py remove-private-packages dist/
This is useful for aftwards using the pypi-publish action to publish the public packages to pypi.org
"""

import sys
from pathlib import Path

import typer
from loguru import logger
from twine.commands.upload import upload
from twine.settings import Settings

app = typer.Typer()

# The packages to publish to pypi.org
_PUBLIC_PACKAGES = ["tilebox-grpc"]

# The packages to publish to all organizations of the private PyPi
_PACKAGES_FOR_ALL_ORGANIZATIONS = ["tilebox-datasets", "tilebox-storage", "tilebox-workflows"]

_PRIVATE_PACKAGES_PER_ORGANIZATION = {
    # Tilebox
    "org_2NMdQVI6zOjfYGVOOcM4h9vyn5c": [
        *_PACKAGES_FOR_ALL_ORGANIZATIONS,
    ],
    # ISEE
    "org_2WqJyOFhqplrneWEXyakXIT9lYg": [
        *_PACKAGES_FOR_ALL_ORGANIZATIONS,
    ],
    # PierSight
    "org_2WqKHe9qH42o21tYawXYPIfX46J": [*_PACKAGES_FOR_ALL_ORGANIZATIONS],
    # AHangler
    "org_2dgH2XmCgq97klxAETyU21yUobn": [*_PACKAGES_FOR_ALL_ORGANIZATIONS],
    # D-Orbit
    "org_2dY4wV4F1E07jzbhL30p1VrtBxG": [*_PACKAGES_FOR_ALL_ORGANIZATIONS],
    # Planetek
    "org_2dXq8XMZWw8aYjgNlcysZZl1Kwk": [*_PACKAGES_FOR_ALL_ORGANIZATIONS],
    # Airmo
    "org_2aijf8kVI9UPY6ayOnJA61IFpgw": [*_PACKAGES_FOR_ALL_ORGANIZATIONS],
}


@app.command()
def publish_private_packages(pypi_url: str, pypi_token: str, dists_directory: Path) -> None:
    logger.info(f"Publishing private packages to {pypi_url}")

    if pypi_url.endswith("/"):
        pypi_url = pypi_url[:-1]

    all_dists = sorted(list(dists_directory.glob("*.whl")) + list(dists_directory.glob("*.tar.gz")))

    for organization, packages in _PRIVATE_PACKAGES_PER_ORGANIZATION.items():
        twine_settings = Settings(username="-", password=pypi_token, repository_url=f"{pypi_url}/{organization}")
        dists = [str(dist) for dist in all_dists if _package_name(dist.name) in packages]
        logger.info(f"Uploading {len(dists)} packages for organization {organization}")
        upload(twine_settings, dists)
        logger.info(f"Upload succeeded for {len(dists)} packages for organization {organization}")


def _package_name(dist: str) -> str:
    """
    Extract a package name from a distribution file name

    Example:
        >>> _package_name("tilebox_datasets-0.1.0-py3-none-any.whl")
        "tilebox-datasets"
    """
    return dist.split("-")[0].replace("_", "-")


@app.command()
def remove_private_packages(dists_directory: Path) -> None:
    """
    Remove all private packages from the dists directory

    This is useful to run after publishing the private packages, so we can then use the pypi-publish action
    to publish the public packages to pypi.org

    Args:
        dists_directory: The directory containing the dists
    """
    for dist in dists_directory.iterdir():
        if dist.is_file() and _package_name(dist.name) not in _PUBLIC_PACKAGES:
            logger.info(f"Removing {dist.name} ({_package_name(dist.name)})")
            dist.unlink()


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="{level}: {message}", catch=True)
    app()
