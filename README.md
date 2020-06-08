## About This Repository
This repository demonstrates how to automate browser interactions for CHARMM-GUI. The examples provided here test the basic functionality of the CHARMM-GUI module Multicomponent Assembler (MCA), but with minimal work, it should be possible to automate any system creation through MCA.

## Prerequisites
 - Python 3
 - [Selenium](https://splinter.readthedocs.io/en/latest/drivers/chrome.html) (if using Chrome)
 - [geckodriver](https://github.com/mozilla/geckodriver/releases) (if using Firefox)
 - [Splinter](https://splinter.readthedocs.io/en/latest/)
 - [PyAML](https://pyyaml.org/)

## Usage
First create a configuration file that points to your CGUI project's `/data/www/` directory. E.g.:
```yaml
BASE_URL: http://localhost:8888/
WWW_DIR: /Users/nathan/multicomp/www
```
This file should be named `config.yml` and be located in the same directory as `run_tests.py`. The `BASE_URL` shown above is for alpha tests. For beta tests, `BASE_URL` should be `http://beta.charmm-gui.org/`, and for production tests, the entry can be omitted. If you are using the beta server, you must also include a `USER` and `PASS` entry.

To run the testing program, execute:
`$ ./run_tests.py [opts]`
From the main project directory. Use the `-h` option to see a list of possible options.

## Writing Tests
The `test_cases/basic.yml` file demonstrates some test cases for MCA. Each test should be written as a YAML array entry, with possible keys described below:
 - `label` (required): The name for this test that will appear in the output log file.
 - `base` (required): Directory containing files to upload to C-GUI
 - `components` (required): an associative array describing each uploaded component, e.g., to upload files named `1ubq.crd` and `1ubq.psf` representing a solvated component that should have 3 copies:
```yaml
    1ubq:
        type: solvated
        count: 3
```
 - `steps`: an array of actions to perform at each step (described later)
 - `final_wait_text` (required): text that should appear only on the final step page
 - `solvent_test`: an array of solvent variations, e.g., `water+ions` (use both water and ions), `water` (don't use ions), or `None` (no water and no ions). If absent, only the `water+ions` variety is tested.

### Step Array Contents
Each step in `steps` should be an associative array with the following keys:
 - `wait_text` (required): text appearing on the page that indicates completion of the previous step
 - `elems` (optional): an array of `{element_id: value}` pairs. This will change the value of the form element with ID `element_id` so that it holds the `value`, instead of its default value. This action is performed with Splinter's [fill](https://splinter.readthedocs.io/en/latest/api/driver-and-element-api.html#splinter.driver.DriverAPI.fill) method.
 - `presteps` (optional): an array of steps to perform *before* filling the values of `elems`. Will be evaluated with `CGUIBrowserProcess.eval()`, which defaults to Python's built-in `eval()`.
 - `poststeps` (optional): an array of steps to perform *after* filling the values of `elems`. Same format as `presteps`.

Next, extend the `CGUIBrowserProcess` class. See the example in `MCABrowserProcess.py`. The most important requirement is that you define an `init_system()` method that determines how to get through the first step of your module.

Finally, write tests for your project. See the examples in `test_cases/basic.yml`.

## Extending CGUIBrowserProcess
`MCABrowserProcess` is for running tests on Multicomponent Assembler. To run tests on a different CHARMM-GUI module, you must extend the `CGUIBrowserProcess` class in a similar manner. This base class manages a Splinter [browser](https://splinter.readthedocs.io/en/latest/browser.html) instance in a thread-safe manner.

For more information about Python's parallelism, see the [multiprocessing](https://docs.python.org/3/library/multiprocessing.html) documentation.
