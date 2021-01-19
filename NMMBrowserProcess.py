import os
import time
from os.path import join as pjoin
from splinter import Browser
from splinter.exceptions import ElementDoesNotExist
from SolutionBrowserProcess import SolutionBrowserProcess

def init_module(test_cases, args):
    """Preprocesses test cases

    Returns: (2-tuple)
    =======
        base_cases  Cases that can begin immediately
        wait_cases  Cases that need one of the base cases to complete first
    """
    base_cases = []
    wait_cases = {}
    for test_case in test_cases:
        base_cases.append(test_case)
    return base_cases, wait_cases

class NMMBrowserProcess(SolutionBrowserProcess):
    def click_by_text(self, text, wait=None):
        self.browser.find_by_text(text).click()
        if wait:
            self.wait_text(wait)

    def select_type(self, text, wait=None):
        css_templ = "[{}='{}']"
        base = 'data-material-type'
        full = css_templ.format(base,text)
        #print(full)
        self.browser.find_by_css(full).click()
        if wait:
            self.wait_text(wait)

    def select_material(self, text, wait=None):
        css_templ = "[{}='{}']"
        base = 'data-value'
        full = css_templ.format(base,text)
        #print(a)
        self.browser.find_by_css(full).click()
        if wait:
            self.wait_text(wait)

    def select_by_attrs(self, text1, text2, wait=None):
        css_templ = "[{}='{}']"
        full = css_templ.format(text1,text2)
        #print(a)
        self.browser.find_by_css(full).click()
        if wait:
            self.wait_text(wait)

    def select_wulff_milidx(self, text, wait=None):
        self.browser.find_by_value(text)
        if wait:
            self.wait_text(wait)


    def init_system(self, test_case, resume=False):
        css_templ = "[{}='{}']"
        url = self.base_url + "?doc=input/nanomaterial"
        browser = self.browser
        browser.visit(url)

        # Nanomaterial Type
        self.wait_text('Nanomaterial Type')

        mat_type = list(test_case['nanomaterial_type'].keys())[0]
        mat_name = test_case['nanomaterial_type'][mat_type]

        self.click_by_text('Nanomaterial Type')
        self.select_type(mat_type)
        self.select_material(mat_name)

        # Nanomaterial Shape

        # Ligand structure handling when the number of ligands is 1
        matTyp = list(test_case['nanomaterial_type'])[0]
        matName = test_case['nanomaterial_type'][matTyp]
        print(matTyp)
        print(matName)
        if matName == 'aum_nanocluster' or matName == 'aum_nanoparticle' or matName == 'aum_surface':
            nligand = test_case['nanomaterial_type']['numligand']
            browser.select('num_ligands', nligand)

            # Solvation or Vacuum
            sys = test_case['nanomaterial_type']['system']
            if sys == 'sol':
                browser.find_by_id('solv_systype').click()
            if sys == 'vac':
                browser.find_by_id('vacuum_systype').click()

            # First linker selection
            linkerPath = '//*[@id="ligand_row_1"]/div[1]/ul/li/span'
            browser.find_by_xpath(linkerPath).click()
            ilinker = test_case['nanomaterial_type']['first_linker']
            browser.find_by_value(ilinker).click()

            qadd = len(test_case['nanomaterial_type']['first_spacer'])
            if qadd == 2:
                self.select_by_attrs('class','polymer_menu_widget xbutton')
                iname = test_case['nanomaterial_type']['first_spacer'][1]['name']
                browser.find_by_value(iname).click()

                # Number of repeat
                self.select_by_attrs('name','subtext_spacer[0][]')
                inumrepeat = test_case['nanomaterial_type']['first_spacer'][1]['numrepeat']
                browser.fill('subtext_spacer[0][]',inumrepeat)
                # Number of spacer
                self.select_by_attrs('name','subtext_outer[]')
                inumspacer = test_case['nanomaterial_type']['first_spacer'][0]['numspacer']
                browser.fill('subtext_outer[]', inumspacer)

            if qadd > 2:
                nadd = qadd - 2
                for iadd in range(0, nadd):
                    self.select_by_attrs('type','button')
                self.select_by_attrs('class','polymer_menu_widget xbutton')
                iname = test_case['nanomaterial_type']['first_spacer'][1]['name']
                browser.find_by_value(iname).click()

                # Number of repeat
                self.select_by_attrs('name','subtext_spacer[0][]')
                inumrepeat = test_case['nanomaterial_type']['first_spacer'][1]['numrepeat']
                browser.fill('subtext_spacer[0][]',inumrepeat)
                # Number of spacer
                self.select_by_attrs('name','subtext_outer[]')
                inumspacer = test_case['nanomaterial_type']['first_spacer'][0]['numspacer']
                browser.fill('subtext_outer[]', inumspacer)

                for ispacer in range(1, nadd + 1):
                    self.select_by_attrs('data-gid',str(ispacer))
                    full = css_templ.format('data-gid',str(ispacer))
                    prestep = browser.find_by_css(full)
                    jname = test_case['nanomaterial_type']['first_spacer'][ispacer+1]['name']
                    prestep.find_by_value(jname).click()

                    ipath = ispacer+1
                    basePath = "/html/body/div[4]/div[2]/div[2]/form/div[4]/div[2]/input["
                    path = basePath + str(ipath) + "]"
                    inumrepeat = test_case['nanomaterial_type']['first_spacer'][ipath]['numrepeat']
                    browser.find_by_xpath(path).fill(inumrepeat)

            # Functional Group Selection
            browser.find_by_text('Select Functional Group').click()
            fgroup = test_case['nanomaterial_type']['first_functional']
            browser.find_by_value(fgroup).click()

            # Ligand structure handling when the number of ligands is 2
            if nligand == 2:
                jlinker = test_case['nanomaterial_type']['second_linker']
                linkers_elem = browser.find_by_xpath("//input[@name='linker[1][]']/..")
                linkers_elem.click()
                linker = linkers_elem.find_by_xpath("ul/li[@value='"+str(jlinker)+"']")
                linker.click()

                jnumspacer = test_case['nanomaterial_type']['second_spacer'][1]['name']
                spacers_elem = browser.find_by_xpath("//input[@name='spacer[1][]']/..")
                spacers_elem.click()
                spacer = spacers_elem.find_by_xpath("ul/li[@value='"+str(jnumspacer)+"']")
                spacer.click()

                # Number of repeat
                self.select_by_attrs('name','subtext_spacer[1][]')
                jnumrepeat = test_case['nanomaterial_type']['second_spacer'][1]['numrepeat']
                browser.fill('subtext_spacer[1][]',jnumrepeat)
