from BilayerBrowserProcess import BilayerBrowserProcess

class NanodiscBrowserProcess(BilayerBrowserProcess):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.module_title = "Nanodisc Builder"
        self.module_url = "?doc=input/membrane.nanodisc"

    def set_msp(self):
        msp = self.test_case.get('msp')
        self.browser.select('msptype', msp)
