"""Handles Free Energy Calculator options"""
import os
from os.path import join as pjoin
from bilayer_builder import BilayerBrowserProcess

_BROWSER_PROCESS = 'FEPBrowserProcess'

class FEPBrowserProcess(BilayerBrowserProcess):
    """Implements structure uploading and selection for inputs, force
    fields, and FEC protocol
    """
    def set_upload_mol2(self):
        """Uploads a .mol2 file in the file upload form"""
        if not 'drags' in self.test_case:
            raise ValueError("Missing drag mol2 files")
        drags = self.test_case['drags']
        for drag in drags:
            ligfile = os.path.abspath(pjoin('files', self.test_case['ligand']))
            self.ligfile = ligfile
            lig_path = pjoin(self.ligfile, drag)
            self.browser.attach_file('files[]', lig_path)

    def set_program(self):
        """Selects the simulation program for input generation"""
        if not 'programs' in self.test_case:
            raise ValueError("Missing program selection")
        programs = self.test_case['programs']
        for program in programs:
            if program == 'genesis':
                self.browser.find_by_name('gns_checked').click()
            elif program == 'amber':
                self.browser.find_by_name('amb_checked').click()
                self.browser.find_by_name('namd_checked').click()
            elif program == 'charmm':
                self.browser.find_by_name('charmm_checked').click()

    def set_other_ff(self):
        """Selects specific AMBER FF types to use"""
        protein_ffs = self.test_case['protein_ffs']
        ligand_ffs = self.test_case['ligand_ffs']
        water_ffs = self.test_case['water_ffs']
        for protein_ff in protein_ffs:
            if protein_ff == 'ff14sb': # default is ff19sb
                self.browser.find_by_value('FF14SB').click()
        for ligand_ff in ligand_ffs:   # default is gaff2
            if ligand_ff == 'gaff':
                self.browser.find_by_value('GAFF').click()
        for water_ff in water_ffs:     # default is tip3
            if water_ff == 'tip4pew':
                self.browser.find_by_value('TIP4PEW').click()
            elif water_ff == 'opc':
                self.browser.find_by_value('OPC').click()

    def set_ff(self):
        """Selects CHARMM or AMBER force field type"""
        if not 'ffs' in self.test_case:
            raise ValueError("Missing force field")
        ffs = self.test_case['ffs']
        for force_field in ffs:
            if force_field == 'amber':
                self.click_by_attrs(value='AMBER FF Checker')
                self.browser.fill("amb_trial", 1)
            elif force_field == 'cgenff':
                self.click_by_attrs(value='CGenFF Checker')

    def set_ff_version(self):
        """Selects CHARMM FF version"""
        if not 'ff_versions' in self.test_case:
            raise ValueError("Missing CGenFF force field version")
        ff_versions = self.test_case['ff_versions']
        for ff_version in ff_versions:
            if ff_version == 'old':
                self.click_by_attrs(value='c36_v1')
            elif ff_version == 'new':
                self.click_by_attrs(value='c36_v2')

    def set_protocol(self):
        """Selects the free energy calculation protocol"""
        protocols = self.test_case['protocols']
        for protocol in protocols:
            if protocol == 'split':
                self.browser.find_by_name('amb_unif_checked').click()
                self.browser.find_by_name('amb_spli_checked').click()
            elif protocol == 'both':
                self.browser.find_by_name('amb_spli_checked').click()
            else:
                return

    def set_path(self):
        path = self.test_case['path']
        self.browser.find_by_value(path).click()

    def init_system(self, **kwargs):
        test_case = self.test_case
        url = self.base_url + test_case['url_ym']
        browser = self.browser

        if kwargs.get('resume'):
            return

        binding_urls = '?doc=input/afes.rbinding', '?doc=input/afes.abinding'
        solvating_urls = '?doc=input/rsolvating', '?doc=input/asolvating'
        if test_case['url_ym'] in binding_urls:
            # select tye system type
            browser.visit(url)
            system_type = test_case.get('system_type', 'solution')
            self.click_by_value(system_type)

            # let PDBBrowserProcess handle the rest
            self.module_url = test_case['url_ym']
            self._handle_pdb_selection(**kwargs)
        elif test_case['url_ym'] in solvating_urls:
            browser.visit(url)
            drags = self.test_case['drags']
            for drag in drags:
                lig_path = pjoin(self.base, drag)
                self.browser.attach_file('files[]', lig_path)

            self.go_next(test_case['steps'][0]['wait_text'])
            self.get_jobid()
