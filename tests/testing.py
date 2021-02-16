from app_logic import CheckAndManagementScaling
import asyncio
import pytest


@pytest.mark.asyncio
async def test_calculate_consumers(prepare_data):
    """Тест подсчёта числа рекоммендуемых консумеров"""
    data, queue_settings, rabbit_settings, expected_result = prepare_data
    inst = CheckAndManagementScaling(queue_settings, rabbit_settings)

    task1 = asyncio.create_task(inst.calculation_consumers(consumer_count=data.get('consumer_count'),
                                                           message_count=data.get('message_count'),
                                                           avg_rate_consumers=data.get('avg_rate_consumers'),
                                                           avg_rate_producers=data.get('avg_rate_producers'),
                                                           ))

    received_result = await task1
    assert received_result == expected_result, f"Expected {expected_result} \n got {received_result} "
