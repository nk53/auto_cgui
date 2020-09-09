import os
import re
import yaml
from os.path import join as pjoin

def find_test_file(filename, module=None):
    """Looks for a test case or related file in the following order:
        - test_cases/module/filename     (if module)
        - test_cases/module/filename.yml (if module)
        - test_cases/filename
        - test_cases/filename/filename
        - test_cases/filename/filename.yml
    """
    # keep track of all paths attempted, for debugging
    tried = []

    if module:
        # try joining all args
        path = pjoin('test_cases', module, filename)
        tried.append(path)

        # try joining all args + .yml
        if os.path.isfile(path):
            return path
        else:
            path += '.yml'
            tried.append(path)
        if os.path.isfile(path):
            return path

    # try omitting module
    path = pjoin('test_cases', filename)
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
        path += '.yml'
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
        if parent == filenames[-1]:
            break

        with open(parent) as parent_file:
            parent_case = yaml.load(parent_file.read(), Loader=yaml.FullLoader)
        lineage.append(parent_case)

        if parent in filenames:
            filenames.append(parent)
            errmsg = "Multiple/circular inheritance not allowed; got: "
            errmsg += repr(filenames)
            raise NotImplementedError(errmsg)
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

