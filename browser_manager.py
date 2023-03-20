"""This module handles most of the inter-process communciation aspects of
BrowserProcess by passing messages through multiprocessing.Queue
"""
# importing readline causes input buffering to be handled automatically
import readline

import sys
from multiprocessing import Queue
from time import sleep
from random import uniform

from logger import Logger

class BrowserManager:
    """A class to manage instances of BrowserProcess

    Usage:
        bm = BrowserManager(process_type, logfile, num_threads, **browser_kwargs)
        bm.start()
        bm.run()
        bm.stop()

    process_type should be an instance of a class that extends BrowserProcess
    """
    def __init__(self, BrowserProcess, logfile, num_threads=1, **browser_kwargs):
        """Initializes BrowserProcess instances

        args in browser_kwargs are passed directly to BrowserProcess.__init__
        """
        self.todo_queue = todo_queue = Queue()
        self.done_queue = done_queue = Queue()

        if browser_kwargs.get('interactive'):
            self.inter_queue = browser_kwargs['inter_q'] = Queue()
            self.msg_queue = browser_kwargs['msg_q'] = Queue()
        else:
            self.inter_queue = browser_kwargs['inter_q'] = None
            self.msg_queue = browser_kwargs['msg_q'] = None

        self.dry_run = browser_kwargs.get('dry_run')

        logfile = sys.stdout if self.dry_run else logfile
        self.logger = Logger(logfile, browser_kwargs['module'])

        self.processes = [BrowserProcess(todo_queue, done_queue, **browser_kwargs)
                for i in range(num_threads)]

    def run(self, base_cases, wait_cases=None):
        """Delegates tasks to BrowserProcess instances and logs results

        Blocks until the number of pending jobs is 0.

        Assumes all processes have been started, and DOES NOT join processes
        before returning. Call stop() to explicitly join.
        """
        wait_cases = wait_cases or {}

        # put regular cases in the task queue
        pending = 0
        for case in base_cases:
            self.todo_queue.put(case)
            pending += 1

        stopped = False # set to True after STOP sent to all threads
        # main communication loop
        while pending:
            result = self.done_queue.get()
            pending -= 1
            if result[0] in ('SUCCESS', 'VALID', 'INVALID', 'FAILURE', 'EXCEPTION'):
                self.logger.log_result(result)
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
                    self.inter_queue.put((partner, cmd))
                    if cmd == 'STOP':
                        break
                    need_more = self.msg_queue.get()
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
                    for _base_case, wait_case in enumerate(wait_cases[done_label]):
                        self.todo_queue.put(wait_case)
                        pending += 1
                    del wait_cases[done_label]
            elif result[0] == 'STOP':
                for proc in self.processes:
                    proc.terminate()

                for proc in self.processes:
                    proc.join()

                print('Processing has been stopped by', result[1], 'for the following reason:')
                print('\t',result[2])
                sys.exit(2)
            else:
                print('Warning: got unknown result:', result)

            if not stopped and not wait_cases:
                for proc in self.processes:
                    self.todo_queue.put('STOP')
                stopped = True

    def start(self):
        """Calls start() method of all processes"""
        # initialize browser processes
        for proc in self.processes:
            proc.start()

    def stop(self):
        """Calls join() method of all processes"""
        # clean up
        for proc in self.processes:
            proc.join()
