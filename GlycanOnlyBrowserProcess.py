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



class GlycanOnlyBrowserProcess(CGUIBrowserProcess):
    def __init__(self, todo_q, done_q, **kwargs):
        self.module_title = "Glycan Reader & Modeler"
        self.module_url = "?doc=input/glycan&step=0"
        super(GlycanOnlyBrowserProcess, self).__init__(todo_q, done_q, **kwargs)

    def run(self):
        super(GlycanOnlyBrowserProcess, self).run()

    def set_glycan(self):
        if not 'glycan' in self.test_case:
            raise ValueError("Missing glycan options")
        glycan = self.test_case['glycan']
        _d = re.compile('- ')
        chemod_init = False
        nchem = 0
        for i,residue in enumerate(glycan['grs'].split('\n')):
            if not residue.strip(): continue
            depth = len(_d.findall(residue))
            linkage, resname = residue.split('- ')[-1].split()
            idx = resname.find('_') #... chemical modification
            chemod = None
            if idx > 0:
                chemod = resname[idx+1:].split('_')
                resname = resname[:idx]
            if i > 0:
                self.browser.find_by_id(str(depth)).find_by_css('.add').first.click()
                self.browser.select("sequence[%d][linkage]" % (i+1), linkage[1])
                self.browser.select("sequence[%d][type]" % (i+1), resname[0])
            self.browser.select("sequence[%d][name]" % (i+1), resname[1:])
            if chemod:
                for chm in chemod:
                    if not chemod_init:
                        self.browser.find_by_id("chem_checked").first.click()
                        chemod_init = True
                    else:
                        self.browser.execute_script("add_chem()")
                    match = re.match('[0-9]+', chm)
                    site = match.group()
                    patch = chm[match.end():]
                    self.browser.select("chem[%d][resid]" % nchem, i+1)
                    self.browser.select("chem[%d][patch]" % nchem, patch)
                    self.browser.select("chem[%d][site]" % nchem, site)
                    nchem += 1
        self.go_next(self.test_case['steps'][0]['wait_text'])


    def init_system(self, test_case, resume=False):
        module_title = self.module_title
        url = self.base_url + self.module_url
        browser = self.browser

        if not resume:
            browser.visit(url)
            self.browser.click_link_by_text("Glycan Only System")
            self.set_glycan()

            jobid = browser.find_by_css(".jobid").first.text.split()[-1]
            test_case['jobid'] = jobid
