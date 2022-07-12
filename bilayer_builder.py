"""Handles bilayer preparation options"""
import time
from selenium.common.exceptions import WebDriverException

import utils
from solution_builder import SolutionBrowserProcess
from input_generator import InputBrowserProcess

_BROWSER_PROCESS = 'BilayerBrowserProcess'

class BilayerBrowserProcess(SolutionBrowserProcess, InputBrowserProcess):
    """Implements options for bilayer/protein alignment, lipid selection,
    and bilayer size determination.
    """
    next_button = None # for resolving multiple next buttons on initial step

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.module_title = "Membrane Builder"
        self.module_url = "?doc=input/membrane.bilayer"

        # reorder the config into a map of lipid name -> lipid cateogry
        self.lipid_config = utils.read_yaml("membrane.lipids.enabled.yml")['default']

        # not present in config, but needed for lipid category activation
        self.lipid_config['glp'] = {'name': 'Glycolipids'}
        self.lipid_config['lps'] = {'name': 'LPS (lipopolysaccharides)'}

        custom_categories = 'glp', 'lps' # glycolipids and LPS
        lipid_map = dict()
        for category_key, category_info in self.lipid_config.items():
            category = category_info['name']

            # TODO: also handle detergents
            if category_key in custom_categories:
                lipid_map[category_key] = category
            elif 'lipids' in category_info:
                for lipid in category_info['lipids']:
                    lipid_map[lipid] = category

        self.lipid_map = lipid_map

    def activate_lipid_category(self, category):
        """Activate a lipid category in the Membrane Builder lipid selection page"""
        category_root = self.browser.find_by_text(category)
        category_root = self.first_visible(category_root)

        arrow_elem = category_root.find_by_xpath('../img').first
        table_elem = category_root.find_by_xpath('../table').first

        if table_elem.visible:
            # expect to see this message only for Sterol
            msg_tpl = "{} '{}' lipid category is already active; skipping"
            print(msg_tpl.format(self.name, category))
            return

        # clicking the arrow is somehow not very reliable ....
        cnt = 0
        while not arrow_elem.visible:
            cnt += 1
            time.sleep(1)
        arrow_elem.click()

        # keep trying in 5 second intervals until it actually activates
        cnt = 0
        while not table_elem.visible:
            cnt += 1
            time.sleep(1)
            if cnt > 5:
                arrow_elem.click()
                cnt = 0

    def align_ppm(self):
        """Align a protein using PPM server"""
        if not 'orient_ppm' in self.test_case:
            raise KeyError("Missing PPM chains")

        self.click_by_attrs(name="align_option", value="4")

        chains = self.test_case.get('orient_ppm')
        if chains is not None:
            if not isinstance(chains, list):
                raise TypeError("Please specify chains as a list")

            name_tpl = "ppm_chains[{}]"
            on_chains = set()
            for chain in chains:
                on_chains.add(name_tpl.format(chain.upper()))

            chain_elems = self.browser.find_by_css('[name^=ppm_chains]')
            for chain_elem in chain_elems:
                if chain_elem._element.get_property('name') in on_chains:
                    chain_elem.check()
                else:
                    chain_elem.uncheck()

    def align_vector(self):
        """Align a protein with a user-defined vector"""
        orient_vector = self.test_case.get('orient_vector')

        if not isinstance(orient_vector, list):
            msg = "Invalid type for orient_vector: expected '{}' but got '{}'"
            expected = 'list'
            got = orient_vector.__class__.__name__
            raise TypeError(msg.format(expected, got))

        if len(orient_vector) != 2:
            raise ValueError("orient_vector must contain exactly 2 entries")

        self.click_by_attrs(name="align_option", value="3")

        field_tpl = 'align[{}][{}]'
        fields = 'segid', 'residue', 'resid'
        for atom_index, atom in enumerate(orient_vector):
            atom = atom.split()
            if len(atom) != 3:
                raise ValueError("Invalid atom format; use: 'segid resname resid'")
            for field, value in zip(fields, atom):
                field = field_tpl.format(atom_index, field)
                self.browser.fill(field, value)

    def _build_glycolipids(self, glycolipids, lipids_root):
        if not glycolipids:
            return

        self.activate_lipid_category(self.lipid_map['glp'])
        for _ in range(1, len(glycolipids)):
            self.browser.execute_script('addGlycolipid()')

        for lipid, lipid_info in glycolipids.items():
            lipid = lipid.upper()

            predefined = lipid_info.get('predefined')
            lipid_type = lipid_info.get('lipid')

            lipids_root.find_by_value(lipid).click()
            self.switch_to_window(1)

            # wait for HTML to stop changing
            html = None
            while True:
                try:
                    if html == self.browser.html:
                        break
                    html = self.browser.html
                    time.sleep(1)
                except WebDriverException as e:
                    print("got a WebDriverException")
                    self.interact(locals())
                    time.sleep(2)

            if predefined:
                tpl = 'loadGRS("{}")'
                self.browser.evaluate_script(tpl.format(predefined))

            if lipid_type:
                self.browser.select('sequence[0][name]', lipid_type)

                # ensure GRS is properly updated
                while True:
                    grs_elem = self.browser.find_by_id('grs')
                    if grs_elem and grs_elem.text and lipid_type in grs_elem.text:
                        break
                    time.sleep(1)

            self.browser.evaluate_script('updateGlycolipid();')
            self.switch_to_window(0)

    def _build_lps(self, lps_lipids, lipids_root):
        if not lps_lipids:
            return

        self.activate_lipid_category(self.lipid_map['lps'])
        for _ in range(1, len(lps_lipids)):
            self.browser.execute_script('addLPS()')

        for lipid, lipid_info in lps_lipids.items():
            lipid = lipid.upper()

            species = lipid_info['species']
            lipid_a = lipid_info['lip']
            core = lipid_info['core']
            oanti = lipid_info.get('oanti')

            lipids_root.find_by_value(lipid).click()
            self.switch_to_window(1)

            # wait for HTML to stop changing
            html = None
            while True:
                try:
                    if html == self.browser.html:
                        break
                    html = self.browser.html
                    time.sleep(1)
                except WebDriverException as e:
                    print("got a WebDriverException")
                    self.interact(locals())
                    time.sleep(2)

            self.browser.select('lps[species]', species)

            # may need to wait for options to repopulate
            self.wait_exists(self.browser.find_by_css('#lps_lipa option[value='+lipid_a+']'))
            self.browser.select('lps[lipa]', lipid_a)

            self.wait_exists(self.browser.find_by_css('#lps_core option[value='+core+']'))
            self.browser.select('lps[core]', core)

            if oanti:
                oanti = oanti.replace(' ', '')
                ocount = None
                if ',' in oanti:
                    oanti, ocount = oanti.split(',')

                self.browser.find_by_id(oanti).click()

                if ocount is not None:
                    self.browser.fill('lps[nounit]', ocount)

            self.browser.execute_script('updateLPS();')
            self.switch_to_window(0)

    def select_lipids(self):
        """Handles most options on the lipid selection page"""
        lipids = self.test_case.get('lipids')
        if not lipids:
            raise KeyError("Missing 'lipids' option")

        if not 'upper' in lipids:
            raise KeyError("Missing 'upper' lipid option")
        if not 'lower' in lipids:
            raise KeyError("Missing 'lower' lipid option")

        size_method = self.test_case.get('size_method', 'ratio').lower()
        # last two are the same
        allowed_size_methods = ('ratio', 'number', 'nlipid')
        if not size_method in allowed_size_methods:
            msg = "Invalid size_method: {}; use one of {!r}"
            raise ValueError(msg.format(size_method, allowed_size_methods))

        if size_method == 'ratio' and self.module_title != "Nanodisc Builder":
            valid_size = False
            for key in ('X', 'Y', 'XY', 'PBCX', 'PBCY'):
                if key in self.test_case:
                    valid_size = True
                    break
            if not valid_size:
                raise ValueError("size_method is 'ratio', but no X/Y length is given")

        size_id = size_method
        if size_method == 'number':
            size_id = 'nlipid'
        elif size_method == 'nlipid':
            size_method = 'number'

        # chrome times out too quickly
        self.browser.driver.set_script_timeout(10000)
        self.browser.driver.set_page_load_timeout(10000)

        if self.module_title != "Nanodisc Builder":
            self.click_by_attrs(name='hetero_xy_option', value=size_id)
        all_lipids_root = self.browser.find_by_id('hetero_xy_option_'+size_id)

        lipid_elems = list()
        categories = set()
        name_tpl = "lipid_"+size_method+"[{}][{}]"

        # extract custom lipid info
        custom_lipids = {
            'lps': {},
            'glp': {},
        }
        for layer, layer_info in lipids.items():
            for lipid, lipid_info in layer_info.items():
                lipid = lipid.lower()

                custom_type = None
                for prefix in custom_lipids:
                    if lipid.startswith(prefix):
                        custom_type = custom_lipids[prefix]
                        break

                if custom_type is not None:
                    if isinstance(lipid_info, int) or not lipid_info:
                        if not lipid in custom_type:
                            tpl = "Missing lipid info for {} lipid: '{}'"
                            raise KeyError(tpl.format(prefix.upper(), lipid))
                        count = lipid_info or 0
                    else:
                        if lipid in custom_type:
                            tpl = "Duplicate {} lipid specification: '{}'"
                            raise KeyError(tpl.format(prefix.upper(), lipid))
                        custom_type[lipid] = lipid_info
                        count = lipid_info['count']
                else:
                    count = lipid_info
                    category = self.lipid_map[lipid]
                    categories.add(category)

                lipid_tup = name_tpl.format(layer, lipid), str(count)
                lipid_elems.append(lipid_tup)

        self._build_lps(custom_lipids['lps'], all_lipids_root)
        self._build_glycolipids(custom_lipids['glp'], all_lipids_root)

        # activate all categories
        for category in categories:
            self.activate_lipid_category(category)

        # fill in all lipid values
        for name, value in lipid_elems:
            self.browser.fill(name, value)

    def calc_size(self):
        """Finds the correct size calculation button, then clicks it"""
        # due to bad HTML design, the ID is not actually unique
        calc_button = self.browser.find_by_css('[id=hetero_size_button]')
        calc_button = self.first_visible(calc_button)
        calc_button.click()

        self.wait_script('is_updated')

    def init_system(self, **kwargs):
        """Handles front page of Bilayer Builder"""
        url = self.base_url + self.module_url
        browser = self.browser
        test_case = self.test_case

        if 'pdb' in test_case:
            kwargs.setdefault('next_button', self.next_button)
            self._handle_pdb_selection(**kwargs)
        elif not kwargs.get('resume'):
            browser.visit(url)
            browser.find_by_xpath("//*[@id='pdb']/h4[2]/input").click()

            self.go_next(test_case['steps'][0]['wait_text'],
                    next_button=self.next_button)
            self.get_jobid()
