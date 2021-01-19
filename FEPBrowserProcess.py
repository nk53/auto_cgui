import ast
import os
import requests
import time
import yaml
from os.path import join as pjoin
from splinter import Browser
from splinter.exceptions import ElementDoesNotExist
from InputBrowserProcess import InputBrowserProcess
from PDBBrowserProcess import PDBBrowserProcess
from SolutionBrowserProcess import SolutionBrowserProcess
from BilayerBrowserProcess import BilayerBrowserProcess

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
        if not 'solvator_tests' in test_case:
            base_cases.append(test_case)
        else:
            do_copy = args.copy
            cases = handle_solvator_tests(test_case, do_copy)

            if 'localhost' in args.base_url.lower() and do_copy:
                base_case = cases[0]
                base_cases.append(base_case)
                wait_cases[base_case['label']] = cases[1:]
            else:
                base_cases += cases
    return base_cases, wait_cases

def handle_solvator_tests(test_case, do_copy=False):
    if not 'solvator_tests' in  test_case:
        raise ValueError("Missing 'solvator_tests'")
    solvtor_tests = test_case[solvent_tests]

    placeholder = 'SOLVATOR_TEST_PLACEHOLDER'
    found = False
    index = None
    check_lists = 'presteps', 'poststeps'
    for step_num, step in enumerate(test_case['steps']):
        for check_list in check_lists:
            if check_list in step and placeholder in step[check_list]:
                found = True
                index = step[check_list].index(placeholder)
                break
        if found:
            break
    if not found:
        raise ValueError("Missing '"+placeholder+"'")

    for num, case in enumerate(cases):
        case['case_id'] = num
        case['solvator_link'] = step_num

    if do_copy:
        copy_action = "copy_dir(ncopy={})".format(len(solvator_tests))
        cases[0]['steps'][step_num][check_list].insert(index, copy_action)

    return cases

