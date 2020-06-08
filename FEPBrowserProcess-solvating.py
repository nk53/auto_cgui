import os
import time
from os.path import join as pjoin
from splinter import Browser
from splinter.exceptions import ElementDoesNotExist
from CGUIBrowserProcess import CGUIBrowserProcess
import requests

class FEPBrowserProcess(CGUIBrowserProcess):
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

    def __init__(self, todo_q, done_q, **kwargs):
        self.jobid = None
        self.output = None # charmm-gui-jobid.tgz
        super(FEPBrowserProcess, self).__init__(todo_q, done_q, **kwargs)

    def select(self, name, value):
        self.browser.select(name, value)

    def fill(self, name, value):
        self.browser.fill(name, value)

    def xpath(self, element):
        self.browser.find_by_xpath(element).click()

    def click_by_name(self, name):
        self.browser.find_by_name(name).click()

    def init_system(self, test_case):
        url = self.base_url + test_case['url_ym']
        browser = self.browser
        browser.visit(url)

        # attach files for this test case
        browser.attach_file('files[]', pjoin(self.base, 'lig1.mol2'))
        browser.attach_file('files[]', pjoin(self.base, 'lig2.mol2'))
        browser.attach_file('files[]', pjoin(self.base, 'lig3.mol2'))

        self.go_next(test_case['steps'][0]['wait_text'])

        jobid = browser.find_by_css(".jobid").first.text.split()[-1]
        test_case['jobid'] = jobid
        self.jobid = jobid
        if 'output' in test_case:
            self.output = test_case['output']

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

    def run(self):
        super(FEPBrowserProcess, self).run()
        if self.output:
            self.download(self.output + '.tgz')
        else:
            self.download('charmm-gui-%s.tgz' % str(self.jobid))
