#!/usr/bin/env python3
"""Command-line interface to testing suite"""
# standard library imports
import argparse
import os
import sys

# auto_cgui imports
from logger import parse_logfile
from utils import warn, read_yaml

# module alias (case-insensitive): base filename
cgui_modules = read_yaml('modules.yml')

parser = argparse.ArgumentParser(
        description="Lookup most recent results for each test run")
parser.add_argument('-l', '--logfile', default='results.log')
parser.add_argument('-m', '--modules', nargs='+')
parser.add_argument('-s', '--success', action='store_true',
        help="Include successes in results (default: include all)")
parser.add_argument('-i', '--invalid', action='store_true',
        help="Include finished, but invalid results (default: include all)")
parser.add_argument('-f', '--failed', action='store_true',
        help="Include failures in results (default: include all)")
parser.add_argument('-e', '--exception', action='store_true',
        help="Include exceptions in results (default: include all)")
parser.add_argument('-a', '--attempts', action='store_true',
        help="Include jobs with more than one attempt")

args = parser.parse_args()
modules = args.modules if args.modules else ['all']

all_types = 'success', 'invalid', 'failed', 'exception'
n_active = sum(map(lambda flag: getattr(args, flag), all_types))

print_result = False
if not n_active:
    for flag in all_types:
        setattr(args, flag, True)
    print_result = True
elif n_active != 1:
    print_result = True

# indicate whether logfile already exists
LOGFILE = args.logfile
if not os.path.exists(LOGFILE):
    warn(f"Error: No such file: '{LOGFILE}'")
    sys.exit(1)

sys_info = parse_logfile(LOGFILE)
for module, jobs in sys_info.items():
    if modules != ['all'] and module not in modules:
        continue
    printed_module = False
    for job, info in jobs.items():
        if args.attempts and not info.get('attempts', False):
            continue
        if getattr(args, info.get('result', 'exception'), False):
            if not printed_module:
                print(module)
                printed_module = True
            print(' '*4 + job)
            for key, value in info.items():
                if key == 'dirname':
                    continue
                if key == 'result' and not print_result:
                    continue
                if value or value == 0:
                    print(' '*8 + f'{key}: {value}')
