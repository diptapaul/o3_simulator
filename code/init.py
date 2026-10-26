# Qing 
# 21st May 2017 
# Modified: input-file parser and issue width support

import re
from collections import namedtuple

'''define data types'''
# reservation station 
def rs_entry():
    rs_entry = namedtuple('rs_entry', 'busy, op, tag_1st, value_1st, valid_1st, tag_2nd, value_2nd, valid_2nd, dest_tag')
    temp = rs_entry
    return temp 
# functional unit 
def fu_entry():
    fu_entry = namedtuple('fu_entry', 'cycle, op, value1, value2, dest_tag')
    temp = fu_entry
    return temp
# function result 
def fu_result():
    fu_result = namedtuple('fu_result', 'value, dest_tag')
    temp = fu_result
    return temp
# ld/sd entry
def ld_sd_entry():
    ld_sd_entry = namedtuple('ld_sd_entry', 'ld_sd_tag, ready, op, address, data, dest_tag, immediate, reg_tag, reg_value, valid, in_exe')
    temp = ld_sd_entry
    temp.in_exe = 0
    return temp
# ld/sd exe (one address adder)
def ld_sd_exe():
    ld_sd_exe = namedtuple('ld_sd_exe', 'busy, cycle, value1, value2, dest_tag')
    temp = ld_sd_exe
    return temp
# ld/sd mem
def ld_sd_mem():
    ld_sd_mem = namedtuple('ld_sd_mem', 'busy, cycle, op, data, address, dest_tag')
    temp = ld_sd_mem
    return temp
# cdb
def cdb():
    cdb = namedtuple('cdb', 'valid, value, dest_tag')
    temp = cdb
    return temp
# ROB_entry 
def ROB_entry():
    ROB_entry = namedtuple('ROB_entry', 'ROB_tag, PC, value, dest_tag, issue, exe, mem, cdb, commit')
    temp = ROB_entry
    temp.issue = []
    temp.exe = []
    temp.mem = []
    temp.cdb = []
    temp.commit =[]
    return temp
# PC 
def PC():
    PC = namedtuple('PC', 'PC, valid')
    temp = PC
    return temp

# function: read instructions (plain list of instructions, one per line)
def read_instruction(codefile):
    instructions = []
    with open(codefile) as f:
        for line in f.read().splitlines():
            if line.strip() != '':
                instructions.append(normalize_instruction(line))
    return instructions

# function: build rs
def build_rs(num):
    rs = []
    for _ in range(num):
        temp = rs_entry()
        temp.busy = 0
        rs.extend([temp])
    return rs

'''input file parsing (new)'''
# op codes as they are written inside the simulator (the input is case insensitive)
OPCODES = {'ld': 'Ld', 'sd': 'Sd', 'beq': 'Beq', 'bne': 'Bne',
           'add': 'Add', 'add.d': 'Add.d', 'addi': 'Addi',
           'sub': 'Sub', 'sub.d': 'Sub.d', 'mult.d': 'Mult.d'}

# hardware unit names in the configuration table and their keys in the config
UNIT_NAMES = [('integer adder', 'int_adder'), ('fp adder', 'fp_adder'),
              ('fp multiplier', 'fp_multi'), ('load/store unit', 'ld_sd')]

# function: convert one assembly line to the internal format "Op A B C"
# (operands may be separated by commas and/or spaces)
def normalize_instruction(line):
    insParts = line.replace(',', ' ').split()
    opName = insParts[0].lower()

    if opName not in OPCODES:
        raise ValueError('unknown instruction: ' + line)

    insParts[0] = OPCODES[opName]
    for i in range(1, len(insParts)):
        insParts[i] = insParts[i].upper()   # r1 -> R1, 0(r1) -> 0(R1)

    return ' '.join(insParts)

# function: instruction text for the output table, e.g. "Ld F4, 8(R1)"
def get_printed_instruction(ins):
    insParts = ins.split(' ')
    return insParts[0] + ' ' + ', '.join(insParts[1:])

# function: number from text, float if it has a decimal point
def get_number(text):
    text = text.strip()
    if ('.' in text) or ('e' in text.lower()):
        return float(text)
    return int(text)

# function: find which hardware unit a configuration line describes
def get_unit_key(lowLine):
    for unitName, unitKey in UNIT_NAMES:
        if lowLine.startswith(unitName):
            return unitName, unitKey
    return None, None

# function: read the whole input file (hardware configuration, issue width,
# initial registers / memory and the program)
def read_input(filename):
    config = {
        'int_adder': {'rs': 2, 'ex': 1, 'fu': 1},
        'fp_adder': {'rs': 3, 'ex': 3, 'fu': 1},
        'fp_multi': {'rs': 2, 'ex': 20, 'fu': 1},
        'ld_sd': {'rs': 3, 'ex': 1, 'mem': 4, 'fu': 1},
        'rob': 128,
        'issue_width': 1,      # default issue width
        'cdb': 1,              # one CDB
        'reg_int': {}, 'reg_fp': {}, 'memory': {},
        'instructions': [],
    }

    with open(filename) as f:
        fileLines = f.read().splitlines()

    for rawLine in fileLines:
        if rawLine.strip().startswith('#'):
            rawLine = rawLine.split('#')[0]
        lineText = rawLine.strip()
        lowLine = lineText.lower()

        if lineText == '':
            continue

        # table header ("# of rs  Cycles in EX ...")
        if ('of rs' in lowLine) or ('cycles in' in lowLine):
            continue

        # hardware unit: # of rs, cycles in EX, (cycles in Mem), # of FUs
        unitName, unitKey = get_unit_key(lowLine)
        if unitKey is not None:
            unitVals = []
            for val in re.findall(r'-?\d+', lowLine[len(unitName):]):
                unitVals.append(int(val))

            unitCfg = config[unitKey]
            unitCfg['rs'] = unitVals[0]
            unitCfg['ex'] = unitVals[1]
            if unitKey == 'ld_sd':
                unitCfg['mem'] = unitVals[2]
                if len(unitVals) > 3:
                    unitCfg['fu'] = unitVals[3]
            else:
                if len(unitVals) > 2:
                    unitCfg['fu'] = unitVals[2]
            continue

        if lowLine.startswith('rob entries'):
            config['rob'] = int(lowLine.split('=')[1])
            continue

        if lowLine.startswith('issue width'):
            issueWidth = int(lowLine.split('=')[1])
            if issueWidth < 1 or issueWidth > 4:
                raise ValueError('Issue width must be between 1 and 4')
            config['issue_width'] = issueWidth
            continue

        if lowLine.startswith('cdb'):
            config['cdb'] = int(lowLine.split('=')[1])
            continue

        # memory: Mem[4]=1, Mem[8]=2
        if lowLine.startswith('mem['):
            for memAddr, memVal in re.findall(r'mem\[\s*(\d+)\s*\]\s*=\s*([-+.\deE]+)', lowLine):
                config['memory'][int(memAddr)] = get_number(memVal)
            continue

        # registers: R1=10, R2=20, F2=30.1
        if re.match(r'^[rf]\d+\s*=', lowLine):
            for regName, regVal in re.findall(r'([rf]\d+)\s*=\s*([-+.\deE]+)', lowLine):
                regNum = int(regName[1:])
                if regName[0] == 'r':
                    if '.' in regVal:
                        config['reg_int'][regNum] = float(regVal)
                    else:
                        config['reg_int'][regNum] = int(float(regVal))
                else:
                    config['reg_fp'][regNum] = float(regVal)
            continue

        # everything else is an instruction
        config['instructions'].append(normalize_instruction(lineText))

    return config
