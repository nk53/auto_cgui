import os
import time
from os.path import join as pjoin
from splinter import Browser
from splinter.exceptions import ElementDoesNotExist
from CGUIBrowserProcess import CGUIBrowserProcess

class FEPBrowserProcess(CGUIBrowserProcess):
    def find_lig_row(self, lig_name, step):
        """Returns the row element page corresponding to the given uploaded
        ligand basename"""
        selectors = {
            'molpacking': lambda: self.browser.find_by_css(".ligand_list table tr:not(:first-child) td:nth-child(2)"),
            'solvent options': lambda: self.browser.find_by_text("Ligand ID").find_by_xpath('../..').find_by_css("tr:not(:first-child) td:nth-child(2)") 
        }
        rows = selectors[step]()
        found = False
        for row in rows:
            if row.text == lig_name:
                found = True
                break
        if  not found:
            raise ElementDoesNotExist("Could not find ligand: " + lig_name) 
        lig_row = row.find_by_xpath('..')
        return lig_row    

    def select_ligands(self):
        ligands = self.ligands
        for lig_name, lig_info in ligands.items():
            row = self.find_lig_row(lig_name, 'molpacking')
            lig_type = lig_info['type']
            lig_type_elem = row.find_by_css("[name^=type_ligand")
            lig_type_elem.select(lig_type)
           
            if lig_type in ['solvent', 'ion']:
                continue

            row = self.find_lig_row(lig_name, 'molpacking')

#            num_ligs = rows.find_by_css("[name^=num_ligands")
#            num_ligs.fill(lig_info['count'])

    def init_system(self, fep_case):
#        url = self.base_url + "?doc=input/asolvating"
        url = self.base_url + "?doc=input/rsolvating"
        browser = self.browser
        browser.visit(url)

        # attach files for this test case
        self.ligands = fep_case['ligands']
        for lig_name in self.ligands.keys():
            lig_name = pjoin(self.base, lig_name)
            browser.attach_file("files[]", lig_name+'.mol2')

        self.go_next(fep_case['steps'][0]['wait_text'])

        jobid = browser.find_by_css(".jobid").first.text.split()[-1]
        fep_case['jobid'] = jobid
