#!/usr/bin/env python3

import time
import os
import sys
import urllib.request, urllib.parse, urllib.error
import subprocess
import yaml
from splinter import Browser
from splinter.exceptions import ElementDoesNotExist
from os.path import join as pjoin

LOGFILE = 'results.log'

def log_failure(case_info, jobid, step, start_time):
    templ = 'Job "{}" ({}) failed on step {} after {:.2f} seconds\n'
    run_time = time.time() - start_time
    with open(LOGFILE, 'a') as fh:
        label = case_info['label']
        fh.write(templ.format(label, jobid, step, run_time))

def log_success(case_info, jobid, start_time):
    templ = 'Job "{}" ({}) finished successfully after {:.2f} seconds\n'
    run_time = time.time() - start_time
    with open(LOGFILE, 'a') as fh:
        label = case_info['label']
        fh.write(templ.format(label, jobid, run_time))

def set_component_density():
    global components
    for comp_name, comp_info in components.items():
        if not 'density' in comp_info:
            continue
        row = find_comp_row(comp_name, 'solvent options')
        comp_type = comp_info['type']
        comp_type_elem = row.find_by_css("[id^=solv_density]")
        comp_type_elem.fill(comp_info['density'])

def select_components():
    global components
    for comp_name, comp_info in components.items():
        row = find_comp_row(comp_name, 'molpacking')
        comp_type = comp_info['type']
        comp_type_elem = row.find_by_css("[name^=type_component")
        comp_type_elem.select(comp_type)

        # can't set number of some component types in this step
        if comp_type in ['solvent', 'ion']:
            continue

        # changing component type might change row element
        row = find_comp_row(comp_name, 'molpacking')

        num_comps = row.find_by_css("[name^=num_components")
        num_comps.fill(comp_info['count'])

def go_next(test_text=None):
    global browser
    browser.find_by_id('nextBtn').click()
    if test_text:
        wait_text(test_text)

def handle_step(step_info):
    global browser
    for elem in step_info['elems']:
        name = list(elem.keys())[0]
        value = elem[name]
        browser.fill(name, value)

def click(click_elem_id, wait_elem_text=None):
    global browser
    browser.find_by_id(click_elem_id).click()
    if wait_elem_text:
        wait_text(wait_elem_text)

def click_by_attrs(wait_elem_text=None, **attrs):
    global browser
    css_templ = "[{}='{}']"
    css_str = ''
    for attr, value in attrs.items():
        css_str += css_templ.format(attr, value)
    browser.find_by_css(css_str).click()
    if wait_elem_text:
        wait_text(wait_elem_text)

def click_lipid_category(category):
    global browser
    browser.find_by_text(category).find_by_xpath('../img').first.click()

def wait_text(text):
    global browser
    print("Waiting for:", text)
    while not browser.is_text_present(text, wait_time=1):
        pass

def wait_text_multi(texts):
    global browser
    wait_time = None
    while True:
        for text in texts:
            if browser.is_text_present(text, wait_time):
                return
            wait_time = None
        wait_time = 1

def resume_step(jobid, project=None, step=None, link_no=None):
    global browser
    """Uses Job Retriever to return to the given step.

    You must provide either:
        1) Project name AND step number
        2) Link number

    project: doc to return to
    step: step of doc to return to
    link_no: 0-indexed order of recovery link to return to
    """
    url = "http://localhost:8888/?doc=input/retriever"
    browser.visit(url)

    browser.fill('jobid', str(jobid))
    browser.find_by_css('input[type=submit]').click()

    success = 'Job found'
    failure = 'No job with that ID'
    wait_text_multi([success, failure])
    if browser.is_text_present(failure):
        raise ValueError(failure)

    if link_no != None:
        assert isinstance(link_no, int), "link_no must be an integer"
        browser.find_by_css("#recovery_table tr:not(:first-child) td:nth-child(3)")[link_no].click()
    else:
        assert project != None and step != None, "Missing args"
        raise NotImplementedError

def find_comp_row(comp_name, step):
    global browser
    """Returns the row element page corresponding to the given uploaded
    component basename"""
    selectors = {
        'molpacking': lambda: browser.find_by_css(".component_list table tr:not(:first-child) td:nth-child(2)"),
        'solvent options': lambda: browser.find_by_text("Component ID").find_by_xpath('../..').find_by_css("tr:not(:first-child) td:nth-child(2)")
    }
    rows = selectors[step]()
    found = False
    for row in rows:
        if row.text == comp_name:
            found = True
            break
    if not found:
        raise ElementDoesNotExist("Could not find component: "+comp_name)
    comp_row = row.find_by_xpath('..')
    return comp_row

# psf name: component type
with open('test_cases/basic.yml') as fh:
    test_cases = yaml.load(fh, Loader=yaml.FullLoader)

# load MCA front page
browser = Browser('chrome')
for test_case in test_cases:
    start_time = time.time()
    components = test_case['components']
    resume_link = 0
    base = os.path.abspath(test_case['base'])
    if 'jobid' in test_case:
        jobid = test_case['jobid']
        resume_link = test_case['resume_link']
        resume_step(jobid, link_no=resume_link)
    else:
        url = "http://localhost:8888/?doc=input/multicomp"
        browser.visit(url)

        # attach files for this test case
        for comp_name in components.keys():
            comp_name = pjoin(base, comp_name)
            browser.attach_file("files[]", comp_name+'.crd')
            browser.attach_file("files[]", comp_name+'.psf')

        go_next(test_case['steps'][0]['wait_text'])

        jobid = browser.find_by_css(".jobid").first.text.split()[-1]
        print("Job ID:", jobid)

    steps = test_case['steps'][resume_link:]
    for step_num, step in enumerate(steps):
        if browser.is_text_present('CHARMM was terminated abnormally.'):
            log_failure(test_case, jobid, step_num, start_time)
        if 'wait_text' in step:
            wait_text(step['wait_text'])
        if 'presteps' in step:
            for prestep in step['presteps']:
                eval(prestep)
        if 'elems' in step:
            handle_step(step)
        if 'poststeps' in step:
            for poststep in step['poststeps']:
                eval(poststep)
        go_next()

    wait_text(test_case['final_wait_text'])
    log_success(test_case, jobid, start_time)

browser.quit()
