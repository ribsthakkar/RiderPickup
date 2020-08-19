import logging.config
import yaml

with open('config/log_config.yaml', 'r') as cfg_file:
    log_config = yaml.load(cfg_file, Loader=yaml.FullLoader)
    log_config['disable_existing_loggers'] = False
    logging.config.dictConfig(log_config)

APP_CONFIG_FILE = 'config/app_config.yaml'
OPTIMIZER_CONFIG_FILE = 'config/optimizer_config.yaml'
