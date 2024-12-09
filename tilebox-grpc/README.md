<h1 align="center">
  <img src="https://storage.googleapis.com/tbx-web-assets-2bad228/banners/tilebox-banner.svg" alt="Tilebox Logo">
  <br>
</h1>

<div align="center">
  <a href="https://pypi.org/project/tilebox-grpc/">
    <img src="https://img.shields.io/pypi/v/tilebox-grpc.svg?style=flat-square&label=version&color=f43f5e" alt="PyPi Latest Release badge"/>
  </a>
  <a href="https://pypi.org/project/tilebox-grpc/">
    <img src="https://img.shields.io/pypi/pyversions/tilebox-grpc.svg?style=flat-square&logo=python&color=f43f5e&logoColor=f43f5e" alt="Required Python Version badge"/>
  </a>
</div>

<p align="center">
  <a href="https://docs.tilebox.com/"><b>Documentation</b></a>
  |
  <a href="https://console.tilebox.com/"><b>Console</b></a>
  |
  <a href="https://tilebox.com/discord"><b>Discord</b></a>
</p>

# Tilebox GRPC

GRPC and Protobuf related functionality used by Tilebox python packages.

## Quickstart

Install using `pip`:

```bash
pip install tilebox-grpc
```

Open a gRPC channel:

```python
from _tilebox.grpc.channel import open_channel

channel = open_channel(
    "https://api.tilebox.com",
    auth_token="YOUR_TILEBOX_API_KEY"
)
```

## License

Distributed under the MIT License (`The MIT License`).
