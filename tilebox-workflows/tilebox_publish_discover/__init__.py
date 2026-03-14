"""Task discovery helper for tilebox publish-release.

This module is invoked as a subprocess by the CLI to discover publishable task
identifiers from a Python project.

Subprocess contract:
    uv run --project <project.root> python -m tilebox_publish_discover \
      --protocol tilebox.discovery.v1 \
      --runtime-kind python_uv \
      --discovery-kind python_explicit \
      --task <module:TaskClass> [--task <module:TaskClass> ...]

Success output JSON (stdout):
    {
      "ok": true,
      "protocol": "tilebox.discovery.v1",
      "runtime_kind": "python_uv",
      "discovery_kind": "python_explicit",
      "tasks": [
        {
          "name": "tilebox.example.MyTask",
          "version": "v1.3",
          "display": "MyTask",
          "source_ref": "workflow:MyTask"
        }
      ],
      "warnings": []
    }

Error output JSON (stdout):
    {
      "ok": false,
      "protocol": "tilebox.discovery.v1",
      "runtime_kind": "python_uv",
      "discovery_kind": "python_explicit",
      "code": "TBX-PUB-010",
      "message": "...",
      "hint": "...",
      "details": {}
    }
"""
