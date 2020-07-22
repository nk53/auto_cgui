import shutil
import os.path
import re
import requests
import time
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

    def __init__(self, todo_q, done_q, **kwargs):
        """Setup Queues, browser settings, and delegate rest to multiprocessing.Process"""
        self.browser_type = kwargs.pop('browser_type', 'chrome')
        self.base_url = kwargs.pop('base_url', 'http://charmm-gui.org/')
        self.www_dir = kwargs.pop('www_dir', None)
        self.interactive = kwargs.pop('interactive', False)
        self.cgui_module = kwargs.pop('cgui_module')
        self.dry_run = kwargs.pop('dry_run', False)
        self.inter_q = kwargs.pop('inter_q', None)
        self.msg_q = kwargs.pop('msg_q', None)

        if not self.base_url.endswith('/'):
            self.base_url += '/'

        super().__init__(**kwargs)

        self.todo_q = todo_q
        self.done_q = done_q

    def _click(self, elem, wait=None):
        elem.click()
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

    def click_lipid_category(self, category):
        """Activate a lipid category in the Membrane Builder lipid selection page"""
        category_root = self.browser.find_by_text(category)
        arrow_elem = category_root.find_by_xpath('../img').first
        table_elem = category_root.find_by_xpath('../table').first
        cnt = 0
        # clicking the arrow is somehow not very reliable ....
        while not arrow_elem.visible:
            cnt += 1
            time.sleep(1)
        arrow_elem.click()
        cnt = 0
        while not table_elem.visible:
            cnt += 1
            time.sleep(1)
            if cnt > 5:
                arrow_elem.click()
                cnt = 0

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
            saveas = 'charmm-gui-{}.tgz'.format(jobid)

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

    def eval(self, expr):
        """Evaluate a Python command that could refer to a method of self
        *OR* to a global function.
        """
        if expr == 'INTERACT' and self.interactive:
            self.interact()
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

    def go_next(self, test_text=None):
        button_elem = self.browser.find_by_id('nextBtn')
        if not button_elem:
            button_elem = self.browser.find_by_id("input_nav").find_by_tag("table")
        assert button_elem, "Can't find next button"

        while not button_elem.visible:
            time.sleep(1)
        button_elem.click()
        if test_text:
            print("waiting for", test_text)
            self.wait_text_multi([test_text, self.CHARMM_ERROR])

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
                elem = ElementList(filter(lambda e: e.value == value, elem))
                elem.check()
            elif input_type == "checkbox":
                if value:
                    elem.check()
            elif input_type == "select":
                elem.select(value)
            else:
                elem.fill(value)

    def find_test_file(self, filename, module=None):
        if not module:
            module = self.cgui_module

        path = pjoin('test_cases', module, filename)
        if not os.path.isfile(path):
            path = pjoin('test_cases', filename)

        if not os.path.exists(path):
            raise FileNotFoundError("No such file or directory: " + path)

        if os.path.isdir(path):
            path = pjoin(path, os.path.basename(path))

        if not os.path.isfile(path):
            path += '.yml'

        if not os.path.isfile(path):
            raise FileNotFoundError("No such file: " + path)

        return path

    def init_system(self):
        raise NotImplementedError("This must be implemented in a child class")

    def interact(self):
        test_case = getattr(self, 'test_case', {})
        jobid = test_case.get('jobid', -1)

        self.done_q.put(('INTERACT', self.name, jobid))
        for cmd in iter(self.inter_q.get, 'STOP'):
            try:
                result = eval(cmd)
                self.msg_q.put(result)
            except Exception as e:
                import sys, traceback
                # give the full exception string
                exc_str = ''.join(traceback.format_exception(*sys.exc_info()))
                self.msg_q.put(exc_str)

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
            assert project != None and step != None, "Missing args"

    def run(self):
        # if user set --dry-run, print test case and return
        if self.dry_run:
            self.run_dry()
        else:
            self.run_full()

    def run_dry(self):
        for test_case in iter(self.todo_q.get, 'STOP'):
            try:
                test_case = self.setup_custom_options(test_case)
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
                    self.interact()
                self.done_q.put(('EXCEPTION', test_case, -1, exc_str))

    def run_full(self):
        with Browser(self.browser_type) as browser:
            self.browser = browser
            self.step = step_num = -1
            for test_case in iter(self.todo_q.get, 'STOP'):
                try:
                    test_case = self.setup_custom_options(test_case)
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
                    self.init_system(test_case, resume)

                    jobid = test_case['jobid']
                    print(self.name, "Job ID:", jobid)

                    steps = test_case['steps'][resume_link:]
                    failure = False
                    for step_num, step in enumerate(steps):
                        self.step = step_num
                        if 'wait_text' in step:
                            print(self.name, "waiting for", step['wait_text'])
                            found_text = self.wait_text_multi([step['wait_text'], self.CHARMM_ERROR, self.PHP_FATAL_ERROR])
                        if found_text != step['wait_text']:
                            failure = True
                            break

                        # Check for PHP errors, warnings, and notices
                        if self.warn_if_text(self.PHP_MESSAGES) and self.interactive:
                            self.interact()

                        if 'presteps' in step:
                            for prestep in step['presteps']:
                                self.eval(prestep)
                        if 'elems' in step:
                            self.handle_step(step)
                        if 'poststeps' in step:
                            for poststep in step['poststeps']:
                                self.eval(poststep)

                        if step_num < len(steps)-1:
                            self.go_next()

                    elapsed_time = time.time() - start_time

                    # early failure?
                    if failure:
                        self.done_q.put(('FAILURE', test_case, step_num, elapsed_time))
                        failure = False
                        continue

                    # late failure?
                    final_wait_text = steps[-1]['wait_text']
                    found_text = self.wait_text_multi([final_wait_text, self.CHARMM_ERROR])
                    if found_text == self.CHARMM_ERROR:
                        self.done_q.put(('FAILURE', test_case, step_num, elapsed_time))
                        failure = False
                    elif self.interactive:
                        self.done_q.put(('SUCCESS', test_case, elapsed_time))
                    else:
                        self.done_q.put(('SUCCESS', test_case, elapsed_time))
                    if not 'localhost' in self.base_url: self.download()
                except Exception as e:
                    import sys, traceback
                    # give the full exception string
                    exc_str = ''.join(traceback.format_exception(*sys.exc_info()))
                    print(exc_str)
                    if self.interactive:
                        self.interact()
                    self.done_q.put(('EXCEPTION', test_case, step_num, exc_str))
                    if not 'localhost' in self.base_url: self.download()

    def setup_custom_options(self, test_case, module=None):
        test_case = self.setup_test_inheritance(test_case)

        map_filename = test_case.get('dict')
        if map_filename:
            map_filename = self.find_test_file(map_filename, module=module)
            with open(map_filename) as fh:
                opt_map = yaml.load(fh.read(), Loader=yaml.FullLoader)
            for opt, settings in opt_map.items():
                if opt in test_case:
                    value = str(test_case[opt])
                    pattern = r'\b' + opt + r'\b'

                    step = settings.get('step')
                    assert step, "Error: 'step' must be defined for custom options"
                    step = int(step) - 1

                    test_step = test_case['steps'][step]

                    presteps = settings.get('presteps')
                    if presteps:
                        for ind, step in enumerate(presteps):
                            presteps[ind] = re.sub(pattern, value, step)

                        test_presteps = test_step.setdefault('presteps', [])
                        test_presteps += presteps

                    elems = settings.get('elems')
                    if elems:
                        for ind, elem in enumerate(elems):
                            for elem_name, elem_value in elem.items():
                                elems[ind][elem_name] = re.sub(pattern, value, elem_value)

                        test_elems = test_step.setdefault('elems', [])
                        test_elems += elems

                    poststeps = settings.get('poststeps')
                    if poststeps:
                        for ind, step in enumerate(poststeps):
                            poststeps[ind] = re.sub(pattern, value, step)

                        test_poststeps = test_step.setdefault('poststeps', [])
                        test_poststeps += poststeps

        # look for "module" in each step
        # can't use for loop b/c iteration is nonlinear
        ind = 0
        while ind < len(test_case['steps']):
            step = test_case['steps'][ind]
            if 'module' in step:
                module_info = step['module']
                module_name = module_info['name']
                module_template = self.find_test_file(module_name, module=module_name)

                with open(module_template) as fh:
                    test_template = yaml.load(fh.read(), Loader=yaml.FullLoader)

                # get steps and dict from template
                test_copy = test_case.copy()
                test_copy['steps'] = test_template['steps']
                test_copy['dict'] = test_template['dict']
                test_template = test_copy

                # generate sub-case as though template were the main case
                test_template = self.setup_custom_options(test_template, module=module_name)

                # obtain user's desired slice of module's steps
                index = module_info.get('index', None)
                if index == None:
                    start = module_info.get('start', None)
                    stop = module_info.get('stop', None)
                    step_slice = slice(start, stop)
                else:
                    step_slice = index
                module_steps = test_template['steps'][step_slice]

                # replace module entry with steps
                before = test_case['steps'][:ind]
                after = test_case['steps'][ind+1:]
                test_case['steps'] = before + module_steps + after

                ind += len(module_steps)
            else:
                ind += 1

        return test_case

    def setup_test_inheritance(self, child_case, module=None):
        if module == None:
            module = self.cgui_module

        if not 'parent' in child_case:
            child_case['parent'] = module

        lineage = [child_case]
        filenames = [None]
        #while 'parent' in child_case:
        parent = child_case.get('parent', module)
        while parent != False:
            # defaults to module name
            if parent == None:
                parent = module
            else:
                parent = parent

            # break if module has itself as parent
            parent = self.find_test_file(parent, module=module)
            if parent == filenames[-1]:
                break

            with open(parent) as parent_file:
                parent_case = yaml.load(parent_file.read(), Loader=yaml.FullLoader)
            lineage.append(parent_case)

            if parent in filenames:
                filenames.append(parent)
                errmsg = "Multiple/circular inheritance not allowed; got: "
                errmsg += repr(filenames)
                raise NotImplementedError(errmsg)
            filenames.append(parent)

            child_case = parent_case
            parent = child_case.get('parent', module)

        parent_case = lineage.pop()
        while lineage:
            child_case = lineage.pop()
            parent_case.update(child_case)

        return parent_case

    def stop(self, reason=None):
        """Message main thread to safely terminate all threads"""
        self.done_q.put(('STOP', self.name, reason))

        # wait to be killed by main thread
        while True:
            time.sleep(1)

    def wait_script(self, script):
        print(self.name, "waiting for Javascript expression to evaluate to True")
        print(self.name, "JS expr:", script)
        while not self.browser.evaluate_script(script):
            time.sleep(1)

    def wait_text(self, text):
        print(self.name, "waiting for text:", text)
        while True:
            try:
                if self.browser.is_text_present(text, wait_time=1):
                    break
            except TimeoutException:
                print(self.name, "timed out receiving message from renderer")

    def wait_text_multi(self, texts):
        wait_time = None
        while True:
            for text in texts:
                try:
                    if self.browser.is_text_present(text, wait_time):
                        return text
                except TimeoutException:
                    print(self.name, "timed out receiving message from renderer")
                wait_time = None
            wait_time = 1

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
