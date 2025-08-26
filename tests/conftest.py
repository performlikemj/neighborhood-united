import pytest, time
from unittest.mock import Mock

# Provide a lightweight stub for the `tiktoken` package so tests that import
# modules depending on it (e.g., utilities that compute token lengths) do not
# attempt to download model data during setup.
import sys
import types

# Stub out the `tiktoken` module to avoid network access during tests. The real
# library attempts to download model files on first use which is unnecessary for
# our unit tests.
if "tiktoken" not in sys.modules:
    stub = types.ModuleType("tiktoken")

    def encoding_for_model(_model):
        class _FakeEncoder:
            def encode(self, text):
                return [0] * len(text)

        return _FakeEncoder()

    stub.encoding_for_model = encoding_for_model
    sys.modules["tiktoken"] = stub

@pytest.fixture(autouse=True)
def _stub_external(monkeypatch, settings):
    if getattr(settings, 'TEST_MODE', False):
        monkeypatch.setattr('openai.ChatCompletion.create', Mock(return_value={
            'choices': [{'message': {'content': 'TEST'}}]})
        )
        monkeypatch.setattr('meals.youtube.find_related_youtube_videos',
            Mock(return_value={'status': 'success', 'videos': ['https://youtu.be/dQw4w9WgXcQ']})
        )
        monkeypatch.setattr('meals.meal_generation.generate_meal_details',
            Mock(return_value={'name': 'Test Meal', 'ingredients': []})
        )
        monkeypatch.setattr(time, 'sleep', lambda *_: None) 