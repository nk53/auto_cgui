"""Base functionality for all CHARMM-GUI module interaction"""
# standard library imports
import code
import shutil
import os.path
import re
import time
import traceback
import signal
import sys
from os.path import join as pjoin
from multiprocessing import Process

# third-party dependencies
import requests
import yaml
from splinter import Browser
from splinter.element_list import ElementList
from splinter.exceptions import ElementDoesNotExist
from selenium.common.exceptions import UnexpectedAlertPresentException, TimeoutException

# auto_cgui imports
import utils

class CGUIBrowserProcess(Process):
    """Usage: subclass this class and write an init_system() method.

    For an example, see MCABrowserProcess or PDBBrowserProcess
    """
    CHARMM_ERROR = 'CHARMM was terminated abnormally.'
    PHP_NOTICE = "Notice:"
    PHP_WARNING = "Warning:"
    PHP_ERROR = "Error:"
    PHP_FATAL_ERROR = "Fatal error:"
    PHP_MESSAGES = PHP_NOTICE, PHP_WARNING, PHP_ERROR

    def __init__(self, todo_q, done_q, **kwargs):
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
        self.credentials = kwargs.pop('credentials', None)

        if not self.base_url.endswith('/'):
            self.base_url += '/'

        super().__init__(**kwargs)

        self.todo_q = todo_q
        self.done_q = done_q

    def _click(self, elem, wait=None, alert=None):
        """Implements common click-and-wait procedure"""
        elem.click()
        if wait:
            self.wait_text(wait, alert=alert)

    def check(self, check_elem_id, wait=None, alert=None):
        """Checks a checkbox and optionally waits for text to appear

        Note that check() is not the same as click(): check() will never
        uncheck a checkbox, whereas click() can if it was already checked.
        """
        elem = self.browser.find_by_id(check_elem_id)
        elem.check()
        if wait:
            self.wait_text(wait, alert=alert)

    def click(self, click_elem_id, wait=None, alert=None):
        """Clicks an element and optionally waits for text to appear"""
        elem = self.browser.find_by_id(click_elem_id)
        self._click(elem, wait, alert=alert)

    def click_by_attrs(self, wait=None, alert=None, **attrs):
        """Finds an element by attributes and clicks it

        Optionally waits for text to appear after clicking
        """
        css_templ = "[{}='{}']"
        css_str = ''
        for attr, value in attrs.items():
            if attr.startswith('_'):
                attr = attr[1:]
            attr = attr.replace('_', '-')
            css_str += css_templ.format(attr, value)
        elem = self.browser.find_by_css(css_str)
        self._click(elem, wait, alert=alert)

    def click_by_text(self, text, wait=None, alert=None):
        """Finds an element by its innerHTML and clicks it

        `text` must be an exact match for the inner text of the element to
        find. Optionally waits for other text to appear.
        """
        elem = self.browser.find_by_text(text)
        self._click(elem, wait, alert=alert)

    def click_by_value(self, value, wait=None, alert=None):
        """Finds an element by its DOM value and clicks it

        Optionally waits for text to appear after clicking
        """
        elem = self.browser.find_by_value(value)
        self._click(elem, wait, alert=alert)

    def copy_dir(self, ncopy, send_continue=True):
        """Make `ncopy` copies of the current project directory.

        Requirements:
            - self.test_case['jobid'] must be set
            - self.www_dir must be set (passed to __init__)
        All copies will be named as {jobid}_{copy_id}


        If the destination already exists, it is *not* overwritten.
        """
        if self.www_dir is None:
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

        if send_continue:
            self.done_q.put(('CONTINUE', self.test_case))

    def download(self, saveas=None):
        """Downloads the user's system in .tgz format"""
        test_case = self.test_case
        # don't attempt an impossible download
        if not 'jobid' in test_case:
            return None

        jobid = test_case['jobid']
        if str(jobid) == '-1':
            return # nothing to download

        if saveas:
            saveas = saveas + '.tgz'
        elif 'output' in test_case:
            saveas = test_case['output'] + '.tgz'
        else:
            saveas = utils.get_archive_name(jobid)

        if os.path.exists(saveas):
            print(saveas, 'already exists, overwriting')
            os.unlink(saveas)

        url = "{url}?doc=input/download&jobid={jobid}".format(url=self.base_url, jobid=jobid)
        print("downloading %s to %s" % (url, saveas))

        user_agent = 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'
        headers = {'User-Agent': user_agent}
        session = {}

        for cookie in self.browser.driver.get_cookies():
            if cookie['name'] == 'PHPSESSID':
                session['PHPSESSID'] = cookie['value']
                break

        user = ''
        password = ''
        if '@' in self.base_url:
            urlname = self.base_url.split('//')[1]
            idx = urlname.find('@')
            user, password = urlname[:idx].split(':')

        req = requests.get(url, headers=headers, auth=(user, password), cookies=session)
        with open(saveas, 'wb') as download_file:
            download_file.write(req.content)
        fsize = float(os.stat(saveas).st_size) / (1024.0 * 1024.0)
        print("download complete, file size is %5.2f MB" % fsize)

        return saveas

    def eval(self, expr):
        """Evaluate a Python command that could refer to a method of self
        *OR* to a global function.
        """
        if expr == 'INTERACT' and self.interactive:
            self.interact(locals())
            return None
        try:
            # isolate the function name
            fname = expr[:expr.index('(')]
        except ValueError as exc:
            raise SyntaxError("invalid syntax: " + expr) from exc
        if fname in dir(self):
            # make it a method call
            expr = 'self.'+expr
        return eval(expr)

    @staticmethod
    def first_visible(elems):
        """Returns the first visible in elems, according to splinter

        Note that splinter may be wrong about element visibility
        """
        if not isinstance(elems, ElementList):
            elems = ElementList([elems])

        return ElementList(filter(lambda elem: elem.visible, elems))

    def get_jobid(self):
        """Returns the user's job ID"""
        elems = self.browser.find_by_css('.jobid')
        if not elems:
            jobid = '-1'
        else:
            jobid = elems.text.split()[-1]

        self.test_case['jobid'] = jobid
        return jobid

    def go_next(self, test_text=None, alert=None, invalid_alert_text=None, next_button=None):
        """Proceeds to the next step by clicking the Next button

        Parameters
        ==========
            test_text           str  text to wait for after clicking Next
            alert               str  either 'accept' or 'dismiss'
            invalid_alert_text  str  alert text indicating a serious error
            next_button         obj  described below

        Any alert will raise splinter.UnexpectedAlertPresentException by
        default, unless alert is passed. The value of `alert` indicates
        whether to accept (click OK) or dismiss (click Cancel) the alert.
        The two options are equivalent if the alert has only one button
        (usually "OK"). Use this ONLY if you expect the user input to cause
        a warning message that is not an actual error.

        If only some alert messages indicate that a serious error has
        occurred, then invalid_alert_text should be passed. If this
        substring is found in the alert's text, it will cause a
        splinter.UnexpectedAlertPresentException to be raised.

        If more than one next button is present on the page, it should be
        provided as `next_button`, which can be any of:
            - tuple of strings: (finder, selector)
            - a splinter.driver.ElementAPI or other clickable object
            - a function that clicks the desired element

        `finder` is the name of a splinter function that finds an element,
        but not including the "find_by_" part. `selector` is the argument
        that would be passed to that function. E.g. to find an element by
        name using splinter.browser.find_by_name(element_name):
            go_next(next_button=('name', element_name))
        """
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
        """Fills all form values in this step's 'elems' dict.

        Each element must be provided as {elem_name: elem_value}. This
        function can handle textbox, radio, checkbox, and select options.

        The default action if an element is not one of the above is to use:
            splinter.driver.find_by_name(elem_name).fill(elem_value)
        """
        for elem_info in step_info['elems']:
            name = list(elem_info.keys())[0]
            value = str(elem_info[name])
            utils.set_form_value(self.browser, name, value)

    def init_system(self, **kwargs):
        """This method handles a module's front page, which is usually
        substantially different from the other module steps.

        Any non-abstract descendant of CGUIBrowserProcess that has a front
        page should define this method. E.g., InputBrowserProcess does NOT
        define this method, because Input Generator does not have a front
        page.

        Parameters
        ==========
            resume  bool  whether this job is resumed via job retriever
        """
        raise NotImplementedError("This must be implemented in a child class")

    def interact(self, local=None):
        """Provide piped instructions to a new Python interpreter

        Expected usage:
            self.interact(locals())

        Alternatively, put INTERACT as a prestep/poststep in a test case to
        run interaction at that step.

        This is a debugging helper function that behaves like a Python
        interpreter as much as possible. If you are using multiple threads,
        then interaction occurs one thread at a time. Dismiss a thread with
        quit() or EOF (Ctrl-d).

        To stop all processes and exit testing, use Ctrl-c.

        This method is called automatically in the following situations:
            - A Python error occurs
            - A PHP or CHARMM error message is observed on the page
            - A PHP "notice" or "warning" message is observed and the -e
              flag is NOT passed to run_tests.py.

        If you are testing a CHARMM-GUI module and you see any PHP error,
        warning, or notice message, YOU SHOULD INFORM THE MODULE'S DEVELOPER
        so that the message is fixed, as this usually indicates bad PHP
        design.
        """
        local = local or {}
        local.setdefault('tb', traceback)
        if not self.interactive:
            warn_msg = os.linesep.join(
                ["WARNING: called interact() but no inter_q was set up.",
                 "Did you forget to use the -i flag?"])
            print(self.name, warn_msg)
            return

        test_case = getattr(self, 'test_case', {})
        jobid = test_case.get('jobid', -1)

        if 'jobid' not in local:
            local['jobid'] = jobid
        if 'label' not in local:
            local['label'] = test_case.get('label')

        self.done_q.put(('INTERACT', self.name, jobid))

        # handle automatic printing of last command's uncaptured return value
        print_last = "\n".join([ # run code in try/except block
            "try:", "{}", "\tif _ != None: print(repr(_))",
            "except:", "\traise", ""
        ])

        assign_pattern = re.compile('[^=\'"]+=[^=]')
        need_more = False
        shell = code.InteractiveInterpreter(locals=local)
        cmd_lines = []
        prefix = '_ = '
        for recipient, cmd in iter(self.inter_q.get, (self.name, 'STOP')):
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
                exc_str = ''.join(traceback.format_exception(*sys.exc_info()))
                self.msg_q.put(exc_str)

                cmd_lines = []
                need_more = False
                continue

            need_more = (code_obj is None)

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

        if link_no is not None:
            assert isinstance(link_no, int), "link_no must be an integer"
            table = browser.find_by_css("#recovery_table tr:not(:first-child) td:nth-child(3)")
            if link_no >= len(table):
                table[-1].click()
            else:
                table[link_no].click()
        else:
            raise NotImplementedError
            #assert project != None and step != None, "Missing args"

    def run(self):
        """Evaluates the steps in a multiprocessing.Queue of test cases

        If the --dry-run command-line option was used, the test's steps are
        simply printed.
        """
        if self.dry_run:
            self.run_dry()
        else:
            self.run_full()

    def run_dry(self):
        """Print pre-processed test cases in YAML format"""
        for test_case in iter(self.todo_q.get, 'STOP'):
            try:
                self.test_case = test_case
                print(yaml.dump([test_case]), end='')
                test_case['jobid'] = -1
                self.done_q.put(('SUCCESS', test_case, -1))
            except:
                # give the full exception string
                exc_str = ''.join(traceback.format_exception(*sys.exc_info()))
                print(exc_str)
                if self.interactive:
                    self.interact(locals())
                self.done_q.put(('EXCEPTION', test_case, -1, exc_str))

    def run_full(self):
        """Execute test cases and log results"""
        with Browser(self.browser_type) as browser:
            self.browser = browser
            self.step = step_num = -1

            # ensure we are logged in
            if self.credentials is not None:
                browser.visit(self.base_url+'?doc=sign')
                browser.fill('email', self.credentials['user'])
                browser.fill('password', self.credentials['pass'])
                self.click_by_value('Submit')

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

                    self.init_system(resume=resume)

                    jobid = test_case['jobid']
                    print(self.name, "Job ID:", jobid)

                    steps = test_case['steps'][resume_link:]
                    failure = False
                    for step_num, step in enumerate(steps):
                        self.step = step_num
                        if 'wait_text' in step:
                            found_text = self.wait_text_multi([step['wait_text'],
                                self.CHARMM_ERROR, self.PHP_FATAL_ERROR, self.PHP_ERROR])
                        if found_text != step['wait_text']:
                            failure = True
                            break

                        # Check for PHP errors, warnings, and notices
                        found_text = self.warn_if_text(self.PHP_MESSAGES)
                        if found_text and self.interactive:
                            if not self.errors_only or \
                                    found_text in (self.PHP_ERROR, self.PHP_FATAL_ERROR):
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

                    if self.interactive and (failure or not self.errors_only):
                        self.interact(locals())

                    # early failure?
                    if failure:
                        self.done_q.put(('FAILURE', test_case, step_num, elapsed_time))
                        failure = False
                        continue

                    # late failure?
                    final_wait_text = steps[-1]['wait_text']
                    found_text = self.wait_text_multi([final_wait_text,
                        self.CHARMM_ERROR, self.PHP_ERROR,
                        self.PHP_FATAL_ERROR])

                    if found_text != final_wait_text:
                        self.done_q.put(('FAILURE', test_case, step_num, elapsed_time))
                        failure = False
                    else:
                        # download project and optionally compare PSF
                        sys_archive = None
                        if not 'localhost' in self.base_url:
                            sys_archive = self.download()
                            sys_dir, _ext = os.path.splitext(sys_archive)
                        else:
                            sys_dir = pjoin(self.www_dir, jobid)

                        validation_result = utils.validate_test_case(test_case, sys_dir,
                                sys_archive=sys_archive,
                                module=self.module,
                                elapsed_time=elapsed_time,
                                printer_name=self.name)

                        self.done_q.put(validation_result)

                except KeyboardInterrupt:
                    raise # reraise and cleanup browser context
                except:
                    # give the full exception string
                    exc_str = ''.join(traceback.format_exception(*sys.exc_info()))
                    print(exc_str)
                    if self.interactive:
                        self.interact(locals())
                    self.done_q.put(('EXCEPTION', test_case, step_num, exc_str))
                    if not 'localhost' in self.base_url:
                        self.download()

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

    def terminate(self):
        """Default SIGTERM does not allow adequate browser cleanup"""
        self._popen._send_signal(signal.SIGINT)

    def wait_exists(self, element_list, min_length=1, verbose=True, alert=None):
        """Waits until the query used to create element_list finds at least
        min_length elements and returns the new list

        By default, prints a warning every time len(element_list) < min_length
        """
        # get a reference to the actual function, and save its arguments
        find_by_str = element_list.find_by
        finder = getattr(element_list, 'find_by_'+find_by_str)
        query = element_list.query

        tpl = "{} waiting for element by {}: '{}' (min_length: {})"
        while len(element_list) < min_length:
            try:
                if verbose:
                    print(tpl.format(self.name, find_by_str, query, min_length))
                element_list = self.browser.find_by(finder, query)
            except UnexpectedAlertPresentException as exc:
                if not alert:
                    raise

        return element_list

    def wait_script(self, script, alert=None):
        """Executes a Javascript expression in 1-second intervals.

        Blocks until the expression's return value bool(ret) is True
        """
        print(self.name, "waiting for Javascript expression to evaluate to True")
        print(self.name, "JS expr:", script)
        while not self.browser.evaluate_script(script):
            time.sleep(1)

    def wait_text(self, text, wait_time=1, alert=None):
        """Blocks until text appears on a page"""
        print(self.name, "waiting for text:", text)
        while True:
            try:
                if self.browser.is_text_present(text, wait_time=wait_time):
                    break
            except UnexpectedAlertPresentException as exc:
                if not alert:
                    raise

    def wait_text_multi(self, texts, alert=None):
        """Blocks until one of the texts in `texts` appears on a page

        Use this is more than one result is expected.
        """
        print(self.name, "waiting for any text in:", texts)
        wait_time = 1
        while True:
            for text in texts:
                try:
                    if self.browser.is_text_present(text, wait_time):
                        return text
                except UnexpectedAlertPresentException as exc:
                    if not alert:
                        raise
                except ElementDoesNotExist as exc:
                    print(f"Warning: received {exc}")

    @staticmethod
    def wait_visible(element, wait=None, click=False, alert=None):
        """Waits until an element is visible and optionally clicks it.

        If wait is not None, then after wait seconds, this function raises a
        TimeoutException. If click is True, then the element is clicked on
        success.

        Returns the element on success.
        """
        start_time = time.time()
        while wait is None or time.time() - start_time < wait:
            try:
                if element.visible:
                    if click:
                        element.click()
                    return
            except UnexpectedAlertPresentException as exc:
                if not alert:
                    raise
        raise TimeoutException

    def warn_if_text(self, text_or_texts):
        """Warns if one or more strings appear on the page

        Parameters
        ==========
            text_or_texts   str or seq  one or more messages to find

        Returns
        =======
            First observed string (if any), else None
        """
        msg = "Warning: {} ({}) found '{{}}' on step {}"
        if not 'jobid' in self.test_case:
            jobid = '-1'
        else:
            jobid = str(self.test_case['jobid'])
        msg = msg.format(self.name, jobid, self.step)
        if isinstance(text_or_texts, (list, tuple)):
            texts = text_or_texts
            for text in texts:
                if self.browser.is_text_present(text):
                    print(msg.format(text))
                    return text
        elif self.browser.is_text_present(text_or_texts):
            print(msg.format(text))
            return text
        return None

    def uncheck(self, check_elem_id, wait=None, alert=None):
        """Unchecks a checkbox and optionally waits for text to appear

        Note that uncheck() is not the same as click(): uncheck() will never
        check a checkbox, whereas click() can if it was not already checked.
        """
        elem = self.browser.find_by_id(check_elem_id)
        elem.uncheck()
        if wait:
            self.wait_text(wait, alert=alert)
