#!/usr/bin/env python3
import readline
import sys
import utils
from multiprocessing import Queue
from time import sleep

class Logger:
    def __init__(self, logfile, module=''):
        """Writes log information in a single-threaded context.

        N.B.: This class is NOT thread-safe.
        """
        self.logfile = logfile
        self.module = module and " in module '{}'".format(module)

        if getattr(logfile, 'write', None):
            self.write = self.write_opened
        else:
            self.write = self.write_append_filename

    def write_opened(self, msg):
        """Write to an already-opened stream"""
        self.logfile.write(msg)

    def write_append_filename(self, msg):
        """Get a new file handle and append to it"""
        with open(self.logfile, 'a') as fh:
            fh.write(msg)

    def log_exception(self, case_info, step_num, exc_info):
        templ = 'Job "{}" ({}){} encountered an exception on step {}:\n{}\n'
        if not 'jobid' in case_info:
            case_info['jobid'] = '-1'
        jobid = case_info['jobid']
        label = case_info['label']
        self.write(templ.format(label, jobid, self.module, step_num, exc_info))

    def log_failure(self, case_info, step, elapsed_time=-1.):
        templ = 'Job "{}" ({}){} failed on step {} after {:.2f} seconds\n'
        if not 'jobid' in case_info:
            case_info['jobid'] = '-1'
        jobid = case_info['jobid']
        label = case_info['label']
        self.write(templ.format(label, jobid, self.module, step, elapsed_time))

    def log_success(self, case_info, elapsed_time=-1., ran_validation=False):
        if ran_validation:
            ran_validation = ' and passed validation'
        else:
            ran_validation = ''

        templ = 'Job "{}" ({}){} finished successfully after {:.2f} seconds{}\n'
        jobid = case_info['jobid']
        label = case_info['label']
        self.write(templ.format(label, jobid, self.module, elapsed_time, ran_validation))

    def log_invalid(self, case_info, elapsed_time=-1., reason=''):
        templ = 'Job "{}" ({}){} finished after {:.2f} seconds, but was invalid:\n{}\n'
        if not 'jobid' in case_info:
            case_info['jobid'] = '-1'
        jobid = case_info['jobid']
        label = case_info['label']
        self.write(templ.format(label, jobid, self.module, elapsed_time, reason))

    def log_result(self, result):
        """Infers result type and logs it

        `result` should be a sequence where result[0] is one of these strings:
            SUCCESS, VALID, INVALID, FAILURE, EXCEPTION
        and where result[1:] are the arguments to pass to a log_* function
        """
        if result[0] in ('SUCCESS', 'VALID'):
            done_case, elapsed_time = result[1:]
            ran_validation = result[0] == 'VALID'
            self.log_success(done_case, elapsed_time, ran_validation)
        elif result[0] == 'INVALID':
            done_case, elapsed_time, reason = result[1:]
            self.log_invalid(done_case, elapsed_time, reason)
        elif result[0] == 'FAILURE':
            done_case, step_num, elapsed_time = result[1:]
            self.log_failure(done_case, step_num, elapsed_time)
        elif result[0] == 'EXCEPTION':
            done_case, step_num, exc_info = result[1:]
            elapsed_time = -1 # don't report time for exceptions
            self.log_exception(done_case, step_num, exc_info)
            print("Exception encountered for job ({})".format(done_case['jobid']))
            print(exc_info)
        else:
            print('Warning: got unknown result:', result)

