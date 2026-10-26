# Qing 
# 24th May 2017
# Modified: oldest-first dispatch, multiple FUs per type, Beq,
#           no double advance of a FU in one cycle, multi-cycle address calculation

''' 
1. calculate valid instructions
    -- for ALU instructions, write results into fu_results, remove that fu entry  
    -- for LD/SD, write address result immediately back to ld_sd_queue
2. fetch instructions into function unit with spare space
    -- remove ALU instructions from rs
    -- don't remove ld/sd instructions
'''
from init import fu_entry, fu_result

# function: find ROB entry by tag
def find_ROB_entry(ROB, tag):
    for index in range(len(ROB)):
        if ROB[index].ROB_tag == tag:
            break
    return index

# function: check rs and return the indices of valid (ready) instructions,
# oldest instruction first (position in the ROB = program order)
def check_valid_ins_in_rs(rs, ROB):
    readyList = []
    for i in range(len(rs)):
        if (rs[i].valid_1st==1)&(rs[i].valid_2nd==1)&(rs[i].busy==1):
            robPos = find_ROB_entry(ROB, rs[i].dest_tag)
            readyList.append((robPos, i))

    readyList.sort()

    readyIdx = []
    for robPos, rsIdx in readyList:
        readyIdx.append(rsIdx)
    return readyIdx

# function: check ld_sd_queue and return valid instruction index
# (queue is in program order; skip entries already in an address adder)
def check_valid_ins_in_ldsd(ldsd):
    index = -1
    if len(ldsd)!=0:
        for i in range(len(ldsd)):
            if (ldsd[i].valid==1) & (ldsd[i].ready==0) & (ldsd[i].in_exe==0):
                index = i
                break
    return index

# function: add entry into fu 
def add_entry_into_fu(fu, ins_in_rs):
    fu[-1].cycle = 0
    fu[-1].op = ins_in_rs.op
    fu[-1].value1 = ins_in_rs.value_1st
    fu[-1].value2 = ins_in_rs.value_2nd
    fu[-1].dest_tag = ins_in_rs.dest_tag

# function: functional units execution 
# advance every entry in "entries" (default: all entries of the fu) by one cycle;
# an entry is advanced at most once per cycle
def fu_exe(fu, fu_results, ROB, time_fu, cycle, PC, entries=None):
    if len(fu)==0:
        return

    if entries is None:
        entries = list(fu)

    for element in entries:
        element.cycle += 1
        # write starting cycle 
        if element.cycle == 1:
            index = find_ROB_entry(ROB, element.dest_tag)
            ROB[index].exe.append(cycle)

    # finished entries, in program order inside the unit
    doneList = []
    for element in fu:
        if element.cycle == time_fu:
            doneList.append(element)

    for element in doneList:
        index = find_ROB_entry(ROB, element.dest_tag)
        ROB[index].exe.append(cycle)

        if (element.op=='Bne')|(element.op=='Beq'):
            # branch is resolved at the end of EX
            brPC = ROB[index].PC
            brOffset = ROB[index].dest_tag
            isEqual = (element.value1 == element.value2)
            if element.op == 'Beq':
                isTaken = isEqual
            else:
                isTaken = not isEqual

            # PC + 4 + offset<<2  ->  instruction index PC + 1 + offset
            if isTaken:
                PC.PC = brPC + 1 + brOffset
            else:
                PC.PC = brPC + 1
            if PC.PC < 0:
                raise ValueError('branch target before the first instruction')
            PC.valid = 1
        else:
            # calculation result
            fu_results.append(fu_result())
            fu_results[-1].dest_tag = element.dest_tag
            if (element.op=='Add')|(element.op=='Add.d')|(element.op=='Addi'):
                fu_results[-1].value = element.value1 + element.value2
            elif (element.op=='Sub')|(element.op=='Sub.d'):
                fu_results[-1].value = element.value1 - element.value2
            elif (element.op=='Mult.d'):
                fu_results[-1].value = element.value1 * element.value2

        # remove from fu 
        fu.remove(element)