#                # Number of spacer
                jnumspacer = test_case['nanomaterial_type']['second_spacer'][0]['numspacer']
                repeats_elem = browser.find_by_xpath("//div[@id='ligand_row_2']/input[@name='subtext_outer[]']")
                repeats_elem.fill(jnumspacer)

                qadd = len(test_case['nanomaterial_type']['second_spacer'])
                if qadd > 2:
                    nadd = qadd -2
                    for jadd in range(0, nadd):
                        adds_elem = browser.find_by_xpath("//div[@id='ligand_row_2']/button[@type='button']")
                        adds_elem.click()
                        #self.select_by_attrs('type','button')

                    tmp = 3
                    for jspacer in range(tmp, tmp + nadd):
                        print(jspacer)

                        # spacers
                        paths_elem = browser.find_by_xpath("/html/body/div[4]/div[2]/div[2]/form/div[4]/div[3]/div["+str(jspacer)+"]")
                        paths_elem.click()
                        jname = test_case['nanomaterial_type']['second_spacer'][jspacer-1]['name']
                        paths_elem.find_by_value(str(jname)).click()

                        # numrepeats
                        repeats_elem = browser.find_by_xpath("/html/body/div[4]/div[2]/div[2]/form/div[4]/div[3]/input["+str(jspacer-1)+"]")
                        jnumrepeats = test_case['nanomaterial_type']['second_spacer'][jspacer-1]['numrepeat']
                        repeats_elem.fill(jnumrepeats)

                # Functional Group Selection
                funcs_elem = browser.find_by_xpath("//input[@name='functional[1][]']/..")
                funcs_elem.click()
                jfunc = funcs_elem.find_by_xpath("ul/li[@value='TMAET']")
                jfunc.click()

            if matName == 'aum_nanocluster':
                print(matName, 'hi')
                # Core Type Selection
                core_type = test_case['nanomaterial_type']['nano_structure'][0]['core_type']
                browser.find_by_value(core_type).click()

                # Ligand Morphology
                if nligand == 2:
                    ilig_distrb = test_case['nanomaterial_type']['nano_structure'][0]['ligand_distribution']
                    lig_distrb = browser.find_by_xpath("//select[@id='ligand_pattern']/option[@value='"+str(ilig_distrb)+"']")
                    lig_distrb.click()

                    if ilig_distrb == 'random':
                        lig_ratio_first = test_case['nanomaterial_type']['nano_structure'][0]['ratio_ligand1']
                        lig_ratio_second = test_case['nanomaterial_type']['nano_structure'][0]['ratio_ligand2']

                        rligFirst_elem = browser.find_by_id('ligand_ratio_1')
                        rligFirst_elem.fill(lig_ratio_first)

                        rligSecond_elem = browser.find_by_id('ligand_ratio_2')
                        rligSecond_elem.fill(lig_ratio_second)

                    if ilig_distrb == 'strip':
                        nstrip = test_case['nanomaterial_type']['nano_structure'][0]['num_strips']
                        nstrip_elem = browser.find_by_id('strip')
                        nstrip_elem.fill(nstrip)

            if matName == 'aum_nanoparticle':
                # Core Type Selection
                core_type = test_case['nanomaterial_type']['nano_structure'][0]['core_type']
                browser.find_by_value(core_type).click()

                if core_type == 'icosahedron':
                    attach_type = test_case['nanomaterial_type']['nano_structure'][0]['attach_type']
                    browser.find_by_value(attach_type).click()

                    chirality = test_case['nanomaterial_type']['nano_structure'][0]['chirality']
                    browser.find_by_value(chirality).click()

                    radius = test_case['nanomaterial_type']['nano_structure'][0]['radius']
                    radius_elem = browser.find_by_id('core_radius')
                    radius_elem.fill(radius)
                if core_type == 'cube':
                    core_x = test_case['nanomaterial_type']['nano_structure'][0]['cube_xlen']
                    core_y = test_case['nanomaterial_type']['nano_structure'][0]['cube_ylen']
                    core_z = test_case['nanomaterial_type']['nano_structure'][0]['cube_zlen']
                    browser.find_by_id('core_x').fill(core_x)
                    browser.find_by_id('core_y').fill(core_y)
                    browser.find_by_id('core_z').fill(core_z)

                # Ligand Morphology
                if nligand == 2:
                    ilig_distrb = test_case['nanomaterial_type']['nano_structure'][0]['ligand_distribution']

                    if ilig_distrb == 'random':
                        lig_distrb = browser.find_by_xpath("//*[@id='ligand_pattern']/option[1]")
                        lig_distrb.click()

                        lig_ratio_first = test_case['nanomaterial_type']['nano_structure'][0]['ratio_ligand1']
                        lig_ratio_second = test_case['nanomaterial_type']['nano_structure'][0]['ratio_ligand2']

                        rligFirst_elem = browser.find_by_id('ligand_ratio_1')
                        rligFirst_elem.fill(lig_ratio_first)

                        rligSecond_elem = browser.find_by_id('ligand_ratio_2')
                        rligSecond_elem.fill(lig_ratio_second)

                    if ilig_distrb == 'janus':
                        lig_distrb = browser.find_by_xpath("//*[@id='ligand_pattern']/option[2]")
                        lig_distrb.click()

                # Coverage
                coverage = test_case['nanomaterial_type']['nano_structure'][0]['coverage']
                browser.find_by_id('coverage').fill(coverage)

            if matName == 'aum_surface':
                if nligand == 2:
                    ilig_distrb = test_case['nanomaterial_type']['nano_structure'][0]['ligand_distribution']

                    if ilig_distrb == 'random':
                        lig_distrb = browser.find_by_xpath("//*[@id='ligand_pattern']/option[1]")
                        lig_distrb.click()

                        lig_ratio_first = test_case['nanomaterial_type']['nano_structure'][0]['ratio_ligand1']
                        lig_ratio_second = test_case['nanomaterial_type']['nano_structure'][0]['ratio_ligand2']

                        rligFirst_elem = browser.find_by_id('ligand_ratio_1')
                        rligFirst_elem.fill(lig_ratio_first)

                        rligSecond_elem = browser.find_by_id('ligand_ratio_2')
                        rligSecond_elem.fill(lig_ratio_second)

                    if ilig_distrb == 'strip':
                        lig_distrb = browser.find_by_xpath("//*[@id='ligand_pattern']/option[2]")
                        lig_distrb.click()

                        nstrips_x = test_case['nanomaterial_type']['nano_structure'][0]['num_strips_x']
                        nstrips_y = test_case['nanomaterial_type']['nano_structure'][0]['num_strips_y']

                        nstrips_x_elem = browser.find_by_id('strip_x')
                        nstrips_x_elem.fill(nstrips_x)

                        nstrips_y_elem = browser.find_by_id('strip_y')
                        nstrips_y_elem.fill(nstrips_y)

                # Coverage
                coverage = test_case['nanomaterial_type']['nano_structure'][0]['coverage']
                browser.find_by_id('coverage').fill(coverage)

                # Box Options
                surf_milidx = test_case['nanomaterial_type']['nano_structure'][0]['surf_midx']
                milindex = surf_milidx[0]
                browser.select('mindex', milindex)
                surf_x = test_case['nanomaterial_type']['nano_structure'][0]['surf_xlen']
                surf_y = test_case['nanomaterial_type']['nano_structure'][0]['surf_ylen']
                surf_z = test_case['nanomaterial_type']['nano_structure'][0]['surf_zlen']
                browser.find_by_id('x_length').fill(surf_x)
                browser.find_by_id('y_length').fill(surf_y)
                browser.find_by_id('z_length').fill(surf_z)

        # Other metals
        ligandmaterials = ['aum_nanocluster','aum_nanoparticle','aum_surface']
        if not matName in ligandmaterials:
            mshape = test_case['nanomaterial_type']['shape']

        if matName == 'acm' or matName == 'agm' or matName == 'alm' or  matName == 'aum' or  matName == 'cem' or  matName == 'cum' or  matName == 'esm' or  matName == 'fem' or  matName == 'irm' or  matName == 'nim' or  matName == 'pbm' or matName == 'pdm' or matName == 'ptm' or matName == 'rhm' or  matName == 'srm' or matName == 'thm' or matName == 'ybm':
            browser.select('shape', mshape)
            if mshape == 'box':
                milidx = test_case['nanomaterial_type']['mindex'][0]
                browser.select('mindex', milidx)
            if mshape == 'sphere':
                rsphere = test_case['nanomaterial_type']['radius']
                browser.fill('radius', rsphere)
            if mshape == 'cylinder' or mshape == 'rod':
                rsphere = test_case['nanomaterial_type']['radius']
                browser.fill('radius', rsphere)
                lheight = test_case['nanomaterial_type']['height']
                browser.fill('lx', lheight)
            if mshape == 'polygon':
                elength = test_case['nanomaterial_type']['edgeLength']
                browser.fill('l_pgon', elength)
                nedge = test_case['nanomaterial_type']['numEdge']
                browser.fill('nnn', nedge)
                lheight = test_case['nanomaterial_type']['height']
                browser.fill('lx', lheight)
            if mshape == 'wulff':
                rsphere = test_case['nanomaterial_type']['radius']
                browser.fill('radius', rsphere)
                qadd = len(test_case['nanomaterial_type']['wmindex'])
                print(len(test_case['nanomaterial_type']['wmindex']))
                if qadd > 2:        # 2 is the default number of Miller Indices
                    nadd = qadd - 2
                    for iadd in range(0, nadd):
                        browser.find_by_id('wulff_add').click()
                    for isurf in range(0, qadd):
                        miller = 'miller_index_'+str(isurf)
                        print(miller)
                        iwmindex = test_case['nanomaterial_type']['wmindex'][isurf]
                        print(iwmindex)
                        select_elem = browser.find_by_id(miller)
                        select_elem.find_by_value(iwmindex).click()
                if qadd == 2:
                    for isurf in range(0, qadd):
                        miller = 'miller_index_'+str(isurf)
                        print(miller)
                        iwmindex = test_case['nanomaterial_type']['wmindex'][isurf]
                        print(iwmindex)
                        select_elem = browser.find_by_id(miller)
                        select_elem.find_by_value(iwmindex).click()

        else:
            if matName == 'mm':
                rdfct = test_case['nanomaterial_type']['rdefect']
                browser.find_by_id('defect_ratio').fill(rdfct)
                ions_type = test_case['nanomaterial_type']['ion_option']
                browser.find_by_value(ions_type).click()

            if matName == 'gs':
                if mshape == 'box':
                    milidx = test_case['nanomaterial_type']['mindex'][0]
                    browser.select('mindex', milidx)
                if mshape == 'wulff':
                    browser.select('shape', mshape)
                    rsphere = test_case['nanomaterial_type']['radius']
                    browser.fill('radius', rsphere)
                    qadd = len(test_case['nanomaterial_type']['wmindex'])
                    if qadd == 3:
                        for isurf in range(0, qadd):
                            miller = 'miller_index_'+str(isurf)
                            print(miller)
                            iwmindex = test_case['nanomaterial_type']['wmindex'][isurf]
                            print(iwmindex)
                            select_elem = browser.find_by_id(miller)
                            select_elem.find_by_value(iwmindex).click()

            if matName == 'ta' or matName == 'ts':
                qhyd = test_case['nanomaterial_type']['hydration']
                    #if matName == 'ta':
                    #    browser.find_by_value(qhyd).click()
                if matName == 'ts':
                    if mshape == 'wulff':
                        browser.select('shape', mshape)
                        rsphere = test_case['nanomaterial_type']['radius']
                        browser.fill('radius', rsphere)
                        browser.find_by_value(qhyd).click()
                        qadd = len(test_case['nanomaterial_type']['wmindex'])
                        if qadd == 3:
                            for isurf in range(0, qadd):
                                miller = 'miller_index_'+str(isurf)
                                print(miller)
                                iwmindex = test_case['nanomaterial_type']['wmindex'][isurf]
                                print(iwmindex)
                                select_elem = browser.find_by_id(miller)
                                select_elem.find_by_value(iwmindex).click()
                    if mshape == 'box':
                        milidx = test_case['nanomaterial_type']['mindex'][0]
                        browser.select('mindex', milidx)
                browser.find_by_value(qhyd).click()

            if matName == 'cr' or matName == 'qz':
                if mshape == 'sphere':
                    rsphere = test_case['nanomaterial_type']['radius']
                    browser.fill('radius', rsphere)
                if mshape == 'box':
                    boxPath = '//*[@id="shape"]/option[5]'
                    browser.find_by_xpath(boxPath).click()
                ionpercent = test_case['nanomaterial_type']['degree_ionization']
                browser.find_by_id('ion_percent').fill(ionpercent)

            if matName == 'ha':
                env_pH = test_case['nanomaterial_type']['environment_pH']
                browser.find_by_value(env_pH).click()
                if mshape == 'box':
                    milidx = test_case['nanomaterial_type']['mindex'][0]
                    browser.select('mindex', milidx)
                if mshape == 'wulff':
                    browser.select('shape', m)
                    rsphere = test_case['nanomaterial_type']['radius']
                    browser.fill('radius', rsphere)
                    qadd = len(test_case['nanomaterial_type']['wmindex'])
                    print(len(test_case['nanomaterial_type']['wmindex']))
                    if qadd > 2:        # 2 is the default number of Miller Indices
                        nadd = qadd - 2
                        for iadd in range(0, nadd):
                            browser.find_by_id('wulff_add').click()
                        for isurf in range(0, qadd):
                            miller = 'miller_index_'+str(isurf)
                            print(miller)
                            iwmindex = test_case['nanomaterial_type']['wmindex'][isurf]
                            print(iwmindex)
                            select_elem = browser.find_by_id(miller)
                            select_elem.find_by_value(iwmindex).click()
                    if qadd == 2:
                        for isurf in range(0, qadd):
                            miller = 'miller_index_'+str(isurf)
                            print(miller)
                            iwmindex = test_case['nanomaterial_type']['wmindex'][isurf]
                            print(iwmindex)
                            select_elem = browser.find_by_id(miller)
                            select_elem.find_by_value(iwmindex).click()

            if matName == 'tube':
                chiralN = test_case['nanomaterial_type']['chirality_n']
                chiralN = int(chiralN)
                chiralNpath = '//*[@id="chirality_n"]'
                try:
                    browser.find_by_xpath(chiralNpath).fill(chiralN)
                except:
                    browser.find_by_xpath(chiralNpath).fill(chiralN)

                chiralM = test_case['nanomaterial_type']['chirality_m']
                chiralMpath = '//*[@id="chirality_m"]'
                try:
                    browser.find_by_xpath(chiralMpath).fill(chiralM)
                except:
                    browser.find_by_xpath(chiralMpath).fill(chiralM)

                cellCopies = test_case['nanomaterial_type']['cell_copies']
                try:
                    browser.find_by_id('cell_copies').fill(cellCopies)
                except:
                    browser.find_by_id('cell_copies').fill(cellCopies)


            if matName == 'gp' or matName == 'gi':
                percentDefect = test_case['nanomaterial_type']['percent_defect']

                if percentDefect == '0':
                    # Box Length for graphene and graphite
                    xlen = test_case['nanomaterial_type']['lx']
                    print(xlen)
                    browser.fill('lx', xlen)

                    ylen = test_case['nanomaterial_type']['ly']
                    browser.fill('ly', ylen)

                    zlen = test_case['nanomaterial_type']['lz']
                    browser.fill('lz', zlen)
                else:
                    browser.find_by_id('percent_defect').fill(percentDefect)
                    time.sleep(0.5)
                    browser.find_by_tag('body').click()
                    time.sleep(0.5)


                chkPBC = browser.is_text_present('Periodic Options')
                if chkPBC == False:
                    print('FalsePBC')
                    browser.find_by_id('dense_defect').check()
                if chkPBC == True:
                    print('TruePBC')
                    pbc_x = test_case['nanomaterial_type']['xpbc']
                    if pbc_x == True:
                        browser.find_by_id('pbc_x').check()
                    if pbc_x == False:
                        browser.find_by_id('pbc_x').uncheck()

                    pbc_y = test_case['nanomaterial_type']['ypbc']
                    if pbc_y == True:
                        browser.find_by_id('pbc_y').check()
                    if pbc_y == False:
                        browser.find_by_id('pbc_y').uncheck()

                    pbc_z = test_case['nanomaterial_type']['zpbc']
                    if pbc_z == True:
                        browser.find_by_id('pbc_z').check()
                    if pbc_z == False:
                        browser.find_by_id('pbc_z').uncheck()

        #if matName == 'aum_nanocluster' or matName == 'aum_nanoparticle' or matName == 'aum_surface':
        ligandmaterials = ['aum_nanocluster','aum_nanoparticle','aum_surface']
        if not matName in ligandmaterials:
            if matName != 'gp':
                if matName != 'gi':
                    if mshape == 'box':
                        # BOx Length
                        xlen = test_case['nanomaterial_type']['lx']
                        print(xlen)
                        browser.fill('lx', xlen)

                        ylen = test_case['nanomaterial_type']['ly']
                        browser.fill('ly', ylen)

                        zlen = test_case['nanomaterial_type']['lz']
                        browser.fill('lz', zlen)

                        # PBC
                        pbc_x = test_case['nanomaterial_type']['xpbc']
                        if pbc_x == True:
                            browser.find_by_id('pbc_x').check()
                        if pbc_x == False:
                            browser.find_by_id('pbc_x').uncheck()

                        pbc_y = test_case['nanomaterial_type']['ypbc']
                        if pbc_y == True:
                            browser.find_by_id('pbc_y').check()
                        if pbc_y == False:
                            browser.find_by_id('pbc_y').uncheck()

                        pbc_z = test_case['nanomaterial_type']['zpbc']
                        if pbc_z == True:
                            browser.find_by_id('pbc_z').check()
                        if pbc_z == False:
                            browser.find_by_id('pbc_z').uncheck()

            # Exception: cristobalite only
            if matName == 'cr':
                if pbc_x == True and pbc_y == True:
                    surf_conc = test_case['nanomaterial_type']['surf_concentration']
                    browser.find_by_id('surf_conc').fill(surf_conc)
                    print('xypbc')

        # System Type
        sys = test_case['nanomaterial_type']['system']
        if sys == 'sol':
            browser.find_by_id('solv_systype').click()
        if sys == 'vac':
            browser.find_by_id('vacuum_systype').click()

        self.go_next(test_case['steps'][0]['wait_text'])

        self.jobid = self.get_jobid()
