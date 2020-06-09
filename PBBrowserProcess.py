import os
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

class PBBrowserProcess(CGUIBrowserProcess):
    def __init__(self, todo_q, done_q, **kwargs):
        self.jobid = None
        self.polydic = None
        self.output = None # charmm-gui-jobid.tgz
        super(PBBrowserProcess, self).__init__(todo_q, done_q, **kwargs)

    def getpath(self, nested_dict, value, prepath=()):
        for k, v in nested_dict.items():
            path = prepath + (k,)
            if v == value: # found value
                return path
            elif hasattr(v, 'items'): # v is a dict
                p = self.getpath(v, value, path) # recursive call
                if p is not None:
                    return p

    def download(self, saveas):
        url = "{url}?doc=input/download&jobid={jobid}".format(url=self.base_url, jobid=self.jobid)
        print("downloading %s to %s" % (url, saveas))

        user_agent = 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'
        headers = {'User-Agent': user_agent}

        user, password = 'testing', 'lammps'
        r = requests.get(url, headers=headers, auth=(user, password))
        open(saveas, "wb").write(r.content)
        fsize = float(os.stat(saveas).st_size) / (1024.0 * 1024.0)
        print("download complete, file size is %5.2f MB" % fsize)

    def select(self, element, value):
        self.browser.select(element, value)

    def choose(self, element, value):
        self.browser.choose(element, value)

    def run_step0(self, pchains, wait_text):
        browser = self.browser
        browser.choose('model', self.model)
        if (len(pchains) > 1):
            clickcnt = 0
            while clickcnt < len(pchains) - 1:
                browser.find_by_id('chainBtn').click()
                clickcnt += 1
        typecnt = 0
        for key in pchains:
            pchain = pchains[key]
            capf = pchain['initcap']
            capl = pchain['endcap']
            repeat = pchain['repeat']
            capfname = 'capf[%s]' % key[6:]
            browser.select(capfname, capf)
            caplname = 'capl[%s]' % key[6:]
            browser.select(caplname, capl)
            repeattext = 'subtext2[%s]' % key[6:]
            browser.find_by_name(repeattext).fill(repeat)
            # count typeX in pchain
            tcnt = 0
            for i in pchain:
                if i.startswith('type'): tcnt += 1
            moncnt = 1
            if tcnt > 1:
                # click Add
                while moncnt < tcnt:
                    buttname = 'butt' + '[' + key[6:] + ']'
                    browser.find_by_id(buttname).click()
                    moncnt += 1

            for i in range(tcnt):
                typ = 'type' + str(i + 1)
                name = pchain[typ]['name']
                length = pchain[typ]['leng']
                path_junk = self.getpath(self.polydic, name)
                idx = (len(path_junk) / 2) - 1
                polyclass = path_junk[2]
                fullname = path_junk[4]
                resi = self.polydic['Polymer']['sub'][polyclass]['sub'][fullname]['resi']
                if len(path_junk) > 6:
                    polytact = path_junk[6]
                else:
                    polytact = None
                poly_elem = browser.find_by_css('[class~=poly_type]')[typecnt]
                poly_elem.click()
                poly_elem.find_by_text(polyclass).click()
                poly_elem.find_by_text(fullname).click()
                if polytact != None:
                    if polytact[0] == 'i' and polytact[-2] == 'R': tacidx = 1
                    if polytact[0] == 'i' and polytact[-2] == 'S': tacidx = 2
                    if polytact[0] == 's': tacidx = 3
                    if polytact[0] == 'a': tacidx = -1
                    x = poly_elem.find_by_value(resi)[tacidx].click()
                subtext = 'subtext[%s][%s]' % (key[6:], str(i + 1))

                browser.find_by_name(subtext).fill(length)
                typecnt += 1

        self.go_next(wait_text)

        # set jobid
        jobid = browser.find_by_css(".jobid").first.text.split()[-1]
        self.jobid = jobid

    def handle_step(self, step_info):
        for elem in step_info['elems']:
            name = list(elem.keys())[0]
            value = elem[name]
            if isinstance(value, bool):
                if value:
                    self.browser.find_by_name(name).check()
            else:
                self.browser.fill(name, value)

    def resume_step(self, jobid, project=None, step=None, link_no=None):
        self.jobid = jobid
        super(PBBrowserProcess, self).resume_step(jobid, link_no=link_no)

    def run(self):
        super(PBBrowserProcess, self).run()
        if self.output:
            self.download(self.output + '.tgz')
        else:
            self.download('charmm-gui-%s.tgz' % str(self.jobid))

    def init_system(self, test_case, resume=False):
        url = self.base_url + "?doc=input/polymer"
        self.browser.visit(url)

        # attach files for this test case
        self.model = test_case['label']
        self.polydic = yaml.load(open("polymer.enabled.yml",'r'))
        self.run_step0(test_case['pchains'],
                       wait_text='Generate Systems')
        test_case['jobid'] = self.jobid
        if 'output' in test_case:
            self.output = test_case['output']
