import shutil
import time
from multiprocessing import Process, Queue
import os.path
from os.path import join as pjoin
from splinter import Browser
from splinter.exceptions import ElementDoesNotExist

class CGUIBrowserProcess(Process):
    """Usage: subclass this class and override the run() method"""
    CHARMM_ERROR = 'CHARMM was terminated abnormally.'

    def __init__(self, todo_q, done_q, **kwargs):
        """Setup Queues, browser settings, and delegate rest to multiprocessing.Process"""
        if not 'browser_type' in kwargs:
            kwargs['browser_type'] = 'chrome'
        self.browser_type = kwargs['browser_type']
        del kwargs['browser_type']

        if not 'base_url' in kwargs:
            kwargs['base_url'] = 'http://charmm-gui.org/'
        self.base_url = kwargs['base_url']
        if not self.base_url.endswith('/'):
            self.base_url += '/'
        del kwargs['base_url']

        if not 'www_dir' in kwargs:
            kwargs['www_dir'] = None
        self.www_dir = kwargs['www_dir']
        del kwargs['www_dir']

        super().__init__(**kwargs)
        self.todo_q = todo_q
        self.done_q = done_q

    def click(self, click_elem_id, wait=None):
        self.browser.find_by_id(click_elem_id).click()
        if wait:
            self.wait_text(wait)

    def click_by_attrs(self, wait=None, **attrs):
        css_templ = "[{}='{}']"
        css_str = ''
        for attr, value in attrs.items():
            css_str += css_templ.format(attr, value)
        self.browser.find_by_css(css_str).click()
        if wait:
            self.wait_text(wait)

    def click_lipid_category(self, category):
        """Activate a lipid category in the Membrane Builder lipid selection page"""
        self.browser.find_by_text(category).find_by_xpath('../img').first.click()


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

    def eval(self, expr):
        """Evaluate a Python command that could refer to a method of self
        *OR* to a global function.
        """
        try:
            # isolate the function name
            fname = expr[:expr.index('(')]
        except ValueError:
            raise SyntaxError("invalid syntax: " + expr)
        if fname in dir(self):
            # make it a method call
            expr = 'self.'+expr
        return eval(expr)

    def go_next(self, test_text=None):
        self.browser.find_by_id('nextBtn').click()
        if test_text:
            self.wait_text_multi([test_text, self.CHARMM_ERROR])

    def handle_step(self, step_info):
        for elem in step_info['elems']:
            name = list(elem.keys())[0]
            value = elem[name]
            self.browser.fill(name, value)

    def resume_step(self, jobid, project=None, step=None, link_no=None):
        browser = self.browser
        """Uses Job Retriever to return to the given step.

        You must provide either:
            1) Project name AND step number
            2) Link number

        project: doc to return to
        step: step of doc to return to
        link_no: 0-indexed order of recovery link to return to
        """
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
            assert project != None and step != None, "Missing args"

    def wait_text(self, text):
        print(self.name, "waiting for text:", text)
        while not self.browser.is_text_present(text, wait_time=1):
            pass

    def wait_text_multi(self, texts):
        wait_time = None
        while True:
            for text in texts:
                if self.browser.is_text_present(text, wait_time):
                    return text
                wait_time = None
            wait_time = 1

