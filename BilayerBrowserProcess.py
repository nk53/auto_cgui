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
