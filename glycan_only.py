"""Handles Glycan Reader & Modeler options for glycan-only systems"""
import re
from cgui_browser_process import CGUIBrowserProcess

_BROWSER_PROCESS = 'GlycanOnlyBrowserProcess'

class GlycanOnlyBrowserProcess(CGUIBrowserProcess):
    """Implements Glycan Only front page options for Glycan Reader & Modeler"""
    def __init__(self, *args, **kwargs):
        self.module_title = "Glycan Reader & Modeler"
        self.module_url = "?doc=input/glycan&step=0"
        super().__init__(*args, **kwargs)

    def set_glycan(self):
        """Builds glycan from GRS sequence"""
        glycan = self.test_case.get('glycan')
        if not glycan:
            raise ValueError("Missing glycan options")

        _d = re.compile('- ')
        chemod_init = False
        nchem = 0
        for i,residue in enumerate(glycan['grs'].split('\n')):
            if not residue.strip():
                continue

            depth = len(_d.findall(residue))
            linkage, resname = residue.split('- ')[-1].split()
            chemod = None

            idx = resname.find('_') #... chemical modification
            if idx > 0:
                chemod = resname[idx+1:].split('_')
                resname = resname[:idx]

            if i > 0:
                self.browser.find_by_id(str(depth)).find_by_css('.add').first.click()
                self.browser.select(f"sequence[{i+1}][linkage]", linkage[1])
                self.browser.select(f"sequence[{i+1}][type]", resname[0])
            self.browser.select(f"sequence[{i+1}][name]", resname[1:])

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

    def init_system(self, **kwargs):
        url = self.base_url + self.module_url
        browser = self.browser

        if not kwargs.get('resume'):
            browser.visit(url)
            self.browser.click_link_by_text("Glycan Only System")
            self.set_glycan()

            self.get_jobid()
