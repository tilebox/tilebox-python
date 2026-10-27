# Tilebox gRPC

Compatibility package for the 0.68 release. This package contains no Python modules;
it depends on `tilebox-core>=0.68.0`, which now owns the shared SDK infrastructure.
Use `tilebox-core` directly in new dependency declarations. This shim is retained for
one release and is planned for removal afterward.
