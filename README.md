# Tomasulo Simulator with Multi-Issue Support (Issue Width 1–4)

Python simulator of an out-of-order processor using the Tomasulo algorithm with a ROB
(register renaming, reorder buffer, load/store queue with memory disambiguation).
Starting from the provided single-issue code, this version **issues and commits up to
1–4 instructions per cycle in program order**. The issue width is read from the input file.

## Requirements

Python 3 (no extra packages).

## How to run

```bash
cd code
python3 main.py ../tests/tc1_given_loop.txt        # issue width taken from the input file
python3 main.py ../tests/tc1_given_loop.txt 4      # optional: override the issue width (1-4)
python3 run_tests.py                               # run all test cases with width 1, 2, 3, 4
```

`python3 main.py` without arguments runs `code/test_case.txt`.

## Input file

Same format as in the assignment (text is case insensitive; operands may be separated
by commas and/or spaces):

```
                # of rs   Cycles in EX   Cycles in Mem   # of FUs
Integer adder      2          1                             1
FP adder           3          3                             1
FP multiplier      2          20                            1
Load/store unit    3          1               4             1

ROB entries = 128
Issue width = 2
R1=10, R2=20, F2=30.1
Mem[4]=1, Mem[8]=2, Mem[12]=3.4

Add.d F1, F2, F3
Ld F4, 8(R1)
Bne R2, R3, -3
```

- `Issue width = N` (1–4). If the line is missing, the default is 1.
- Registers and memory are 0 unless initialized. R0 is hardwired to 0.
- Branch offsets follow the ISA in the assignment: `Bne Rs, Rt, offset` jumps to
  `PC + 4 + offset<<2`, i.e. `offset` counts instructions (`-3` = 3 instructions back
  from the next instruction).
- Optional: `CDB = N` sets the number of common data buses (default 1, as specified).

## Output

The instruction status table (ISSUE, EX, MEM, WB, COMMIT cycles for every executed
instruction), the final register values (R0–R31, F0–F31) and the non-zero memory values.

## Files

| Path | Content |
|------|---------|
| `code/main.py` | Main loop; reads the input file; prints the results |
| `code/init.py` | Data structures; **input-file parser** |
| `code/issue.py` | Issue stage; **issues up to issue-width instructions per cycle, in order** |
| `code/exe.py` | Execution stage (functional units, address calculation, branch resolution) |
| `code/mem.py` | Memory stage (load/store queue, store-to-load forwarding) |
| `code/wb.py` | Write back on the CDB |
| `code/commit.py` | Commit stage; **commits up to issue-width instructions per cycle, in order** |
| `code/check.py` | Correctness checker: sequential reference model + pipeline timing rules |
| `code/run_tests.py` | Runs all test cases with issue width 1–4 and checks them |
| `tests/` | Test cases (input files) |
| `results/` | Simulator output for every test case and issue width |
| `REPORT.md` | Report |
