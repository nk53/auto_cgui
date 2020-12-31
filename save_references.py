#!/usr/bin/env python3
import argparse
import os
import re
import shutil
import sys
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
        help="name of source reference file (default: 'step1_pdbreader.psf'")
parser.add_argument('results_file', nargs='?',
        type=argparse.FileType('r'), default='results.log',
        help="log file containing testing results (default: 'results.log')")
parser.add_argument('dest', type=directory,
        help="directory to place reference files")

args = parser.parse_args()

with args.results_file as fh:
    for line in fh:
        line = line.lower()

        if not line.startswith('job'):
            continue

        line = line.strip()
        if not 'success' in line:
            print("Skipping failed test case:", line, file=sys.stderr)
            continue

        jobid, label = utils.parse_jobid_label(line)

        ref_dir = 'charmm-gui-'+jobid
        ref_archive = ref_dir+'.tgz'
        if os.path.exists(ref_dir):
            if not os.path.isdir(ref_dir):
                errmsg = "Warning: '{}' exists but is not a directory; skipping"
                print(errmsg.format(ref_dir), file=sys.stderr)
                continue
        elif os.path.exists(ref_archive):
            shutil.unpack_archive(ref_archive)
        else:
            errmsg = "Warning: couldn't find '{}'; skipping"
            print(errmsg.format(ref_archive), file=sys.stderr)
            continue

        # allow reference naming scheme to be modified in one place
        ref_filename = utils.ref_from_label(label)

        src = os.path.join(ref_dir, args.ref[0])
        dest = os.path.join(args.dest, ref_filename)

        print('copying', src, '->', dest)
        shutil.copy(src, dest)

