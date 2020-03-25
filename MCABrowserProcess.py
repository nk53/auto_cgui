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

    def run(self):
        with Browser(self.browser_type) as browser:
            self.browser = browser
            self.step = step_num = -1
            for test_case in iter(self.todo_q.get, 'STOP'):
                try:
                    self.test_case = test_case
                    print(self.name, "starting", test_case['label'])
                    start_time = time.time()
                    self.components = test_case['components']
                    resume_link = 0
                    base = os.path.abspath(test_case['base'])
                    if 'jobid' in test_case:
                        jobid = test_case['jobid']
                        resume_link = test_case['resume_link']
                        self.resume_step(jobid, link_no=resume_link)
                    else:
                        url = self.base_url + "?doc=input/multicomp"
                        browser.visit(url)

                        # attach files for this test case
                        for comp_name in self.components.keys():
                            comp_name = pjoin(base, comp_name)
                            browser.attach_file("files[]", comp_name+'.crd')
                            browser.attach_file("files[]", comp_name+'.psf')

                        self.go_next(test_case['steps'][0]['wait_text'])

                        jobid = browser.find_by_css(".jobid").first.text.split()[-1]
                        print(self.name, "Job ID:", jobid)
                        test_case['jobid'] = jobid

                    steps = test_case['steps'][resume_link:]
                    failure = False
                    for step_num, step in enumerate(steps):
                        self.step = step_num
                        if 'wait_text' in step:
                            print(self.name, "waiting for", step['wait_text'])
                            found_text = self.wait_text_multi([step['wait_text'], self.CHARMM_ERROR, self.PHP_FATAL_ERROR])
                        if found_text == self.CHARMM_ERROR:
                            failure = True
                            break
                        # Check for PHP errors, warnings, and notices

                        if self.warn_if_text(self.PHP_MESSAGES) and self.pause:
                            print(self.name, "pausing; interrupt to exit")
                            while True:
                                time.sleep(1)

                        if 'presteps' in step:
                            for prestep in step['presteps']:
                                self.eval(prestep)
                        if 'elems' in step:
                            self.handle_step(step)
                        if 'poststeps' in step:
                            for poststep in step['poststeps']:
                                self.eval(poststep)
                        self.go_next()

                    elapsed_time = time.time() - start_time

                    # early failure?
                    if failure:
                        self.done_q.put(('FAILURE', test_case, step_num, elapsed_time))
                        failure = False
                        continue

                    # late failure?
                    found_text = self.wait_text_multi([test_case['final_wait_text'], self.CHARMM_ERROR])
                    if found_text == self.CHARMM_ERROR:
                        self.done_q.put(('FAILURE', test_case, step_num, elapsed_time))
                        failure = False
                    else:
                        self.done_q.put(('SUCCESS', test_case, elapsed_time))
                except Exception as e:
                    import sys, traceback
                    # give the full exception string
                    exc_str = ''.join(traceback.format_exception(*sys.exc_info()))
                    self.done_q.put(('EXCEPTION', test_case, step_num, exc_str))
                    if self.pause:
                        print(self.name, "pausing; interrupt to exit")
                        while True:
                            time.sleep(1)

