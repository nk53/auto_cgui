import ast
import os
import re
import time
import yaml
from os.path import join as pjoin
from splinter import Browser
from splinter.exceptions import ElementDoesNotExist
from CGUIBrowserProcess import CGUIBrowserProcess

class PDBBrowserProcess(CGUIBrowserProcess):
    def __init__(self, todo_q, done_q, **kwargs):
        self.module_title = "PDB Reader"
        self.module_url = "?doc=input/pdbreader"
        super(PDBBrowserProcess, self).__init__(todo_q, done_q, **kwargs)

    def set_mutation(self):
        if not 'mutations' in self.test_case:
            raise ValueError("Missing stapling options")

        mutations = self.test_case['mutations']
        # open stapling menu
        self.click('mutation_checked', 'Mutant')

        # add as many mutations as needed
        add_btn = self.browser.find_by_value("Add Mutation")
        for mutation in mutations[1:]:
            add_btn.click()

        # set stapling options
        mutation_fmt = 'chain', 'rid', 'res', 'patch'
        id_fmt = 'mutation_{}_{}'
        for mutation_no, mutation in enumerate(mutations):
            mutation = mutation.split()
            if len(mutation) != 4:
                raise ValueError("Invalid mutation format")

            for name, value in zip(mutation_fmt, mutation):
                sid = id_fmt.format(name, mutation_no)
                self.browser.find_by_id(sid).select(value)

    def set_gpi(self):
        if not 'gpi' in self.test_case:
            raise ValueError("Missing gpi options")
        glyc_button = self.browser.find_by_id("gpi_checked").first
        if not glyc_button.checked:
            glyc_button.click()
        gpi = self.test_case['gpi']
        self.browser.select("gpi[chain]", gpi['segid'])
        table = self.browser.find_by_id("id_gpi")
        table.find_by_value("edit").first.click()
        self.browser.windows.current = self.browser.windows[1]
        lipid = ast.literal_eval(gpi['lipid'])
        self.browser.select("lipid_type", lipid['lipid_type'])
        self.browser.select("sequence[0][name]", lipid['name'])
        _d = re.compile('- ')
        nchem = 1
        for i,residue in enumerate(gpi['grs'].split('\n')):
            if not residue.strip(): continue
            depth = len(_d.findall(residue))
            linkage, resname = residue.split('- ')[-1].split()
            idx = resname.find('_')
            chemod = None
            if idx > 0:
                chemod = resname[idx+1:].split('_')
                resname = resname[:idx]
            if depth > 4:
                self.browser.find_by_id(str(depth-1)).find_by_css('.add').first.click()
            self.browser.select("sequence[%d][name]" % (i+1), resname[1:])
            self.browser.select("sequence[%d][type]" % (i+1), resname[0])
            self.browser.select("sequence[%d][linkage]" % (i+1), linkage[1])
            if chemod:
                for chm in chemod:
                    if chm == '6PEA' and i == 3: continue
                    self.browser.execute_script("add_chem()")
                    match = re.match('[0-9]+', chm)
                    site = match.group()
                    patch = chm[match.end():]
                    self.browser.select("chem[%d][residue]" % nchem, resname[1:])
                    self.browser.select("chem[%d][resid]" % nchem, i+1)
                    self.browser.select("chem[%d][site]" % nchem, site)
                    self.browser.select("chem[%d][patch]" % nchem, patch)
                    nchem += 1
        self.browser.execute_script("updateGPI()")
        self.browser.windows.current = self.browser.windows[0]

    def set_glycosylation(self):
        if not 'glycan' in self.test_case:
            raise ValueError("Missing glycosylation options")
        glyc_button = self.browser.find_by_id("glyc_checked").first
        if not glyc_button.checked:
            glyc_button.click()
        table = self.browser.find_by_id("id_glyc_table")
        for g in self.test_case['glycan']:
            if 'segid' in g:
                rows = table.find_by_id("glycan_{segid}".format(segid=g['segid'])).first
            else:
                self.browser.find_by_id("add_glycosylation").first.click()
                rows = table.find_by_tag("tr").last
            cols = rows.find_by_tag("td")[4]
            cols.find_by_value("edit").last.click()
            self.browser.windows.current = self.browser.windows[1]

            GRS_button = self.browser.find_by_value("Upload GRS").first
            GRS_field = self.browser.find_by_id("upload_GRS").first
            while not GRS_field.visible:
                GRS_button.click()
                time.sleep(1)

            GRS_field.fill(g['grs'])
            self.browser.find_by_id('apply_GRS').click()
            if g['type'] in ['n-linked', 'o-linked']:
                prot = ast.literal_eval(g['prot'])
                self.browser.select("sequence[0][name]", prot['segid'])
                self.browser.select("sequence[0][name2]", prot['resname'])
                self.browser.select("sequence[0][name3]", prot['resid'])
            self.browser.execute_script("seqUpdate()")
            self.browser.windows.current = self.browser.windows[0]

    def set_csml(self):
        if not 'hcr' in self.test_case:
            raise ValueError("Missing Hetero Chain options")
        pdb = self.pdb = self.test_case['pdb']
        pdb_id, pdb_fmt = pdb.split('.')
        hcrs = self.test_case['hcr']
        hid_fmt = "rename[{}]"
        csmlb_fmt = "openCSMLSearch('{}')"

        for csml_no, csml in enumerate(hcrs):
            hcr,name = csml.split()
            hid = hid_fmt.format(hcr)
            antc_fmt = "//input[@name='rename[{}]' and @value='antechamber']"
            cgen_fmt = "//input[@name='rename[{}]' and @value='cgenff']"
            ctop_fmt = "//input[@name='rename[{}]' and @value='charmm']"
            sdf_fmt = "//input[@name='rename_option[{}][{}]' and @value='sdf']"
            mol2_fmt = "//input[@name='rename_option[{}][{}]' and @value='mol2']"
            molup_fmt = "mol2_{}[{}]"
            sdfup_fmt = "sdf_{}[{}]"
            top_fmt = "top[{}]"
            par_fmt = "par[{}]"
            mfile_fmt = "{}.mol2"
            sfile_fmt = "{}.sdf"
            rtffile_fmt = "{}.rtf"
            prmfile_fmt = "{}.prm"
            ligfile = os.path.abspath(pjoin('files', self.test_case['ligand']))
            self.ligfile = ligfile

            if name == 'charmm':
                cgenid = cgen_fmt.format(hcr)
                self.browser.find_by_xpath(cgenid).first.click()
            elif name == 'antc':
                antcid = antc_fmt.format(hcr)
                self.browser.find_by_xpath(antcid).first.click()
            elif name == 'charmm_mol':
                cgen_opt = 'cgenff'
                cgenid = cgen_fmt.format(hcr)
                mol2id = mol2_fmt.format(cgen_opt, hcr)
                molupid = molup_fmt.format(cgen_opt, hcr)
                mfileid = mfile_fmt.format(hcr)
                molpath = pjoin(self.ligfile, mfileid)
                self.browser.find_by_xpath(cgenid).first.click()
                self.browser.find_by_xpath(mol2id).first.click()
                self.browser.attach_file(molupid, molpath)
            elif name == 'charmm_sdf':
                cgen_opt = 'cgenff'
                cgenid = cgen_fmt.format(hcr)
                sdfid = sdf_fmt.format(cgen_opt, hcr)
                sdfupid = sdfup_fmt.format(cgen_opt, hcr)
                sfileid = sfile_fmt.format(hcr)
                sdfpath = pjoin(self.ligfile, sfileid)
                self.browser.find_by_xpath(cgenid).first.click()
                self.browser.find_by_xpath(sdfid).first.click()
                self.browser.attach_file(sdfupid, sdfpath)
            elif name == 'antc_mol':
                cgen_opt = 'antechamber'
                antcid = antc_fmt.format(hcr)
                mol2id = mol2_fmt.format(cgen_opt, hcr)
                molupid = molup_fmt.format(cgen_opt, hcr)
                mfileid = mfile_fmt.format(hcr)
                molpath = pjoin(self.ligfile, mfileid)
                self.browser.find_by_xpath(antcid).first.click()
                self.browser.find_by_xpath(mol2id).first.click()
                self.browser.attach_file(molupid, molpath)
            elif name == 'antc_sdf':
                cgen_opt = 'antechamber'
                antcid = antc_fmt.format(hcr)
                sdfid = sdf_fmt.format(cgen_opt, hcr)
                sdfupid = sdfup_fmt.format(cgen_opt, hcr)
                sfileid = sfile_fmt.format(hcr)
                sdfpath = pjoin(self.ligfile, sfileid)
                self.browser.find_by_xpath(antcid).first.click()
                self.browser.find_by_xpath(sdfid).first.click()
                self.browser.attach_file(sdfupid, sdfpath)
            elif name == 'param':
                cid = csmlb_fmt.format(hcr)
                cid_button = self.browser.execute_script(cid)
                self.browser.windows.current = self.browser.windows[1]
                self.browser.find_by_css("div#options input[type=radio]").first.click()
                self.browser.find_by_id("nextBtn").first.click()
                self.browser.windows.current = self.browser.windows[0]
                cgenid = cgen_fmt.format(hcr)
                self.browser.find_by_xpath(cgenid).first.click()
            elif name == 'ctop_upload':
                cgen_opt = 'charmm'
                ctopid = ctop_fmt.format(hcr)
                topupid = top_fmt.format(hcr)
                parupid = par_fmt.format(hcr)
                topfid = rtffile_fmt.format(pdb_id)
                parfid = prmfile_fmt.format(pdb_id)
                toppath = pjoin(self.ligfile, topfid)
                parpath = pjoin(self.ligfile, parfid)
                self.browser.find_by_xpath(ctopid).first.click()
                self.browser.attach_file(topupid, toppath)
                self.browser.attach_file(parupid, parpath)
            else:
                hid_button = self.browser.find_by_name(hid)
                if not hid_button.checked:
                    hid_button.click()
                cid = csmlb_fmt.format(hcr)
                cid_button = self.browser.execute_script(cid)
                self.browser.windows.current = self.browser.windows[1]
                self.wait_text('residue name')
                self.browser.find_by_value(name).first.click()
                self.browser.find_by_id("nextBtn").first.click()
                self.browser.windows.current = self.browser.windows[0]

    def set_sdf(self):
        if not 'sdf' in self.test_case:
            raise ValueError("Missing sdf options")
        sdfid_fmt = "//input[@name='rename[{}]' and @value='cgenff']"
        rcsb_fmt = "//input[@name='rename_option[cgenff][{}]' and @value='rcsb']"

        for sdf in self.test_case['sdf']:
            sdfid = sdfid_fmt.format(sdf)
            sdf_button = self.browser.find_by_xpath(sdfid)
            if not sdf_button.checked:
                sdf_button.click()
            rcsb = rcsb_fmt.format(sdf)
            rcsb_button = self.browser.find_by_xpath(rcsb)
            if not rcsb_button.checked:
                rcsb_button.click()

    def set_symop(self):
        if not 'symop' in self.test_case:
            raise ValueError("Missing Symmetry options")
        symop_fmt = "{}_checked"

        for option in self.test_case['symop']:
            symop = symop_fmt.format(option)
            symop_button = self.browser.find_by_value(symop).first
            if not symop_button.checked:
               symop_button.click()

    def set_pstate(self):
        if not 'pstate' in self.test_case:
            raise ValueError("Missing Protonation State options")

        pstates = self.test_case['pstate']
        pstate_button = self.browser.find_by_id("prot_checked").first
        if not pstate_button.checked:
            pstate_button.click()
            add_btn = self.browser.find_by_value("Add Protonation")
            for pstate in pstates[1:]:
                add_btn.click()

        # set pstate options
        pstate_fmt = 'chain', 'res', 'rid', 'patch'
        id_fmt = 'prot_{}_{}'
        for pstate_no, pstate in enumerate(pstates):
            pstate = pstate.split()

            if len(pstate) != 4:
                raise ValueError("Invalid pstate format")

            for name, value in zip(pstate_fmt, pstate):
                psid = id_fmt.format(name, pstate_no)
                self.browser.find_by_id(psid).select(value)

    def set_ssbonds(self):
        if not 'ssbonds' in self.test_case:
            raise ValueError("Missing ssbond options")

        ssbonds = self.test_case['ssbonds']
        ssbond_button = self.browser.find_by_id("ssbonds_checked").first
        if not ssbond_button.checked:
            ssbond_button.click()
            add_btn = self.browser.find_by_value("Add Bonds")
            for ssbond in ssbonds[1:]:
                add_btn.click()

        # set ssbond options
        ssbond_fmt = 'chain1', 'resid1', 'chain2', 'resid2'
        id_fmt = 'ssbond_{}_{}'
        for ssbond_no, ssbond in enumerate(ssbonds):
            ssbond = ssbond.split()

            if len(ssbond) != 4:
                raise ValueError("Invalid sbond format")

            for name, value in zip(ssbond_fmt, ssbond):
                ssid = id_fmt.format(name, ssbond_no)
                self.browser.find_by_id(ssid).select(value)

    def set_hcoor(self):
        if not 'hcoor' in self.test_case:
            raise ValueError("Missing hcoor options")

        hcoors = self.test_case['hcoor']
        hcoor_button = self.browser.find_by_id("heme_checked").first
        if not hcoor_button.checked:
            hcoor_button.click()

        # set ssbond options
        hcoor_fmt = 'chain', 'res', 'rid'
        name_fmt = 'heme[{}][{}][]'
        for hcoor_no, hcoor in enumerate(hcoors):
            hcoor = hcoor.split()

            if len(hcoor) != 3:
                raise ValueError("Invalid hcoor format")

            for name, value in zip(hcoor_fmt, hcoor):
                hcname = name_fmt.format(hcoor_no, name)
                self.browser.find_by_name(hcname).select(value)

    def set_stapling(self):
        staples = self.test_case.get('staples')
        if staples == None:
            raise ValueError("Missing stapling options")

        # open stapling menu
        self.click('stapling_checked', 'Stapling Method')

        # add as many staples as needed
        add_btn = self.browser.find_by_value("Add Stapling")
        for staple in staples[1:]:
            add_btn.click()

        # set stapling options
        staple_fmt = 'type', 'chain1', 'rid1', 'chain2', 'rid2'
        id_fmt = 'stapling_{}_{}'
        for staple_no, staple in enumerate(staples):
            staple = staple.split()

            if len(staple) != 5:
                raise ValueError("Invalid staple format")

            for name, value in zip(staple_fmt, staple):
                sid = id_fmt.format(name, staple_no)
                self.browser.find_by_id(sid).select(value)

    def set_phosphorylation(self):
        phos = self.test_case.get('phosphorylation')
        if phos == None:
            raise ValueError("Missing phosphorylation options")

        phos_checked_elem = self.browser.find_by_id('phos_checked')
        phos_button = self.browser.find_by_value('Add Phosphorylation')

        # open phosphorylation menu
        phos_checked_elem.check()

        # add as many phosphorylations as needed
        for p in phos[1:]:
            phos_button.click()

        # set phosphorylation options; continue iteration as necessary
        phos_fmt = 'chain', 'res', 'rid', 'patch'
        id_fmt = 'phos_{}_{}'
        for phos_no, p in enumerate(phos):
            p = p.upper().split()

            if len(p) != len(phos_fmt):
                raise ValueError("Invalid phosphorylation format")

            for name, value in zip(phos_fmt, p):
                sid = id_fmt.format(name, phos_no)
                self.browser.find_by_id(sid).select(value)

    def set_term(self):
        if not 'terms' in self.test_case:
            raise ValueError("Missing terminal group ptaching")

        terms = self.test_case['terms']
        id_fmt = 'terminal[{}][{}]'
        terms_fmt = ['first', 'last']
        for term in terms:
            patchs = []
            term = term.split()
            patchs.append(term[0])
            if len(term) != 3:
                raise ValueError("Invaild terminal group patching format")
            for name,value in zip(terms_fmt,term[1:]):
                for patch in patchs:
                    tname = id_fmt.format(patch, name)
                    self.browser.find_by_name(tname).select(value)

    def set_lipid_tail(self):
        if not 'lipid_tails' in self.test_case:
            raise ValueError("Missing lipid tails")

        lipid_tails = self.test_case['lipid_tails']
        self.click('ltl_checked', 'Lipid-tail')
        add_btn = self.browser.find_by_value("Add Lipid-tail")
        for lipid_tail in lipid_tails[1:]:
            add_btn.click()

        ltl_fmt = 'patch', 'chain', 'res', 'rid'
        id_fmt = 'ltl_{}_{}'
        for ltl_no, lipid_tail in enumerate(lipid_tails):
            lipid_tail = lipid_tail.split()
            if len(lipid_tail) != 4:
                raise ValueError("Invaild lipid tail format")

            for name, value in zip(ltl_fmt, lipid_tail):
                lid = id_fmt.format(name, ltl_no)
                self.browser.find_by_id(lid).select(value)

    def set_fluo_label(self):
        if not 'fluo_labels' in self.test_case:
            raise ValueError("Missing fluorophore labels")

        fluo_labels = self.test_case['fluo_labels']
        self.click('ret_checked', 'Fluorophore label')
        add_btn = self.browser.find_by_value("Add fluorophore label")
        for fluo_label in fluo_labels[1:]:
            add_btn.click()

        fluo_fmt = 'patch', 'chain', 'res', 'rid'
        id_fmt = 'ret_{}_{}'
        for ret_no, fluo_label in enumerate(fluo_labels):
            fluo_label = fluo_label.split()
            if len(fluo_label) != 4:
                raise ValueError("Invalid fluorophore labels format")

            for name, value in zip(fluo_fmt, fluo_label):
               rid = id_fmt.format(name, ret_no)
               self.browser.find_by_id(rid).select(value)

    def set_llp(self):
        if not 'llps' in self.test_case:
            raise ValueError("Missing lbt-loops")
        llps = self.test_case['llps']
        self.click('lbt_checked', 'SEGID')
        add_btn = self.browser.find_by_value("Add Tb-binding site")
        for llp in llps[1:]:
            add_btn.click()
        llp_fmt = 'chain', 'res', 'atom', 'rid'
        id_fmt = 'lbt_{}_0_{}'
        for lbt_no, llp in enumerate(llps):
            llp = llp.split()
            if len(llp) != 4:
                raise ValueError("Invaild lbt-loops format")

            for name, value in zip(llp_fmt, llp):
                lid = id_fmt.format(name, lbt_no)
                self.browser.find_by_id(lid).select(value)

    def set_mts_nitride(self):
        if not 'mts_nitrides' in self.test_case:
            raise ValueError("Missing MTS regents: nitroxide spin labels")

        mts_nitrides = self.test_case['mts_nitrides']
        self.click('epr_checked', 'Spin label')
        add_btn = self.browser.find_by_value("Add spin label")
        for mts_nitride in mts_nitrides[1:]:
            add_btn.click()

        epr_fmt ='patch', 'chain', 'res', 'rid'
        id_fmt = 'epr_{}_{}'
        for epr_no, mts_nitride in enumerate(mts_nitrides):
            mts_nitride = mts_nitride.split()
            if len(mts_nitride) != 4:
                raise ValueError("Invalid MTS reagents (nitroxide) format")
            for name, value in zip(epr_fmt, mts_nitride):
                eid = id_fmt.format(name, epr_no)
                self.browser.find_by_id(eid).select(value)

    def set_mts_modifier(self):
        if not 'mts_modifiers' in self.test_case:
            raise ValueError("Missing MTS regents: chemical modifier")

        mts_modifiers = self.test_case['mts_modifiers']
        self.click('mts_checked', 'MTS reagent')
        add_btn = self.browser.find_by_value("Add MTS reagent")
        for mts_modifier in mts_modifiers[1:]:
            add_btn.click()

        mts_fmt ='patch', 'chain', 'res', 'rid'
        id_fmt = 'mts_{}_{}'
        for mts_no, mts_modifier in enumerate(mts_modifiers):
            mts_modifier = mts_modifier.split()
            if len(mts_modifier) != 4:
                raise ValueError("Invalid MTS reagents (modifier) format")
            for name, value in zip(mts_fmt, mts_modifier):
                mid = id_fmt.format(name, mts_no)
                self.browser.find_by_id(mid).select(value)

    def set_uaa(self):
        if not 'uaas' in self.test_case:
            raise ValueError("Missing Unnatural amino acid substitution")

        uaas = self.test_case['uaas']
        self.click('uaa_checked', 'Unnatural amino acid')
        add_btn = self.browser.find_by_value("more substitution")
        for uaa in uaas[1:]:
            add_btn.click()

        uaa_fmt ='patch', 'chain', 'res', 'rid'
        id_fmt = 'uaa_{}_{}'
        for uaa_no, uaa in enumerate(uaas):
            uaa = uaa.split()
            if len(uaa) != 4:
                raise ValueError("Invalid unnatural amino acid format")
            for name, value in zip(uaa_fmt, uaa):
                uid = id_fmt.format(name, uaa_no)
                self.browser.find_by_id(uid).select(value)

    def set_bio(self):
        click_btn = self.browser.find_by_value("biomat_checked")
        click_btn.click()

    def set_crystal_packing(self):
        click_btn = self.browser.find_by_value("crystal_checked")
        click_btn.click()

    def set_unit_cell(self):
        click_btn = self.browser.find_by_value("unitcell_checked")
        click_btn.click()

    def rid_select(self):
        if not 'rids' in self.test_case:
            raise ValueError("Missing residue id")

        rids = self.test_case['rids']
        name_fmt = 'chains[{}][{}]'
        terms_fmt = ['first', 'last']
        for rid in rids:
            chain_ids = []
            rid = rid.split()
            chain_ids.append(rid[0])
            if len(rid) != 3:
                raise ValueError("Invaild residue id selection format")
            for term, value in zip(terms_fmt, rid[1:]):
                for i in chain_ids:
                    tname = name_fmt.format(i, term)
                    self.browser.find_by_name(tname).fill(value)

    def chain_select(self):
        if not 'chains' in self.test_case:
            raise ValueError("Missing chains")

        chains = self.test_case['chains']
        print(chains)

        # shortcut for selecting all chains
        if isinstance(chains, str) and chains.lower() == 'all':
            # returns all unchecked chain selection buttons
            pattern = 'input[type=checkbox][name$="[checked]"]:not(:checked)'
            buttons = self.browser.find_by_css(pattern)

            for button in buttons:
                button.check()
        else:
            name_fmt = 'chains[{}][checked]'
            for chain in chains:
                name_chain = name_fmt.format(chain)
                click_btn = self.browser.find_by_name(name_chain)
                click_btn.click()
    def test_glycosylation(self):
        if 'reference' in self.test_case:
            print('pdbid: %s' % self.pdb)
            reference = self.test_case['reference']
            for ref in reference:
                segid = ref['segid']
                grs = ref['grs'].strip()
                value = self.browser.find_by_name('glycan[%s][grs]' % segid).value
                assert grs == value, "{segid} GRS value is not correct during benchmark test, grs:{grs}, value:{value}".format(segid=segid, grs=str([grs]), value=str(value))

    def init_system(self, test_case, resume=False):
        module_title = self.module_title
        url = self.base_url + self.module_url
        browser = self.browser

        pdb = self.pdb = test_case['pdb']

        if not resume:
            browser.visit(url)
            # infer as much as possible about the PDB format
            if isinstance(pdb, dict):
                if 'format' in pdb:
                    pdb_fmt = pdb['format']
                else:
                    pdb_fmt = pdb['name'].split('.')[-1]

                source = 'source' in pdb and pdb['source']
                pdb_name = test_case['pdb']['name']
            else:
                pdb_name = test_case['pdb']
                pdb_fmt = '.' in pdb_name and pdb_name.split('.')[-1]
                source = not pdb_fmt and 'RCSB'

            if pdb_fmt:
                pdb_fmt = {
                    'pdb': 'PDB',
                    'pqr': 'PDB',
                    'cif': 'mmCIF',
                    'charmm': 'CHARMM',
                }[pdb_fmt]

            if source and self.name.split('-')[-1] != '1':
                reason = "Multithreading is not allowed for "+module_title+\
                         " when downloading from RCSB/OPM. Please use an"\
                         " upload option instead."
                self.stop(reason)

            if source:
                browser.fill('pdb_id', pdb_name)
                browser.select('source', 'RCSB')
            else:
                pdb_path = pjoin(self.base, pdb_name)
                browser.attach_file("file", pdb_path)
                browser.find_by_value(pdb_fmt).click()

            self.go_next(test_case['steps'][0]['wait_text'])

            jobid = browser.find_by_css(".jobid").first.text.split()[-1]
            test_case['jobid'] = jobid
