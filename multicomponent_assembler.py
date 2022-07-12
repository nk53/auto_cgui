"""Handles Multicomponent Assembler options"""
import copy
from os.path import join as pjoin
from splinter.exceptions import ElementDoesNotExist
from bilayer_builder import BilayerBrowserProcess
from input_generator import InputBrowserProcess
from utils import set_elem_value

_BROWSER_PROCESS = 'MCABrowserProcess'

def init_module(test_cases, args):
    """Preprocesses test cases

    Returns: (2-tuple)
    =======
        base_cases  Cases that can begin immediately
        wait_cases  Cases that need one of the base cases to complete first
    """
    base_cases = []
    wait_cases = {}
    for test_case in test_cases:
        if not 'solvent_tests' in test_case:
            base_cases.append(test_case)
        else:
            do_copy = args.copy
            if 'memb' in test_case['label']:
                cases = handle_solvent_memb_tests(test_case, do_copy)
            else:
                cases = handle_solvent_tests(test_case, do_copy)

            # for tests on localhost, computation can be sped up by copying
            # the project directory at the test-branching point; for remote
            # tests, this is not possible
            if 'localhost' in args.base_url.lower() and do_copy:
                base_case = cases[0]
                base_cases.append(base_case)
                wait_cases[base_case['label']] = cases[1:]
            else:
                base_cases += cases
    return base_cases, wait_cases

def handle_solvent_memb_tests(test_case, do_copy=False):
    """Like handle_solvent_tests(), but for systems with a membrane"""
    if not 'solvent_tests' in test_case:
        raise KeyError("Missing 'solvent_tests'")
    solvent_tests = test_case['solvent_tests']

    # find the step containing SOLVENT_TEST_PLACEHOLDER
    placeholder = 'SOLVENT_TEST_PLACEHOLDER'
    found = False
    index = None
    step_num = None
    check_lists = 'presteps', 'poststeps'
    for step_num, step in enumerate(test_case['steps']):
        for check_list in check_lists:
            if check_list in step and placeholder in step[check_list]:
                found = True
                index = step[check_list].index(placeholder)
                break
        if found:
            break
    if not found:
        raise KeyError("Missing '"+placeholder+"'")

    # action to do to *uncheck* an option
    test_map = {
        'water': "uncheck('water_checked')",
        'ions': "uncheck('ion_checked')",
    }

    cases = []
    for test_str in solvent_tests:
        test = test_str.split('+')
        case = copy.deepcopy(test_case)
        step_proc = case['steps'][step_num][check_list]
        step_proc.pop(index)

        ion_step_proc = case['steps'][step_num-1]
        if not 'presteps' in ion_step_proc:
            ion_step_proc['presteps'] = []

        if not 'ions' in test:
            ion_step_proc['presteps'].insert(0, test_map['ions'])
            ion_step_proc['poststeps'].remove("click_by_value('Calculate Solvent Composition')")
            ion_step_proc['poststeps'].remove("wait_script('is_updated')")
            case['ion_type'] = False
        if not 'water' in test:
            step_proc.insert(index, test_map['water'])

        case['label'] += ' (solvent: '+test_str+')'
        cases.append(case)

    for num, case in enumerate(cases):
        case['case_id'] = num
        case['solvent_link'] = step_num - 1

    if do_copy:
        copy_action = "copy_dir(ncopy={})".format(len(solvent_tests))
        cases[0]['steps'][step_num-1]['presteps'].insert(index, copy_action)

    return cases

def handle_solvent_tests(test_case, do_copy=False):
    """Modifies water/ion options to include solvents according to the
    following scheme:
        None: no water and no ions
        water: water only
        ions: ions only
        water+ions: water and ions
    The return value is a set of new test cases modified to test each case in
    the solvent_tests list.
    """
    if not 'solvent_tests' in test_case:
        raise KeyError("Missing 'solvent_tests'")
    solvent_tests = test_case['solvent_tests']

    # find the step containing SOLVENT_TEST_PLACEHOLDER
    placeholder = 'SOLVENT_TEST_PLACEHOLDER'
    found = False
    index = None
    step_num = None
    check_lists = 'presteps', 'poststeps'
    for step_num, step in enumerate(test_case['steps']):
        for check_list in check_lists:
            if check_list in step and placeholder in step[check_list]:
                found = True
                index = step[check_list].index(placeholder)
                break
        if found:
            break
    if not found:
        raise KeyError("Missing '"+placeholder+"'")

    # action to do to *uncheck* an option
    test_map = {
        'water': "uncheck('water_checked')",
        'ions': "uncheck('ion_checked')",
    }

    cases = []
    for test_str in solvent_tests:
        test = test_str.split('+')
        case = copy.deepcopy(test_case)
        step_proc = case['steps'][step_num][check_list]
        step_proc.pop(index)

        if 'None' in test:
            for component, action in test_map.items():
                step_proc.insert(index, action)
        else:
            for component, action in test_map.items():
                if not component in test:
                    step_proc.insert(index, action)

        case['label'] += ' (solvent: '+test_str+')'
        cases.append(case)

    for num, case in enumerate(cases):
        case['case_id'] = num
        case['solvent_link'] = step_num

    if do_copy:
        copy_action = "copy_dir(ncopy={})".format(len(solvent_tests))
        cases[0]['steps'][step_num][check_list].insert(index, copy_action)

    return cases

