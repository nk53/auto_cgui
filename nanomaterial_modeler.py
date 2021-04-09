"""Handles Nanomaterial Modeler options"""
from solution_builder import SolutionBrowserProcess
from utils import read_yaml, set_elem_value, set_form_value

_BROWSER_PROCESS = 'NMMBrowserProcess'
_nanomaterial_menu = read_yaml('nanomaterials.yml')['nanomaterial']['sub']
_ligand_menu = read_yaml('lig.enabled.yml')

# Some settings have aliases, e.g. 'lx' can also be 'height'. In all cases,
# the name submitted by the form should be given first. Settings are handled
# in the order specified below. Any other settings are derived from
# nanomaterial.yml and handled *after* _shape_settings.
_shape_settings = (
    'shape',
    'mindex',
    'radius',
    ('lx', 'height', 'x_len', 'x_length'),
    ('ly', 'y_len', 'y_length'),
    ('lz', 'z_len', 'z_length'),
    ('l_pgon', 'edge_length', 'edge_len'),
    ('nnn', 'num_edges'),
    ('miller_index[]', 'miller_index', 'wmindex'),
    ('surface_energy[]', 'surface_energy', 'surf'),
    ('qhyd', 'hydration'),
    'degree',
    'percent_defect',
    'systype',
)

def _build_material_settings(mat_info, category):
    ignore_names = ['shapes', 'name', 'ligand', 'pbc', 'info_table', 'unitcell', 'general']
    for setting in _shape_settings:
        if isinstance(setting, (list, tuple)):
            ignore_names.append(setting[0])
        else:
            ignore_names.append(setting)

    material = mat_info['material']
    mat_config = _nanomaterial_menu[category]['sub'][material]

    settings = []
    for key in mat_config.keys():
        if key in ignore_names:
            continue
        if isinstance(mat_config[key], dict):
            for key in mat_config[key].keys():
                settings.append(key)
        else:
            settings.append(key)

    general = mat_config.get('general')
    if general:
        fields = general.get('fields')
        if fields:
            general = fields
        general = [s for s in general.keys() if not s.get('type') == 'span']
        settings += general

    return settings

def _get_allowed_pbc(mat_info, category):
    material = mat_info['material']
    mat_config = _nanomaterial_menu[category]['sub'][material]
    pbc = mat_config.get('pbc')

    if pbc is None:
        return 'uuu'

    return pbc

def _get_material_type(material):
    material_types = _nanomaterial_menu
    for category, entries in material_types.items():
        materials = entries['sub']
        if material in materials:
            return category
    raise KeyError(f"no such material: '{material}'")

