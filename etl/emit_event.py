from prefect.events import emit_event
from etl.utils import mock_event_data

if __name__ == "__main__":
    emit_event(
        event="entsoe-event",
        resource={
            "prefect.resource.id": "entsoe-msg-webhook-id",
            "prefect.resource.name": "mock_event",
        },
        payload={"body": mock_event_data()},
    )
