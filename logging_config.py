LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'json_formatter': {
            'class': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
    },
    'handlers': {
        'stream_handler': {
            'level': 'DEBUG',
            'formatter': 'json_formatter',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
        },
        'file_handler': {
            'level': 'DEBUG',
            'formatter': 'json_formatter',
            'class': "logging.handlers.TimedRotatingFileHandler",
            'filename': 'logfiles/test_logfile.log',
            'when': 'M',  # Надо поменять потом подумаю на сколько
            'encoding': 'utf-8'
        },
    },
    'loggers': {
        'app_logger': {  # root logger
            'handlers': ['stream_handler', 'file_handler'],
            'level': 'DEBUG',
            'propagate': True,
        }
    },
}

# logging.config.dictConfig(LOGGING_CONFIG)
