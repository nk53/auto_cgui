"""Handles LPS Modeler options"""
from itertools import product

from utils import read_yaml, set_form_value
from cgui_browser_process import CGUIBrowserProcess

_BROWSER_PROCESS = 'LPSBrowserProcess'

_species = read_yaml('lps.enabled.yml')
_valid_settings = 'species', 'lipa', 'core', 'nounit', 'oanti', 'lipaphos'
_list_possible = _valid_settings[1:]

def _validate_settings(test_case):
    """Checks that settings exist, and also does some preprocessing"""
    species = test_case.get('species')
    if not species:
        raise KeyError("missing a value for 'species'")
    if not species in _species:
        raise KeyError(f"unknown LPS species: '{species}'")

    species_abbr = species
    species = _species[species]
    species_name = species['name']

    # the approach below allows any of 'lipa', 'Type1', or 'type1'
    lipa = test_case.get('lipa')
    if not lipa:
        lipa = sorted(species['lipa'].keys())[0]

    if lipa in species['lipa']:
        lipa_info = species['lipa']
    else:
        lipas = [k.lower() for k in species['lipa'].keys()]
        if lipa.lower() in lipas:
            lipa = species[lipas.index(lipa.lower())]
        else:
            lipas = [(k, species['lipa'][k]['type'])
                    for k in species['lipa'].keys()]
            found = False
            for liptype, typename in lipas:
                if lipa.lower() == typename.lower():
                    lipa = liptype
                    found = True
                    break
        if not found:
            lipa = test_case['lipa']
            raise KeyError(f"unknown lipid A type: '{lipa}'")

        test_case['lipa'] = lipa
        lipa_info = species['lipa'][lipa]

    lipaphos = test_case.get('lipaphos')
    if lipaphos:
        for phosphate, charge in lipaphos:
            if not phosphate in lipa_info['phosphate']:
                raise KeyError(f"unknown phosphate group for {lipa}")
            if not charge in (-2, -1, 0):
                raise ValueError(f"invalid phosphate charge '{charge}'; use 0, -1, or -2")

    for setting in ('core', 'oanti'):
        value = test_case.get(setting)
        if not value:
            continue
        valid_values = species[setting]
        if not value in valid_values:
            raise ValueError(f"unknown {setting} for {species_abbr} ({species_name}): '{value}'")

# lipaphos test case example: lipaphos: {A: -2, B: 0}

def init_module(test_cases, args):
    """Preprocesses test cases

    Returns: (2-tuple)
    =======
        base_cases  Cases that can begin immediately
        wait_cases  Cases that need one of the base cases to complete first
    """

    base_cases = []
    for test_case in test_cases:
        # check whether Cartesian product of options is desired
        settings = [s for s in _list_possible if isinstance(test_case.get(s), list)]
        use_product = False
        for opt in settings:
            value = test_case.get(opt)
            if len(value) > 1:
                use_product = True
                break
            if value:
                test_case[opt] = value[0]

        if use_product:
            values = [test_case[opt] for opt in settings]
            for combo in product(*values):
                base_case = test_case.copy()
                for opt, value in zip(settings, combo):
                    base_case[opt] = value

                # check whether this combination of settings is valid
                _validate_settings(base_case)
                base_cases.append(base_case)
        else:
            _validate_settings(test_case)
            base_cases.append(test_case)

    return base_cases, {}

class LPSBrowserProcess(CGUIBrowserProcess):
    """Implements selection for LPS Modeler's front page"""
    def __init__(self, *args, **kwargs):
        self.module_title = "LPS Builder"
        self.module_url = "?doc=input/lps"
        super().__init__(*args, **kwargs)

    def init_system(self, **kwargs):
        url = self.base_url + self.module_url
        browser = self.browser
        browser.visit(url)

        browser.driver.implicitly_wait(10)
        browser.driver.set_script_timeout(10000)
        browser.driver.set_page_load_timeout(10000)

        for setting in _valid_settings:
            value = self.test_case.get(setting)
            if not value:
                continue
            if isinstance(value, dict):
                # for elements like lps[lipsaphos][A]
                for key, value in value.items():
                    set_form_value(browser, f'lps[{setting}][{key}]', value)
            else:
                set_form_value(browser, f'lps[{setting}]', value)

        self.go_next(self.test_case['steps'][0]['wait_text'])

        self.get_jobid()
