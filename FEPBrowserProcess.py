import os
import time
from os.path import join as pjoin
from splinter import Browser
from splinter.exceptions import ElementDoesNotExist
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
