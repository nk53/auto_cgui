#!/usr/bin/env python3
import argparse
import os
import sys
import utils
import yaml
from BrowserManager import BrowserManager
from importlib import import_module
from os.path import join as pjoin
from time import sleep

# module alias (case-insensitive): base filename
cgui_modules = utils.read_yaml('modules.yml')

parser = argparse.ArgumentParser(
        description="Test a C-GUI project by simulating browser interactions")
parser.add_argument('-m', '--modules', type=str, nargs='+', metavar='MODULE',
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
        help="Directory where C-GUI projects are stored. Uses value stored in config by default.")
parser.add_argument('-b', '--base-url', metavar="URL",
        default='http://charmm-gui.org/',
        help="Web address to CHARMM-GUI (default: http://charmm-gui.org/)")
parser.add_argument('--copy', action='store_true',
        help="For tests on localhost, run solvent tests by cloning the project at the solvent test's branch point; saves time, but can cause errors if the request cache is corrupted")
parser.add_argument('-l', '--logfile', default='results.log')
parser.add_argument('--config', type=argparse.FileType('r'),
        default="config.yml", metavar="PATH",
        help="Path to configuration file (default: config.yml)")
parser.add_argument('--dry-run', action='store_true',
        help="Don't actually run anything, just print the resulting test cases after preprocessing")
parser.add_argument('--validate-only', action='store_true',
        help="Reads logfile and attempts to infer and validate PSFs of all logged test cases")

args = parser.parse_args()

# because dictionary unpacking looks cleaner, all kwargs are placed here
settings = {}

# indicate whether logfile already exists
LOGFILE = args.logfile
if args.validate_only:
    if not os.path.exists(LOGFILE):
        print("Can't validate: logfile ({}) does not exist".format(LOGFILE))
else:
    if os.path.exists(LOGFILE):
        print("Appending to existing logfile:", LOGFILE)
    else:
        print("Creating new logfile:", LOGFILE)

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

browser_type = 'firefox'
if 'BROWSER_TYPE' in CONFIG:
    browser_type = CONFIG['BROWSER_TYPE']
settings['browser_type'] = browser_type

# validate WWW_DIR as a directory
WWW_DIR = args.www_dir
if not 'WWW_DIR' in CONFIG:
    if 'localhost' in BASE_URL.lower():
        raise KeyError("Missing WWW_DIR from "+args.config.name)
else:
    WWW_DIR = CONFIG['WWW_DIR']

if WWW_DIR != None:
    if not os.path.exists(WWW_DIR):
        raise ValueError(WWW_DIR+" does not exist")
    elif not os.path.isdir(WWW_DIR):
        raise ValueError(WWW_DIR+" is not a directory")
settings['www_dir'] = WWW_DIR

if not args.modules:
    if not 'MODULE' in CONFIG:
        raise KeyError('Missing C-GUI module name, either use -m opt or specify MODULE in config.yml')
    args.modules = [CONFIG['MODULE']]

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
    BrowserProcess = getattr(module, MODULE_FILE)

    # look for a test case in a standard order
    file_tests = 'standard', 'minimal', 'full'
    if args.test_name and not args.test_name in file_tests:
        TEST_CASE_PATH = pjoin('test_cases', cgui_module, args.test_name+'.yml')

        # test cases from this module before (pre-) custom option setup
        pre_test_cases = utils.read_yaml(TEST_CASE_PATH)
    else:
        #default_tests = file_tests + ('basic',)
        #for test_name in default_tests:
        #    TEST_CASE_PATH = pjoin('test_cases', cgui_module, test_name+'.yml')
        #    if os.path.exists(TEST_CASE_PATH):
        #        break
        #if not os.path.exists(TEST_CASE_PATH):
        #    errmsg = "Couldn't find any default test for module {}: {!r}"
        #    raise FileNotFoundError(errmsg.format(MODULE_NAME, default_tests))

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
        test_files = test_files or ['basic.yml']

        # get all test cases from filenames
        pre_test_cases = []
        for test_file in test_files:
            test_file = utils.find_test_file(test_file, module=cgui_module)
            test_cases = utils.read_yaml(test_file)
            pre_test_cases.extend(test_cases)

    base_cases = [utils.setup_custom_options(test_case, cgui_module) for test_case in pre_test_cases]

    if callable(init_module):
        base_cases, wait_cases = init_module(base_cases, args)
    else:
        wait_cases = {}

    if args.validate_only:
        if wait_cases:
            # processing the wait cases is too complicated and rare for now
            print("Warning: wait_cases can only be checked at their original runtime; skipping ...")

        with open(LOGFILE) as results_file:
            sys_info = {}
            for line in results_file:
                jobid, label = utils.parse_jobid_label(line)
                sys_info[label] = {
                    'dirname': utils.get_sys_dirname(jobid),
                    'archive': utils.get_archive_name(jobid),
                    'jobid': jobid,
                }

        # log messages directly to stdout
        from Logger import Logger
        logger = Logger(sys.stdout)

        for test_case in base_cases:
            # try to find the system directory for this test case
            label = test_case['label']
            if not label in sys_info:
                continue

            # add jobid to test case
            case_info = sys_info[label]
            test_case['jobid'] = case_info['jobid']

            result = utils.validate_test_case(test_case, case_info['dirname'],
                    sys_archive=case_info['archive'],
                    module=MODULE_NAME)

            logger.log_result(result)
    else:
        settings['dry_run'] = args.dry_run
        settings['interactive'] = args.interactive
        settings['errors_only'] = args.errors_only

        # sets up multiprocessing info
        manager = BrowserManager(BrowserProcess, LOGFILE, args.num_threads, **settings)

        # initializes the other threads
        manager.start()

        # runs test-case event loop
        manager.run(base_cases, wait_cases)

        # blocks until all BrowserProcesses terminate
        manager.stop()
