import yaml
import logging

class Config:
    def __init__(self, config_file):
        self.config_file = config_file
        self.config = self.load_config()

    def load_config(self):
        logging.debug(f"Loading configuration from {self.config_file}")
        try:
            with open(self.config_file, 'r') as stream:
                config = yaml.safe_load(stream)
                logging.debug(f"Loaded configuration: {config}")
        except FileNotFoundError:
            logging.error(f"Configuration file {self.config_file} not found")
            config = {}
        except yaml.YAMLError as exc:
            logging.error(f"Error while parsing the configuration file: {exc}")
            config = {}
        return config

    def get_param(self, param):
        value = self.config.get(param, None)
        if value is None:
            logging.warning(f"Parameter {param} not found in configuration")
        else:
            logging.debug(f"Parameter {param} = {value}")
        return value

    def substitute_variables(self, code):
        for key, value in self.config.items():
            code = code.replace(f"${{{key}}}", str(value))
        return code
