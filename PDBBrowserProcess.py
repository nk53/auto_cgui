import os
import ast
import time
from os.path import join as pjoin
from splinter import Browser
from splinter.exceptions import ElementDoesNotExist
from CGUIBrowserProcess import CGUIBrowserProcess
import yaml
import requests

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

class PDBBrowserProcess(CGUIBrowserProcess):
    def __init__(self, todo_q, done_q, **kwargs):
        self.jobid = None
        self.output = None # charmm-gui-jobid.tgz
        self.user = None
        self.password = None
        self.glycan = None
        super(PDBBrowserProcess, self).__init__(todo_q, done_q, **kwargs)

    def download(self, saveas):
        url = "{url}?doc=input/download&jobid={jobid}".format(url=self.base_url, jobid=self.jobid)
        print("downloading %s to %s" % (url, saveas))

        user_agent = 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'
        headers = {'User-Agent': user_agent}
        user = ''
        password = ''
        if ':' in self.base_url:
            urlname = self.base_url.split('//')[1]
            idx = urlname.find('@')
            user, password = urlname[:idx].split(':')

        r = requests.get(url, headers=headers, auth=(user, password))
        open(saveas, "wb").write(r.content)
        fsize = float(os.stat(saveas).st_size) / (1024.0 * 1024.0)
        print("download complete, file size is %5.2f MB" % fsize)


    def set_glycosylation(self):
        if self.glycan:
            glyc_button = self.browser.find_by_id("glyc_checked").first
            if not glyc_button.checked:
                glyc_button.click()
            table = self.browser.find_by_id("id_glyc_table")
            for g in self.glycan:
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



    def init_system(self, test_case, resume=False):
        url = self.base_url + "?doc=input/pdbreader"
        browser = self.browser
        browser.visit(url)

        if 'glycan' in test_case:
            self.glycan = test_case['glycan']

        if not resume:
            # give pdb info
            pdb_name= test_case['pdb']
            browser.fill('pdb_id', pdb_name)

            self.go_next(test_case['steps'][0]['wait_text'])

            jobid = browser.find_by_css(".jobid").first.text.split()[-1]
            test_case['jobid'] = jobid
            self.jobid = jobid
            if 'output' in test_case:
                self.output = test_case['output']

    def run(self):
        super(PDBBrowserProcess, self).run()
        if self.output:
            self.download(self.output + '.tgz')
        else:
            self.download('charmm-gui-%s.tgz' % str(self.jobid))
