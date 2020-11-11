import os
import ast
import time
import utils
import yaml
from os.path import join as pjoin
from splinter import Browser
from splinter.exceptions import ElementDoesNotExist
from SolutionBrowserProcess import SolutionBrowserProcess
from InputBrowserProcess import InputBrowserProcess

class BilayerBrowserProcess(SolutionBrowserProcess, InputBrowserProcess):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.module_title = "Membrane Builder"
        self.module_url = "?doc=input/membrane.bilayer"

        # reorder the config into a map of lipid name -> lipid cateogry
        self.lipid_config = utils.read_yaml("membrane.lipids.enabled.yml")['default']

        lipid_map = dict()
        for category_key, category_info in self.lipid_config.items():
            category = category_info['name']

            # TODO: also handle detergents
            if 'lipids' in category_info:
                for lipid in category_info['lipids']:
                    lipid_map[lipid] = category

        self.lipid_map = lipid_map

    def activate_lipid_category(self, category):
        """Activate a lipid category in the Membrane Builder lipid selection page"""
        category_root = self.browser.find_by_text(category)
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

    def activate_mlipid_category(self, category):
        """Activate a lipid category in the Membrane Builder lipid selection page"""
        mcategory_root = self.browser.find_by_id('hetero_xy_option_nlipid')
        category_root = mcategory_root.find_by_text(category)

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
        if not 'orient_ppm' in self.test_case:
            raise KeyError("Missing PPM chains")

        self.click_by_attrs(name="align_option", value="4")

        chains = self.test_case.get('orient_ppm')
        if chains != None:
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

    def select_lipids(self):
        if not 'lipids' in self.test_case:
            raise KeyError("Missing 'lipids' option")

        lipids = self.test_case['lipids']

        if not 'upper' in lipids:
            raise KeyError("Missing 'upper' lipid option")
        if not 'lower' in lipids:
            raise KeyError("Missing 'lower' lipid option")

        size_method = self.test_case.get('size_method', 'ratio').lower()
        allowed_size_methods = ('ratio', 'count')
        if not size_method in allowed_size_methods:
            msg = "Invalid size_method: {}; use one of {!r}"
            raise ValueError(msg.format(size_method, allowed_size_methods))

        # reorganize lipid list by lipid category and determine full element name
        lipid_elems = list()
        categories = set() # the categories we need to activate
        name_tpl = "lipid_"+size_method+"[{}][{}]"
        for layer in ('upper', 'lower'):
            for lipid, count in lipids[layer].items():
                lipid = lipid.lower()

                category = self.lipid_map[lipid]
                categories.add(category)

                # browser.fill() needs both name and count
                lipid_tup = name_tpl.format(layer, lipid), count
                lipid_elems.append(lipid_tup)

        # activate all categories
        for category in categories:
            self.activate_lipid_category(category)

        # fill in all lipid values
        for name, value in lipid_elems:
            self.browser.fill(name, value)

    def set_mion_method(self):
        """Uses Monte-Carlo method unless ion_method[0] is d or D"""
        if not 'mion_method' in self.test_case:
            raise ValueError("Missing ion_method")

        ion_method = str(self.test_case['mion_method']).lower()[0]
        ion_method = ion_method == 'd' and 'dist' or 'mc'

        self.browser.select('ion_method', ion_method)

    def select_mlipids(self):
        if not 'mlipids' in self.test_case:
            raise KeyError("Missing 'mlipids' option")

        lipids = self.test_case['mlipids']

        if not 'upper' in lipids:
            raise KeyError("Missing 'upper' mlipid option")
        if not 'lower' in lipids:
            raise KeyError("Missing 'lower' mlipid option")

        size_method = self.test_case.get('msize', 'number').lower()
        allowed_size_methods = ('ratio', 'number')
        if not size_method in allowed_size_methods:
            msg = "Invalid size_method: {}; use one of {!r}"
            raise ValueError(msg.format(size_method, allowed_size_methods))

        # reorganize lipid list by lipid category and determine full element name
        lipid_elems = list()
        categories = set() # the categories we need to activate
        name_tpl = "lipid_"+size_method+"[{}][{}]"
        ch = 'a'
        Uch = 'A'
        inc_num = 0
        for layer in self.test_case['mlipids']:
            for mlipid in self.test_case['mlipids'][layer]:
                if mlipid == "lpsa":
                    lipid = "lpsa"
                    Ulipid = "LPSA"
                    lps_preface = "lps"
                    Ulps_preface = "LPS"
                    self.browser.driver.implicitly_wait(10);
                    self.browser.driver.set_script_timeout(10000);
                    self.browser.driver.set_page_load_timeout(10000);
                    category = self.lipid_map[lipid]
                    categories.add(category)
                    self.activate_mlipid_category(category)
                    lps_count = (len(self.test_case['mlipids'][layer][mlipid]) - 1)
                    for i in range(lps_count):
                        self.browser.execute_script('addLPS()')
                    for species in self.test_case['mlipids'][layer][mlipid]:
                        lps_letter = chr(ord(ch) + inc_num)
                        Ulps_letter = chr(ord(Uch) + inc_num)
                        lipid = (lps_preface + lps_letter)
                        Ulipid = (Ulps_preface + Ulps_letter)
                        try:
                            speciesn,speciesc = species.split('_')
                        except:
                            speciesn = species
                        for lipn, lip in enumerate(self.test_case['mlipids'][layer][mlipid][species]['lip']):
                            lip = str(lip)
                        for coren, core in enumerate(self.test_case['mlipids'][layer][mlipid][species]['core']):
                            core, count = core.split(', ')
                        if 'oanti' in self.test_case['mlipids'][layer][mlipid][species]:
                            for oantin, oanti in enumerate(self.test_case['mlipids'][layer][mlipid][species]['oanti']):
                                oanti, ocount = oanti.split(', ')
                        nlipid_root = self.browser.find_by_id('hetero_xy_option_nlipid')
                        nlipid_root.find_by_value(Ulipid).first.click()
                        time.sleep(5)
                        self.browser.windows.current = self.browser.windows[1]
                        self.browser.find_by_value(speciesn).first.click()
                        self.browser.find_by_value(lip).first.click()
                        self.browser.find_by_value(core).first.click()
                        if 'oanti' in self.test_case['mlipids'][layer][mlipid][species]:
                            self.browser.find_by_id(oanti).first.click()
                            self.browser.find_by_name('lps[nounit]').first.fill(ocount)
                        self.browser.execute_script("updateLPS();")
                        self.browser.windows.current = self.browser.windows[0]
                        lipid_tup = name_tpl.format(layer, lipid), count
                        lipid_elems.append(lipid_tup)
                        inc_num += 1
                elif mlipid == "glycolipid":
                    lipid = "glpa"
                    Ulipid = "GLPA"
                    glp_preface = "glp"
                    Uglp_preface = "GLP"
                    pglyc_fmt = "//span[.='{}']"
                    sub2_fmt = "//input[@value='{}']"
                    sub3_fmt = "//input[@value='{}']"
                    self.browser.driver.implicitly_wait(10);
                    self.browser.driver.set_script_timeout(10000);
                    self.browser.driver.set_page_load_timeout(10000);
                    category = self.lipid_map[lipid]
                    categories.add(category)
                    self.activate_mlipid_category(category)
                    glp_count = (len(self.test_case['mlipids']['upper'][mlipid]) + len(self.test_case['mlipids']['upper'][mlipid]) - 1 - inc_num)
                    for i in range(glp_count):
                        self.browser.execute_script('addGlycolipid()')
                    for species in self.test_case['mlipids'][layer][mlipid]:
                        glp_letter = chr(ord(ch) + inc_num)
                        Uglp_letter = chr(ord(Uch) + inc_num)
                        lipid = (glp_preface + glp_letter)
                        Ulipid = (Uglp_preface + Uglp_letter)
                        try:
                            speciesn,speciesc = species.split('_')
                        except:
                            speciesn = species
                        for sub2n, sub2 in enumerate(self.test_case['mlipids'][layer][mlipid][species]['sub2']):
                            try:
                                sub2name, sub2id, count = sub2.split(', ')
                                sub2 = str(sub2id)
                            except:
                                sub2 = str(sub2)
                                msub3 = self.test_case['mlipids'][layer][mlipid][species]['sub2'][sub2]
                                for sub3 in msub3:
                                    sub3name,sub3id, count = sub3.split(', ')
                                    sub3 = str(sub3id)
                        nlipid_root = self.browser.find_by_id('hetero_xy_option_nlipid')
                        nlipid_root.find_by_value(Ulipid).first.click()
                        time.sleep(5)
                        self.browser.windows.current = self.browser.windows[1]
                        try:
                            pglyc_id = pglyc_fmt.format(speciesn)
                            sub2_id = pglyc_fmt.format(sub2)
                            sub3_id = sub3_fmt.format(sub3)
                            self.browser.execute_script("$('sub1').toggle()")
                            time.sleep(1)
                            self.browser.find_by_xpath(pglyc_id).click()
                            time.sleep(1)
                            sub2_sibling = self.browser.find_by_xpath(sub2_id)
                            sub2_sibling.find_by_xpath("./..").click()
                            time.sleep(1)
                            sub3_sibling = self.browser.find_by_xpath(sub3_id)
                            sub3_sibling.find_by_xpath("./..").click()
                            time.sleep(1)
                        except:
                            pglyc_id = pglyc_fmt.format(speciesn)
                            sub2_id = sub2_fmt.format(sub2)
                            self.browser.execute_script("$('sub1').toggle()")
                            time.sleep(1)
                            self.browser.find_by_xpath(pglyc_id).click()
                            time.sleep(1)
                            sub2_sibling = self.browser.find_by_xpath(sub2_id)
                            sub2_sibling.find_by_xpath("./..").click()
                            time.sleep(1)
                        self.browser.execute_script("updateGlycolipid();")
                        self.browser.windows.current = self.browser.windows[0]
                        lipid_tup = name_tpl.format(layer, lipid), count
                        lipid_elems.append(lipid_tup)
                        inc_num += 1
                else:
                    for lipid, count in lipids[layer].items():
                        lipid = lipid.lower()
                        category = self.lipid_map[lipid]
                        categories.add(category)

                        # browser.fill() needs both name and count
                        lipid_tup = name_tpl.format(layer, lipid), count
                        lipid_elems.append(lipid_tup)
        # activate all categories
        for category in categories:
            self.activate_mlipid_category(category)

        # fill in all lipid values
        for name, value in lipid_elems:
            self.browser.fill(name, value)

    def calc_msize(self):
        msizecalc_root = self.browser.find_by_id('hetero_xy_option_nlipid')
        sizecalc_root = msizecalc_root.find_by_id('hetero_size_button')

        sizecalc_root.click()
        time.sleep(5)

    def init_system(self, test_case, resume=False):
        module_title = self.module_title
        url = self.base_url + self.module_url
        browser = self.browser

        if 'pdb' in self.test_case:
            pdb = self.pdb = test_case['pdb']
            if not resume:
                browser.visit(url)
                # infer as much as possible about the PDB format
                if isinstance(pdb, dict):
                    if 'format' in pdb:
                        pdb_fmt = pdb['format']
                    else:
                        pdb_fmt = pdb['name'].split('.')[-1]

                    source = 'source' in pdb and pdb['source']
                    pdb_name = test_case['pdb']['name']
                else:
                    pdb_name = test_case['pdb']
                    pdb_fmt = '.' in pdb_name and pdb_name.split('.')[-1]
                    source = not pdb_fmt and 'RCSB'

                if pdb_fmt:
                    pdb_fmt = {
                        'pdb': 'PDB',
                        'pqr': 'PDB',
                        'cif': 'mmCIF',
                        'charmm': 'CHARMM',
                    }[pdb_fmt]

                if source and self.name.split('-')[-1] != '1':
                    reason = "Multithreading is not allowed for "+module_title+\
                             " when downloading from RCSB/OPM. Please use an"\
                             " upload option instead."
                    self.stop(reason)

                if source:
                    browser.fill('pdb_id', pdb_name)
                else:
                    pdb_path = pjoin(self.base, pdb_name)
                    browser.attach_file("file", pdb_path)
                    browser.find_by_value(pdb_fmt).click()

                self.go_next(test_case['steps'][0]['wait_text'])

                jobid = browser.find_by_css(".jobid").first.text.split()[-1]
                test_case['jobid'] = jobid
        else:
            if not resume:
                browser.visit(url)
                browser.find_by_xpath("//*[@id='pdb']/h4[2]/input").click()

                self.go_next(test_case['steps'][0]['wait_text'])

                jobid = browser.find_by_css(".jobid").first.text.split()[-1]
                test_case['jobid'] = jobid

