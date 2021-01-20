import ast
import re
import time
import os
import sys
import yaml
from splinter import Browser
from CGUIBrowserProcess import CGUIBrowserProcess

def init_module(test_cases, args):
    """Preprocesses test cases

    Returns: (2-tuple)
    =======
        base_cases  Cases that can begin immediately
        wait_cases  Cases that need one of the base cases to complete first
    """
    base_cases = []
    wait_cases = {}
    for test_case in test_cases:
        base_cases.append(test_case)
    return base_cases, wait_cases

class LPSBrowserProcess(CGUIBrowserProcess):
    def __init__(self, *args, **kwargs):
        self.module_title = "LPS Builder"
        self.module_url = "?doc=input/lps"
        super(LPSBrowserProcess, self).__init__(*args, **kwargs)

    def run_step0(self, speciesn = None, lip = None, core = None, oanti = None):
        module_title = self.module_title
        url = self.base_url + self.module_url
        browser = self.browser
        browser.visit(url)

        browser.driver.implicitly_wait(10);
        browser.driver.set_script_timeout(10000);
        browser.driver.set_page_load_timeout(10000);
        browser.find_by_value(speciesn).click()
        time.sleep(1)
        browser.find_by_value(lip).click()
        time.sleep(1)
        browser.find_by_value(core).click()
        time.sleep(1)
        if oanti:
            browser.find_by_id(oanti).click()
            time.sleep(1)
        self.go_next(self.test_case['steps'][0]['wait_text'])

        self.get_jobid()
        if not 'species' in self.test_case:
            if oanti:
                print("Finished test:%s %s %s %s"% (speciesn, lip, core, oanti))
            else:
                print("Finished test:%s %s %s"% (speciesn, lip, core))
        elif self.test_case['download'] == 'yes':
            if oanti:
                print("Finished test:%s %s %s %s"% (speciesn, lip, core, oanti))
                self.download()
            else:
                print("Finished test:%s %s %s"% (speciesn, lip, core))
                self.download()
        elif 'oanti' is not None:
            print("Finished test:%s %s %s %s"% (speciesn, lip, core, oanti))
        else:
            print("Finished test:%s %s %s"% (speciesn, lip, core))

    def run(self):
        super(LPSBrowserProcess, self).run()

    def init_system(self, test_case, resume=False):
        if not 'species' in self.test_case:
            lps_lib = yaml.load(open('test_cases/lps/exhaustive.yml','r'), Loader=yaml.Loader)
            for species in self.test_case:
                speciesn = self.test_case['label']
                mlipid = self.test_case['lip']
                for lipn, lip in enumerate(mlipid):
                    lip = str(lip)
                    for core in self.test_case['core']:
                        core = str(core)
                        if species == 'pa' and ( core == '1a' or core == '1b'):
                            self.run_step0(species, core)
                        elif 'oanti' in self.test_case:
                            for oanti in self.test_case['oanti']:
                                    oanti = str(oanti)
                                    self.run_step0(speciesn, lip, core, oanti)
                        else:
                            self.run_step0(speciesn, lip, core)
        elif 'species' and 'lip' and 'core' and 'oanti' in self.test_case:
            for species in self.test_case:
                speciesn = self.test_case['species']
                mlipid = self.test_case['lip']
                for lipn, lip in enumerate(mlipid):
                    lip = str(lip)
                    for core in self.test_case['core']:
                        core = str(core)
                        if species == 'pa' and ( core == '1a' or core == '1b'):
                            self.run_step0(species, core)
                        elif 'oanti' in self.test_case:
                            for oanti in self.test_case['oanti']:
                                    oanti = str(oanti)
                                    self.run_step0(speciesn, lip, core, oanti)
                        else:
                            self.run_step0(speciesn, lip, core)
        elif 'species' and 'lip' and 'core' in self.test_case and not 'oanti' in self.test_case:
            lps_lib = yaml.load(open('test_cases/lps/exhaustive.yml','r'), Loader=yaml.Loader)
            lps_master = [mspecies for mspecies in lps_lib]
            next_species = False

            for species in list(self.test_case):
                speciesn = self.test_case['species']
                mlipid = self.test_case['lip']
                for mspecies in lps_master:
                    mlabel = mspecies['label']
                    if mlabel == speciesn and next_species == False:
                        for lipn, lip in enumerate(mlipid):
                            lip = str(lip)
                            for core in self.test_case['core']:
                                core = str(core)
                                if speciesn == 'pa' and ( core == '1a' or core == '1b'):
                                    self.run_step0(species, core)
                                    next_species = True
                                elif 'oanti' in mspecies:
                                    for oanti in mspecies['oanti']:
                                            oanti = str(oanti)
                                            self.run_step0(speciesn, lip, core, oanti)
                                            next_species = True
                                else:
                                    self.run_step0(speciesn, lip, core)
                                    next_species = True
        elif 'species' and 'lip' in self.test_case and not ('core' and 'oanti') in self.test_case:
            lps_lib = yaml.load(open('test_cases/lps/exhaustive.yml','r'), Loader=yaml.Loader)
            lps_master = [mspecies for mspecies in lps_lib]
            next_species = False

            for species in list(self.test_case):
                speciesn = self.test_case['species']
                mlipid = self.test_case['lip']
                for mspecies in lps_master:
                    mlabel = mspecies['label']
                    if mlabel == speciesn and next_species == False:
                        for lipn, lip in enumerate(mlipid):
                            lip = str(lip)
                            for core in mspecies['core']:
                                core = str(core)
                                if speciesn == 'pa' and ( core == '1a' or core == '1b'):
                                    self.run_step0(species, core)
                                    next_species = True
                                elif 'oanti' in mspecies:
                                    for oanti in mspecies['oanti']:
                                            oanti = str(oanti)
                                            self.run_step0(speciesn, lip, core, oanti)
                                            next_species = True
                                else:
                                    self.run_step0(speciesn, lip, core)
                                    next_species = True
        elif 'species' in self.test_case and not ('lip' and 'core' and 'oanti') in self.test_case:
            lps_lib = yaml.load(open('test_cases/lps/exhaustive.yml','r'), Loader=yaml.Loader)
            lps_master = [mspecies for mspecies in lps_lib]
            next_species = False

            for species in list(self.test_case):
                speciesn = self.test_case['species']
                for mspecies in lps_master:
                    mlabel = mspecies['label']
                    mlipid = mspecies['lip']
                    if mlabel == speciesn and next_species == False:
                        for lipn, lip in enumerate(mlipid):
                            lip = str(lip)
                            for core in mspecies['core']:
                                core = str(core)
                                if speciesn == 'pa' and ( core == '1a' or core == '1b'):
                                    self.run_step0(species, core)
                                    next_species = True
                                elif 'oanti' in mspecies:
                                    for oanti in mspecies['oanti']:
                                            oanti = str(oanti)
                                            self.run_step0(speciesn, lip, core, oanti)
                                            next_species = True
                                else:
                                    self.run_step0(speciesn, lip, core)
                                    next_species = True
        else:
            print("Invalid building options")
