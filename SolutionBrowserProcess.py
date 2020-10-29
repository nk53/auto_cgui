import ast
import os
import time
import yaml
from os.path import join as pjoin
from splinter import Browser
from splinter.exceptions import ElementDoesNotExist
from PDBBrowserProcess import PDBBrowserProcess
from InputBrowserProcess import InputBrowserProcess
import pdb

class SolutionBrowserProcess(PDBBrowserProcess, InputBrowserProcess):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.module_title = "Solution Builder"
        self.module_url = "?doc=input/solution"

    def set_ion_method(self):
        """Uses Monte-Carlo method unless ion_method[0] is d or D"""
        if not 'ion_method' in self.test_case:
            raise ValueError("Missing ion_method")

        ion_method = str(self.test_case['ion_method']).lower()[0]
        ion_method = ion_method == 'd' and 'dist' or 'mc'

        self.browser.select('ion_method', ion_method)


    def set_ion_type(self):
        if not 'ion_type' in self.test_case:
            raise ValueError("Missing ion_type")

        # map ion type in case-insensitive manner
        ion_type = str(self.test_case['ion_type']).lower()
        ion_type = {
            'kcl': 'KCl',
            'nacl': 'NaCl',
            'mgcl2': 'MgCl2',
            'cacl2': 'CaCl2',
        }[ion_type]

        self.browser.select('ion_type', ion_type)

    def set_xyz(self):
        dims = 'xyz'
        boxtype_names = 'boxtype', 'solvtype'

        # user must set at least one dimension when calling this function
        found = False
        for dim in dims:
            if dim in self.test_case:
                # only process XYZ dimensions once
                if self.test_case[dim] == False:
                    return
                found = True
                break
            elif dim.upper() in self.test_case:
                self.test_case[dim] = self.test_case.pop(dim.upper())
                found = True

        if not found:
            raise ValueError("Must specify at least one XYZ dimension")

        self.click_by_attrs(name="solvate_option", value="explicit")
        # the fact that this alert appears is a bug in Solution Builder
        # that I am too lazy to fix
        alert = self.browser.get_alert()
        if alert:
            with alert:
                alert.accept()

        solvtype = 'rect'
        for name in boxtype_names:
            if name in self.test_case:
                solvtype = self.test_case[name][:4].lower()
                break

        name_tpl = "box[{}][{}]"
        for dim in dims:
            if dim in self.test_case:
                value = self.test_case[dim]
                dim = dim.lower()

                name = name_tpl.format(solvtype, dim)
                self.browser.fill(name, value)

                # prevents set_xyz() from doing anything more than once
                self.test_case[dim] = False
