"""Common helper functions"""
import os
import re
import shutil
import sys
from os.path import join as pjoin

import yaml
from splinter.element_list import ElementList

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
            if index is None:
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
    """Option inheritance logic is handled here.

    Test cases can inherit options from another test case. Option resolution
    works similarly to variable-name resolution in Python's object inheritance
    scheme, except that multiple inheritance is not allowed; i.e., test cases
    may have only one parent.

    If an option is defined in both the child and the parent, then the child's
    value for that option used.
    """
    if not 'parent' in child_case:
        child_case['parent'] = module

    lineage = [child_case]
    filenames = [None]
    parent = child_case.get('parent', module)
    while parent != False:
        # defaults to module name
        if parent is None:
            parent = module

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
    """Shortcut for reading a YAML file referred by a filename"""
    with open(filename) as file_obj:
        return yaml.full_load(file_obj.read())

def set_elem_value(elem, value):
    """Same as set_form_value, but if you have a ref to the actual element

    Infers action from HTML tag.

    Warning: This will fail if splinter/slelenium changes their API!
    """
    input_type = elem._element.get_property('type')
    if input_type == "radio":
        elem = ElementList(filter(lambda e: e.value == str(value), elem),
                find_by=elem.find_by, query=elem.query)
        elem.check()
    elif input_type == "checkbox":
        if value:
            elem.check()
        else:
            elem.uncheck()
    elif "select" in input_type:
        elem.select(value)
    else:
        elem.fill(str(value))

def set_form_value(browser, name, value):
    """A smarter version of browser.fill

    Handles text, radio, checkbox, and select inputs with unified interface.
    The default action for any other element is to use:
        splinter.driver.find_by_name(name).fill(value)
    """
    # potentially returns more than one element
    elem = browser.find_by_name(name)
    set_elem_value(elem, value)

def psf_seek_title(file_obj):
    """Advances the file pointer to the first line after the title

    Assumes file_obj is newly-opened and pointing at the first character

    Return
    ======
        success, num_lines_read
    """
    _psf_format = file_obj.readline()
    in_section = None
    line_no = 1
    for line in file_obj:
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
    invalid_file = 'Error: {} is not a regular file: {}'
    file_does_not_exist = 'Error: {} does not exist: {}'
    invalid_title = 'Error: invalid title format for PSF: {}'

    if isinstance(target, str):
        if not os.path.exists(target):
            return file_does_not_exist.format('target', target)
        if not os.path.isfile(target):
            return invalid_file.format('target', target)
        target = open(target)

    if isinstance(reference, str):
        if not os.path.exists(reference):
            return file_does_not_exist.format('reference', reference)
        if not os.path.isfile(reference):
            return invalid_file.format('reference', reference)
        reference = open(reference)

    with target:
        with reference:
            success, target_line_no = psf_seek_title(target)
            if not success:
                return invalid_title.format(target.name)

            success, ref_line_no = psf_seek_title(reference)
            if not success:
                return invalid_title.format(reference.name)

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

    return None

def ref_from_label(label):
    """Returns an os-friendly filename from a test case label"""
    return label.strip().lower().replace(' ', '_')+'.psf'

def validate_test_case(test_case, sys_dir, sys_archive=None, module=None,
        elapsed_time=-1., printer_name=None):
    """Attempts to infer a test's reference PSF, then validates it

    Parameters
    ==========
        sys_dir       str    name of project directory produced by this test case
        sys_archive   str    name of compressed archive containing project directory
        test_case     dict   item from a test case configuration file
        module        str    module name
        elapsed_time  float  time since start of test case

    Returns
    =======
        A tuple representing the test cases's validation, for use with
        BrowserManager / CGUIBrowserProcess
    """
    # check test case for reference/target files
    ref = test_case.get('psf_validation')

    # modules must override this with psf_validation as necessary
    target = 'step1_pdbreader.psf'
    if isinstance(ref, dict):
        target = ref.get('target') or target
        ref = ref.get('reference') or ref.get('ref')

    # looking in a standard location for the reference file
    ref_psf = ref or ref_from_label(test_case['label'])
    try:
        ref = find_test_file(ref_psf,
                module=module,
                root_dir='files/references',
                ext='.psf')
    except FileNotFoundError:
        msg = "couldn't find a reference PSF for "+\
              "'{}', skipping PSF validation"
        if printer_name:
            print(printer_name, msg.format(test_case['label']))
        else:
            print(msg.format(test_case['label']))

    if not ref:
        # no reference for this system, just go to the next case
        return 'SUCCESS', test_case, elapsed_time

    # extract system files if necessary
    if not os.path.exists(sys_dir):
        if os.path.exists(sys_archive):
            shutil.unpack_archive(sys_archive)
        else:
            errmsg = "Error: Couldn't find archive: '{}'".format(sys_archive)
            return 'INVALID', test_case, elapsed_time, errmsg

    # ensure system directory exists
    if not os.path.isdir(sys_dir):
        if os.path.exists(sys_dir):
            msg = "'{}' already exists and is not a directory"
            raise FileExistsError(msg.format(sys_dir))
        msg = "could not find project at '{}/'"
        raise FileNotFoundError(msg.format(sys_dir))

    # finally, do the actual PSF comparison
    target = pjoin(sys_dir, target)
    result = diff_psf(target, ref)

    # result is a string if PSF can't be parsed
    if isinstance(result, str):
        errmsg = result + os.linesep
    # result is a tuple if files differ
    if isinstance(result, tuple):
        target_line_no, ref_line_no, target_line, ref_line = result
        errmsg = [
            'Target ({}) differs from reference ({}):',
            '{} line {}',
            target_line,
            '{} line {}',
            ref_line,
        ]
        errmsg = os.linesep.join(errmsg)
        errmsg = errmsg.format(target, ref, target, target_line_no, ref, ref_line_no)
    # result is None on success
    if result is None:
        return 'VALID', test_case, elapsed_time
    return 'INVALID', test_case, elapsed_time, errmsg

def get_sys_dirname(jobid):
    """Returns the directory name associated with a job ID"""
    return 'charmm-gui-{}'.format(jobid)

def get_archive_name(jobid):
    """Returns the archive (.tgz) file associated with a job ID"""
    return 'charmm-gui-{}.tgz'.format(jobid)

def warn(*strs):
    """Shortcut for print(..., file=sys.stderr)"""
    print(*strs, file=sys.stderr)
