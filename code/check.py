# Correctness checker for the simulator (used by run_tests.py)
#  1. functional check: final registers and memory must equal a simple
#     one-instruction-at-a-time reference model
#  2. timing check: rules of an in-order-issue / in-order-commit machine
import re
from init import read_input


# function: execute the program sequentially (no pipeline) and return the final state
def get_reference_state(input_file):
    config = read_input(input_file)

    regInt = [0] * 32
    regFp = [0] * 32
    memory = [0] * 256
    for regNum, regVal in config['reg_int'].items():
        if regNum != 0:
            regInt[regNum] = regVal
    for regNum, regVal in config['reg_fp'].items():
        regFp[regNum] = regVal
    for memAddr, memVal in config['memory'].items():
        memory[memAddr] = memVal

    def get_reg(regName):
        if regName[0] == 'R':
            return regInt[int(regName[1:])]
        return regFp[int(regName[1:])]

    def set_reg(regName, val):
        if regName[0] == 'R':
            if int(regName[1:]) != 0:
                regInt[int(regName[1:])] = val
        else:
            regFp[int(regName[1:])] = val

    program = config['instructions']
    pc = 0
    nSteps = 0
    pcTrace = []

    while pc < len(program):
        insParts = program[pc].split(' ')
        opName = insParts[0]
        pcTrace.append(pc)
        nextPc = pc + 1

        if (opName == 'Ld') | (opName == 'Sd'):
            m = re.match(r'(-?\d+)\((R\d+)\)', insParts[2])
            memAddr = int(m.group(1)) + get_reg(m.group(2))
            if opName == 'Ld':
                set_reg(insParts[1], memory[memAddr])
            else:
                memory[memAddr] = get_reg(insParts[1])
        elif (opName == 'Bne') | (opName == 'Beq'):
            isEqual = (get_reg(insParts[1]) == get_reg(insParts[2]))
            if (opName == 'Beq' and isEqual) or (opName == 'Bne' and not isEqual):
                nextPc = pc + 1 + int(insParts[3])
        elif opName == 'Addi':
            set_reg(insParts[1], get_reg(insParts[2]) + int(insParts[3]))
        elif (opName == 'Add') | (opName == 'Add.d'):
            set_reg(insParts[1], get_reg(insParts[2]) + get_reg(insParts[3]))
        elif (opName == 'Sub') | (opName == 'Sub.d'):
            set_reg(insParts[1], get_reg(insParts[2]) - get_reg(insParts[3]))
        elif opName == 'Mult.d':
            set_reg(insParts[1], get_reg(insParts[2]) * get_reg(insParts[3]))

        pc = nextPc
        nSteps += 1
        if nSteps > 100000:
            raise RuntimeError('reference: infinite loop')

    return regInt, regFp, memory, pcTrace


# function: read the cycle numbers of every row of the status table
def get_table_rows(status_rows):
    tableRows = []
    for line in status_rows:
        insName = line[:30].strip()
        cycleLists = []
        for listText in re.findall(r'\[([^\]]*)\]', line[30:]):
            cycles = []
            for val in listText.split(','):
                if val.strip() != '':
                    cycles.append(int(val))
            cycleLists.append(cycles)
        tableRows.append({'name': insName, 'issue': cycleLists[0], 'exe': cycleLists[1],
                          'mem': cycleLists[2], 'wb': cycleLists[3], 'commit': cycleLists[4]})
    return tableRows


# function: count how many times each value appears
def get_counts(values):
    counts = {}
    for val in values:
        if val in counts:
            counts[val] += 1
        else:
            counts[val] = 1
    return counts


# function: returns a list of error strings (empty list = everything correct)
def check(input_file, result):
    errors = []
    regInt, regFp, memory, pcTrace = get_reference_state(input_file)

    # ---- functional check
    if result['reg_int'] != regInt:
        errors.append('integer registers differ from reference')
    for i in range(32):
        if abs(result['reg_fp'][i] - regFp[i]) > 1e-9:
            errors.append('FP registers differ from reference')
            break
    for i in range(256):
        if abs(result['memory'][i] - memory[i]) > 1e-9:
            errors.append('memory differs from reference')
            break

    tableRows = get_table_rows(result['status'])
    program = result['config']['instructions']
    if len(tableRows) != len(pcTrace):
        errors.append('committed %d instructions, reference executed %d' % (len(tableRows), len(pcTrace)))
        return errors

    issueWidth = result['issue_width']
    nCdb = result['config']['cdb']

    # ---- timing check
    for k in range(len(tableRows)):
        row = tableRows[k]
        opName = program[pcTrace[k]].split(' ')[0]
        iss = row['issue'][0]
        ex = row['exe']
        mm = row['mem']
        wb = row['wb']
        com = row['commit'][0]
        tag = '#%d %s' % (k + 1, row['name'])

        if len(ex) != 2 or ex[0] <= iss or ex[1] < ex[0]:
            errors.append(tag + ': EX must start after ISSUE')

        if opName == 'Ld':
            if len(mm) == 0 or mm[0] <= ex[1]:
                errors.append(tag + ': MEM must start after EX')
            if len(wb) == 0 or wb[0] <= mm[-1]:
                errors.append(tag + ': WB must be after MEM')
        elif opName == 'Sd':
            if len(mm) == 0 or mm[0] <= ex[1] or com != mm[0]:
                errors.append(tag + ': Sd commits when it starts MEM, after EX')
        elif (opName == 'Bne') | (opName == 'Beq'):
            if com <= ex[1]:
                errors.append(tag + ': branch commits after it is resolved')
        else:
            if len(wb) == 0 or wb[0] <= ex[1]:
                errors.append(tag + ': WB must be after EX')

        if (opName != 'Sd') & (opName != 'Bne') & (opName != 'Beq'):
            if com <= wb[0]:
                errors.append(tag + ': COMMIT must be after WB')

        if k > 0:
            if iss < tableRows[k - 1]['issue'][0]:
                errors.append(tag + ': issued out of program order')
            if com < tableRows[k - 1]['commit'][0]:
                errors.append(tag + ': committed out of program order')

    # the instruction after a branch is issued only after the branch is resolved
    for k in range(len(pcTrace) - 1):
        opName = program[pcTrace[k]].split(' ')[0]
        if (opName == 'Bne') | (opName == 'Beq'):
            if tableRows[k + 1]['issue'][0] <= tableRows[k]['exe'][1]:
                errors.append('#%d issued before the branch was resolved' % (k + 2))

    # per cycle limits: issue width, commit width, one result per CDB
    issueCycles = []
    commitCycles = []
    wbCycles = []
    for row in tableRows:
        issueCycles.append(row['issue'][0])
        commitCycles.append(row['commit'][0])
        if len(row['wb']) > 0:
            wbCycles.append(row['wb'][0])

    limitChecks = [('issued', get_counts(issueCycles), issueWidth),
                   ('committed', get_counts(commitCycles), issueWidth),
                   ('written back', get_counts(wbCycles), nCdb)]
    for what, counts, limit in limitChecks:
        for cyc in counts:
            if counts[cyc] > limit:
                errors.append('cycle %d: %d instructions %s (limit %d)' % (cyc, counts[cyc], what, limit))

    # single-ported memory: memory accesses (2-value MEM entries) never overlap
    memSpans = []
    for row in tableRows:
        if len(row['mem']) == 2:
            memSpans.append((row['mem'][0], row['mem'][1]))
    memSpans.sort()
    for k in range(1, len(memSpans)):
        if memSpans[k][0] <= memSpans[k - 1][1]:
            errors.append('memory port used by two accesses in cycle %d' % memSpans[k][0])

    return errors
