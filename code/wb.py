# Qing 
# 29th May 2017 
# Modified: RAT is only updated if it still points to the broadcasting ROB entry;
#           optional support for more than one CDB (default: one CDB)

'''
1. broadcast data on cdb 
2. fetch data from results queue 
3. remove entry in results queue

'''
# function: find ROB entry by tag
def find_ROB_entry(ROB, tag):
    for index in range(len(ROB)):
        if ROB[index].ROB_tag == tag:
            break
    return index

# function: boroadcast
# rat_int, rat_fp, reservation stations, ld_sd_queue, ROB
def boroadcast(cdb, rat_int, rat_fp, 
                rs_int_adder, rs_fp_adder, rs_fp_multi,
                ld_sd_queue, ROB, cycle):
    # dest_tag
    dest_tag = cdb.dest_tag
    index = find_ROB_entry(ROB, dest_tag)
    reg_tag = ROB[index].dest_tag
    # rat_int / rat_fp: a younger instruction may have renamed the same register
    # after this one was issued; then the RAT must keep pointing to the younger one
    if reg_tag[0] == 'R':
        if rat_int[int(reg_tag[1:])] == dest_tag:
            rat_int[int(reg_tag[1:])] = cdb.value
    if reg_tag[0] == 'F':
        if rat_fp[int(reg_tag[1:])] == dest_tag:
            rat_fp[int(reg_tag[1:])] = cdb.value 
    # rs list
    rs_list = [rs_int_adder, rs_fp_adder, rs_fp_multi]
    for rs in rs_list:
        for element in rs:
            if (element.busy==1)&(element.tag_1st==dest_tag)&(element.valid_1st==0):
                element.value_1st = cdb.value
                element.valid_1st = 1
            if (element.busy==1)&(element.tag_2nd==dest_tag)&(element.valid_2nd==0):
                element.value_2nd = cdb.value
                element.valid_2nd = 1
    # ld_sd_queue 
    for element in ld_sd_queue:
        if (element.data==dest_tag)&(element.op=='Sd'):
            element.data = cdb.value
        if (element.reg_tag==dest_tag)&(element.valid==0):
            element.reg_value = cdb.value
            element.valid = 1
    # ROB
    for element in ROB:
        if element.ROB_tag == dest_tag:
            element.value = cdb.value
            element.cdb.append(cycle)

# function: wb 
# cdb is a list of CDBs (the default machine has exactly one)
def wb(cdb, rat_int, rat_fp, 
        rs_int_adder, rs_fp_adder, rs_fp_multi,
        ld_sd_queue, ROB, cycle,
        results_buffer):
    if not isinstance(cdb, list):
        cdb = [cdb]
    # broadcast 
    for bus in cdb:
        if bus.valid == 1:
            boroadcast(bus, rat_int, rat_fp, 
                        rs_int_adder, rs_fp_adder, rs_fp_multi,
                        ld_sd_queue, ROB, cycle)
            bus.valid = 0
    # fetch data from results queue: one result per CDB; when several results
    # are waiting, the oldest instruction (closest to the ROB head) goes first
    for bus in cdb:
        if (bus.valid == 0) & (len(results_buffer) > 0):
            oldIdx = 0
            oldRobPos = find_ROB_entry(ROB, results_buffer[0].dest_tag)
            for k in range(1, len(results_buffer)):
                robPos = find_ROB_entry(ROB, results_buffer[k].dest_tag)
                if robPos < oldRobPos:
                    oldRobPos = robPos
                    oldIdx = k

            bus.valid = 1
            bus.value = results_buffer[oldIdx].value
            bus.dest_tag = results_buffer[oldIdx].dest_tag
            del results_buffer[oldIdx]
