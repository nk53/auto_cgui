import os
import ast
import time
import utils
import yaml
from os.path import join as pjoin
from splinter import Browser
from splinter.exceptions import ElementDoesNotExist
from BilayerBrowserProcess import BilayerBrowserProcess

class HMMMBrowserProcess(BilayerBrowserProcess):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.module_title = "HMMM Builder"
        self.module_url = "?doc=input/membrane.hmmm"
