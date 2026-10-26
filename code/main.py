# Qing 
# 21st May 2017 
# Modified: configuration is read from the input file, multi-issue (1-4, in order),
#           register / memory output
#
# usage:  python3 main.py [input_file] [issue_width]
#   input_file   default: test_case.txt
#   issue_width  optional, overrides "Issue width = N" in the input file

import sys
from copy import deepcopy
from collections import deque, namedtuple
from init import read_input, build_rs, ld_sd_entry, ld_sd_exe, ld_sd_mem, cdb, ROB_entry, PC
from print_status import ps, pss
from issue import issue, check_rs_space
from exe import exe 
from mem import mem
from wb import wb 
from commit import commit


def run(input_file, issue_width=None, quiet=False):
    '''initialize'''
    config = read_input(input_file)
    if issue_width is not None:
        if issue_width < 1 or issue_width > 4:
            raise ValueError('Issue width must be between 1 and 4')
        config['issue_width'] = issue_width
    issue_width = config['issue_width']

    # read instructions into a list 
    instructions = config['instructions']

    '''initialize regs, RAT, memory''' 
    # integer REG
    reg_int = [0] * 32
    for regNum, regVal in config['reg_int'].items():
        if regNum != 0:                     # R0 is hardwired to 0
            reg_int[regNum] = regVal
    rat_int = deepcopy(reg_int)

    # fp REG
    reg_fp = [0] * 32
    for regNum, regVal in config['reg_fp'].items():
        reg_fp[regNum] = regVal
    rat_fp = deepcopy(reg_fp)

    # memory: 256 B
    memory = [0] * 256
    for memAddr, memVal in config['memory'].items():
        memory[memAddr] = memVal

    '''intialize reservation stations'''
    rs_int_adder = build_rs(config['int_adder']['rs'])
    rs_fp_adder = build_rs(config['fp_adder']['rs'])
    rs_fp_multi = build_rs(config['fp_multi']['rs'])

    '''initilize function unit'''
    fu_int_adder = deque()
    time_fu_int_adder = config['int_adder']['ex']
    fu_fp_adder = deque()
    time_fu_fp_adder = config['fp_adder']['ex']
    fu_fp_multi = deque()
    time_fu_fp_multi = config['fp_multi']['ex']
    numFu = {'int_adder': config['int_adder']['fu'],
             'fp_adder': config['fp_adder']['fu'],
             'fp_multi': config['fp_multi']['fu']}

    '''initialize load/store queue'''
    ld_sd_queue = deque()
    size_ld_sd_queue = config['ld_sd']['rs']

    # one address adder per load/store FU
    addrUnits = []
    for _ in range(config['ld_sd']['fu']):
        addrUnit = ld_sd_exe()
        addrUnit.busy = 0
        addrUnits.append(addrUnit)
    time_ld_sd_exe = config['ld_sd']['ex']

    # memory is single ported
    memUnit = ld_sd_mem()
    memUnit.busy = 0
    time_ld_sd_mem = config['ld_sd']['mem']

    '''initialize ROB'''
    ROB = deque()
    size_ROB = config['rob']

    '''initialize CDB'''
    results_buffer = deque()
    cdbList = []
    for _ in range(config['cdb']):
        bus = cdb()
        bus.valid = 0
        cdbList.append(bus)

    """issue first instruction"""
    # instruction pointer 
    pc = PC()
    pc.PC = 0
    pc.valid = 1 
    cycle = 1
    statusRows = []

    # main: run until every instruction is committed and the last store reached memory
    while (len(ROB)>0) | ((pc.PC<len(instructions)) & (pc.valid==1)) | (cycle==1) \
            | (memUnit.busy==1) | (len(ld_sd_queue)>0):

        '''ISSUE stage (up to issue_width instructions, in order)'''
        if (pc.PC<len(instructions))&(pc.valid==1):
            issue(cycle, pc, instructions, ROB, size_ROB, 
                    rs_int_adder, 
                    rs_fp_adder, 
                    rs_fp_multi, 
                    ld_sd_queue, size_ld_sd_queue, 
                    rat_int, rat_fp, issue_width)

        '''EXE stage'''
        exe(fu_int_adder, time_fu_int_adder, 
            fu_fp_adder, time_fu_fp_adder, 
            fu_fp_multi, time_fu_fp_multi, results_buffer,  
            rs_int_adder, rs_fp_adder, rs_fp_multi, 
            addrUnits, time_ld_sd_exe, ld_sd_queue,
            cycle, ROB, pc, numFu)

        '''MEM stage'''
        mem(ld_sd_queue, memUnit, time_ld_sd_mem, results_buffer,
            memory, ROB, cycle)

        '''CDB stage'''
        wb(cdbList, rat_int, rat_fp, 
            rs_int_adder, rs_fp_adder, rs_fp_multi,
            ld_sd_queue, ROB, cycle,
            results_buffer) 
        
        '''COMMIT stage (up to issue_width instructions, in order)'''
        commit(ROB, reg_int, reg_fp, cycle, instructions, issue_width, statusRows)
        
        # cycle number 
        cycle +=1  
        if cycle > 100000:
            raise RuntimeError('simulation did not finish (infinite loop in the program?)')

    result = {'status': statusRows, 'reg_int': reg_int, 'reg_fp': reg_fp,
              'memory': memory, 'cycles': cycle - 1, 'issue_width': issue_width,
              'config': config}
    if not quiet:
        print_results(result)
    return result


# function: value text for the output (4 decimals at most, no trailing zeros)
def get_value_text(value):
    if isinstance(value, float):
        if value == int(value):
            return str(value)
        valText = '%.4f' % value
        valText = valText.rstrip('0').rstrip('.')
        return valText
    return str(value)


def print_results(result):
    print('Issue width = ' + str(result['issue_width']))
    print()

    # print title 
    item = ''.ljust(30)
    item += 'ISSUE'.ljust(15)
    item += 'EX'.ljust(15)
    item += 'MEM'.ljust(15)
    item += 'WB'.ljust(15)
    item += 'COMMIT'.ljust(15)
    print(item)
    for row in result['status']:
        print(row)
    print()

    # registers, 8 per line
    print('REGISTER VALUES')
    for regPrefix, regVals in (('R', result['reg_int']), ('F', result['reg_fp'])):
        for start in range(0, 32, 8):
            nameLine = '        '
            valLine = 'value:  '
            for i in range(start, start + 8):
                nameLine += (regPrefix + str(i)).ljust(9)
                valLine += get_value_text(regVals[i]).ljust(9)
            print(nameLine)
            print(valLine)
    print()

    print('NON-ZERO MEMORY VALUES')
    print('Addresses'.ljust(15) + 'Values')
    memory = result['memory']
    for memAddr in range(len(memory)):
        if memory[memAddr] != 0:
            print(str(memAddr).ljust(15) + get_value_text(memory[memAddr]))


if __name__ == '__main__':
    inputFile = 'test_case.txt'
    issueWidth = None
    if len(sys.argv) > 1:
        inputFile = sys.argv[1]
    if len(sys.argv) > 2:
        issueWidth = int(sys.argv[2])
    run(inputFile, issueWidth)
