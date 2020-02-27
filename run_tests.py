#!/usr/bin/env python3

import copy
import os
import shutil
import sys
import yaml
from multiprocessing import Queue
from os.path import join as pjoin

#from AsyncResultWaiter import AsyncResultWaiter
from MCABrowserProcess import MCABrowserProcess

LOGFILE = 'results.log'
WWW_DIR = '/Users/nathan/multicomp/www'

def log_exception(case_info, step_num, exc_info):
    templ = 'Job "{}" ({}) encountered an exception on step {}:\n{}\n'
    if not 'jobid' in case_info:
        case_info['jobid'] = '-1'
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

def handle_solvent_tests(test_case):
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
        raise ValueError("Missing 'solvent_tests'")
    solvent_tests = test_case['solvent_tests']

    # find the step containing SOLVENT_TEST_PLACEHOLDER
    placeholder = 'SOLVENT_TEST_PLACEHOLDER'
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
        raise ValueError("Missing '"+placeholder+"'")

    # action to do to *uncheck* an option
    test_map = {
        'water': "click('water_checked')",
        'ions': "click('ion_checked')",
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

    copy_action = "copy_dir(ncopy=3)"
    cases[0]['steps'][step_num][check_list].insert(index, copy_action)

    return cases

# psf name: component type
with open('test_cases/basic.yml') as fh:
    test_cases = yaml.load(fh, Loader=yaml.FullLoader)

# rather than giving a separate test case for each variation of solvent
# settings, the 'solvent_tests' variable indicates which variants should be
# tested
base_cases = []
wait_cases = {}
for test_case in test_cases:
    if not 'solvent_tests' in test_case:
        base_cases.append(test_case)
    else:
        cases = handle_solvent_tests(test_case)
        base_case = cases[0]
        base_cases.append(base_case)
        wait_cases[base_case['label']] = cases[1:]

cap = 3
todo_queue = Queue()
done_queue = Queue()
processes = [MCABrowserProcess(todo_queue, done_queue, www_dir=WWW_DIR) for i in range(cap)]

# initialize browser processes
for p in processes:
    p.start()

# main communication loop
pending = 0
for case in base_cases:
    todo_queue.put(case)
    pending += 1

while pending:
    result = done_queue.get()
    pending -= 1
    if result[0] == 'SUCCESS':
        done_case, elapsed_time = result[1:]
        done_label = done_case['label']
        done_jobid = str(done_case['jobid'])
        log_success(done_case, elapsed_time)
    elif result[0] == 'FAILURE':
        done_case, step_num, elapsed_time = result[1:]
        log_failure(test_case, step_num, elapsed_time)
    elif result[0] == 'EXCEPTION':
        done_case, step_num, exc_info = result[1:]
        elapsed_time = -1 # don't report time for exceptions
        log_exception(test_case, step_num, exc_info)
        print("Exception encountered for job ({})".format(test_case['jobid']))
        print(exc_info)
    elif result[0] == 'CONTINUE':
        pending += 1
        done_case = result[1]
        done_label = done_case['label']
        # are any tasks waiting on this one?
        if done_label in wait_cases:
            done_jobid = str(done_case['jobid'])
            for num, wait_case in enumerate(wait_cases[done_label]):
                wait_case['jobid'] = done_jobid+'_'+str(num+1)
                wait_case['resume_link'] = done_case['solvent_link']
                todo_queue.put(wait_case)
                pending += 1
            del wait_cases[done_label]

# signal to stop
for p in processes:
    todo_queue.put('STOP')

# clean up
for p in processes:
    p.join()
