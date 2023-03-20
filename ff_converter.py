"""Handle steps of Force Field Converter."""
import ast
import os
import re
import time
from os.path import join as pjoin
from input_generator import InputBrowserProcess
from utils import set_elem_value, set_form_value

_BROWSER_PROCESS = 'FFConverterBrowserProcess'

class FFConverterBrowserProcess(InputBrowserProcess):
    """Implements actions for all Force Field Converter options"""
    def __init__(self, *args, **kwargs):
        self.module_title = "Force Field Converter"
        self.module_url = "?doc=input/converter.ffconverter"
        super().__init__(*args, **kwargs)

    def init_system(self, **kwargs):
        url = self.base_url + self.module_url
        module_title = self.module_title

        if not kwargs.get('resume'):
            self.browser.visit(url)

            psf = self.test_case.get('psf')
            crd = self.test_case.get('crd')

            if psf is None:
                raise KeyError("Missing PSF")

            if crd is None:
                raise KeyError("Missing CRD")

            self.browser.find_by_id('psffile').fill(pjoin(self.base, psf))
            self.browser.find_by_id('crdfile').fill(pjoin(self.base, crd))

            toppar = self.test_case.get('toppar')
            if toppar is not None:
                set_form_value(self.browser, 'add_toppar', True)
                add_button = self.browser.find_by_id('add_toppar')

                for _ in range(len(toppar)-1):
                    add_button.click()

                file_types = self.browser.find_by_attrs(name="toppar_types[]")
                file_uploads = self.browser.find_by_attrs(name="toppar_files[]")

                for file_index, toppar_file in enumerate(toppar):
                    file_type = file_types[file_index]
                    file_upload = file_upload[file_index]

                    toppar_file = pjoin(self.base, toppar_file)
                    ext = os.path.splitext(toppar_file)[1].lower()

                    set_elem_value(file_type, ext)
                    file_upload.fill(toppar_file)

            pbc = self.test_case.get('pbc')
            set_form_value(self.browser, 'setup_pbc', pbc)
            if pbc is not None:
                solvtype = pbc.get('solvtype')
                if solvtype is None:
                    raise KeyError("Missing PBC solvtype (box type)")

                solvtype = solvtype[:4]
                if solvtype not in ('cube', 'rect', 'octa', 'hexa'):
                    raise ValueError(f"Unrecognized solvtype: '{solvtype}'")

                self.browser.find_by_id('solvtype').select(solvtype)

                dims = pbc.get('dims')
                if dims is None:
                    raise KeyError("Missing PBC dims")

                for dim, value in dims.items():
                    dim = dim.lower()
                    set_form_value(self.browser, f'box[{solvtype}][{dim}]', value)

            self.go_next(self.test_case['steps'][0]['wait_text'])
            self.get_jobid()
