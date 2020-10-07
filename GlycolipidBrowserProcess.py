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

class GlycolipidBrowserProcess(CGUIBrowserProcess):
    def __init__(self, todo_q, done_q, **kwargs):
        self.module_title = "Glycolipid Modeler"
        self.module_url = "?doc=input/glycolipid"
        super(GlycolipidBrowserProcess, self).__init__(todo_q, done_q, **kwargs)

    def run_step0(self, pglycolipid = None, sub2 = None, sub3 = None):
        module_title = self.module_title
        url = self.base_url + self.module_url
        browser = self.browser
        browser.visit(url)
        browser.driver.implicitly_wait(10);
        browser.driver.set_script_timeout(10000);
        browser.driver.set_page_load_timeout(10000);
        pglyc_fmt = "//span[.='{}']"
        sub2_fmt = "//input[@value='{}']"
        sub3_fmt = "//input[@value='{}']"
        if sub3:
            pglyc_id = pglyc_fmt.format(pglycolipid)
            sub2_id = pglyc_fmt.format(sub2)
            sub3_id = sub3_fmt.format(sub3)
            browser.execute_script("$('sub1').toggle()")
            time.sleep(1)
            browser.find_by_xpath(pglyc_id).click()
            time.sleep(1)
            sub2_sibling = browser.find_by_xpath(sub2_id)
            sub2_sibling.find_by_xpath("./..").click()
            time.sleep(1)
            sub3_sibling = browser.find_by_xpath(sub3_id)
            sub3_sibling.find_by_xpath("./..").click()
            time.sleep(1)
        else:
            pglyc_id = pglyc_fmt.format(pglycolipid)
            sub2_id = sub2_fmt.format(sub2)
            browser.execute_script("$('sub1').toggle()")
            time.sleep(1)
            browser.find_by_xpath(pglyc_id).click()
            time.sleep(1)
            sub2_sibling = browser.find_by_xpath(sub2_id)
            sub2_sibling.find_by_xpath("./..").click()
            time.sleep(1)
        self.go_next(self.test_case['steps'][0]['wait_text'])

        jobid = browser.find_by_css(".jobid").first.text.split()[-1]
        self.test_case['jobid'] = jobid
        if not 'glycolipid' in self.test_case:
            if sub3:
                print("Finished test:%s %s %s"% (pglycolipid, sub2, sub3))
            else:
                print("Finished test:%s %s"% (pglycolipid, sub2))
        elif self.test_case['download'] == 'yes':
            if sub3:
                print("Finished test:%s %s %s"% (pglycolipid, sub2, sub3))
                self.download()
            else:
                print("Finished test:%s %s"% (pglycolipid, sub2))
                self.download()
        elif sub3:
            print("Finished test:%s %s %s"% (pglycolipid, sub2, sub3))
        else:
            print("Finished test:%s %s"% (pglycolipid, sub2))

    def run(self):
        super(GlycolipidBrowserProcess, self).run()

    def init_system(self, test_case, resume=False):
        if not 'glycolipid' in self.test_case:
            glycolipid_lib = yaml.load(open('test_cases/glycolipid/basic.yml','r'), Loader=yaml.Loader)
            next_glycolipid = False

            for glycolipid in list(self.test_case):
                pglycolipid = self.test_case['label']
                msub2 = self.test_case['sub2']
                if not (pglycolipid == 'Ganglio-series' or pglycolipid == 'Blood groups') and next_glycolipid == False:
                    for sub2n, sub2 in enumerate(msub2):
                        sub2name,sub2id = sub2.split()
                        sub2 = str(sub2id)
                        self.run_step0(pglycolipid, sub2)
                        next_glycolipid = True
                elif pglycolipid == 'Ganglio-series' or pglycolipid == 'Blood groups':
                    for sub2n in msub2:
                        sub2 = str(sub2n)
                        msub3 = self.test_case['sub2'][sub2]
                        for sub3 in msub3:
                            sub3name,sub3id = sub3.split()
                            sub3 = str(sub3id)
                            self.run_step0(pglycolipid, sub2, sub3)
        elif 'glycolipid' and 'sub2' in self.test_case:
            glycolipid_lib = yaml.load(open('test_cases/glycolipid/basic.yml','r'), Loader=yaml.Loader)
            next_glycolipid = False

            for glycolipid in list(self.test_case):
                pglycolipid = self.test_case['glycolipid']
                msub2 = self.test_case['sub2']
                if not (pglycolipid == 'Ganglio-series' or pglycolipid == 'Blood groups') and next_glycolipid == False:
                    for sub2 in msub2:
                        sub2name,sub2id = sub2.split()
                        sub2 = str(sub2id)
                        self.run_step0(pglycolipid, sub2)
                        next_glycolipid = True
                elif pglycolipid == 'Ganglio-series' or pglycolipid == 'Blood groups':
                    for sub2n in msub2:
                        sub2 = str(sub2n)
                        msub3 = self.test_case['sub2'][sub2]
                        for sub3 in msub3:
                            sub3name,sub3id = sub3.split()
                            sub3 = str(sub3id)
                            self.run_step0(pglycolipid, sub2, sub3)
        elif 'glycolipid' in self.test_case and not 'sub2' in self.test_case:
            glycolipid_lib = yaml.load(open('test_cases/glycolipid/basic.yml','r'), Loader=yaml.Loader)
            glycolipid_master = [mpglycolipid for mpglycolipid in glycolipid_lib]
            next_glycolipid = False

            for glycolipid in list(self.test_case):
                pglycolipid = self.test_case['glycolipid']
                for mpglycolipid in glycolipid_master:
                    mlabel = mpglycolipid['label']
                    msub2 = mpglycolipid['sub2']
                    if mlabel == pglycolipid and next_glycolipid == False:
                        if not (pglycolipid == 'Ganglio-series' or pglycolipid == 'Blood groups'):
                            for sub2n, sub2 in enumerate(msub2):
                                sub2name,sub2id = sub2.split()
                                sub2 = str(sub2id)
                                self.run_step0(pglycolipid, sub2)
                                next_glycolipid = True
                        else:
                            for sub2n in msub2:
                                sub2 = str(sub2n)
                                msub3 = mpglycolipid['sub2'][sub2]
                                for sub3 in msub3:
                                    sub3name,sub3id = sub3.split()
                                    sub3 = str(sub3id)
                                    self.run_step0(pglycolipid, sub2, sub3)
                                    next_glycolipid = True
        else:
            print("Invalid building options")
