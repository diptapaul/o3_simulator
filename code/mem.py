# Qing 
# 26th May 2017
# Modified: memory disambiguation fixes (see report)

''' 
1. Ld forward check from Sd in ld_sd_queue
    -- check the older Sd instructions from the nearest one
2. execute LD/SD instruction in ld_sd_mem
    -- once LD instruction gets data, write back to ld_sd_queue
    -- LD instruction should be removed after get data  
    -- SD instruction should be removed at commit stage 
3. fetch new LD/SD instruction into ld_sd_mem
    -- if first element is SD, ready and has valid data, only SD to be committed can be fetched into ld_sd_mem 
    -- else put the first no-matched Ld into ld_sd_mem    
'''
from init import fu_result

# function: True if an Sd entry holds a value (not a ROB tag that is still pending)
def has_data(value):
    if (type(value)==int)|(type(value)==float):
        return True
    return False

# function: forward check from sd
# walk back from the nearest older Sd: stop at an Sd whose address is not known yet
# (address calculated in an earlier cycle); forward from the first Sd with the same
# address (if its data is ready)
def forward_check_from_sd(ld_sd_queue, index, ROB, cycle):
    data = []

    for i in reversed(range(index)):
        if (ld_sd_queue[i].op!='Sd'):
            continue

        # address of this Sd is not known yet
        if ld_sd_queue[i].ready == 0:
            break
        sdRobIdx = find_ROB_entry(ROB, ld_sd_queue[i].dest_tag)
        if ROB[sdRobIdx].exe[-1] >= cycle:
            break

        if (ld_sd_queue[i].address == ld_sd_queue[index].address):
            if has_data(ld_sd_queue[i].data):
                data.append(ld_sd_queue[i].data)
            break

    return data

# function: check if previous all Sds are ready and un-matched
def check_all_previous_Sd_no_match(ld_sd_queue, index):
    flag = True
    for i in range(index):
        # all Sd instructions
        if (ld_sd_queue[i].op=='Sd'):
            if ld_sd_queue[i].ready == 0:
                flag = False
                break 
            elif (ld_sd_queue[i].address==ld_sd_queue[index].address):
                flag = False
                break
            else:
                pass
    return flag
 
# function: find ROB entry by tag
def find_ROB_entry(ROB, tag):
    for index in range(len(ROB)):
        if ROB[index].ROB_tag == tag:
            break
    return index

# function: put entry into ld_sd_mem
def put_entry_into_ld_sd_mem(ld_sd_mem, entry):
    ld_sd_mem.busy = 1
    ld_sd_mem.cycle = 0
    ld_sd_mem.address = entry.address
    ld_sd_mem.dest_tag = entry.dest_tag
    ld_sd_mem.op = entry.op
    if ld_sd_mem.op == 'Sd':
        ld_sd_mem.data = entry.data

# function: check if Sd is at the head of the ROB (all older instructions committed),
# stores write the memory only when they commit
def check_if_sd_committable(ld_sd_queue, ROB):
    if len(ROB) == 0:
        return False
    return ld_sd_queue[0].ld_sd_tag == ROB[0].dest_tag

# function: mem 
def mem(ld_sd_queue, ld_sd_mem, time_ld_sd_mem, results_buffer, 
        memory, ROB, cycle):
    '''look forward check for all Ld instructions'''
    remove_list = []
    for index in range(len(ld_sd_queue)):
        element = ld_sd_queue[index]
        if (index>=1)&(element.op=='Ld')&(element.ready==1):
            # address must have been calculated in an earlier cycle
            ldRobIdx = find_ROB_entry(ROB, element.dest_tag)
            if ROB[ldRobIdx].exe[-1] >= cycle:
                continue

            fwdData = forward_check_from_sd(ld_sd_queue, index, ROB, cycle)
            if len(fwdData)>0:
                # Ld gets data (forwarding takes 1 cycle)
                results_buffer.append(fu_result())
                results_buffer[-1].value = fwdData[0]
                results_buffer[-1].dest_tag = element.dest_tag
                # remove the Ld instruction
                remove_list.append(element)
                # write mem cylce in ROB
                ROB[ldRobIdx].mem.append(cycle)
    # remove lookforwared Ld
    for element in remove_list:
        ld_sd_queue.remove(element)
    '''ld_sd_mem execution'''
    if ld_sd_mem.busy == 1:
        # write mem starting cycle 
        if ld_sd_mem.cycle == 0:
            index = find_ROB_entry(ROB, ld_sd_mem.dest_tag)
            ROB[index].mem.extend([cycle, cycle+time_ld_sd_mem-1])
            # for Sd, write commit cycle
            if ld_sd_mem.op == 'Sd':
                ROB[index].commit.append(cycle)
        
        # cycle ++
        ld_sd_mem.cycle +=1
        # get the data for Ld or reach the memory for Sd
        if ld_sd_mem.cycle == time_ld_sd_mem:
            ld_sd_mem.busy = 0
            if ld_sd_mem.op == 'Ld': 
                # put Ld data into results_buffer
                address = ld_sd_mem.address 
                data = memory[address]
                results_buffer.append(fu_result())
                results_buffer[-1].value = data
                results_buffer[-1].dest_tag = ld_sd_mem.dest_tag
            # put data into memory for Sd
            else:
                memory[ld_sd_mem.address]=ld_sd_mem.data

    '''fetch new instruction into ld_sd_mem (memory is single ported)'''
    if (ld_sd_mem.busy==0)&(len(ld_sd_queue)>0):
        # flag_1st_ldsd
        flag_1st_ldsd_sent = False 
        # fetch the ld_sd_queue header if it's Sd, ready and to be committed
        if (ld_sd_queue[0].op=='Sd'):
            # check if this Sd is ready and to be commited 
            if (ld_sd_queue[0].ready==1):
                # Sd commits now (it is the oldest instruction in the ROB)
                if check_if_sd_committable(ld_sd_queue, ROB):
                    # already have data in Sd
                    if has_data(ld_sd_queue[0].data):
                        # put the Sd entry into ld_sd_mem
                        entry = ld_sd_queue.popleft()
                        put_entry_into_ld_sd_mem(ld_sd_mem, entry)
                        flag_1st_ldsd_sent = True
                        ld_sd_mem.busy = 1

        # if the 1st Sd is not sent to ld_sd_mem, or the 1st is not Sd
        if (flag_1st_ldsd_sent==False):
            for index in range(len(ld_sd_queue)):
                # ready Ld (memory access starts in the next cycle)
                if (ld_sd_queue[index].op=='Ld')&(ld_sd_queue[index].ready==1):
                    # all previous Sd instructions are ready but no address match 
                    if check_all_previous_Sd_no_match(ld_sd_queue, index): 
                        put_entry_into_ld_sd_mem(ld_sd_mem, ld_sd_queue[index])
                        ld_sd_queue.remove(ld_sd_queue[index])
                        ld_sd_mem.busy =1
                        break 
