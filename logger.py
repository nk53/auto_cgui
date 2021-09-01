"""Central interface for message logging"""
import os
import re
import utils

class Logger:
    """Writes log information in a single-threaded context.

    N.B.: This class is NOT thread-safe.
    """
    def __init__(self, logfile, module=''):
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
        with open(self.logfile, 'a') as file_obj:
            file_obj.write(msg)

    def log_exception(self, case_info, step_num, exc_info):
        """Writes test cases resulting in a Python exception to logfile"""
        templ = 'Job "{}" ({}){} encountered an exception on step {}:\n{}\n'
        if not 'jobid' in case_info:
            case_info['jobid'] = '-1'
        if 'resume_link' in case_info and step_num == 0:
            step_num = case_info['resume_link']
        jobid = case_info['jobid']
        label = case_info['label']
        self.write(templ.format(label, jobid, self.module, step_num, exc_info))

    def log_failure(self, case_info, step, elapsed_time=-1.):
        """Writes test cases resulting in CHARMM error to logfile"""
        templ = 'Job "{}" ({}){} failed on step {} after {:.2f} seconds\n'
        if not 'jobid' in case_info:
            case_info['jobid'] = '-1'
        jobid = case_info['jobid']
        label = case_info['label']
        self.write(templ.format(label, jobid, self.module, step, elapsed_time))

    def log_success(self, case_info, elapsed_time=-1., ran_validation=False):
        """Writes test cases that reach final page without error to logfile"""
        if ran_validation:
            ran_validation = ' and passed validation'
        else:
            ran_validation = ''

        templ = 'Job "{}" ({}){} finished successfully after {:.2f} seconds{}\n'
        jobid = case_info['jobid']
        label = case_info['label']
        self.write(templ.format(label, jobid, self.module, elapsed_time, ran_validation))

    def log_notice(self, case_info, step, elapsed_time=-1.):
        templ = 'Job "{}" ({}){} encountered PHP message on step {}:\n{}\n'

    def log_invalid(self, case_info, elapsed_time=-1., reason=''):
        """Writes test cases that finish, but failed validation to logfile"""
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

def parse_logfile(logfile):
    regexes = ( # varname, regex
        ('jobid', re.compile(r'Job.*\((-?\d+)\)')),
        ('label', re.compile(r'Job.*"([^"]+)"')),
        ('module', re.compile(r"Job.*'([^']+)'")),
        ('step', re.compile(r"Job.*on step (-?\d+)")),
    )

    sys_info = {}
    notices = {}

    if isinstance(logfile, str):
        logfile = open(logfile)

    with logfile as results_file:
        for line in results_file:
            jobinfo = {}
            for key, regex in regexes:
                result = regex.search(line)
                jobinfo[key] = result.group(1) if result else None

            if jobinfo['jobid'] is None:
                continue

            for sentinel in ('exception', 'failed', 'invalid', 'success'):
                if sentinel in line:
                    jobinfo['result'] = sentinel
                    break

            module = jobinfo.pop('module')
            jobid = jobinfo['jobid']
            if 'encountered PHP message' in line:
                notices.setdefault(jobid, [])
                notices[jobid].append({'step': jobinfo['step']})
            else:
                label = jobinfo.pop('label')

                archive = utils.get_archive_name(jobid)
                if os.path.exists(archive):
                    jobinfo['archive'] = archive

                jobinfo['dirname'] = utils.get_sys_dirname(jobid)
                jobinfo['notices'] = notices.pop(jobid, [])

                sys_info.setdefault(module, {})
                if prev_job := sys_info[module].get(label, None):
                    jobinfo['attempts'] = prev_job.get('attempts', 1) + 1
                sys_info[module][label] = jobinfo

    return sys_info
