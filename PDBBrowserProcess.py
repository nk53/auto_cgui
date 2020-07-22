import os
import re
import ast
import time
from os.path import join as pjoin
from splinter import Browser
from splinter.exceptions import ElementDoesNotExist
from CGUIBrowserProcess import CGUIBrowserProcess
import yaml

def init_module(test_cases, args):
    """Minimalistic placeholder"""
    return test_cases, {}

class PDBBrowserProcess(CGUIBrowserProcess):
    def __init__(self, todo_q, done_q, **kwargs):
        self.module_title = "PDB Reader"
        self.module_url = "?doc=input/pdbreader"
        super(PDBBrowserProcess, self).__init__(todo_q, done_q, **kwargs)

    def set_gpi(self):
        if not 'gpi' in self.test_case:
            raise ValueError("Missing gpi options")
        glyc_button = self.browser.find_by_id("gpi_checked").first
        if not glyc_button.checked:
            glyc_button.click()
        gpi = self.test_case['gpi']
        self.browser.select("gpi[chain]", gpi['segid'])
        table = self.browser.find_by_id("id_gpi")
        table.find_by_value("edit").first.click()
        self.browser.windows.current = self.browser.windows[1]
        lipid = ast.literal_eval(gpi['lipid'])
        self.browser.select("lipid_type", lipid['lipid_type'])
        self.browser.select("sequence[0][name]", lipid['name'])
        _d = re.compile('- ')
        for i,residue in enumerate(gpi['grs'].split('\n')):
            if not residue.strip(): continue
            depth = len(_d.findall(residue))
            linkage, resname = residue.split('- ')[-1].split()
            idx = resname.find('_')
            if idx > 0:
                resname = resname[:idx]
            if depth > 4:
                self.browser.find_by_id(str(depth-1)).find_by_css('.add').first.click()
            self.browser.select("sequence[%d][name]" % (i+1), resname[1:])
            self.browser.select("sequence[%d][type]" % (i+1), resname[0])
            self.browser.select("sequence[%d][linkage]" % (i+1), linkage[1])
        self.browser.execute_script("updateGPI()")
        self.browser.windows.current = self.browser.windows[0]

    def set_glycosylation(self):
        if not 'glycan' in self.test_case:
            raise ValueError("Missing glycosylation options")
        glyc_button = self.browser.find_by_id("glyc_checked").first
        if not glyc_button.checked:
            glyc_button.click()
        table = self.browser.find_by_id("id_glyc_table")
        for g in self.test_case['glycan']:
            if 'segid' in g:
                rows = table.find_by_id("glycan_{segid}".format(segid=g['segid'])).first
            else:
                self.browser.find_by_id("add_glycosylation").first.click()
                rows = table.find_by_tag("tr").last
            cols = rows.find_by_tag("td")[4]
            cols.find_by_value("edit").last.click()
            self.browser.windows.current = self.browser.windows[1]
            self.browser.find_by_value("Upload GRS").first.click()
            self.browser.find_by_id("upload_GRS").first.fill(g['grs'])
            prot = ast.literal_eval(g['prot'])
            self.browser.select("sequence[0][name]", prot['segid'])
            self.browser.select("sequence[0][name2]", prot['resname'])
            self.browser.select("sequence[0][name3]", prot['resid'])
            self.browser.execute_script("seqUpdate()")
            self.browser.windows.current = self.browser.windows[0]

    def set_stapling(self):
        if not 'staples' in self.test_case:
            raise ValueError("Missing stapling options")

        staples = self.test_case['staples']
        # open stapling menu
        self.click('stapling_checked', 'Stapling Method')

        # add as many staples as needed
        add_btn = self.browser.find_by_value("Add Stapling")
        for staple in staples[1:]:
            add_btn.click()

        # set stapling options
        staple_fmt = 'type', 'chain1', 'rid1', 'chain2', 'rid2'
        id_fmt = 'stapling_{}_{}'
        for staple_no, staple in enumerate(staples):
            staple = staple.split()

            if len(staple) != 5:
                raise ValueError("Invalid staple format")

            for name, value in zip(staple_fmt, staple):
                sid = id_fmt.format(name, staple_no)
                self.browser.find_by_id(sid).select(value)

    def init_system(self, test_case, resume=False):
        module_title = self.module_title
        url = self.base_url + self.module_url
        browser = self.browser

        pdb = self.pdb = test_case['pdb']

        if not resume:
            browser.visit(url)
            # infer as much as possible about the PDB format
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

            jobid = browser.find_by_css(".jobid").first.text.split()[-1]
            test_case['jobid'] = jobid
