"""Handles Highly Mobile Membrane-Mimetic (HMMM) system building options"""
from os.path import join as pjoin, splitext
from bilayer_builder import BilayerBrowserProcess

_BROWSER_PROCESS = 'HMMMBrowserProcess'

class HMMMBrowserProcess(BilayerBrowserProcess):
    """Implements options specific to HMMM systems"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.module_title = "HMMM Builder"
        self.module_url = "?doc=input/membrane.hmmm"

    def init_system(self, **kwargs):
        # index of the radio button to click to switch projects
        conversion_radios = {
            'hmmm2full': 2,
            'full2hmmm': 3,
        }

        test_case = self.test_case
        convert = test_case.get('convert')
        if convert:
            # do nothing if we're using Job Retriever
            if kwargs.get('resume'):
                return

            url = self.base_url + self.module_url
            browser = self.browser

            conv_idx = conversion_radios[convert]
            fmt_suffix = ''
            if conv_idx > 2:
                fmt_suffix = '2'

            browser.visit(url)

            # switch project to x2y conversion
            conv_button = browser.find_by_name('select_project')[conv_idx]
            conv_button.click()

            psf = test_case.get('psf')
            pdb = test_case.get('pdb')
            str_file = test_case.get('str')

            if not psf:
                raise KeyError("Missing 'psf' for conversion")
            if not pdb:
                raise KeyError("Missing 'pdb' for conversion")
            if not str_file:
                raise KeyError("Missing 'str' for conversion")

            str_file = pjoin(self.base, str_file)

            # determine psf filename and format
            if isinstance(psf, dict):
                psf_file = psf['name']
                psf_ext = splitext(psf_file)[1]
                psf_fmt = psf.get('format', psf_ext)
            else:
                psf_file = psf
                psf_fmt = splitext(psf)[1]

            if psf_fmt and psf_fmt[0] == '.':
                psf_fmt = psf_fmt[1:]

            if psf_fmt == 'psf':
                psf_fmt = 'charmm'

            # determine coordinate filename and format
            if isinstance(pdb, dict):
                pdb_file = pdb['name']
                pdb_ext = splitext(pdb_file)[1]
                pdb_fmt = pdb.get('format', pdb_ext)
            else:
                pdb_file = pdb
                pdb_fmt = splitext(pdb)[1]

            if pdb_fmt and pdb_fmt[0] == '.':
                pdb_fmt = pdb_fmt[1:]

            if pdb_fmt == 'namd':
                pdb_fmt = 'coor'

            # click format buttons and upload file
            ft_css_tpl = 'input[name="{}"][value="{}"]'
            for filetype in ('psf', 'pdb'):
                ft_name = filetype+'_format'+fmt_suffix
                ft_value = locals()[filetype+'_fmt']
                ft_file = locals()[filetype+'_file']

                ft_css = ft_css_tpl.format(ft_name, ft_value)
                ft_button = browser.find_by_css(ft_css)

                ft_button.click()

                ft_file = pjoin(self.base, ft_file)

                if filetype == 'pdb':
                    filetype = 'crd'

                upload_name = filetype+'file'+fmt_suffix
                browser.attach_file(upload_name, ft_file)

            # upload stream file
            upload_name = 'strfile'+fmt_suffix
            browser.attach_file(upload_name, str_file)

            terminal_carbon = test_case.get('terminal_carbon')
            if terminal_carbon:
                browser.fill('ccut', terminal_carbon)

            self.go_next(test_case['steps'][0]['wait_text'])
            self.get_jobid()
        else:
            self.next_button = self.protein_membrane_next_button
            super().init_system(**kwargs)

    def protein_membrane_next_button(self):
        """Finds and returns the HMMM next button for uploaded PDB systems

        This function is necessary because HMMM conversion uses a different
        next button.
        """
        # prevents wrong button from being clicked if a conversion job is
        # queued after a protein/membrane job
        self.next_button = None
        return self.browser.find_by_id("input_nav").find_by_tag("table")
