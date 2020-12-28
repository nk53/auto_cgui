#!/usr/bin/env python3
import argparse
import os
import readline
import shutil
import sys
import utils
import yaml
from importlib import import_module
from multiprocessing import Queue
from os.path import join as pjoin
from time import sleep

# module alias (case-insensitive): base filename
cgui_modules = utils.read_yaml('modules.yml')

def log_exception(case_info, step_num, exc_info):
    global LOGFILE
    templ = 'Job "{}" ({}) encountered an exception on step {}:\n{}\n'
    if not 'jobid' in case_info:
        case_info['jobid'] = '-1'
    jobid = case_info['jobid']
    label = case_info['label']
    with open(LOGFILE, 'a') as fh:
        label = case_info['label']
        fh.write(templ.format(label, jobid, step_num, exc_info))

def log_failure(case_info, step, elapsed_time):
    global LOGFILE

    templ = 'Job "{}" ({}) failed on step {} after {:.2f} seconds\n'
    if not 'jobid' in case_info:
        case_info['jobid'] = '-1'
    jobid = case_info['jobid']
    label = case_info['label']
    with open(LOGFILE, 'a') as fh:
        label = case_info['label']
        fh.write(templ.format(label, jobid, step, elapsed_time))

def log_success(case_info, elapsed_time, ran_validation=False):
    global LOGFILE

    if ran_validation:
        ran_validation = ' and passed validation'
    else:
        ran_validation = ''

    templ = 'Job "{}" ({}) finished successfully after {:.2f} seconds{}\n'
    jobid = case_info['jobid']
    label = case_info['label']
    with open(LOGFILE, 'a') as fh:
        label = case_info['label']
        fh.write(templ.format(label, jobid, elapsed_time, ran_validation))

def log_invalid(case_info, elapsed_time, reason):
    global LOGFILE
    templ = 'Job "{}" ({}) finished after {:.2f} seconds, but was invalid:\n{}\n'
    if not 'jobid' in case_info:
        case_info['jobid'] = '-1'
    jobid = case_info['jobid']
    label = case_info['label']
    with open(LOGFILE, 'a') as fh:
        label = case_info['label']
        fh.write(templ.format(label, jobid, elapsed_time, reason))

parser = argparse.ArgumentParser(description="Test a C-GUI project")
parser.add_argument('-m', '--module', type=str)
parser.add_argument('-t', '--test-name', default='basic',
        help="Name of test to run (default: basic)")
parser.add_argument('-n', '--num-threads', type=int, default=1,
        metavar="N",
        help="Number of parallel threads to spawn for testing (default: 1)")
parser.add_argument('-i', '--interactive', action='store_true',
        help="Accept commands interactively when complete or on error")
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
parser.add_argument('--dry-run', action='store_true', help="Don't actually run anything, just print the resulting test cases after preprocessing")

args = parser.parse_args()

# because dictionary unpacking looks cleaner, all kwargs are placed here
settings = {}

# indicate whether logfile already exists
LOGFILE = args.logfile
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

MODULE_NAME = args.module
if not MODULE_NAME:
    if not 'MODULE' in CONFIG:
        raise KeyError('Missing C-GUI module name, either use -m opt or specify MODULE in config.yml')
    MODULE_NAME = CONFIG['MODULE']
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

TEST_CASE_PATH = pjoin('test_cases', MODULE_NAME.lower(), args.test_name+'.yml')
test_cases = utils.read_yaml(TEST_CASE_PATH)

base_cases = [utils.setup_custom_options(test_case, cgui_module) for test_case in test_cases]
if callable(init_module):
    base_cases, wait_cases = init_module(base_cases, args)
else:
    wait_cases = {}

todo_queue = Queue()
done_queue = Queue()

if args.interactive:
    inter_queue = Queue()
    msg_queue = Queue()
else:
    inter_queue = None
    msg_queue = None

settings['dry_run'] = args.dry_run
settings['interactive'] = args.interactive
settings['inter_q'] = inter_queue
settings['msg_q'] = msg_queue

processes = [BrowserProcess(todo_queue, done_queue, **settings) for i in range(args.num_threads)]

# initialize browser processes
for p in processes:
    p.start()

# put regular cases in the task queue
pending = 0
for case in base_cases:
    if not args.dry_run:
        sleep(0.1 * pending)
    todo_queue.put(case)
    pending += 1

stopped = False # set to True after STOP sent to all threads
# main communication loop
while pending:
    result = done_queue.get()
    pending -= 1
    if result[0] in ('SUCCESS', 'VALID'):
        done_case, elapsed_time = result[1:]
        done_label = done_case['label']
        ran_validation = result[0] == 'VALID'
        log_success(done_case, elapsed_time, ran_validation)
    elif result[0] == 'INVALID':
        done_case, elapsed_time, reason = result[1:]
        log_invalid(done_case, elapsed_time, reason)
    elif result[0] == 'FAILURE':
        done_case, step_num, elapsed_time = result[1:]
        log_failure(done_case, step_num, elapsed_time)
    elif result[0] == 'EXCEPTION':
        done_case, step_num, exc_info = result[1:]
        elapsed_time = -1 # don't report time for exceptions
        log_exception(done_case, step_num, exc_info)
        print("Exception encountered for job ({})".format(done_case['jobid']))
        print(exc_info)
    elif result[0] == 'INTERACT':
        partner, partner_jobid = result[1:]
        print("Interacting with {} ({})".format(partner, partner_jobid))
        normal_prompt = partner+'> '
        continue_prompt = '... '
        prompt = normal_prompt
        pending += 1
        while True:
            try:
                cmd = input(prompt)
                if cmd == 'quit()' or cmd.startswith('sys.exit('):
                    cmd = 'STOP'
            except EOFError:
                cmd = 'STOP'
            inter_queue.put((partner, cmd))
            if cmd == 'STOP':
                break
            need_more = msg_queue.get()
            if bool(need_more) != need_more:
                exc_str = need_more
                print(exc_str)
                need_more = False
            if need_more:
                prompt = continue_prompt
            else:
                prompt = normal_prompt
        del partner, partner_jobid
    elif result[0] == 'CONTINUE':
        pending += 1
        done_case = result[1]
        done_label = done_case['label']
        # are any tasks waiting on this one?
        if done_label in wait_cases:
            done_jobid = str(done_case['jobid'])
            for num, wait_case in enumerate(wait_cases[done_label]):
                if do_copy:
                    wait_case['jobid'] = done_jobid+'_'+str(num+1)
                    wait_case['resume_link'] = done_case['solvent_link']
                todo_queue.put(wait_case)
                pending += 1
            del wait_cases[done_label]
    elif result[0] == 'STOP':
        from signal import SIGINT

        for p in processes:
            p._popen._send_signal(SIGINT)

        for p in processes:
            p.join()

        print('Processing has been stopped by', result[1], 'for the following reason:')
        print('\t',result[2])
        sys.exit(2)
    else:
        print('Warning: got unknown result:', result)

    if not stopped and not wait_cases:
        for p in processes:
            todo_queue.put('STOP')
        stopped = True

# clean up
for p in processes:
    p.join()
