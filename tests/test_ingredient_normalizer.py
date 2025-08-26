from unittest.mock import Mock, patch

from meals.ingredient_normalizer import (
    aggregate_items,
    normalize_ingredient,
    LOCAL_SYNONYMS,
)


@patch('meals.ingredient_normalizer.get_openai_client')
def test_normalize_ingredient_uses_api_and_cache(mock_client_factory):
    mock_client = Mock()
    mock_response = Mock()
    mock_response.output_text = "Bell Pepper"
    mock_client.responses.create.return_value = mock_response
    mock_client_factory.return_value = mock_client

    # first call hits API
    assert normalize_ingredient("Bell peppers") == "bell pepper"
    # second call should use cache, not API again
    assert normalize_ingredient("Bell peppers") == "bell pepper"
    assert mock_client.responses.create.call_count == 1


@patch('meals.ingredient_normalizer.get_openai_client', side_effect=Exception('api down'))
def test_normalize_ingredient_falls_back_to_synonyms(_mock_client_factory):
    LOCAL_SYNONYMS['capsicums'] = 'bell pepper'
    assert normalize_ingredient('capsicums') == 'bell pepper'


@patch('meals.ingredient_normalizer.get_openai_client')
def test_aggregate_items_uses_normalized_names(mock_client_factory):
    def create_side_effect(*args, **kwargs):
        prompt = kwargs['input'][0]['content']
        response = Mock()
        if 'Bell peppers' in prompt:
            response.output_text = 'bell pepper'
        else:
            response.output_text = prompt.split('\n')[1].strip().lower()
        return response

    mock_client = Mock()
    mock_client.responses.create.side_effect = create_side_effect
    mock_client_factory.return_value = mock_client

    items = [
        {'ingredient': 'Bell peppers', 'quantity': 1},
        {'ingredient': 'bell pepper', 'quantity': 2},
    ]
    result = aggregate_items(items)
    assert result == {'bell pepper': 3}
