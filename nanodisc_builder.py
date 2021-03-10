"""Handles options specific to Nanodisc Builder"""
from bilayer_builder import BilayerBrowserProcess

_BROWSER_PROCESS = 'NanodiscBrowserProcess'

class NanodiscBrowserProcess(BilayerBrowserProcess):
    """Handles msp selection and delegates rest to BilayerBrowserProcess"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.module_title = "Nanodisc Builder"
        self.module_url = "?doc=input/membrane.nanodisc"

    def set_msp(self):
        """Sets the membrane scaffold protein type"""
        msp = self.test_case.get('msp')
        self.browser.select('msptype', msp)
