#!/usr/bin/env python3
"""Command-line interface to autosave PSF references from previous tests"""
import argparse
import os
import shutil
import sys

import logger
import utils

def directory(path, errtype=argparse.ArgumentTypeError):
    """Pretends to be a casting function, but really just checks that a
    string is a path to a directory"""
    errmsg = ''
    if not os.path.exists(path):
        errmsg = "'{}' does not exist"
    if not os.path.isdir(path):
        errmsg = "'{}' is not a directory"
    if errmsg:
        raise errtype(errmsg.format(path))
    return path

parser = argparse.ArgumentParser()
parser.add_argument('--ref', nargs=1, metavar='filename',
        default=['step1_pdbreader.psf'],
        help="name of source reference file (default: step1_pdbreader.psf")
parser.add_argument('-o', '--output', type=directory,
        help="output directory in which to place reference files")
parser.add_argument('results_file', nargs='?',
        type=argparse.FileType('r'), default='results.log',
        help="log file containing testing results (default: 'results.log')")

args = parser.parse_args()
results = None
with args.results_file as fh:
    results = logger.parse_logfile(args.results_file)

if results:
    for module, cases in results.items():
        for label, case in cases.items():
            jobid = case['jobid']

            ref_dir = 'charmm-gui-'+jobid
            ref_archive = ref_dir+'.tgz'
            if os.path.exists(ref_dir):
                if not os.path.isdir(ref_dir):
                    ERRMSG = "Warning: '{}' exists but is not a directory; skipping"
                    print(ERRMSG.format(ref_dir), file=sys.stderr)
                    continue
            elif os.path.exists(ref_archive):
                shutil.unpack_archive(ref_archive)
            else:
                ERRMSG = "Warning: couldn't find '{}'; skipping"
                print(ERRMSG.format(ref_archive), file=sys.stderr)
                continue

            # allow reference naming scheme to be modified in one place
            ref_filename = utils.ref_from_label(label)

            src = os.path.join(ref_dir, args.ref[0])
            if args.output:
                dest = os.path.join(args.output, ref_filename)
            else:
                dest = os.path.join('files', 'references', module, ref_filename)

            if not os.path.exists(src):
                print("Skipping nonexistent file:", src)
                continue

            print('copying', src, '->', dest)
            shutil.copy(src, dest)
