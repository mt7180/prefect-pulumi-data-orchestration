import pathlib
from prefect.blocks.system import String
from typing import NamedTuple, List


class User(NamedTuple):
    name: str
    email: str


def get_users() -> List[User]:
    """here you could connect to your database (local, AWS or any other)
    but for the sake of simplicity in this example only a List
    with one user is returned
    """
    return [
        User(
            name="test_user",
            email=String.load("test-email").value,
        )
    ]


def mock_event_data() -> str:
    cfd = pathlib.Path(__file__).parent
    with open(cfd / "mock_data.txt", "r") as f:
        payload_str = f.read()
    return payload_str
