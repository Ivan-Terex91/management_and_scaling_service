import json

# Подготовка данных для метода calculation_consumers
data1 = {'consumer_count': 0, 'message_count': 0, 'avg_rate_consumers': 0, 'avg_rate_producers': 0,}
expected_result1 = 0

data2 = {'consumer_count': 0, 'message_count': 10, 'avg_rate_consumers': 0, 'avg_rate_producers': 0}
expected_result2 = 2

data3 = {'consumer_count': 2, 'message_count': 10, 'avg_rate_consumers': 1, 'avg_rate_producers': 0.4}
expected_result3 = 1

# Настройки из файла конфига
with open('tests/test1_config.json') as inf:
    settings = json.load(inf)

queue_settings = settings.get('Queues')[0]
rabbit_settings = settings.get('Rabbit')

# Формирование тестовых датасетов
first_dataset = (data1, queue_settings, rabbit_settings, expected_result1)
second_dataset = (data2, queue_settings, rabbit_settings, expected_result2)
third_dataset = (data3, queue_settings, rabbit_settings, expected_result3)

list_datasets = [first_dataset, second_dataset, third_dataset]
