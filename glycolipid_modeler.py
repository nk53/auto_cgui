"""Handles Glycolipid Modeler options"""
from utils import read_yaml
from cgui_browser_process import CGUIBrowserProcess

_BROWSER_PROCESS = 'GlycolipidBrowserProcess'

_categories = read_yaml('glycolipid.enabled.yml')
_infos = read_yaml('glycolipid.sequence.yml')

def _get_all_glycolipids(category):
    glycolipids = []

    for gid in category:
        name = _infos[gid]['name']+', '+gid
        glycolipids.append(name)

    return glycolipids

def init_module(test_cases, args):
    """Preprocesses test cases

    Returns: (2-tuple)
    =======
        base_cases  Cases that can begin immediately
        wait_cases  Cases that need one of the base cases to complete first
    """
    base_cases = []
    for test_case in test_cases:
        glycolipid = test_case.get('glycolipid')
        if not glycolipid:
            raise KeyError("Missing glycolipid type")

        sub2 = test_case.get('sub2')
        if not sub2:
            category = _categories[glycolipid]
            glycolipids = _get_all_glycolipids(category)
            for glycolipid in glycolipids:
                base_case = test_case.copy()
                base_case['sub2'] = [glycolipid]
                base_case['label'] += ' ({})'.format(glycolipid)
                base_cases.append(base_case)
        elif len(sub2) > 1:
            if isinstance(sub2, list):
                for glycolipid in sub2:
                    base_case = test_case.copy()
                    base_case['sub2'] = [glycolipid]
                    base_case['label'] += ' ({})'.format(glycolipid)
                    base_cases.append(base_case)
            elif isinstance(sub2, dict):
                for category, glycolipid in sub2.items():
                    base_case = test_case.copy()
                    base_case['sub2'] = {category: glycolipid}
                    base_case['label'] += ' ({})'.format(glycolipid[0])
                    base_cases.append(base_case)
            else:
                raise TypeError("Unrecognized type for sub2: "+type(sub2).__name__)
        else:
            base_cases.append(test_case)
    return base_cases, {}

class GlycolipidBrowserProcess(CGUIBrowserProcess):
    """Implements selection for Glycolipid Modeler's front page"""
    def __init__(self, *args, **kwargs):
        self.module_title = "Glycolipid Modeler"
        self.module_url = "?doc=input/glycolipid"
        super().__init__(*args, **kwargs)

    def run_step0(self, pglycolipid = None, sub2 = None, sub3 = None):
        """Handles front page of Glycolipid Modeler"""
        url = self.base_url + self.module_url
        browser = self.browser
        browser.visit(url)
        browser.driver.set_script_timeout(10000)
        browser.driver.set_page_load_timeout(10000)
        pglyc_fmt = "//span[.='{}']"
        sub2_fmt = "//input[@value='{}']"
        sub3_fmt = "//input[@value='{}']"
        if sub3:
            pglyc_id = pglyc_fmt.format(pglycolipid)
            sub2_id = pglyc_fmt.format(sub2)
            sub3_id = sub3_fmt.format(sub3)
            browser.execute_script("$('sub1').toggle()")
            self.wait_visible(browser.find_by_xpath(pglyc_id), click=True)
            sub2_sibling = browser.find_by_xpath(sub2_id)
            self.wait_visible(sub2_sibling.find_by_xpath("./.."), click=True)
            sub3_sibling = browser.find_by_xpath(sub3_id)
            self.wait_visible(sub3_sibling.find_by_xpath("./.."), click=True)
        else:
            sub2_fmt = "//span[.='{}']/../ul/li/label/input[@value='{}']"
            pglyc_id = pglyc_fmt.format(pglycolipid)
            sub2_id = sub2_fmt.format(pglycolipid, sub2)
            browser.execute_script("$('sub1').toggle()")
            self.wait_visible(browser.find_by_xpath(pglyc_id), click=True)
            sub2_sibling = browser.find_by_xpath(sub2_id)
            self.wait_visible(sub2_sibling.find_by_xpath("./.."), click=True)
        self.go_next(self.test_case['steps'][0]['wait_text'])

        self.get_jobid()

    def init_system(self, **kwargs):
        glycolipid = self.test_case['glycolipid']
        msub2 = self.test_case['sub2']
        if glycolipid not in ('Ganglio-series', 'Blood groups'):
            for sub2 in msub2:
                _sub2name, sub2id = sub2.split()
                sub2 = str(sub2id)
                self.run_step0(glycolipid, sub2)
        else:
            for sub2n in msub2:
                sub2 = str(sub2n)
                msub3 = self.test_case['sub2'][sub2]
                for sub3 in msub3:
                    _sub3name, sub3id = sub3.split()
                    sub3 = str(sub3id)
                    self.run_step0(glycolipid, sub2, sub3)
