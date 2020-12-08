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

        size_method = self.test_case.get('size', 'number').lower()
        allowed_size_methods = ('ratio', 'number')
        if not size_method in allowed_size_methods:
            msg = "Invalid size_method: {}; use one of {!r}"
            raise ValueError(msg.format(size_method, allowed_size_methods))

        size_id = size_method
        if size_id == 'number':
            size_id = 'nlipid'

        all_lipids_root = self.browser.find_by_id('hetero_xy_option_'+size_id)

        # chrome times out too quickly
        self.browser.driver.set_script_timeout(10000);
        self.browser.driver.set_page_load_timeout(10000);

        # reorganize lipid list by lipid category and determine full element name
        lipid_elems = list()
        categories = set() # the categories we need to activate
        name_tpl = "lipid_"+size_method+"[{}][{}]"
        ch = 'a'
        Uch = 'A'
        linc_num = 0
        ginc_num = 0
        for layer in self.test_case['lipids']:
            for lipid in self.test_case['lipids'][layer]:
                if lipid == "lpsa":
                    lipid = "lpsa"
                    Ulipid = "LPSA"
                    lps_preface = "lps"
                    Ulps_preface = "LPS"
                    category = self.lipid_map[lipid]
                    categories.add(category)
                    self.activate_lipid_category(category)
                    if 'lpsa' in self.test_case['lipids']['upper'] and 'lpsa' in self.test_case['lipids']['lower']:
                        lps_count = ((len(self.test_case['lipids']['upper'][lipid]) + len(self.test_case['lipids']['lower'][lipid])) - 1)
                    else:
                        lps_count = (len(self.test_case['lipids'][layer][lipid]) - 1)
                    for i in range(lps_count):
                        if linc_num == 0:
                            self.browser.execute_script('addLPS()')
                    for species in self.test_case['lipids'][layer][lipid]:
                        lps_letter = chr(ord(ch) + linc_num)
                        Ulps_letter = chr(ord(Uch) + linc_num)
                        lipid = (lps_preface + lps_letter)
                        Ulipid = (Ulps_preface + Ulps_letter)

                        if '_' in species:
                            speciesn,speciesc = species.split('_')
                        else:
                            speciesn = species

                        for lipn, lip in enumerate(self.test_case['lipids'][layer][lipid][species]['lip']):
                            lip = str(lip)

                        for coren, core in enumerate(self.test_case['lipids'][layer][lipid][species]['core']):
                            core, count = core.split(', ')

                        if 'oanti' in self.test_case['lipids'][layer][lipid][species]:
                            for oantin, oanti in enumerate(self.test_case['lipids'][layer][lipid][species]['oanti']):
                                oanti, ocount = oanti.split(', ')

                        all_lipids_root.find_by_value(Ulipid).first.click()
                        self.switch_to_window(1)

                        # may need to wait for elements to appear
                        for selector in (speciesn, lip, core):
                            elem = self.browser.find_by_value(selector)
                            self.wait_exists(elem).click()

                        if 'oanti' in self.test_case['lipids'][layer][lipid][species]:
                            self.browser.find_by_id(oanti).first.click()
                            self.browser.find_by_name('lps[nounit]').first.fill(ocount)

                        self.browser.execute_script("updateLPS();")
                        self.switch_to_window(0)

                        lipid_tup = name_tpl.format(layer, lipid), count
                        lipid_elems.append(lipid_tup)
                        linc_num += 1
                elif lipid == "glycolipid":
                    lipid = "glpa"
                    Ulipid = "GLPA"
                    glp_preface = "glp"
                    Uglp_preface = "GLP"
                    pglyc_fmt = "//span[.='{}']"
                    sub2_fmt = "//input[@value='{}']"
                    sub3_fmt = "//input[@value='{}']"
                    category = self.lipid_map[lipid]
                    categories.add(category)
                    self.activate_lipid_category(category)

                    if 'glycolipid' in self.test_case['lipids']['upper'] and 'glycolipid' in self.test_case['lipids']['lower']:
                        glp_count = ((len(self.test_case['lipids']['upper'][lipid]) + len(self.test_case['lipids']['lower'][lipid])) - 1)
                    else:
                        glp_count = (len(self.test_case['lipids'][layer][lipid]) - 1)

                    for i in range(glp_count):
                        if ginc_num == 0:
                            self.browser.execute_script('addGlycolipid()')

                    for species in self.test_case['lipids'][layer][lipid]:
                        glp_letter = chr(ord(ch) + ginc_num)
                        Uglp_letter = chr(ord(Uch) + ginc_num)
                        lipid = (glp_preface + glp_letter)
                        Ulipid = (Uglp_preface + Uglp_letter)

                        if '_' in species:
                            speciesn,speciesc = species.split('_')
                        else:
                            speciesn = species

                        if (species == 'CER' or species == 'PICER' or species == 'DAG' or species == 'PIDAG' or species == 'ACYL'):
                            nlipid_root = self.browser.find_by_id('hetero_xy_option_nlipid')
                            nlipid_root.find_by_value(Ulipid).first.click()
                            self.switch_to_window(1)

                            for modn, mod in enumerate(self.test_case['lipids'][layer][lipid][species]):
                                modnum, modid, count = mod.split(', ')
                                self.browser.find_by_value(species).click()
                                self.wait_exists(self.browser.find_by_value(modid)).click()

                            time.sleep(2) # TODO: is an explicit wait possible?
                            self.browser.execute_script("updateGlycolipid();")
                            self.switch_to_window(0)

                            lipid_tup = name_tpl.format(layer, lipid), count
                            lipid_elems.append(lipid_tup)
                            ginc_num += 1
                        else:
                            for sub2n, sub2 in enumerate(self.test_case['lipids'][layer][lipid][species]['sub2']):
                                if ', ' in sub2:
                                    sub2name, sub2, count = sub2.split(', ')
                                else:
                                    msub3 = self.test_case['lipids'][layer][lipid][species]['sub2'][sub2]
                                    for sub3 in msub3:
                                        sub3name,sub3id, count = sub3.split(', ')
                                        sub3 = str(sub3id)
                            nlipid_root = self.browser.find_by_id('hetero_xy_option_nlipid')
                            all_lipids_root.find_by_value(Ulipid).first.click()
                            self.switch_to_window(1)
                            self.interact(locals())
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
                                sub2_fmt = "//span[.='{}']/../ul/li/label/input[@value='{}']"
                                pglyc_id = pglyc_fmt.format(speciesn)
                                sub2_id = sub2_fmt.format(speciesn, sub2)
                                self.browser.execute_script("$('sub1').toggle()")
                                time.sleep(1)
                                self.browser.find_by_xpath(pglyc_id).click()
                                time.sleep(1)
                                sub2_sibling = self.browser.find_by_xpath(sub2_id)
                                sub2_sibling.find_by_xpath("./..").click()
                                time.sleep(1)
                            try:
                                for modn, mod in enumerate(self.test_case['lipids'][layer][lipid][species]['modification']):
                                    modnum, modtype, modid = mod.split(', ')
                                    modtype = str(modtype)
                                    modid = str(modid)
                                    self.browser.find_by_value(modtype).click()
                                    time.sleep(1)
                                    self.browser.find_by_value(modid).click()
                                    time.sleep(1)
                                self.browser.execute_script("updateGlycolipid();")
                                self.browser.windows.current = self.browser.windows[0]
                                lipid_tup = name_tpl.format(layer, lipid), count
                                lipid_elems.append(lipid_tup)
                                ginc_num += 1
                            except:
                                self.browser.execute_script("updateGlycolipid();")
                                self.browser.windows.current = self.browser.windows[0]
                                lipid_tup = name_tpl.format(layer, lipid), count
                                lipid_elems.append(lipid_tup)
                                ginc_num += 1
                else:
                    for lipid, count in lipids[layer].items():
                        lipid = lipid.lower()
                        if not (lipid == "glycolipid" or lipid == "lpsa"):
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

    def calc_size(self):
        # due to bad HTML design, the ID is not actually unique
        calc_button = self.browser.find_by_css('[id=hetero_size_button]')
        calc_button = self.first_visible(calc_button)
        calc_button.click()

        # text varies depending on options; just wait for any text at all
        hetero_size = self.browser.find_by_id('hetero_size')
        while not hetero_size.text:
            print(self.name, 'waiting for hetero_size to have text')
            time.sleep(2)

            # element reference might be stale
            hetero_size = self.browser.find_by_id('hetero_size')

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

