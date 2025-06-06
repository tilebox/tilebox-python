from tilebox.workflows.task import AsyncTask, SyncTask


def initialize_recurrent_task(task: SyncTask | AsyncTask) -> None:
    # needed to make it compatible with betterproto.Message serialization
    task.__dict__["_serialized_on_wire"] = False
    task.__dict__["_unknown_fields"] = b""
    task.__dict__["_group_current"] = {}