# function: ld_sd_execution (one address adder)
def ld_sd_execution(ld_sd_exe, time_ld_sd_exe, ld_sd_queue, ROB, cycle):
    if ld_sd_exe.busy == 0:
        return

    for element in ld_sd_queue:
        if element.ld_sd_tag == ld_sd_exe.dest_tag:
            break

    ld_sd_exe.cycle += 1

    # write down starting cycle
    if ld_sd_exe.cycle == 1:
        index = find_ROB_entry(ROB, element.dest_tag)
        ROB[index].exe.append(cycle)

    # write address back to ld_sd_queue
    if ld_sd_exe.cycle == time_ld_sd_exe:
        element.address = ld_sd_exe.value1 + ld_sd_exe.value2
        element.ready = 1
        element.in_exe = 0
        # write down finish cycle
        index = find_ROB_entry(ROB, element.dest_tag)
        ROB[index].exe.append(cycle)
        ld_sd_exe.busy = 0

# function: move ready instructions from a reservation station into its FU
# num_fu FUs per type; a pipelined FU accepts 1 new instruction per cycle,
# an unpipelined FU only when it is empty
def dispatch_rs(rs, fu, time_fu, num_fu, pipelined, results_buffer, ROB, cycle, PC):
    if pipelined:
        nFree = num_fu
    else:
        nFree = num_fu - len(fu)
    if nFree < 0:
        nFree = 0

    readyIdx = check_valid_ins_in_rs(rs, ROB)
    nDispatch = min(nFree, len(readyIdx))

    for k in range(nDispatch):
        index = readyIdx[k]
        fu.append(fu_entry())
        add_entry_into_fu(fu, rs[index])

        # waiting instruction (issued in an earlier cycle) starts now
        if ROB[find_ROB_entry(ROB, rs[index].dest_tag)].issue[0] < cycle:
            fu_exe(fu, results_buffer, ROB, time_fu, cycle, PC, entries=[fu[-1]])

        # remove ins from rs 
        rs[index].busy = 0

# function: execution
def exe(fu_int_adder, time_fu_int_adder,
        fu_fp_adder, time_fu_fp_adder,
        fu_fp_multi, time_fu_fp_multi, results_buffer,
        rs_int_adder, rs_fp_adder, rs_fp_multi, 
        ld_sd_exe, time_ld_sd_exe, ld_sd_queue,
        cycle, ROB, PC, num_fu=None):
    if num_fu is None:
        num_fu = {'int_adder': 1, 'fp_adder': 1, 'fp_multi': 1}
    if not isinstance(ld_sd_exe, list):
        ld_sd_exe = [ld_sd_exe]

    '''execution in fu and ld_sd address calculation'''
    for addrUnit in ld_sd_exe:
        ld_sd_execution(addrUnit, time_ld_sd_exe, ld_sd_queue, ROB, cycle) 

    # functional units 
    fu_exe(fu_int_adder, results_buffer, ROB, time_fu_int_adder, cycle, PC)
    fu_exe(fu_fp_adder, results_buffer, ROB, time_fu_fp_adder, cycle, PC)
    fu_exe(fu_fp_multi, results_buffer, ROB, time_fu_fp_multi, cycle, PC)

    '''fetch instructions from rs and ld_sd_queue'''
    # from ld_sd_queue: one instruction per free address adder
    for addrUnit in ld_sd_exe:
        if addrUnit.busy == 1:
            continue

        index = check_valid_ins_in_ldsd(ld_sd_queue)
        if index < 0:
            break

        addrUnit.busy = 1
        addrUnit.cycle = 0
        addrUnit.value1 = ld_sd_queue[index].reg_value
        addrUnit.value2 = ld_sd_queue[index].immediate
        addrUnit.dest_tag = ld_sd_queue[index].ld_sd_tag
        ld_sd_queue[index].in_exe = 1

        if ROB[find_ROB_entry(ROB, ld_sd_queue[index].dest_tag)].issue[0] < cycle:
            ld_sd_execution(addrUnit, time_ld_sd_exe, ld_sd_queue, ROB, cycle)

    # from rs (integer adder is unpipelined, FP adder and multiplier are pipelined)
    dispatch_rs(rs_int_adder, fu_int_adder, time_fu_int_adder, num_fu['int_adder'], False,
                results_buffer, ROB, cycle, PC)
    dispatch_rs(rs_fp_adder, fu_fp_adder, time_fu_fp_adder, num_fu['fp_adder'], True,
                results_buffer, ROB, cycle, PC)
    dispatch_rs(rs_fp_multi, fu_fp_multi, time_fu_fp_multi, num_fu['fp_multi'], True,
                results_buffer, ROB, cycle, PC)
