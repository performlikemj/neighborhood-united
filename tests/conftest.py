import pytest, time
from unittest.mock import Mock

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