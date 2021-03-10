"""Handles polymer builder options"""
import yaml
from cgui_browser_process import CGUIBrowserProcess

_BROWSER_PROCESS = 'PBBrowserProcess'

class PBBrowserProcess(CGUIBrowserProcess):
    """Implements option selection for all polymer pages"""
    def __init__(self, *args, **kwargs):
        self.jobid = None
        self.polydic = None
        self.output = None # charmm-gui-jobid.tgz
        super().__init__(*args, **kwargs)

    def _getpath(self, nested_dict, value, prepath=()):
        for k, v in nested_dict.items():
            path = prepath + (k,)
            if v == value: # found value
                return path
            if hasattr(v, 'items'): # v is a dict
                p = self._getpath(v, value, path) # recursive call
                if p is not None:
                    return p
        return None

    def run_step0(self, pchains, wait_text):
        """Handles front page"""
        browser = self.browser
        browser.choose('model', self.model)
        if len(pchains) > 1:
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
                if i.startswith('type'):
                    tcnt += 1
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
                path_junk = self._getpath(self.polydic, name)
                idx = (len(path_junk) / 2) - 1 # unused?
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
                if polytact is not None:
                    if polytact[0] == 'i' and polytact[-2] == 'R':
                        tacidx = 1 # unused in this case?
                    if polytact[0] == 'i' and polytact[-2] == 'S':
                        tacidx = 2
                    if polytact[0] == 's':
                        tacidx = 3
                    if polytact[0] == 'a':
                        tacidx = -1
                    x = poly_elem.find_by_value(resi)[tacidx].click() # unused?
                subtext = 'subtext[%s][%s]' % (key[6:], str(i + 1))

                browser.find_by_name(subtext).fill(length)
                typecnt += 1

        self.go_next(wait_text)

        # set jobid
        self.jobid = self.get_jobid()

    def resume_step(self, jobid, project=None, step=None, link_no=None):
        self.jobid = jobid
        super().resume_step(jobid, link_no=link_no)

    def init_system(self, **kwargs):
        url = self.base_url + "?doc=input/polymer"
        self.browser.visit(url)
        test_case = self.test_case

        # attach files for this test case
        self.model = test_case['label']
        self.polydic = yaml.load(open("polymer.enabled.yml",'r'))
        self.run_step0(test_case['pchains'],
                       wait_text='Generate Systems')
        test_case['jobid'] = self.jobid
        if 'output' in test_case:
            self.output = test_case['output']