class FEPBrowserProcess(BilayerBrowserProcess):

    def select(self, name, value):
        self.browser.select(name, value)

    def fill(self, name, value):
        self.browser.fill(name, value)

    def xpath(self, element):
        self.browser.find_by_xpath(element).click()

    def click_by_name(self, name):
        self.browser.find_by_name(name).click()

    def set_upload_mol2(self):
        if not 'drags' in self.test_case:
            raise ValueError("Missing drag mol2 files")
        drags = self.test_case['drags']
        for drag in drags:
            ligfile = os.path.abspath(pjoin('files', self.test_case['ligand']))
            self.ligfile = ligfile
            lig_path = pjoin(self.ligfile, drag)
            self.browser.attach_file('files[]', lig_path)

    def set_program(self):
        if not 'programs' in self.test_case:
            raise ValueError("Missing program selection")
        programs = self.test_case['programs']
        for program in programs:
            if program == 'genesis':
                self.browser.find_by_name('gns_checked').click()
            elif program == 'amber':
                self.browser.find_by_name('amb_checked').click()
                self.browser.find_by_name('namd_checked').click()
            elif program == 'charmm':
                self.browser.find_by_name('charmm_checked').click()
    def set_path(self):
        path = self.test_case['path']
        self.browser.find_by_value(path).click()

    def set_other_ff(self):
        protein_ffs = self.test_case['protein_ffs']
        ligand_ffs = self.test_case['ligand_ffs']
        water_ffs = self.test_case['water_ffs']
        for protein_ff in protein_ffs:
            if protein_ff == 'ff14sb': # default is ff19sb
                 self.browser.find_by_value('FF14SB').click()
        for ligand_ff in ligand_ffs:   # default is gaff2
            if ligand_ff == 'gaff':
                 self.browser.find_by_value('GAFF').click()
        for water_ff in water_ffs:     # default is tip3
            if water_ff == 'tip4pew':
                 self.browser.find_by_value('TIP4PEW').click()
            elif water_ff == 'opc':
                 self.browser.find_by_value('OPC').click()

    def set_ff(self):
        if not 'ffs' in self.test_case:
            raise ValueError("Missing force field")
        ffs = self.test_case['ffs']
        for ff in ffs:
            if ff == 'amber':
                self.click_by_attrs(value='AMBER FF Checker')
                self.browser.fill("amb_trial", 1)
            elif ff == 'cgenff':
                self.click_by_attrs(value='CGenFF Checker')

    def set_ff_version(self):
        if not 'ff_versions' in self.test_case:
            raise ValueError("Missing CGenFF force field version")
        ff_versions = self.test_case['ff_versions']
        for ff_version in ff_versions:
            if ff_version == 'old':
                self.click_by_attrs(value='c36_v1')
            elif ff_version == 'new':
                self.click_by_attrs(value='c36_v2')

    def set_protocol(self):
        protocols = self.test_case['protocols']
        for protocol in protocols:
            if protocol == 'split':
                self.browser.find_by_name('amb_unif_checked').click()
                self.browser.find_by_name('amb_spli_checked').click()
            elif protocol == 'both':
                self.browser.find_by_name('amb_spli_checked').click()
            else:
                return

    def init_system(self, test_case, resume=False):
        url = self.base_url + test_case['url_ym']
        browser = self.browser

        if resume:
            return

        binding_urls = '?doc=input/afes.rbinding', '?doc=input/afes.abinding'
        solvating_urls = '?doc=input/rsolvating', '?doc=input/asolvating'
        if test_case['url_ym'] in binding_urls:
            pdb = self.pdb = test_case['pdb']
            system_type = test_case['system_type']
            browser.visit(url)
            # infer as much as possible about the PDB format
            if system_type == 'bilayer':
                self.browser.find_by_value('bilayer').click()
                if isinstance(pdb, dict):
                    if 'format' in pdb:
                        pdb_fmt = pdb['format']
                    else:
                        pdb_fmt = pdb['name'].split('.')[-1]

                    source = 'source' in pdb and pdb['source']
                    pdb_name = test_case['pdb']['name']
                else:
                    pdb_name = test_case['pdb']
                    pdb_fmt = '.' in pdb_name and pdb_name.split('.')[-1]
                    source = not pdb_fmt and 'RCSB'

                if pdb_fmt:
                    pdb_fmt = {
                        'pdb': 'PDB',
                        'pqr': 'PDB',
                        'cif': 'mmCIF',
                        'charmm': 'CHARMM',
                    }[pdb_fmt]

                if source and self.name.split('-')[-1] != '1':
                    reason = "Multithreading is not allowed for "+module_title+\
                             " when downloading from RCSB/OPM. Please use an"\
                             " upload option instead."
                    self.stop(reason)

                if source:
                    browser.fill('pdb_id', pdb_name)
                else:
                    pdb_path = pjoin(self.base, pdb_name)
                    browser.attach_file("file", pdb_path)
                    browser.find_by_value(pdb_fmt).click()

                self.go_next(test_case['steps'][0]['wait_text'])
                self.get_jobid()
            elif system_type =='solution':
                self.browser.find_by_value('solution').click()
                if isinstance(pdb, dict):
                    if 'format' in pdb:
                        pdb_fmt = pdb['format']
                    else:
                        pdb_fmt = pdb['name'].split('.')[-1]

                    source = 'source' in pdb and pdb['source']
                    pdb_name = test_case['pdb']['name']
                else:
                    pdb_name = test_case['pdb']
                    pdb_fmt = '.' in pdb_name and pdb_name.split('.')[-1]
                    source = not pdb_fmt and 'RCSB'

                if pdb_fmt:
                    pdb_fmt = {
                        'pdb': 'PDB',
                        'pqr': 'PDB',
                        'cif': 'mmCIF',
                        'charmm': 'CHARMM',
                    }[pdb_fmt]

                if source and self.name.split('-')[-1] != '1':
                    reason = "Multithreading is not allowed for "+module_title+\
                             " when downloading from RCSB/OPM. Please use an"\
                             " upload option instead."
                    self.stop(reason)

                if source:
                    browser.fill('pdb_id', pdb_name)
                else:
                    pdb_path = pjoin(self.base, pdb_name)
                    browser.attach_file("file", pdb_path)
                    browser.find_by_value(pdb_fmt).click()

                self.go_next(test_case['steps'][0]['wait_text'])
                self.get_jobid()
        elif test_case['url_ym'] in solvating_urls:
            browser.visit(url)
            drags = self.test_case['drags']
            for drag in drags:
                lig_path = pjoin(self.base, drag)
                self.browser.attach_file('files[]', lig_path)

            self.go_next(test_case['steps'][0]['wait_text'])
            self.get_jobid()
