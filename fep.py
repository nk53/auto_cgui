#!/usr/bin/env python3
import argparse
import copy
import os
import shutil
import sys
import yaml
from multiprocessing import Queue
from os.path import join as pjoin

#from 
from FEPBrowserProcess import FEPBrowserProcess

LOGFILE = 'fep_results.log'

def log_exception(case_info, step_num, exc_info):
    templ = 'Job "{}" ({}) encountered an exception on step {}:\n{}\n'
    if not 'jobid' in case_info:
        case_info['jobid'] ='-1'
    jobid = case_info['jobid']
    label = case_info['label']
    with open(LOGFILE, 'a') as fh:
        label = case_info['label']
        fh.write(templ.format(label, jobid, step_num, exc_info))

def log_failure(case_info, step, elapsed_time):
    templ = 'Job "{}" ({}) failed on step {} after {:.2f} seconds\n'
    if not 'jobid' in case_info:
        case_info['jobid'] = '-1'
    jobid = case_info['jobid']
    label = case_info['label']
    with open(LOGFILE, 'a') as fh:
        label = case_info['label']
        fh.write(templ.format(label, jobid, step, elapsed_time))

def log_success(case_info, elapsed_time):
    templ = 'Job "{}" ({}) finished successfully after {:.2f} seconds\n'
    jobid = case_info['jobid']
    label = case_info['label']
    with open(LOGFILE, 'a') as fh:
        label = case_info['label']
        fh.write(templ.format(label, jobid, elapsed_time))

def handle_solvator_tests(test_case, do_copy=False):
    if not 'solvator_tests' in  test_case:
        raise ValueError("Missing 'solvator_tests'")
    solvtor_tests = test_case[solvent_tests]

    placeholder = 'SOLVATOR_TEST_PLACEHOLDER'
    found = False
    index = None
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
        raise ValueError("Miss'" + placeholder + "'")

    for num, case in enumerate(cases):
        case['case_id'] = num
        case['solvator_link'] = step_num

    if do_copy:
        copy_action = "copy_dir(ncopy={})".format(len(solvator_tests))
        cases[0]['steps'][step_num][check_list].insert(index, copy_action)

    return cases

parser = argparse.ArgumentParser(description='Test a C-GUI project')
parser.add_argument('-t', '--test-name', default='basic',
        help="Name of test on run (default:basic)")
parser.add_argument('-n', '--num-threads', type=int, default=1,
        metavar="N",
        help="Number of parallel threads  to spawn for testing (default: 1)")
parser.add_argument('-p', '--pause', action='store_true',
        help="Pause execution on error")
parser.add_argument('-w', '--www-dir', metavar="PATH",
        help="Directory where C-GUI projects are stored. Uses  value stored in config by default.")
parser.add_argument('-b', '--base-url', metavar="URL",
        default='http://charmm-gui.org/',
        help="Web address to CHARMM-GUI (default: http://charmm-gui.org/)")
parser.add_argument('--copy', action='store_true',
        help="For tests on localhost, run solvent tests by cloning the project at the solvent test's branch point; save time, but cause errors if the request cache is corrupted")
parser.add_argument('--config', type=argparse.FileType('r'),
        default="config.yml", metavar="PATH",
        help="Path to configuration file (default: config.yml)")
args = parser.parse_args()

#read configuration
with args.config:
      CONFIG = yaml.load(args.config,  Loader=yaml.FullLoader)

BASE_URL = args.base_url
if 'BASE_URL' in CONFIG:
    BASE_URL = CONFIG['BASE_URL']
if 'USER' in CONFIG and 'PASS' in CONFIG:
    BASE_URL = BASE_URL.split('/')
    BASE_URL[2] = CONFIG['USER']+':'+CONFIG['PASS']+'@'+BASE_URL[2]
    BASE_URL = '/'.join(BASE_URL)
'localhost' in BASE_URL.lower()
# validate WWW_DIR as a directory
WWW_DIR = args.www_dir
if not 'WWW_DIR' in CONFIG:
    if 'localhost' in BASE_URL.lower():
        raise ValueError("Missing WWW_DIR from "+args.config)
else:
    WWW_DIR = CONFIG['WWW_DIR']

if WWW_DIR != None:
    if not os.path.exists(WWW_DIR):
        raise ValueError(WWW_DIR+" does not exist")
    elif not os.path.isdir(WWW_DIR):
        raise ValueError(WWW_DIR+" is not a directory")

with open('test_cases/'+args.test_name+'.yml') as fh:
    test_cases = yaml.load(fh, Loader=yaml.FullLoader)


base_cases = []
wait_cases = {}
for test_case in test_cases:
    if not 'solvator_tests' in test_case:
        base_cases.append(test_case)
    else:
        do_copy = args.copy
        cases = handle_solvator_tests(test_case, do_copy) 

        if 'localhost' in BASE_URL and do_copy:
            base_case = cases[0]
            base_cases.append(base_case)
            wait_cases[base_case['label']] = cases[1:]
        else:
            base_cases += cases

todo_queue = Queue()
done_queue = Queue()
processes = [FEPBrowserProcess(todo_queue, done_queue, www_dir=WWW_DIR, base_url=BASE_URL, pause=args.pause) for i in range(args.num_threads)]
#initialize browser processes
for p in processes:
    p.start() 

#put regular cases in the task queue
pending = 0
for case in base_cases:
    todo_queue.put(case)
    pending += 1

# main communication loop
while pending:
    result = done_queue.get()
    pending -=1
    if result[0] == 'SUCCESS':
        done_case, elapsed_time = result[1:]
        done_label = done_case['label']
        done_jobid = str(done_case['jobid'])
        log_success(done_case, elapsed_time)
    elif result[0] == 'FAILURE':
        done_case, step_num, elapsed_time = result[1:]
        log_failure(done_case, step_num, slapsed_time)
    elif result[0] == 'EXCEPTION':
        done_case, step_num, exc_info = result[1:]
        elapsed_time = -1
        log_exception(done_case, step_num, exc_info)
        print("Exception encountered for job ({})".format(done_case['jobid']))
        print(exc_info)
    elif result[0] == 'CONTINUE':
        pending += 1
        done_case = result[1]
        done_label = done_case['label']
        if done_label in wait_cases:
            done_jobid = str(done_case['jobid'])
            for num, wait_case in enumerate(wait_case[done_label]):
                if do_copy:
                    wait_case['jobid'] = done_jobid + '_' + str(num+1)
                    wait_case['resume_link'] = done_case['solvator_link']
                todo_queue.put(wait_case)
                pending += 1
            del wait_case[done_label]

#signal to stop
for p in processes:
    todo_queue.put('STOP')

# clean up
for p in processes:
    p.join()
