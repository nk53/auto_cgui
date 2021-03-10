"""Handles input generation options"""
from cgui_browser_process import CGUIBrowserProcess

class InputBrowserProcess(CGUIBrowserProcess):
    """Implements options for input generation"""
    def set_input(self):
        """Sets the simulation input programs for input generation"""
        if not 'input' in self.test_case:
            raise ValueError("Missing input options")

        # input option names are not intuitive
        opt_map = {
            'namd': 'namd',
            'gromacs': 'gmx',
            'amber': 'amb',
            'openmm': 'omm',
            'charmm/openmm': 'comm',
            'genesis': 'gns',
            'desmond': 'dms',
            'lammps': 'lammps',
        }

        input_opts = self.test_case['input']

        if not isinstance(input_opts, list):
            input_opts = [input_opts]

        for opt in input_opts:
            opt = opt.strip().lower()
            opt = opt_map.get(opt, opt)
            opt += '_checked'
            self.browser.find_by_name(opt).check()

    def set_ensemble(self):
        """This function is only necessary because the value button's case
        does not match its text's case, making it likely that test-case
        developers will input the wrong value.
        """
        if not 'ensemble' in self.test_case:
            raise ValueError("Missing ensemble options")

        ensemble = self.test_case['ensemble'].split()[0].lower()
        self.browser.find_by_value(ensemble).check()

    def set_force_field(self):
        """Handles CHARMM/AMBER force field options"""
        if not 'force_field' in self.test_case:
            raise ValueError("Missing force_field options")

        amberff_fields = (
            'prot', 'dna', 'rna', 'glycan', 'lipid', 'water',
            'ligand',
        )

        ff_opts = self.test_case['force_field']
        if not isinstance(ff_opts, dict):
            ff_opts = {'type': ff_opts}

        # force field type MUST be set first
        ff_type = ff_opts.pop('type')
        self.browser.select('fftype', ff_type)

        # for convenience, allow full "protein" instead of just "prot"
        for field in ff_opts.keys():
            f_lower = field.lower()
            if f_lower.startswith('prot') and f_lower != 'prot':
                ff_opts['prot'] = ff_opts.pop(field)

        for field, value in ff_opts.items():
            field = field.lower()

            if field in amberff_fields:
                field = 'amberff['+field+']'
            self.browser.select(field, value)
