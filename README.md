## About This Repository
This repository demonstrates how to automate browser interactions for the most commonly-used CHARMM-GUI modules. It is designed primarily for testing CHARMM-GUI functionality. It is also possible to create and run custom jobs with Auto CGUI in parallel, but you will notice that the browser sessions managed through Splinter/Selenium require large amounts of memory, limiting the effectiveness of parallelism. The UI is also geared more toward reproducibility than ease of use. Generally, if you have <100 models to generate, you are better off creating them manually.

Via the `--interact` or `-i` CLI option, Auto CGUI also allows interaction with browsers as though they had been run through `python -i`. If `-e` is included (e.g., `-ie`), this interaction is set to run only when Auto CGUI encounters an error.

Please note that the CHARMM-GUI servers have a finite capacity for simultaneous workloads. Please be considerate to other users and do not run more than 4 jobs simultaneously.

## Prerequisites
 - Python 3.8 or version with compatible multiprocessing requirements
 - [Selenium](https://splinter.readthedocs.io/en/latest/drivers/chrome.html)
 - [geckodriver](https://github.com/mozilla/geckodriver/releases) (if using Firefox)
 - [Splinter](https://splinter.readthedocs.io/en/latest/)
 - [PyYAML](https://pyyaml.org/)

## Configuration: Regular CHARMM-GUI users
Create `config.yml` at the root of the Auto CGUI project, and add the following settings:
```yaml
BASE_URL: https://charmm-gui.org/
CGUSER: your cgui email goes here
CGPASS: your plain text password goes here
BROWSER_TYPE: firefox
```

The allowed browser types are `firefox` and `chrome`. Make sure to use your actual username and password. The full set of options regular users might want to know:
 - `BASE_URL`: location of CHARMM-GUI, this should always be `https://charmm-gui.org/`, including the trailing slash (`/`).
 - `CGUSER`: your CHARMM-GUI username/email
 - `CGPASS`: your CHARMM-GUI password (do not send this to anyone)
 - `BROWSER_TYPE`: either `firefox` or `chrome`
 - `MODULE`: default value of `-m` if not given on CLI. See output of `./run_tests.py -h` for more info.

## Configuration: CHARMM-GUI Developers ONLY
Create `config.yml` at the root of the Auto CGUI project, and add the following settings if you want to test your local copy of the CHARMM-GUI source code:
```yaml
BASE_URL: http://localhost:8888/
WWW_DIR: /path/to/your/data/www/
CGUSER: your cgui email goes here (if you configured AUTH, else omit)
CGPASS: your cgui password goes here (if you configured AUTH, else omit)
BROWSER_TYPE: either firefox or chrome
MODULE: see modules.yml for possible values
```

Note that `WWW_DIR` is optional and (if given) should contain the path to `data/www/`.

To instead test beta CHARMM-GUI functions, use this template:
```yaml
BASE_URL: http://beta.charmm-gui.org/
USER: beta access username (NOT your email)
PASS: beta access password
CGUSER: your cgui email goes here
CGPASS: your cgui password goes here
BROWSER_TYPE: either firefox or chrome
MODULE: see modules.yml for possible values
```

## Usage

To run the testing program, execute:
`$ ./run_tests.py [opts]`
From the main project directory. Use the `-h` option to see a list of possible options.

## Writing Tests

See examples in `test_cases`. To develop test cases for a module already covered by Auto CGUI, see examples in that module's subdirectory in `test_cases`. Some guidelines follow.

### Test Case Directory Organization

Each subdirectory of `test_cases` is the short name for a CHARMM-GUI module (lower case). To see the correspondence between short and long module names, see `modules.yml`.

Within each subdirectory, the following filenames are reserved:
 - `basic.yml`: if it exists, it contains the default tests to run if `-t` is not provided on the command-line.
 - `minimal.yml`, `standard.yml`, and `extensive.yml`: these are shortcuts that contain a list of test case files to combine into one larger test.
 - `basic.map.yml`: This controls the behavior of some settings in test case files.
 - A `.yml` file with the same name as its containing directory: Tests in this directory automatically inherit from this file (unless a different `parent` is specified in the test case; see **Test Case Options** below for more detail). E.g.:
    - `test_cases/pdb/pdb.yml`
    - `test_cases/mca/mca.yml`
    - `test_cases/bilayer/bilayer.yml`
 - Any other file is *either* a file containing test cases *OR* an alternate parent file from which test cases can inherit options.

### Test Case Files

Test cases are contained in YAML files as a list-of-dicts.

Each of the keys below are required in all tests. By default, all except `label` are inherited from the module's parent settings file (e.g., `test_cases/solution/solution.yml`).
In general, these keys are required, although most of them will be set in the default parent file:
 - `label`: Unique name to use for the test in logs
 - `base`: Directory containing files to upload, which may be referenced by other options.
 - `dict`: File containing shortcut options. All modules use `basic.map.yml` as the default, but you can override it via this option.
 - `steps`: The general flow of the CGUI module. For more detail, see **Test Case Options**. Do not override this unless you know what you are doing.

For a typical example of a test case file, see `test_cases/solution/explicit.yml`, reprinted below:
```yaml
- label: 1UBQ with two staples in solution with explicit size
  staples:
    - RMETA3 PROA 1 PROA 3
    - META5 PROA 25 PROA 29
  pdb: 1ubq.pdb
  input: openmm
  hmr: True
  size_option: explicit
  X: 50
  Y: 60
  Z: 70
- label: 186L modified with explicit size
  pdb: 186l_modified.charmm
  ligand: ligands/basic
  chains:
    - HETA
    - HETB
    - HETC
    - HETD
    - WATA
  hcr:
    - CLA CLA
    - HED charmm
    - LIG ctop_upload
  X: 50
  Y: 60
  Z: 70
- label: 2OI0_modified parameterized with explicit size
  pdb: 2oi0_modified.pdb
  ligand: ligands/basic
  chains:
    - HETA
  hcr:
    - LIG param
  X: 50
  Y: 60
  Z: 70
```

Three test cases are shown above, designated by the YAML list item token (`-`). Options can be specified in any order within the list item, but for readability, please ensure `label` is the first option. For an explanation of the options used in this test, see **Solution Tests**.

### Test Case Options: General

As stated above, these keys are required in all test cases:
 - `label`: Unique name to use for the test in logs
 - `base`: Directory containing files to upload, which may be referenced by other options.
 - `dict`: File containing shortcut options. All modules use `basic.map.yml` as the default, but you can override it via this option.
 - `steps`: The general flow of the CGUI module.

#### `label`

This label is used to identify a test case whenever writing to the console or log files.

#### `base`

Directory, relative to root of Auto CGUI, containing any files referenced by test cases. E.g., `test_cases/solution/explicit.yml` references three files located in `pdb/basic`:
```yaml
  pdb: 1ubq.pdb
  pdb: 186l_modified.charmm
  pdb: 2oi0_modified.pdb
```

#### `dict`

Name of file containing shortcut options, which is always `basic.map.yml` in the Auto CGUI's default tests.

Each Auto CGUI module's `basic.map.yml` file is organized as a dict-of-dicts. E.g., the top of `test_cases/solution/basic.map.yml` includes these shortcut options:
```yaml
X:
  step: 2
  presteps:
    - set_xyz()
edge:
  step: 2
  elems:
    - fitedge: edge
```

In each case, the outer dict key (`X`, `edge`) is the name of the option, as it will appear in test cases. `step` is the (1-indexed) step number in which the expanded setting should be inserted. The expanded settings may include any combination of `presteps`, `elems`, and `poststeps` (see **steps** below). For `X`, this setting:
```yaml
X:
  step: 2
  presteps:
    - set_xyz()
```
causes the Python function call `solution_browser_process.set_xyz()` to be appended to the `presteps` array in STEP 2.

In `presteps`, `elems`, and `poststeps` settings, a value (but *not* a key) with the same name as the option causes the value in a test case to replace that value in the test case. E.g., if a Solution Builder test case looks like this:
```yaml
- label: example test case
  pdb: 1ubq
  edge: 15
```

Then the edge shortcut in `test_cases/solution/basic.map.yml` causes a list item containing `fitedge: 15` to be inserted in the `elems` array in STEP 2.

#### `steps`

The `steps` setting is a list-of-dicts that defines the sequence of clicks, form entries, and Python function calls needed to progress through a CHARMM-GUI module. Generally, only CHARMM-GUI developers should encounter situations where they need to modify this value.

Except for the special `module` item, each entry in `steps` should contain these keys:
##### `elems`

Default: `elems: []`

A list of form entries of the form `element_name: value`. To check an element's name, first ensure you have your browser's web developer tools enabled, then right-click that element and click "Inspect". This shows you the form element's HTML. If the element contains an attribute like `name="element_name"`, then whatever name is in quotes can be autofilled by including a corresponding entry in `elems`. If the element only has an `id` attribute (or worse, has neither a name nor id attribute), then some other method is required to set it. In most cases, this is handled by a shortcut option in `basic.map.yml`.

To use an example from **Test Case Options: `dict`**, this value for `elems`:
```yaml
  elems:
    - fitedge: 15
    - other_option: other_value
```

Causes an element with the attribute `name="fitedge"` to be filled with the value `15` and another element named `other_option` to be filled with the text `other_value`.

##### `presteps`

Default: `presteps: []` 

A list of Python function calls to run *before* any elements from `elems` are updated. Possible function names are checked in this order:
 - The special `INTERACT` option resolves to `cgui_browser_process.interact()`. Only include this if you also pass `-i` to `run_tests.py`.
 - If the function exists in the Python class corresponding to the test being run, then `self.` is prepended to the function call.
 - Any other function is assumed to be accessible from the global namespace.

##### `poststeps`

Default: `poststeps: []`

A list of Python function calls to run *after* any elements from `elems` are updated. The same name resolution order is followed as in `presteps`.

##### `wait_text`

Because Splinter and Selenium give control over a browser potentially before a web page has finished loading, each browser process must have a way to determine when a step has loaded sufficiently to start manipulating the page. In Auto CGUI, this is done by waiting for a given piece of text to appear on the page. This `wait_text` is case-sensitive and should be unique from any previous or later step, otherwise the browser process may incorrectly determine that the page has finished loading. The text should also be guaranteed to appear on a loaded page, otherwise the browser process will hang looking for nonexistent text.

In all cases, the text `'CHARMM was terminated abnormally.'`, and certain PHP messages are searched for, regardless of the value of `wait_text`.

##### `module`

This special option indicates that another Python module should take over interpretation of commands. E.g., most Solution Builder jobs start with 3 pages of PDB Reader & Manipulator pages, followed by 2 pages of Solution Builder, followed by 2 pages of input generator (where the last page has no options). To reduce the need to re-specify workflow of other modules, this option can be used.

Example usage from `test_cases/solution/solution.yml`:
```yaml
steps:
  - module:
      name: pdb
      stop: -1
[...other steps...]
  - module:
      name: input
```

And from `test_cases/glycan/glycan_only.yml`:
```yaml
steps:
  - module:
      name: solution
      start: 1
```

The three possible options to `module` are:
 - `name`: the directory name in `test_cases` of the other module to switch to
 - `start`: 0-based index of the step (in `steps`) to begin (default: 0)
 - `stop`: 0-based index of the step on which to stop using this module (default: final step + 1)

The steps from the other module are selected via a Python [slice()](https://docs.python.org/3.8/library/functions.html#slice) from `start` to `stop`.

