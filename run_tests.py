#!/usr/bin/env python3
"""Command-line interface to testing suite"""
# standard library imports
import argparse
import os
import sys
from importlib import import_module
from os.path import join as pjoin

# third-party dependencies
import yaml

# auto_cgui imports
import utils
from browser_manager import BrowserManager
from utils import warn

if __name__ == '__main__':
    # module alias (case-insensitive): base filename
    cgui_modules = utils.read_yaml('modules.yml')

    parser = argparse.ArgumentParser(
            description="Test a C-GUI project by simulating browser interactions")
    parser.add_argument('-m', '--modules', nargs='+', metavar='MODULE',
            help="One or more C-GUI modules to test")
    parser.add_argument('-t', '--test-name',
            help="Name of test to run (default: standard)")
    parser.add_argument('-n', '--num-threads', type=int, default=1,
            metavar="N",
            help="Number of parallel threads to spawn for testing (default: 1)")
    parser.add_argument('-i', '--interactive', action='store_true',
            help="Accept commands interactively when complete or on error")
    parser.add_argument('-e', '--errors-only', action='store_true',
            help="(-i modifier) only interact on exceptions and errors")
    parser.add_argument('-w', '--www-dir', metavar="PATH",
            help="Directory where C-GUI projects are stored. "+\
                 "Uses value stored in config by default.")
    parser.add_argument('-b', '--base-url', metavar="URL",
            default='http://charmm-gui.org/',
            help="Web address to CHARMM-GUI (default: http://charmm-gui.org/)")
    parser.add_argument('--copy', action='store_true',
            help="For tests on localhost, run solvent tests by cloning the "+\
                 "project at the solvent test's branch point; saves time, "+\
                 "but can cause errors if the request cache is corrupted")
    parser.add_argument('-l', '--logfile', default='results.log')
    parser.add_argument('--config', type=argparse.FileType('r'),
            default="config.yml", metavar="PATH",
            help="Path to configuration file (default: config.yml)")
    parser.add_argument('--dry-run', action='store_true',
            help="Don't actually run anything, just print the resulting test "+\
                 "cases after preprocessing")
    parser.add_argument('--validate-only', action='store_true',
            help="Reads logfile and attempts to infer and validate PSFs of all logged test cases")
    parser.add_argument('-s', '--skip-success', action='store_true',
            help="Don't repeat tests that have already succeeded")
    parser.add_argument('-d', '--skip-done', action='store_true',
            help="Do not repeat any logged tests")
    parser.add_argument('-r', '--resume', action='store_true',
            help="Resume failed test cases from the step that failed (implies --skip-success)")

    args = parser.parse_args()
    args.skip_success = args.skip_success or args.resume

    # because dictionary unpacking looks cleaner, all kwargs are placed here
    settings = {}

    # indicate whether logfile already exists
    LOGFILE = args.logfile
    if args.validate_only:
        if not os.path.exists(LOGFILE):
            warn("Can't validate: logfile ({}) does not exist".format(LOGFILE))

        from logger import Logger, parse_logfile
        sys_info = parse_logfile(LOGFILE)
    else:
        if os.path.exists(LOGFILE):
            warn("Appending to existing logfile:", LOGFILE)

            from logger import parse_logfile
            sys_info = parse_logfile(LOGFILE)
        else:
            warn("Creating new logfile:", LOGFILE)
            sys_info = {}

    # read configuration
    with args.config:
        CONFIG = yaml.full_load(args.config)

    BASE_URL = args.base_url
    if 'BASE_URL' in CONFIG:
        BASE_URL = CONFIG['BASE_URL']
    if 'USER' in CONFIG and 'PASS' in CONFIG:
        BASE_URL = BASE_URL.split('/')
        BASE_URL[2] = CONFIG['USER']+':'+CONFIG['PASS']+'@'+BASE_URL[2]
        BASE_URL = '/'.join(BASE_URL)
    settings['base_url'] = BASE_URL

    if 'CGUSER' in CONFIG and 'CGPASS' in CONFIG:
        settings['credentials'] = {
            'user': CONFIG['CGUSER'],
            'pass': CONFIG['CGPASS'],
        }

    BROWSER_TYPE = 'firefox'
    if 'BROWSER_TYPE' in CONFIG:
        BROWSER_TYPE = CONFIG['BROWSER_TYPE']
    settings['browser_type'] = BROWSER_TYPE

    # validate WWW_DIR as a directory
    WWW_DIR = args.www_dir
    if not 'WWW_DIR' in CONFIG:
        if 'localhost' in BASE_URL.lower():
            raise KeyError("Missing WWW_DIR from "+args.config.name)
    else:
        WWW_DIR = CONFIG['WWW_DIR']

    if WWW_DIR is not None:
        if not os.path.exists(WWW_DIR):
            raise ValueError(WWW_DIR+" does not exist")
        if not os.path.isdir(WWW_DIR):
            raise ValueError(WWW_DIR+" is not a directory")
    settings['www_dir'] = WWW_DIR

    if not args.modules:
        if not 'MODULE' in CONFIG:
            raise KeyError('Missing C-GUI module name, either use -m opt '+\
                           'or specify MODULE in config.yml')
        args.modules = [CONFIG['MODULE']]
    else:
        modules = [module.upper() for module in args.modules]
        if 'ALL' in modules:
            # get the argument as actually given, for output formatting
            if len(args.modules) > 1:
                all_arg = args.modules[modules.index('ALL')]
                MODULES = ' '.join(args.modules)
                ERRMSG = "Got '-m {}'. Did you mean '-m {}'?"
                ERRMSG = ERRMSG.format(MODULES, all_arg)
                raise argparse.ArgumentTypeError(ERRMSG)

            # some module names have duplicate keys for convenience
            values = []
            for key, value in list(cgui_modules.items()):
                if value in values:
                    del cgui_modules[key]
                else:
                    values.append(value)
            del values

            args.modules = cgui_modules

    test_cases = []
    for MODULE_NAME in args.modules:
        MODULE_NAME = MODULE_NAME.upper()
        if not MODULE_NAME in cgui_modules:
            raise ValueError('Unknown C-GUI module: '+MODULE_NAME)
        MODULE_FILE = cgui_modules[MODULE_NAME]
        cgui_module = MODULE_NAME.lower()
        settings['module'] = cgui_module

        # import relevant names from the module file
        module = import_module(MODULE_FILE)
        init_module = getattr(module, 'init_module', None)

        # to avoid ambiguity, class name should be provided in module file
        BrowserProcess = getattr(module, '_BROWSER_PROCESS')
        BrowserProcess = getattr(module, BrowserProcess)

        # look for a test case in a standard order
        file_tests = 'standard', 'minimal', 'full'
        if args.test_name and not args.test_name in file_tests:
            TEST_CASE_PATH = pjoin('test_cases', cgui_module, args.test_name+'.yml')

            # test cases from this module before (pre-) custom option setup
            pre_test_cases = utils.read_yaml(TEST_CASE_PATH)
        else:
            file_order = 'full', 'standard', 'minimal'
            test_name = args.test_name or 'standard'
            rank = file_order.index(test_name)
            defaults = file_order[rank:]

            test_files = []
            for default in defaults:
                default_path = pjoin('test_cases', MODULE_NAME, default+'.yml')

                if not os.path.exists(default_path):
                    continue

                test_files += utils.read_yaml(default_path)['files']

            # remove duplicates
            test_files = list(set(test_files))

            # if there are no tests, look for basic.yml
            if not test_files:
                BASIC_FILE = 'basic.yml'
                try:
                    utils.find_test_file(BASIC_FILE, module=cgui_module)
                except FileNotFoundError:
                    if not os.path.exists(BASIC_FILE):
                        warn('No test files for {} module, skipping'.format(cgui_module))
                        continue
                test_files = [BASIC_FILE]

            # get all test cases from filenames
            pre_test_cases = []
            for test_file in test_files:
                test_file = utils.find_test_file(test_file, module=cgui_module)
                test_cases = utils.read_yaml(test_file)
                pre_test_cases.extend(test_cases)

        base_cases = [utils.setup_custom_options(test_case, cgui_module)
                      for test_case in pre_test_cases]

        # check for duplicate labels, which make debugging very difficult
        labels = []
        duplicates = False
        for case in base_cases:
            if case['label'] in labels:
                warn(f"Error: found duplicate label in module '{cgui_module}': {case['label']}")
                duplicates = True
            else:
                labels.append(case['label'])
        if duplicates:
            sys.exit(1)
        del labels, duplicates

        if callable(init_module):
            base_cases, wait_cases = init_module(base_cases, args)
        else:
            wait_cases = {}

        if args.skip_success or args.skip_done:
            module_info = sys_info.get(cgui_module, {})
            case_no = 0
            while case_no < len(base_cases):
                case = base_cases[case_no]
                if args.skip_done:
                    base_cases.pop(case_no)
                elif case_log := module_info.pop(case['label'], None):
                    if step := case_log['step']:
                        step = int(step)
                        if args.resume and step > 0:
                            case['jobid'] = case_log['jobid']
                            if case_log['result'] == 'failed':
                                step -= 1
                            case['resume_link'] = step
                            print(f"will resume '{case['label']}' on step {step}")
                        else:
                            print(f"restarting '{case['label']}'")
                    else:
                        print(f"skipping completed job: '{case['label']}")
                        base_cases.pop(case_no)
                else:
                    case_no += 1

        if not base_cases and not wait_cases:
            print("nothing to do for", cgui_module)
            continue

        if args.validate_only:
            if wait_cases:
                # processing the wait cases is too complicated and rare for now
                warn("Warning: wait_cases can only be checked at their "+\
                     "original runtime; skipping ...")

            module_info = sys_info[cgui_module]

            # log messages directly to stdout
            logger = Logger(sys.stdout, cgui_module)

            for test_case in base_cases:
                # try to find the system directory for this test case
                label = test_case['label']
                if not label in module_info:
                    continue

                # add jobid to test case
                case_info = module_info[label]
                test_case['jobid'] = case_info['jobid']

                result = utils.validate_test_case(test_case, case_info['dirname'],
                        sys_archive=case_info['archive'],
                        module=cgui_module)

                logger.log_result(result)
        else:
            print("starting", cgui_module)
            settings['dry_run'] = args.dry_run
            settings['interactive'] = args.interactive
            settings['errors_only'] = args.errors_only

            # set max threads to higher of number of jobs and CLI argument
            num_threads = len(base_cases) + len(wait_cases)
            if num_threads > args.num_threads:
                num_threads = args.num_threads

            # sets up multiprocessing info
            manager = BrowserManager(BrowserProcess, LOGFILE, num_threads, **settings)

            # initializes the other threads
            manager.start()

            # runs test-case event loop
            manager.run(base_cases, wait_cases)

            # blocks until all BrowserProcesses terminate
            manager.stop()
