import json

"""Подготовка данных для метода calculation_consumers"""

# Обработка случая когда очередь пустая ---> return минимальное количество
data1 = {'consumer_count': 5, 'message_count': 0, 'avg_rate_consumers': 0, 'avg_rate_producers': 0}
expected_result1 = 2

# Обработка случая когда сообщения есть и консумеров 0 ---> return 1
data2 = {'consumer_count': 0, 'message_count': 50, 'avg_rate_consumers': 0, 'avg_rate_producers': 0}
expected_result2 = 1

# Обработка случая когда существующие консумеры справляются в допустимое время и можно уменьшать ---> return 3
data3 = {'consumer_count': 10, 'message_count': 150, 'avg_rate_consumers': 2.5, 'avg_rate_producers': 0}
expected_result3 = 3

# Обработка случая когда существующие консумеры не справляются в допустимое время и надо увеличивать  ---> return 6
data4 = {'consumer_count': 2, 'message_count': 450, 'avg_rate_consumers': 1.5, 'avg_rate_producers': 3}
expected_result4 = 6

# Обработка случая когда существующие консумеры не справляются в допустимое время и надо увеличивать,
# но максимальное число консумеров в настройках - 9 ---> return 9
data5 = {'consumer_count': 4, 'message_count': 1500, 'avg_rate_consumers': 0.5, 'avg_rate_producers': 2}
expected_result5 = 9

# Настройки из файла конфига
with open('tests/test1_config.json') as inf:
    settings = json.load(inf)

queue_settings = settings.get('Queues')[0]
rabbit_settings = settings.get('Rabbit')
redis_settings = settings.get('Redis')

# Формирование тестовых датасетов
first_dataset = (data1, queue_settings, rabbit_settings, redis_settings, expected_result1)
second_dataset = (data2, queue_settings, rabbit_settings, redis_settings, expected_result2)
third_dataset = (data3, queue_settings, rabbit_settings, redis_settings, expected_result3)
fourth_dataset = (data4, queue_settings, rabbit_settings, redis_settings, expected_result4)
fifth_dataset = (data5, queue_settings, rabbit_settings, redis_settings, expected_result5)

list_datasets = [first_dataset, second_dataset, third_dataset, fourth_dataset, fifth_dataset]