class MCABrowserProcess(BilayerBrowserProcess, InputBrowserProcess):
    """Implements front page, solvent, and membrane selection for MCA"""
    def find_comp_row(self, comp_name, step):
        """Returns the row element page corresponding to the given uploaded
        component basename"""
        def molpacking_selector():
            return self.browser.find_by_css(
                ".component_list table tr:not(:first-child) td:nth-child(2)")
        def solvent_options_selector():
            return self.browser.find_by_text("Component ID").\
                   find_by_xpath('../../..').\
                   find_by_css("tr:not(:first-child) td:nth-child(2)")

        selectors = {
            'molpacking': molpacking_selector,
            'solvent options': solvent_options_selector,
        }

        rows = selectors[step]()
        row = None
        found = False
        for row in rows:
            if row.text == comp_name:
                found = True
                break

        if not found:
            raise ElementDoesNotExist("Could not find component: "+comp_name)

        comp_row = row.find_by_xpath('..')
        return comp_row

    def set_component_density(self):
        """Sets solvent density of uploaded components on the solvent options page"""
        components = self.components
        for comp_name, comp_info in components.items():
            if not 'density' in comp_info:
                continue
            row = self.find_comp_row(comp_name, 'solvent options')
            comp_type_elem = row.find_by_css("[id^=solv_density]")
            comp_type_elem.fill(str(comp_info['density']))
            if ratio := comp_info.get('ratio'):
                row.find_by_css("[id&=solv_vol_frac]").fill(str(ratio))

    def select_components(self):
        """Handles most options on the size determination step"""
        test_case = self.test_case

        components = self.components
        count_types = {
            'solvated': None,
            'membrane': None,
            'periodic': 'count',
        }
        radio_names = {
            'solvated': 'component_type',
            'membrane': 'memb_comp_type',
        }
        radio_values = {
            'count': 'num_components',
            'ratio': 'component_ratio',
        }
        obj_attrs = {
            'solvated': 'solv_count_type',
            'membrane': 'memb_count_type',
        }

        # initialize count types to None
        for field in obj_attrs.values():
            test_case[field] = None

        # need to know whether there are membrane components for some options
        has_membrane = False
        num_non_solvents = 0
        for comp_name, comp_info in components.items():
            row = self.find_comp_row(comp_name, 'molpacking')
            comp_type = comp_info['type']
            comp_type_elem = row.find_by_css("[name^=type_component")
            comp_type_elem.select(comp_type)

            # can't set number of some component types in this step
            if comp_type in ['solvent', 'ion']:
                continue
            if comp_type == 'membrane':
                has_membrane = True
            elif comp_type == 'periodic':
                has_periodic = True
                pbc_z = comp_info['pbc_z']
                exclude_length = comp_info.get('exclude_length', 0)
                pbc_z_elem = self.browser.find_by_css('[name="pbc_z[{}]'.format(comp_name))
                set_elem_value(pbc_z_elem, pbc_z)
                exclude_elem = self.browser.find_by_css('[name="exclude_length[{}]'.format(comp_name))

            num_non_solvents += 1

            count_type = count_types[comp_type]
            if count_type is None:
                if 'count' in comp_info:
                    count_types[comp_type] = count_type = 'count'
                elif 'ratio' in comp_info:
                    count_types[comp_type] = count_type = 'ratio'
                else:
                    raise KeyError("Must specify either count or ratio for "+comp_name)
                test_case[obj_attrs[comp_type]] = count_type

                self.click_by_attrs(name=radio_names[comp_type], value=radio_values[count_type])
            elif not count_type in comp_info and comp_type != 'periodic':
                raise ValueError("Can't mix 'count' and 'ratio' for same component type")

            # changing component type might change row element
            row = self.find_comp_row(comp_name, 'molpacking')

            num_comps = row.find_by_css("[name^=num_components")
            if count_type == 'count':
                num_comps.fill(comp_info.get('count', 1))
            else:
                num_comps.fill(comp_info.get('ratio', 1))

        if test_case.get('lipids', False) and not has_membrane:
            # special case for membrane systems without membrane components
            test_case['solv_membrane'] = True
            test_case['has_memb_comps'] = False

            if not has_periodic:
                self.check('solv_membrane_checkbox', 'Calculate membrane area using')
        else:
            test_case['has_memb_comps'] = has_membrane

        test_case['has_membrane'] = has_membrane

        # position settings must be given last
        for comp_name, comp_info in components.items():
            row = self.find_comp_row(comp_name, 'molpacking')
            comp_type = comp_info['type']
            position = comp_info.get('pos')
            if position is None:
                continue

            # can't set position of some component types in this step
            if comp_type in ['solvent', 'ion']:
                continue

            row.find_by_value('Set Position').click()
            self.switch_to_window(1)

            # determine whether user's position settings are individualized
            multi_pos = False
            if len(position) > 1:
                for dim, values in position.items():
                    if isinstance(values, (list, tuple)):
                        multi_pos = True
                    break
                if multi_pos:
                    self.browser.find_by_id('position_type_single')
                else:
                    self.browser.find_by_id('position_type_all')

                    if comp_type != 'periodic':
                        # determine constraint type
                        if values is None:
                            self.browser.find_by_id(f'constraint_type_none[{comp_name}][0]').click()
                        elif 'x' in position:
                            self.browser.find_by_id(f'constraint_type_xyz_fixed[{comp_name}][0]').click()
                        else:
                            self.browser.find_by_id(f'constraint_type_z_planar[{comp_name}][0]').click()

            for dim, values in position.items():
                if isinstance(values, (list, tuple)):
                    for index, value in enumerate(values, start=1):
                        # determine constraint type
                        if value is None:
                            self.browser.find_by_id(f'constraint_type_none[{comp_name}][{index}]').click()
                        elif 'x' in position:
                            self.browser.find_by_id(f'constraint_type_xyz_fixed[{comp_name}][{index}]').click()
                        else:
                            self.browser.find_by_id(f'constraint_type_z_planar[{comp_name}][{index}]').click()

                        pos_elem = self.browser.find_by_name(f'{dim}[{comp_name}][{index}]')
                        set_elem_value(pos_elem, values)

                else:
                    pos_elem = self.browser.find_by_name(f'{dim}[{comp_name}][0]')
                    set_elem_value(pos_elem, values)

            self.browser.evaluate_script('apply()')
            self.switch_to_window(0)

        if num_non_solvents:
            poststeps = test_case['steps'][0].setdefault('poststeps', [])
            poststeps.insert(0, "click('size_button', 'Calculated System Size', alert='accept')")

    def setup_afrac(self, validate=True):
        """Handles options specific to area fraction for membrane components"""
        test_case = self.test_case

        # look in XYZ, then XY, then default to None
        xy_dim = test_case.get('XYZ', test_case.get('XY', None))
        count_type = test_case.get('memb_count_type')
        size_type = test_case.get('memb_size_type', None)

        if size_type is not None:
            size_type = size_type.lower()

        if validate:
            if not test_case['has_memb_comps']:
                raise ValueError("Can't use area fraction without membrane components")
            if xy_dim is not None:
                if count_type == 'count':
                    raise ValueError("Can't use mixed size type with component count")
                if size_type is None:
                    raise KeyError("Missing 'memb_size_type'; use one of: 'afrac', 'xy', 'xyz'")
                if size_type not in ('xy', 'xyz'):
                    raise ValueError("Invalid 'memb_size_type'; use one of: 'afrac', 'xy', 'xyz'")

        # set form values
        if xy_dim is None:
            self.click_by_attrs(name='memb_size_type', value="area_fraction")
        else:
            if size_type == 'afrac':
                self.click_by_attrs(name='memb_size_type', value="area_fraction")
            else:
                # already selected by default, but helps check form/test consistency
                self.click_by_attrs(name='memb_size_type', value='memb_side_length')

    def setup_vfrac(self, validate=True):
        """Handles options specific to volume fraction for solvated components"""
        test_case = self.test_case

        # look in XYZ, then Z, then default to None
        z_dim = test_case.get('XYZ', test_case.get('Z', None))
        count_type = test_case.get('solv_count_type')
        size_type = test_case.get('solv_size_type', None)

        if size_type is not None:
            size_type = size_type.lower()

        if validate:
            if z_dim is not None:
                if count_type == 'count':
                    raise ValueError("Can't use mixed size type with component count")
                if size_type is None:
                    raise KeyError("Missing 'solv_size_type'; use one of: 'vfrac', 'z', 'xyz'")
                if size_type not in ('z', 'xyz'):
                    raise ValueError("Invalid 'solv_size_type'; use one of: 'vfrac', 'z', 'xyz'")

        # set form values
        if z_dim is None:
            self.click_by_attrs(name='size_type', value="volume_fraction")
        else:
            if size_type == 'vfrac':
                self.click_by_attrs(name='size_type', value="volume_fraction")
            elif test_case['has_membrane']:
                # already selected by default, but helps check form/test consistency
                self.click_by_attrs(name='size_type', value='solv_side_length')
            else:
                # already selected by default, but helps check form/test consistency
                self.click_by_attrs(name='size_type', value='cube_side_length')

    def init_system(self, **kwargs):
        browser = self.browser
        self.components = self.test_case['components']

        if not kwargs.get('resume'):
            url = self.base_url + "?doc=input/multicomp"
            browser.visit(url)

            # attach files for this test case
            for comp_name, comp_info in self.components.items():
                comp_name = pjoin(self.base, comp_name)
                browser.attach_file("files[]", comp_name+'.crd')
                browser.attach_file("files[]", comp_name+'.psf')
                other_files = comp_info.get('files')
                if other_files:
                    if not isinstance(other_files, (list, tuple)):
                        other_files = [other_files]
                    for filename in other_files:
                        browser.attach_file("files[]",
                            pjoin(self.base, filename))

            self.go_next(self.test_case['steps'][0]['wait_text'])

            self.get_jobid()
