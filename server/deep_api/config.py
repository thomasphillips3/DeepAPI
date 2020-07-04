"""
Configuration classes.
If used as script, will pretty print the CFG content
using the --config-file param.
Most of the script was taken from:
    https://gist.github.com/mattupstate/2046115
Classes:
    Config: extends Flask configuration to load from cfg
    Flask: extends Flask base class to load config from custom config
    CFG: saves all configuration
"""

import os
import yaml
import argparse
import beeprint
from flask import Flask as BaseFlask, Config as BaseConfig
from utils.exception import ConfigError


class CfgNode:
    """ Configuration Node. """
    def __init__(self, d):
        self.__dict__.update(d)


class CFG(CfgNode):
    """ Configuration Class """
    levels = {
        'DEVELOPMENT': 'DEBUG',
        'STAGING': 'INFO',
        'PRODUCTION': 'WARNING'}

    def __init__(self, config_file='./support/config.yaml'):
        # read config
        cfg = self._read_config(config_file)

        # load general config
        super(CFG, self).__init__(cfg['GENERAL'])
        self.LEVEL = self.levels[self.FLASK_ENV]

        # load env config
        self.ENV_CONFIG = cfg['ENV_CONFIG'][self.FLASK_ENV]

        # load model config
        self.MODEL = CfgNode(cfg['MODEL'])

        # setup log config
        self.LOG = cfg['LOG']

        # create output folder
        if not os.path.isdir(self.OUTPUT_FOLDER):
            os.mkdir(self.OUTPUT_FOLDER)

    def _read_config(self, config_file):
        """ Read the config as dict from file """
        with open(os.path.join(config_file), 'r') as stream:
            try:
                cfg = yaml.safe_load(stream)
                return cfg
            except yaml.YAMLError as exc:
                raise ConfigError(exc)


class Config(BaseConfig):
    """ Flask config enhanced - `from_cfg` method. """

    def from_cfg(self, cfg):
        self['ENV'] = cfg.FLASK_ENV.lower()
        for key in cfg.ENV_CONFIG:
            self[key] = cfg.ENV_CONFIG[key]


class Flask(BaseFlask):
    """ Extended version of `Flask` that implements custom config class """

    def make_config(self, instance_relative=False):
        root_path = self.root_path
        if instance_relative:
            root_path = self.instance_path
        return Config(root_path, self.default_config)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config-file',
                        default='./support/config.yaml')
    args = parser.parse_args()
    cfg = CFG(args.config_file)
    beerprint.pp(cfg)
