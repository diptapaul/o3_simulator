# Qing 
# 29th may 2017
# Modified: commit up to issue_width instructions per cycle (in order), Beq,
#           the status table is collected and printed at the end
'''
1. commit ROB_buffer
2. fetch header into ROB_buffer
'''
from init import get_printed_instruction

# function: format ROB entry as one row of the status table
def print_ROB(entry, instructions):
    item = get_printed_instruction(instructions[entry.PC]).ljust(30)
    item += str(entry.issue).ljust(15) 
    item += str(entry.exe).ljust(15) 
    item += str(entry.mem).ljust(15)
    item += str(entry.cdb).ljust(15)
    item += str(entry.commit)
    return item

# function: modify architectual reg
def modify_arch_reg(entry, reg_int, reg_fp):
    if entry.dest_tag[0] == 'F':
        reg_fp[int(entry.dest_tag[1:])] = entry.value
    elif entry.dest_tag[0] == 'R':
        regNum = int(entry.dest_tag[1:])
        if regNum != 0:   # R0 is hardwired to 0
            reg_int[regNum] = entry.value
    else:
        pass

# function: True if the ROB entry is a branch (Bne / Beq)
def is_branch(entry, instructions):
    opName = instructions[entry.PC].split(' ')[0]
    if (opName == 'Bne') | (opName == 'Beq'):
        return True
    return False

# function: commit
# up to issue_width instructions leave the ROB head per cycle, in program order.
# (committed in this call = shown as commit in cycle+1, same convention as before;
#  an Sd already committed when it entered memory and is only removed here)
def commit(ROB, reg_int, reg_fp, cycle, instructions, issue_width=1, status_rows=None):
    if status_rows is None:
        status_rows = []

    nCommitted = 0

    while (len(ROB)>0) & (nCommitted < issue_width):
        robHead = ROB[0]

        if is_branch(robHead, instructions):
            # branch: commits once it has been resolved (EX finished)
            if len(robHead.exe) != 2:
                break
            robHead.commit.append(cycle+1)
            entry = ROB.popleft()
            status_rows.append(print_ROB(entry, instructions))
            nCommitted += 1

        elif len(robHead.cdb)!=0: # broadcasted instructions
            robHead.commit.append(cycle+1)
            entry = ROB.popleft()
            modify_arch_reg(entry, reg_int, reg_fp)
            status_rows.append(print_ROB(entry, instructions))
            nCommitted += 1

        elif len(robHead.commit)!=0: # Sd (committed when it entered memory)
            entry = ROB.popleft()
            status_rows.append(print_ROB(entry, instructions))

        else:
            break

    return status_rows
