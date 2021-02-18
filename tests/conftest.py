import pytest
from .datasets import list_datasets
import aioredis


@pytest.fixture(scope="function", params=list_datasets)
async def prepare_data(request):
    """Фикстура подготовки и очистки данных"""
    dict_data, queue_settings, rabbit_settings, redis_settings, expected_result = request.param
    con = await aioredis.create_redis(address=(redis_settings.get('host'), redis_settings.get('port')))
    name_queue = 'queue:' + queue_settings.get('name_queue')
    await con.hmset_dict(
        name_queue,
        {"avg_speed_proc_cons": 1, "quantity_values_speed_proc_cons": 1, "avg_speed_start_cons": 0.0,
         "quantity_values_speed_start_cons": 0}
    )
    yield dict_data, queue_settings, rabbit_settings, redis_settings, expected_result
    print("\nCleaning prepared data")
    con = await aioredis.create_redis(address=(redis_settings.get('host'), redis_settings.get('port')))
    await con.delete(key='queue:' + queue_settings.get('name_queue'))
    del dict_data, queue_settings, rabbit_settings, redis_settings
