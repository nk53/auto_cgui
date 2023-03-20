"""Implements options for Solution Builder"""
import time
from pdb_reader import PDBBrowserProcess
from input_generator import InputBrowserProcess
from utils import read_yaml, set_elem_value, set_form_value

_BROWSER_PROCESS = 'SolutionBrowserProcess'
_ions_menu = read_yaml('custom_ions_menu.yml')['charmm']

class SolutionBrowserProcess(PDBBrowserProcess, InputBrowserProcess):
    """Implements selection of solution settings"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.module_title = "Solution Builder"
        self.module_url = "?doc=input/solution"

    def _select_ion(self, compound):
        """Selects the ions in the given compound, returns compound in dict form"""
        if isinstance(compound, list):
            compound = dict(zip(['cation', 'anion', 'conc', 'neutral'], compound))

        if not isinstance(compound, dict):
            type_name = type(compound).__name__
            errmsg = f"Invalid compound type, expected 'dict' but got '{type_name}': '{compound}'"
            raise TypeError(errmsg)

        def menu_path(menu, item):
            """Return the clickable parts of the menu path to ion"""
            for key, value in menu.items():
                if key == item:
                    return [value['name']]
                if isinstance(value, dict) and 'sub' in value:
                    if path := menu_path(value['sub'], item):
                        return [value['title']] + path
            return False

        for category in ('cation', 'anion'):
            ion = compound[category]
            category_menu = _ions_menu[f'{category}s']['sub']

            # open the cation or anion menu
            category_root = self.browser.find_by_id(f'{category}_menu')
            self.wait_visible(category_root, click=True)

            # check that ion actually exists
            path = menu_path(category_menu, ion)
            if not path:
                raise KeyError(f"no such {category}: '{ion}'")

            # click all necessary menu entries to select ion
            for text in path:
                self.wait_visible(category_root.find_by_xpath(
                    f'//*[text()="{text}" or @data-value="{text}"]'), click=True)

        return compound

    def set_custom_ions(self):
        """Supports custom ion UI"""
        ions = self.test_case.get('ions')
        if not ions:
            raise ValueError("Missing ions")

        if isinstance(ions, dict):
            ions = [ions]

        remove_btn = self.browser.find_by_css("[onclick='remove_ion_row(this)']")
        self.wait_exists(remove_btn).click()

        ion_menu_container = self.browser.find_by_id('ion_menu_widget')
        more_ions_btn = ion_menu_container.find_by_xpath('../input')
        more_ions_btn.check() # show "More Ions" section

        for ion_num, compound in enumerate(ions, start=1):
            compound = self._select_ion(compound)
            ion_menu_container.find_by_value("Add This Ion").click()

            if conc := compound.get('conc'):
                self.wait_exists(self.browser.find_by_name('ion_conc[]'),
                        min_length=ion_num).last.fill(str(conc))

            if compound.get('neutral'):
                self.browser.find_by_name('is_neutralizing').last.click()

        self.browser.evaluate_script('update_nion()')

    def set_ion_method(self):
        """Uses Monte-Carlo method unless ion_method[0] is d or D"""
        if not 'ion_method' in self.test_case:
            raise ValueError("Missing ion_method")

        if self.test_case.get('ion_type') == False:
            # this is probably an autogenerated test variation with ions disabled
            print(self.name, "warning: skipping ion method selection")
            return

        ion_method = str(self.test_case['ion_method']).lower()[0]
        ion_method = 'dist' if ion_method == 'd' else 'mc'

        self.browser.select('ion_method', ion_method)

    def set_ion_type(self):
        """Sets the type of ion to place in solution"""
        if not 'ion_type' in self.test_case:
            raise ValueError("Missing ion_type")

        if 'ions' in self.test_case:
            # do not override custom ion options
            return

        # map ion type in case-insensitive manner
        ion_type = str(self.test_case['ion_type']).lower()
        ion_type = {
            'kcl': 'KCl',
            'nacl': 'NaCl',
            'mgcl2': 'MgCl2',
            'cacl2': 'CaCl2',
        }[ion_type]

        if ions_table := self.browser.find_by_id('ions_table'):
            remove_button = ions_table.find_by_css('input[onclick="remove_ion_row(this)"]')
            self.wait_exists(remove_button).click()
            self.browser.find_by_id('ion_type').select(ion_type)
            self.browser.evaluate_script('add_simple_ion_row()')
        else:
            self.browser.select('ion_type', ion_type)

    def set_xyz(self):
        """Sets box dimensions"""
        dims = 'xyz'
        boxtype_names = 'boxtype', 'solvtype'

        # user must set at least one dimension when calling this function
        found = False
        for dim in dims:
            if dim in self.test_case:
                # only process XYZ dimensions once
                if self.test_case[dim] == False:
                    return
                found = True
                break
            if dim.upper() in self.test_case:
                self.test_case[dim] = self.test_case.pop(dim.upper())
                found = True

        if not found:
            raise ValueError("Must specify at least one XYZ dimension")

        self.click_by_attrs(name="solvate_option", value="explicit")

        solvtype = 'rect'
        for name in boxtype_names:
            if name in self.test_case:
                solvtype = self.test_case[name][:4].lower()
                break

        name_tpl = "box[{}][{}]"
        for dim in dims:
            if dim in self.test_case:
                value = self.test_case[dim]
                dim = dim.lower()

                name = name_tpl.format(solvtype, dim)
                self.browser.fill(name, value)

                # prevents set_xyz() from doing anything more than once
                self.test_case[dim] = False