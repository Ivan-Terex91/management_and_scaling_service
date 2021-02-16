import pytest
from .datasets import list_datasets


@pytest.fixture(scope="function", params=list_datasets)
def prepare_data(request):
    """Фикстура подготовки и очистки данных"""
    dict_data, queue_settings, rabbit_settings, expected_result = request.param
    yield dict_data, queue_settings, rabbit_settings, expected_result
    print("\nCleaning prepared data")
    del dict_data, queue_settings, rabbit_settings