class NMMBrowserProcess(SolutionBrowserProcess):
    """Implements front page options for Nanomaterial Modeler"""
    def _select_material(self, mat_info, category, wait=None):
        # open menu
        self.click_by_text('Nanomaterial Type')

        # select material's category
        material = mat_info['material']
        self.click_by_attrs(wait=wait, data_material_type=category)

        # select material
        self.click_by_attrs(wait=wait, data_value=material)

    def _set_pbc(self, mat_info, category):
        material = mat_info['material']
        pbc = mat_info.get('pbc')
        if pbc is not None:
            allowed_pbc = _get_allowed_pbc(mat_info, category)
            for dim, allowed in zip('xyz', allowed_pbc):
                if allowed in 'uc': # don't change disabled PBC dims
                    set_form_value(self.browser, 'pbc_'+dim, dim in pbc)

    def _set_from_possible(self, possible_settings, mat_info):
        special_handling = {'miller_index[]': self._check_wulff_rows}
        for setting in possible_settings:
            # get the setting's value, if it is set
            if isinstance(setting, (list, tuple)):
                # check possible aliases
                for alias in setting:
                    value = mat_info.get(alias)
                    if value is not None:
                        break
                setting = setting[0]
            else:
                value = mat_info.get(setting)

            # change form value, if it is set in test_case
            if value is not None:
                if setting in special_handling.keys():
                    special_handling[setting](setting)
                if setting.endswith('[]'):
                    # set all values in the order they are given in the form
                    values = value if isinstance(value, list) else [value]
                    elems = self.browser.find_by_name(setting)
                    for elem, value in zip(elems, values):
                        set_elem_value(elem, value)
                else:
                    set_form_value(self.browser, setting, value)

    def _check_wulff_rows(self, miller_index):
        num_mindex_rows = len(self.browser.find_by_name('miller_index[]'))
        if not isinstance(miller_index, (list, tuple)):
            mindex_type = type(miller_index).__name__
            raise TypeError(f"Expected list for 'miller_index', but got {mindex_type}")
        for _ in range(len(miller_index) - num_mindex_rows):
            self.browser.evaluate_script('add_wulff_row()')

    def _set_monomer(self, elem_list, index, value, count=None):
        # open the menu
        monomer_root = elem_list[index].find_by_xpath('../../..')
        monomer_root.click()

        # find monomer in menu and click it
        monomer = monomer_root.find_by_value(value)
        self.wait_visible(monomer, click=True)

        if count is not None:
            # count element is the first input after monomer_root
            count_elem = monomer_root.find_by_xpath('following-sibling::input[1]')
            count_elem.fill(count)

    def _set_ligand(self, mat_info):
        ligands = mat_info.get('ligands') or mat_info.get('ligand')

        if not ligands:
            return

        self.browser.select('num_ligands', len(ligands))

        if not len(ligands) in (1, 2):
            raise IndexError("Ligand count out of range: {len(ligands)}")

        functionals = _ligand_menu['functional']['sub'].keys()
        add_monomer_btns = self.browser.find_by_text('Add monomer unit')

        for ligand_ind, ligand in enumerate(ligands):
            linker = ligand.pop(0)
            functional = ligand.pop() if ligand[-1] in functionals else 'none'
            spacers = []
            spacer_repeat = None

            # preprocess spacers to look like [monomer_name, monomer_count]
            while ligand:
                spacer = ligand.pop(0)
                if isinstance(spacer, str):
                    if ',' in spacer:
                        spacer, count = spacer.split(',')
                    else:
                        count = 1
                    spacers.append((spacer, count))
                elif isinstance(spacer, int):
                    if spacer_repeat is not None:
                        raise ValueError("Got more than one spacer repeat value")
                    if ligand:
                        raise ValueError("Bad position for spacer repeat")
                    spacer_repeat = spacer
                elif isinstance(spacer, (list, tuple)):
                    spacers.append(spacer)
                else:
                    raise TypeError(f"Unknown spacer data type: {type(spacer).__name__}")

            monomer_list = self.browser.find_by_name(f"linker[{ligand_ind}][]")
            self._set_monomer(monomer_list, 0, linker)

            # ensure there are enough spacer fields
            for _ in range(len(spacers)-1):
                add_monomer_btns[ligand_ind].click()

            monomer_list = self.browser.find_by_name(f"spacer[{ligand_ind}][]")

            # easiest method for linker-only ligands
            if not spacers and functional == 'none':
                self._set_monomer(monomer_list, 0, 'none')
                continue

            # set all spacers and their counts
            for monomer_ind, monomer in enumerate(spacers):
                monomer, count = monomer
                self._set_monomer(monomer_list, monomer_ind, monomer, count)

            if spacer_repeat is not None:
                # set outer subtext (spacer pattern repeat)
                self.browser.find_by_name("subtext_outer[]")[ligand_ind].fill(spacer_repeat)

            # set functional group for ligands that have a spacer
            monomer_list = self.browser.find_by_name(f"functional[{ligand_ind}][]")
            self._set_monomer(monomer_list, 0, functional)

    def init_system(self, **kwargs):
        if kwargs.get('resume'):
            return

        # navigate to NMM front page
        url = self.base_url + "?doc=input/nanomaterial"
        self.browser.visit(url)

        # wait for nanomaterial menu to load
        self.wait_text('Nanomaterial Type')

        # select nanomaterial from materials menu
        mat_info = self.test_case['nanomaterial_type']

        category = _get_material_type(mat_info['material'])
        self._select_material(mat_info, category)

        self._set_from_possible(_shape_settings, mat_info)
        self._set_ligand(mat_info)
        self._set_pbc(mat_info, category)

        # autogenerate and set other fields from _nanomaterial_menu
        other_settings = _build_material_settings(mat_info, category)
        self.interact(locals())
        self._set_from_possible(other_settings, mat_info)

        self.go_next(self.test_case['steps'][0]['wait_text'])
        self.get_jobid()
