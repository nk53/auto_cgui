import os
import time
from os.path import join as pjoin
from splinter import Browser
from splinter.exceptions import ElementDoesNotExist
from CGUIBrowserProcess import CGUIBrowserProcess

class MCABrowserProcess(CGUIBrowserProcess):
    def find_comp_row(self, comp_name, step):
        """Returns the row element page corresponding to the given uploaded
        component basename"""
        selectors = {
            'molpacking': lambda: self.browser.find_by_css(".component_list table tr:not(:first-child) td:nth-child(2)"),
            'solvent options': lambda: self.browser.find_by_text("Component ID").find_by_xpath('../..').find_by_css("tr:not(:first-child) td:nth-child(2)")
        }
        rows = selectors[step]()
        found = False
        for row in rows:
            if row.text == comp_name:
                found = True
                break
        if not found:
            raise ElementDoesNotExist("Could not find component: "+comp_name)
        comp_row = row.find_by_xpath('..')
        return comp_row

    def set_component_density(self):
        components = self.components
        for comp_name, comp_info in components.items():
            if not 'density' in comp_info:
                continue
            row = self.find_comp_row(comp_name, 'solvent options')
            comp_type = comp_info['type']
            comp_type_elem = row.find_by_css("[id^=solv_density]")
            comp_type_elem.fill(comp_info['density'])

    def select_components(self):
        components = self.components
        for comp_name, comp_info in components.items():
            row = self.find_comp_row(comp_name, 'molpacking')
            comp_type = comp_info['type']
            comp_type_elem = row.find_by_css("[name^=type_component")
            comp_type_elem.select(comp_type)

            # can't set number of some component types in this step
            if comp_type in ['solvent', 'ion']:
                continue

            # changing component type might change row element
            row = self.find_comp_row(comp_name, 'molpacking')

            num_comps = row.find_by_css("[name^=num_components")
            num_comps.fill(comp_info['count'])

    def init_system(self, test_case):
        url = self.base_url + "?doc=input/multicomp"
        browser = self.browser
        browser.visit(url)

        # attach files for this test case
        self.components = test_case['components']
        for comp_name in self.components.keys():
            comp_name = pjoin(self.base, comp_name)
            browser.attach_file("files[]", comp_name+'.crd')
            browser.attach_file("files[]", comp_name+'.psf')

        self.go_next(test_case['steps'][0]['wait_text'])

        jobid = browser.find_by_css(".jobid").first.text.split()[-1]
        test_case['jobid'] = jobid

