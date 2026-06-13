import pytest
from pydantic import BaseModel
from doxygen_mcp.caveman import compress_text, compress_payload


class DummyModel(BaseModel):
    name: str
    info: str

    def model_dump(self, **kwargs):  # pylint: disable=unused-argument
        return {"name": self.name, "info": self.info}


@pytest.mark.parametrize(
    "input_text,expected",
    [
        # Edge cases
        (None, None),
        ("", ""),
        (123, 123),
        (3.14, 3.14),
        # Filler words removal
        # 'the' is removed by FILLER_RE, so we need to account for it in our expectations
        ("This is actually a really simple test", "This is simple test"),
        ("basically, we just need to authenticate", ", we need to auth"),
        (
            "Actually, I am happy to help",
            ", I am help",
        ),  # "happy to" -> removed. "Actually" -> removed.
        # Synonym replacements
        # "The" is removed.
        ("The authentication configuration is implemented", "auth config is impl"),
        ("Functions and arguments for the database", "Fns and args for DB"),
        ("INITIALIZE the repository", "INIT repo"),  # Case preservation test
        ("Initialize the Directory", "Init Dir"),  # Case preservation test
        # Whitespace cleanup
        ("This   has    many spaces", "This has many spaces"),
        ("Newlines\nare\tcompressed", "Newlines\nare compressed"),
        # Punctuation cleanup
        ("Hello , world !", "Hello, world!"),
        ("Wait ; what ?", "Wait; what?"),
        # Combined rules
        # "Actually," -> ",", "the" -> removed
        (
            "Actually, the authentication function    needs to be configured !",
            ", auth fn needs to be config!",
        ),
    ],
)
def test_compress_text(input_text, expected):
    """Test compress_text for various scenarios including edge cases, filler words, synonyms, and formatting."""
    assert compress_text(input_text) == expected


def test_compress_payload_dict():
    payload = {
        "id": 1,
        "name": "The authentication service",  # "The" is removed
        "nested": {"description": "This is actually really important !"},
    }
    expected = {
        "id": 1,
        "name": "auth service",
        "nested": {"description": "This is important!"},
    }
    assert compress_payload(payload) == expected


def test_compress_payload_list_and_tuple():
    payload = [
        "Initialize database",
        (1, "Configure environment"),
        ["Actually just testing"],
    ]
    expected = ["Init DB", (1, "Config env"), ["testing"]]
    assert compress_payload(payload) == expected


def test_compress_payload_pydantic_model():
    payload = DummyModel(
        name="Authentication Module",
        info="Basically it configures the database connection .",
    )
    compressed = compress_payload(payload)

    assert isinstance(compressed, DummyModel)
    assert compressed.name == "Auth Module"
    assert (
        compressed.info == "it configures DB conn."
    )  # "configures" -> is not a synonym rule!


def test_compress_payload_edge_cases():
    assert compress_payload(None) is None
    assert compress_payload(42) == 42
    assert compress_payload("") == ""
