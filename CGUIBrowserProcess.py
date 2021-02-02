import code
import shutil
import os.path
import re
import requests
import time
import utils
import yaml
from multiprocessing import Process, Queue
from os.path import join as pjoin
from splinter import Browser
from splinter.exceptions import ElementDoesNotExist
from splinter.element_list import ElementList
from selenium.common.exceptions import TimeoutException

class CGUIBrowserProcess(Process):
    """Usage: subclass this class and write an init_system() method.

    For an example, see MCABrowserProcess.
    """
    CHARMM_ERROR = 'CHARMM was terminated abnormally.'
    PHP_NOTICE = "Notice:"
    PHP_WARNING = "Warning:"
    PHP_ERROR = "Error:"
    PHP_FATAL_ERROR = "Fatal error:"
    PHP_MESSAGES = PHP_NOTICE, PHP_WARNING, PHP_ERROR

    def __init__(self, todo_q, done_q, lock, **kwargs):
        """Setup Queues, browser settings, and delegate rest to multiprocessing.Process"""
        self.browser_type = kwargs.pop('browser_type', 'firefox')
        self.base_url = kwargs.pop('base_url', 'http://charmm-gui.org/')
        self.www_dir = kwargs.pop('www_dir', None)
        self.interactive = kwargs.pop('interactive', False)
        self.errors_only = kwargs.pop('errors_only', False)
        self.dry_run = kwargs.pop('dry_run', False)
        self.inter_q = kwargs.pop('inter_q', None)
        self.msg_q = kwargs.pop('msg_q', None)
        self.module = kwargs.pop('module', None)

        if not self.base_url.endswith('/'):
            self.base_url += '/'

        super().__init__(**kwargs)

        self.todo_q = todo_q
        self.done_q = done_q
        self.lock = lock

    def _click(self, elem, wait=None):
        elem.click()
        if wait:
            self.wait_text(wait)

    def check(self, check_elem_id, wait=None):
        elem = self.browser.find_by_id(check_elem_id)
        elem.check()
        if wait:
            self.wait_text(wait)

    def click(self, click_elem_id, wait=None):
        elem = self.browser.find_by_id(click_elem_id)
        self._click(elem, wait)

    def click_by_attrs(self, wait=None, **attrs):
        css_templ = "[{}='{}']"
        css_str = ''
        for attr, value in attrs.items():
            css_str += css_templ.format(attr, value)
        elem = self.browser.find_by_css(css_str)
        self._click(elem, wait)

    def click_by_text(self, text, wait=None):
        elem = self.browser.find_by_text(text)
        self._click(elem, wait)

    def click_by_value(self, value, wait=None):
        elem = self.browser.find_by_value(value)
        self._click(elem, wait)

    def copy_dir(self, ncopy, signal=True):
        """Make `ncopy` copies of the current project directory.

        Requirements:
            - self.test_case['jobid'] must be set
            - self.www_dir must be set (passed to __init__)
        All copies will be named as {jobid}_{copy_id}


        If the destination already exists, it is *not* overwritten.
        """
        if self.www_dir == None:
            raise ValueError("www_dir is not set")
        jobid = str(self.test_case['jobid'])
        src = pjoin(self.www_dir, jobid)
        for i in range(ncopy):
            i = str(i+1)
            dst = pjoin(self.www_dir, jobid+'_'+i)
            if os.path.exists(dst):
                print(self.name, "warning:", dst, "exists; skipping ...")
                continue
            shutil.copytree(src, dst)

        if signal:
            self.done_q.put(('CONTINUE', self.test_case))

    def download(self, saveas=None):
        test_case = self.test_case
        # don't attempt an impossible download
        if not 'jobid' in test_case:
            return

        jobid = test_case['jobid']

        if saveas:
            saveas = saveas + '.tgz'
        elif 'output' in test_case:
            saveas = test_case['output'] + '.tgz'
        else:
            saveas = utils.get_archive_name(jobid)

        url = "{url}?doc=input/download&jobid={jobid}".format(url=self.base_url, jobid=jobid)
        print("downloading %s to %s" % (url, saveas))

        user_agent = 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'
        headers = {'User-Agent': user_agent}
        user = ''
        password = ''
        if '@' in self.base_url:
            urlname = self.base_url.split('//')[1]
            idx = urlname.find('@')
            user, password = urlname[:idx].split(':')

        r = requests.get(url, headers=headers, auth=(user, password))
        open(saveas, "wb").write(r.content)
        fsize = float(os.stat(saveas).st_size) / (1024.0 * 1024.0)
        print("download complete, file size is %5.2f MB" % fsize)

        return saveas

    def eval(self, expr):
        """Evaluate a Python command that could refer to a method of self
        *OR* to a global function.
        """
        if expr == 'INTERACT' and self.interactive:
            self.interact(locals())
            return
        try:
            # isolate the function name
            fname = expr[:expr.index('(')]
        except ValueError:
            raise SyntaxError("invalid syntax: " + expr)
        if fname in dir(self):
            # make it a method call
            expr = 'self.'+expr
        return eval(expr)

    def first_visible(self, elems):
        if not isinstance(elems, ElementList):
            elems = ElementList([elems])

        return ElementList(filter(lambda elem: elem.visible, elems))

    def get_jobid(self):
        elems = self.browser.find_by_css('.jobid')
        if not elems:
            jobid = '-1'
        else:
            jobid = elems.text.split()[-1]

        self.test_case['jobid'] = jobid
        return jobid

    def go_next(self, test_text=None, alert=None, invalid_alert_text=None, next_button=None):
        if isinstance(alert, str):
            alert = alert.lower()
        assert alert in (None, 'accept', 'dismiss'), "unrecognized alert response: "+str(alert)

        if isinstance(next_button, (tuple, list)):
            finder = getattr('find_by_'+next_button[0])
            selector = next_button[1]
            button_elem = self.browser.find_by(finder, selector)
        elif getattr(next_button, 'click', None):
            button_elem = next_button
        elif callable(next_button):
            button_elem = next_button()
        else:
            button_elem = self.browser.find_by_id('nextBtn')
            if not button_elem:
                button_elem = self.browser.find_by_id("input_nav").find_by_tag("table")
            assert button_elem, "Can't find next button"

        while not button_elem.visible:
            time.sleep(1)
        button_elem.click()

        # some modules give warning dialogs that we don't care about
        if alert:
            prompt = self.browser.get_alert()

            if prompt:
                alert_text = prompt.text
                alert_invalid = invalid_alert_text and invalid_alert_text in alert_text
                # allow UnexpectedAlertPresentException to propagate if alert is invalid
                if not alert_invalid:
                    with prompt:
                        if alert == 'accept':
                            prompt.accept()
                        elif alert == 'dismiss':
                            prompt.dismiss()
                        else:
                            raise NotImplementedError
                        print(self.name, "{}ed alert with text: '{}'".format(alert, alert_text))

        if test_text:
            self.wait_text_multi([test_text, self.CHARMM_ERROR, self.PHP_ERROR])

    def handle_step(self, step_info):
        for elem_info in step_info['elems']:
            name = list(elem_info.keys())[0]
            value = str(elem_info[name])

            # potentially returns more than one element
            elem = self.browser.find_by_name(name)

            # infer action from HTML tag
            # fails if splinter/selenium changes their API
            input_type = elem._element.get_property('type')
            if input_type == "radio":
                elem = ElementList(filter(lambda e: e.value == str(value), elem))
                elem.check()
            elif input_type == "checkbox":
                if value:
                    elem.check()
            elif "select" in input_type:
                elem.select(value)
            else:
                elem.fill(value)

    def init_system(self, *args):
        raise NotImplementedError("This must be implemented in a child class")

    def interact(self, local={}):
        """Provide piped instructions to a new Python interpreter"""
        if not self.interactive:
            return
        test_case = getattr(self, 'test_case', {})
        jobid = test_case.get('jobid', -1)

        if not 'jobid' in local:
            local['jobid'] = jobid
        if not 'label' in local:
            local['label'] = test_case.get('label')

        self.done_q.put(('INTERACT', self.name, jobid))

        # handle automatic printing of last command's uncaptured return value
        print_last = "\n".join(["try:","{}","\tif _ != None: print(repr(_))","except:","\traise", ""])

        assign_pattern = re.compile('[^=\'"]+=[^=]')
        need_more = False
        shell = code.InteractiveInterpreter(locals=local)
        cmd_lines = []
        prefix = '_ = '
        for recipient, cmd in iter(self.inter_q.get, (self.name, 'STOP')):
            print(recipient, cmd)
            # prevent interpreting commands for someone else
            if recipient != self.name:
                self.inter_q.put((recipient, cmd))
                time.sleep(2)
                continue

            # obtain potentailly multi-line command
            cmd_lines.append(cmd)
            cmd = "\n".join(cmd_lines)
            n_lines = len(cmd_lines)
            assigned = (n_lines == 1) and assign_pattern.match(cmd)

            # check that prefix+cmd is valid Python code
            if n_lines == 1:
                use_prefix = True
                try:
                    code_obj = code.compile_command(prefix+cmd)
                    source = prefix+cmd
                except SyntaxError: # complain and continue normally
                    use_prefix = False
                    source = cmd
            else:
                source = cmd
                use_prefix = False

            # any SyntaxError at this point is user's fault
            try:
                code_obj = code.compile_command(source)
            except SyntaxError: # abort this command
                import sys, traceback
                exc_str = ''.join(traceback.format_exception(*sys.exc_info()))
                self.msg_q.put(exc_str)

                cmd_lines = []
                need_more = False
                continue

            need_more = (code_obj == None)

            # intelligently prints _, if doing so would not cause error
            if use_prefix and not need_more and not assigned:
                cmd_lines[0] = prefix + cmd_lines[0]
                cmd_lines = ["\t" + line for line in cmd_lines]
                cmd = "\n".join(cmd_lines)
                cmd = print_last.format(cmd)
                code_obj = code.compile_command(cmd)

            if not need_more:
                shell.runcode(code_obj)
                cmd_lines = []

            # tell parent we're ready for next input
            self.msg_q.put(need_more)

    def resume_step(self, jobid, project=None, step=None, link_no=None):
        """Uses Job Retriever to return to the given step.

        You must provide either:
            1) Project name AND step number
            2) Link number

        project: doc to return to
        step: step of doc to return to
        link_no: 0-indexed order of recovery link to return to
        """
        browser = self.browser
        url = self.base_url + "?doc=input/retriever"
        browser.visit(url)

        browser.fill('jobid', str(jobid))
        browser.find_by_css('input[type=submit]').click()

        success = 'Job found'
        failure = 'No job with that ID'
        found_text = self.wait_text_multi([success, failure])
        if found_text == failure:
            raise ValueError(failure)

        if link_no != None:
            assert isinstance(link_no, int), "link_no must be an integer"
            table = browser.find_by_css("#recovery_table tr:not(:first-child) td:nth-child(3)")
            table[link_no].click()
        else:
            raise NotImplementedError
            #assert project != None and step != None, "Missing args"

    def run(self):
        # if user set --dry-run, print test case and return
        if self.dry_run:
            self.run_dry()
        else:
            self.run_full()

    def run_dry(self):
        for test_case in iter(self.todo_q.get, 'STOP'):
            try:
                self.test_case = test_case
                print(yaml.dump([test_case]), end='')
                test_case['jobid'] = -1
                self.done_q.put(('SUCCESS', test_case, -1))
            except:
                import sys, traceback
                # give the full exception string
                exc_str = ''.join(traceback.format_exception(*sys.exc_info()))
                print(exc_str)
                if self.interactive:
                    self.interact(locals())
                self.done_q.put(('EXCEPTION', test_case, -1, exc_str))

    def run_full(self):
        with Browser(self.browser_type) as browser:
            self.browser = browser
            self.step = step_num = -1
            for test_case in iter(self.todo_q.get, 'STOP'):
                try:
                    self.test_case = test_case
                    print(self.name, "starting", test_case['label'])
                    start_time = time.time()
                    resume_link = 0
                    base = os.path.abspath(pjoin('files', test_case['base']))
                    self.base = base

                    resume = 'jobid' in test_case
                    if resume:
                        jobid = test_case['jobid']
                        resume_link = test_case['resume_link']
                        self.resume_step(jobid, link_no=resume_link)

                    # prevent Job ID race condition
                    with self.lock:
                        self.init_system(test_case, resume)

                    jobid = test_case['jobid']
                    print(self.name, "Job ID:", jobid)

                    steps = test_case['steps'][resume_link:]
                    failure = False
                    for step_num, step in enumerate(steps):
                        self.step = step_num
                        if 'wait_text' in step:
                            found_text = self.wait_text_multi([step['wait_text'], self.CHARMM_ERROR, self.PHP_FATAL_ERROR, self.PHP_ERROR])
                        if found_text != step['wait_text']:
                            failure = True
                            break

                        # Check for PHP errors, warnings, and notices
                        found_text = self.warn_if_text(self.PHP_MESSAGES)
                        if found_text and self.interactive:
                            if not self.errors_only or found_text in (self.PHP_ERROR, self.PHP_FATAL_ERROR):
                                self.interact(locals())

                        for prestep in step.get('presteps', []):
                            self.eval(prestep)
                        if 'elems' in step:
                            self.handle_step(step)
                        for poststep in step.get('poststeps', []):
                            self.eval(poststep)

                        if step_num < len(steps)-1:
                            alert = step.get('alert')
                            invalid_alert_text = step.get('invalid_alert_text')
                            self.go_next(alert=alert, invalid_alert_text=invalid_alert_text)

                    elapsed_time = time.time() - start_time

                    if self.interactive and not self.errors_only:
                        self.interact(locals())

                    # early failure?
                    if failure:
                        self.done_q.put(('FAILURE', test_case, step_num, elapsed_time))
                        failure = False
                        continue

                    # late failure?
                    final_wait_text = steps[-1]['wait_text']
                    found_text = self.wait_text_multi([final_wait_text, self.CHARMM_ERROR, self.PHP_ERROR, self.PHP_FATAL_ERROR])
                    if found_text != final_wait_text:
                        self.done_q.put(('FAILURE', test_case, step_num, elapsed_time))
                        failure = False
                    else:
                        # download project and optionally compare PSF
                        sys_archive = None
                        if not 'localhost' in self.base_url:
                            sys_archive = self.download()
                            sys_dir, ext = os.path.splitext(sys_archive)
                        else:
                            sys_dir = pjoin(self.www_dir, jobid)

                        validation_result = utils.validate_test_case(test_case, sys_dir,
                                sys_archive=sys_archive,
                                module=self.module,
                                elapsed_time=elapsed_time,
                                printer_name=self.name)

                        self.done_q.put(validation_result)

                except Exception as e:
                    import sys, traceback
                    # give the full exception string
                    exc_str = ''.join(traceback.format_exception(*sys.exc_info()))
                    print(exc_str)
                    if self.interactive:
                        self.interact(locals())
                    self.done_q.put(('EXCEPTION', test_case, step_num, exc_str))
                    if not 'localhost' in self.base_url: self.download()

    def stop(self, reason=None):
        """Message main thread to safely terminate all threads"""
        self.done_q.put(('STOP', self.name, reason))

        # wait to be killed by main thread
        while True:
            time.sleep(1)

    def switch_to_window(self, index, wait=60, poll_frequency=.5):
        """Waits up to `wait` seconds for a new window, then switches to it"""
        # warn if we are waiting for more than one window
        windows = self.browser.windows
        if index > len(windows):
            print("warning: waiting for window", index, "but only",
                  len(windows), "window(s) exist")

        # try once without time checking
        if len(windows) > index:
            windows.current = windows[index]
            self.browser.find_by_tag('body') # wait for page to have any html
            return True

        # poll periodically
        start_time = time.time()
        while time.time() - start_time < wait:
            if len(windows) > index:
                windows.current = windows[index]
                self.browser.find_by_tag('body')
                return True
            time.sleep(poll_frequency)

        # window took too long to load
        raise TimeoutException("Failed to get window " +str(index))

    def wait_exists(self, element_list, verbose=True):
        """Waits until the query used to create element_list finds at least one
        element and returns the new list

        By default, prints a warning every time bool(element_list) is False
        """
        # get a reference to the actual function, and save its arguments
        find_by_str = element_list.find_by
        finder = getattr(element_list, 'find_by_'+find_by_str)
        query = element_list.query

        tpl = "{} waiting for element by {}: '{}'"
        while not element_list:
            if verbose:
                print(tpl.format(self.name, find_by_str, query))
            element_list = self.browser.find_by(finder, query)

        return element_list

    def wait_script(self, script):
        print(self.name, "waiting for Javascript expression to evaluate to True")
        print(self.name, "JS expr:", script)
        while not self.browser.evaluate_script(script):
            time.sleep(1)

    def wait_text(self, text, wait_time=None):
        print(self.name, "waiting for text:", text)
        while True:
            if self.browser.is_text_present(text, wait_time=1):
                break

    def wait_text_multi(self, texts):
        print(self.name, "waiting for any text in:", texts)
        wait_time = 1
        while True:
            for text in texts:
                if self.browser.is_text_present(text, wait_time):
                    return text

    def wait_visible(self, element, wait=None, click=False):
        """Waits until an element is visible and optionally clicks it.

        If wait is not None, then after wait seconds, this function raises a
        TimeoutException. If click is True, then the element is clicked on
        success.

        Returns the element on success.
        """
        start_time = time.time()
        while wait == None or time.time() - start_time < wait:
            if element.visible:
                if click:
                    element.click()
                return
        raise TimeoutException

    def warn_if_text(self, text):
        msg = "Warning: {} ({}) found '{{}}' on step {}"
        if not 'jobid' in self.test_case:
            jobid = '-1'
        else:
            jobid = str(self.test_case['jobid'])
        msg = msg.format(self.name, jobid, self.step)
        if isinstance(text, list) or isinstance(text, tuple):
            texts = text
            for text in texts:
                if self.browser.is_text_present(text):
                    print(msg.format(text))
                    return text
        elif self.browser.is_text_present(text):
            print(msg.format(text))
            return text

    def uncheck(self, check_elem_id, wait=None):
        elem = self.browser.find_by_id(check_elem_id)
        elem.uncheck()
        if wait:
            self.wait_text(wait)
