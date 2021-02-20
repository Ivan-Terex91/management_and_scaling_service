import asyncio
import aiohttp
import json
import logging.config
from logging_config import LOGGING_CONFIG
from math import ceil
import aioredis

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger('app_logger')


class CalculatingTheNeedScaling:
    """Класс вычисления потребности в масштабировании"""
    # TODO изменить название класса
    def __init__(self, queue_settings: dict, rabbit_settings: dict, redis_settings: dict):
        """
        :param queue_settings: параметры очереди
        :param rabbit_settings: настройки rabbitmq
        :param redis_settings: настройки redis
        """
        self.rabbit_name_queue = queue_settings.get('name_queue')
        self.min_consumers = queue_settings.get('min_quantity_consumers')
        self.max_consumers = queue_settings.get('max_quantity_consumers')
        self.default_consumers = queue_settings.get('default_quantity_consumers')
        self.freq_check = queue_settings.get('freq_check')
        ############
        self._max_allowed_time = queue_settings.get('max_allowed_time')
        self.max_allowed_time = self._max_allowed_time
        self.messages = 0
        self.consumers = 0
        ############
        # Параметры redis
        self.redis_host = redis_settings.get('host', '127.0.0.1')
        self.redis_port = redis_settings.get('port', '6379')
        self.number_db = redis_settings.get('db', 0)
        self.namespace_redis = 'queue:'
        # Параметры rabbit
        self.user = rabbit_settings.get('user')
        self.password = rabbit_settings.get('password')
        self.host = rabbit_settings.get('host')
        self.port = rabbit_settings.get('port')
        self.vhost = rabbit_settings.get('vhost')
        self.url = f"http://{self.host}:{self.port}/api/queues/{self.vhost}/{self.rabbit_name_queue}"

    async def polling_length_queue_and_count_consumers(self):
        """Метод опроса длины очереди и количества консумеров подписанных на очередь"""
        while True:
            try:
                # TODO  Может стоит перенести в main открывать сессию, а сюда передовать объект сессии
                # Опрашиваем очередь rabbit получаем response и берём из него количество консумеров и сообщений
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                            auth=aiohttp.BasicAuth(self.user, self.password),
                            url=self.url

                    ) as response:
                        # Райзим ошибки связанные с получение response от rabbit
                        if response.status != 200:
                            raise Exception(
                                f"request to {self.url} returned with error; status code {response.status}, reason {response.reason}")
                        response = await response.json()
                        # print(response['backing_queue_status'])
                    consumer_count = response.get('consumers')
                    message_count = response.get('messages')

                    ############
                    # if message_count > self.messages:
                    #     self.max_allowed_time = self._max_allowed_time
                    # self.messages = message_count
                    ############
                    # TODO это костыль, мне не очень нравится, но пока он необходим
                    if message_count > self.messages:
                        # Регулирование максимально допустимого времени
                        self.max_allowed_time = self._max_allowed_time
                        #  Когда в очереди появляются новые сообщения (0 ---> N),
                        #  то avg_rate_cons (средняя скорость обработки сообщений в очереди)
                        #  не совсем корректно использовать сразу, поэтому ставлю задержку
                        if self.messages == 0 and consumer_count > 0:
                            await asyncio.sleep(10)
                            self.messages = message_count
                            continue

                    if message_count == 0:
                        self.messages = message_count
                    # TODO конец костыля
                    # средняя скорость обработки сообщений в очереди (сообщ/сек)
                    avg_rate_consumers = response.get('backing_queue_status').get('avg_egress_rate')
                    # средняя скорость поступления сообщений в очередь (сообщ/сек)
                    avg_rate_producers = response.get('backing_queue_status').get('avg_ingress_rate')

                    # вызываем метод подсчёта консумеров
                    recommended_consumer_count = await self.calculation_consumers(message_count, consumer_count,
                                                                                  avg_rate_consumers, avg_rate_producers)

                    logger.info(
                        msg=f'Polling {self.rabbit_name_queue}, consumer_count={consumer_count}, message_count={message_count}')

                    #  будем отправлять recommended_consumer_count
            except Exception as e:
                # тут логируем ошибки
                logger.error(msg=e)

            await asyncio.sleep(self.freq_check)

    async def calculation_consumers(self, message_count: int, consumer_count: int, avg_rate_consumers: float,
                                    avg_rate_producers: float) -> int:
        """
        Метод рассчёта рекомендуемого количества консумеров
        :param message_count: количество сообщений в очереди
        :param consumer_count: количество консумеров
        :param avg_rate_consumers: средняя скорость обработки сообщений в очереди (сообщ/сек)
        :param avg_rate_producers: средняя скорость поступления сообщений в очередь (сообщ/сек)
        :return: recommended_consumer_count: рекомендумое количество консумеров
        Краткое описание алгоритма работы метода:
        1) Если сообщений в очереди нет, то рекомендуемое количество консумеров равно минимальному количеству в очереди.
        2) Если сообщений в очереди нет и по каким-то причинам консумеров тоже нет, осуществляем подсчёт консумеров
           следующим образом:
                - Получаем из базы среднюю скорость обработки одного консумера (сообщ/сек)
                - Вычисляем рекомендуемое число консумеров по следующей формуле:
                  (кол-во сообщений в очереди / сред.скор.обр-ки консумером) / максимально допустимое время
                - Результат окруляем в большую сторону
        3) Если сообщения есть и есть консумеры
           Обновляем статистику по консумерам в Redis. Рассчитываем время обработки сообщений существующими консумерами.
            3.1) Если максимально допустимое время <= времени обработки сущ. консумерами
                Если скорость поступления сообщения близкая к нулю (меньше 0.001 сообщ/сек),
                значит сущ. консумеры справляются и можно постепенно "схлопывать" ненужные, для этого делаем следующее:
                    - Рассчитываем необходимую скорость обработки чтобы уложиться в максимально допустимое время:
                        необходимая скорость обработки = количество сообщений в очереди / максимально допустимое время
                    - Рассчитываем рекомендуемое количество консумеров:
                        необходимая скорость обработки / сред.скор.обр-ки консумером
                    - Результат окруляем в большую сторону
                Если скорость поступления сообщения не меньше 0.001 сообщ/сек, наблюдаем за работой консумеров
            3.2) Если максимально допустимое время >= времени обработки сущ. консумерами
                 Рассчитываем рекомендумое количество консумеров как в п.3.1, если значение > максимально допустимого
                 числа консумеров, то возвращаем его
        """
        if message_count == 0:
            self.max_allowed_time = self._max_allowed_time
            recommended_consumer_count = self.min_consumers
            logger.info(
                f"name_queue={self.rabbit_name_queue}, consumer_count={consumer_count}, recommended_consumer_count={recommended_consumer_count}")
            return recommended_consumer_count
        elif consumer_count == 0:
            self.max_allowed_time = self.max_allowed_time - self.freq_check
            # Если консумеры не поднимаются в течении половины максимально допустимого времени,
            # даю лог с уровнем warning и переопределяю максимально допустимое время (логика обсуждаема)
            if self.max_allowed_time < self._max_allowed_time / 2:
                logger.warning(
                    f'There are no consumers in the {self.rabbit_name_queue} queue, but the messages_count = {message_count}'
                )
                self.max_allowed_time = self._max_allowed_time / 2


            # TODO Надо предусматреть случай если данных нет, пока по умолчанию даю константу если redis пустая
            avg_speed_proc_cons, quantity_values_speed_proc_cons = await self.read_data_from_redis()
            # Считаем количество консумеров необходимых для обработки сообщений в очереди в допустимое время
            recommended_consumer_count = ceil((message_count / avg_speed_proc_cons) / self.max_allowed_time)

            logger.info(
                f"name_queue={self.rabbit_name_queue}, consumer_count={consumer_count}, recommended_consumer_count={recommended_consumer_count}"
            )
            return recommended_consumer_count

        else:
            self.max_allowed_time = self.max_allowed_time - self.freq_check

            #  Тут получается есть сообщения и есть консумеры значит можно обновлять статистику
            avg_speed_proc_cons, quantity_values_speed_proc_cons = await self.read_data_from_redis()
            # Пересчитываем
            sum_speed_cons_in_db = avg_speed_proc_cons * quantity_values_speed_proc_cons
            quantity_values_speed_proc_cons += 1
            # Берём ср скорость одного консумера из rabbit
            avg_speed_proc_cons_in_rabbit = avg_rate_consumers / consumer_count
            avg_speed_proc_cons = (sum_speed_cons_in_db + avg_speed_proc_cons_in_rabbit) / quantity_values_speed_proc_cons

            await self.write_data_in_redis(avg_speed_proc_cons, quantity_values_speed_proc_cons)

            # время выполнения задач существующими консумерами
            messages_execution_time = message_count / (avg_speed_proc_cons * consumer_count)

            # Если кол-во консумеров которые есть недостаточно (точно не укладываемся во время),
            # даю лог с уровнем warning и переопределяю максимально допустимое время (логика обсуждаема)
            if self.max_allowed_time < self._max_allowed_time / 2 and self.max_allowed_time < messages_execution_time:
                logger.warning(
                    f'There are only {consumer_count} consumers in the {self.rabbit_name_queue} queue, but the messages_count={message_count}'
                )
                self.max_allowed_time = self._max_allowed_time / 2

            if messages_execution_time <= self.max_allowed_time:
                # Скорость поступления сообщений около 0
                if avg_rate_producers < 0.001:
                    # Тут можно потихоньку схлопывать консумеры
                    # Считаем сколько нужно консумеров чтобы уложиться в допустимое время
                    required_speed_processing = message_count / self.max_allowed_time
                    recommended_consumer_count = ceil(required_speed_processing / avg_speed_proc_cons)
                    logger.info(
                        f"name_queue={self.rabbit_name_queue}, existing consumer count enough"
                    )
                    logger.info(
                        f"name_queue={self.rabbit_name_queue}, consumer_count={consumer_count}, recommended_consumer_count={recommended_consumer_count}"
                    )
                else:
                    # Не меняем количество консумеров, наблюдаем за работой
                    recommended_consumer_count = consumer_count
                    logger.info(
                        f"name_queue={self.rabbit_name_queue}, consumer_count={consumer_count}, recommended_consumer_count={recommended_consumer_count}"
                    )
                return recommended_consumer_count
            else:
                # TODO может вынесу формулу в отдельный метод, повторяется 2-й раз
                # Считаем сколько нужно консумеров чтобы уложиться в допустимое время
                required_speed_processing = message_count / self.max_allowed_time
                recommended_consumer_count = ceil(required_speed_processing / avg_speed_proc_cons)

                if recommended_consumer_count > self.max_consumers:
                    logger.warning(
                        f"name_queue={self.rabbit_name_queue}, consumer_count={consumer_count}, recommended_consumer_count={recommended_consumer_count}, "
                        f"max_allowed_consumer_count={self.max_consumers}"
                    )
                    return self.max_consumers

                logger.info(
                    f"name_queue={self.rabbit_name_queue}, consumer_count={consumer_count}, recommended_consumer_count={recommended_consumer_count}"
                )
                return recommended_consumer_count

    async def init_redis(self):
        """Метод инициализации данных в redis"""
        red = await aioredis.create_redis(address=(self.redis_host, self.redis_port), encoding='utf8')
        name_queue = self.namespace_redis + self.rabbit_name_queue
        if not await red.exists(name_queue):
            await red.hmset_dict(
                name_queue,
                {"avg_speed_proc_cons": 1, "quantity_values_speed_proc_cons": 1, "avg_speed_start_cons": 0.0,
                 "quantity_values_speed_start_cons": 0}
            )

    async def read_data_from_redis(self):
        """Метод чтения данных из redis"""
        name_queue = self.namespace_redis + self.rabbit_name_queue
        conn = await aioredis.create_redis(address=(self.redis_host, self.redis_port), encoding='utf8')
        avg_speed_proc_cons = float(await conn.hget(key=name_queue, field='avg_speed_proc_cons'))
        quantity_values_speed_proc_cons = int(await conn.hget(key=name_queue,
                                                              field='quantity_values_speed_proc_cons'))
        return avg_speed_proc_cons, quantity_values_speed_proc_cons

    async def write_data_in_redis(self, avg_speed_proc_cons, quantity_values_speed_proc_cons):
        """Метод записи данных в редис"""
        name_queue = self.namespace_redis + self.rabbit_name_queue
        conn = await aioredis.create_redis(address=(self.redis_host, self.redis_port), encoding='utf8')
        await conn.hset(key=name_queue, field='avg_speed_proc_cons', value=avg_speed_proc_cons)
        await conn.hset(key=name_queue, field='quantity_values_speed_proc_cons',
                        value=quantity_values_speed_proc_cons)

    async def __call__(self, *args, **kwargs):
        await self.init_redis()
        await self.polling_length_queue_and_count_consumers()


class ManagingScaling:
    """Класс управления масштабированием"""
    pass


async def main():
    """Точка входа"""

    with open('test_config.json') as inf:
        settings = json.load(inf)

    # Берём настройки Rabbit и redis
    rabbit_settings = settings.get('Rabbit')
    redis_settings = settings.get('Redis')
    # Список экземпляров классов check_scaling (очередь-экземпляр)
    list_rabbit_queues = []

    for queue_settings in settings.get('Queues'):
        list_rabbit_queues.append(
            CalculatingTheNeedScaling(queue_settings, rabbit_settings, redis_settings)
        )

    # Создание списка задач на вычисления потребности в масштабировании
    tasks = [asyncio.create_task(inst_check_scaling()) for inst_check_scaling in list_rabbit_queues]
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    asyncio.run(main())
