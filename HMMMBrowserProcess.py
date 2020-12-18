from BilayerBrowserProcess import BilayerBrowserProcess

class HMMMBrowserProcess(BilayerBrowserProcess):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.module_title = "HMMM Builder"
        self.module_url = "?doc=input/membrane.hmmm"
