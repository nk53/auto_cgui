import os
import re
import yaml
from os.path import join as pjoin

def find_test_file(filename, module=None, root_dir='test_cases', ext='.yml'):
    """Looks for a test case or related file in the following order:
        - test_cases/module/filename     (if module)
        - test_cases/module/filename.yml (if module)
        - test_cases/filename
        - test_cases/filename/filename
        - test_cases/filename/filename.yml
    On success, returns the path to the test file.
    On failure, raises FileNotFoundError.
    """
    # keep track of all paths attempted, for debugging
    tried = []

    if module:
        # try joining all args
        path = pjoin(root_dir, module, filename)
        tried.append(path)

        # try joining all args + .yml
        if os.path.isfile(path):
            return path
        else:
            path += ext
            tried.append(path)
        if os.path.isfile(path):
            return path

    # try omitting module
    path = pjoin(root_dir, filename)
    tried.append(path)

    # one of the above should at least be a file or directory
    if not os.path.exists(path):
        raise FileNotFoundError("No such file or directory: " + repr(tried))

    # try getting default file for this directory
    if os.path.isdir(path):
        path = pjoin(path, os.path.basename(path))
        tried.append(path)

    if os.path.isfile(path):
        return path
    else:
        path += ext
        tried.append(path)

    if not os.path.isfile(path):
        raise FileNotFoundError("No such file: " + repr(tried))

    return path

def setup_custom_options(test_case, module):
    test_case = setup_test_inheritance(test_case, module)

    map_filename = test_case.get('dict')
    if map_filename:
        map_filename = find_test_file(map_filename, module=module)
        opt_map = read_yaml(map_filename)
        for opt, settings in opt_map.items():
            if opt in test_case:
                value = str(test_case[opt])
                pattern = r'\b' + opt + r'\b'

                step = settings.get('step')
                assert step, "Error: 'step' must be defined for custom options"
                step = int(step) - 1

                test_step = test_case['steps'][step]

                presteps = settings.get('presteps')
                if presteps:
                    for ind, step in enumerate(presteps):
                        presteps[ind] = re.sub(pattern, value, step)

                    test_presteps = test_step.setdefault('presteps', [])
                    test_presteps += presteps

                elems = settings.get('elems')
                if elems:
                    for ind, elem in enumerate(elems):
                        for elem_name, elem_value in elem.items():
                            elem_value = str(elem_value)
                            elems[ind][elem_name] = re.sub(pattern, value, elem_value)

                    test_elems = test_step.setdefault('elems', [])
                    test_elems += elems

                poststeps = settings.get('poststeps')
                if poststeps:
                    for ind, step in enumerate(poststeps):
                        poststeps[ind] = re.sub(pattern, value, step)

                    test_poststeps = test_step.setdefault('poststeps', [])
                    test_poststeps += poststeps

    # look for "module" in each step
    # can't use for loop b/c iteration is nonlinear
    ind = 0
    while ind < len(test_case['steps']):
        step = test_case['steps'][ind]
        if 'module' in step:
            module_info = step['module']
            module_name = module_info['name']
            module_template = find_test_file(module_name, module=module_name)

            test_template = read_yaml(module_template)

            # inherit options from test_template
            test_copy = test_case.copy()

            # default to test_copy's options except for steps/dict/parent
            for key in ('steps', 'dict', 'parent'):
                if key in test_copy:
                    del test_copy[key]

            test_template.update(test_copy)

            test_template = test_copy

            # generate sub-case as though template were the main case
            test_template = setup_custom_options(test_template, module=module_name)

            # obtain user's desired slice of module's steps
            index = module_info.get('index', None)
            if index == None:
                start = module_info.get('start', None)
                stop = module_info.get('stop', None)
                step_slice = slice(start, stop)
                module_steps = test_template['steps'][step_slice]
            else:
                module_steps = [test_template['steps'][index]]

            # replace module entry with steps
            before = test_case['steps'][:ind]
            after = test_case['steps'][ind+1:]
            test_template['steps'] = before + module_steps + after
            test_case = test_template

            ind += len(module_steps)
        else:
            ind += 1

    return test_case

def setup_test_inheritance(child_case, module):
    if not 'parent' in child_case:
        child_case['parent'] = module

    lineage = [child_case]
    filenames = [None]
    parent = child_case.get('parent', module)
    while parent != False:
        # defaults to module name
        if parent == None:
            parent = module
        else:
            parent = parent

        # break if module has itself as parent
        parent = find_test_file(parent, module=module)
        if parent in filenames:
            break

        with open(parent) as parent_file:
            parent_case = yaml.load(parent_file.read(), Loader=yaml.FullLoader)
        lineage.append(parent_case)
        filenames.append(parent)

        child_case = parent_case
        parent = child_case.get('parent', module)

    parent_case = lineage.pop()
    while lineage:
        child_case = lineage.pop()
        parent_case.update(child_case)

    return parent_case

def read_yaml(filename):
    with open(filename) as fh:
        return yaml.full_load(fh.read())

def psf_seek_title(fh):
    """Advances the file pointer to the first line after the title

    Assumes fh is newly-opened and pointing at the first character

    Return
    ======
        success, num_lines_read
    """
    psf_format = fh.readline()
    in_section = None
    line_no = 1
    for line in fh:
        line_no += 1

        line = line.strip()
        if not line:
            continue

        if not in_section:
            title_size = line.split()[0]
            if not title_size.isdigit():
                return False, line_no
            title_size = int(title_size)
            title_lines_read = 1
            in_section = True
        elif title_lines_read < title_size:
            title_lines_read += 1
        else:
            return True, line_no

    return False, line_no

def diff_psf(target, reference):
    """Compares target and reference line-by-line.

    Comparison begins after the title.

    Parameters
    ==========
      target        structure to check
      reference     structure considered "correct"

    Return
    ======
        None if there are no differences;
        An error string if file can't be parsed;
        Otherwise, a tuple showing the first difference is returned:
            target_line_no, reference_line_no, target_line, reference_line
    """
    INVALID_TARGET = 'Error: target is not a valid PSF: {}'
    INVALID_REFERENCE = 'Error: reference is not a valid PSF: {}'
    INVALID_TITLE = 'Error: invalid title format for PSF: {}'

    if isinstance(target, str):
        if not os.path.isfile(target):
            return INVALID_TARGET.format(target)
        target = open(target)
    if isinstance(reference, str):
        if not os.path.isfile(reference):
            return INVALID_REFERENCE.format(reference)
        reference = open(reference)

    with target:
        with reference:
            success, target_line_no = psf_seek_title(target)
            if not success:
                return INVALID_TITLE.format(target.name)

            success, ref_line_no = psf_seek_title(reference)
            if not success:
                return INVALID_TITLE.format(reference.name)

            for target_line, reference_line in zip(target, reference):
                target_line_no += 1
                ref_line_no += 1
                target_line = target_line.strip().upper()
                reference_line = reference_line.strip().upper()
                if target_line != reference_line:
                    return target_line_no, ref_line_no, target_line, reference_line

            # compress any whitespace at end of file
            target_data = target.read(512).rstrip()
            reference_data = reference.read(512).rstrip()

    if target_data != reference_data:
        return target_line_no, ref_line_no, target_data, reference_data

def ref_from_label(label):
    return label.strip().lower().replace(' ', '_')+'.psf'
