# Runs every test case in ../tests with issue width 1, 2, 3 and 4.
# For every run it
#   - saves the simulator output to ../results/<test>_w<N>.txt
#   - checks the final registers/memory against a sequential reference model
#   - checks the pipeline timing rules (in-order issue/commit, width limits, ...)
# usage: python3 run_tests.py
import glob
import io
import os
import sys
from contextlib import redirect_stdout
from main import run, print_results
from check import check, get_table_rows


# function: test number from the file name, e.g. tc10_pdf_format.txt -> 10
def get_test_number(path):
    fileName = os.path.basename(path)
    return int(fileName.split('_')[0][2:])


codeDir = os.path.dirname(os.path.abspath(__file__))
testFiles = glob.glob(os.path.join(codeDir, '..', 'tests', '*.txt'))
testFiles.sort(key=get_test_number)
outDir = os.path.join(codeDir, '..', 'results')
os.makedirs(outDir, exist_ok=True)

nFailed = 0
print('Total cycles = cycle of the last commit (OK = matches reference model and timing rules)')

header = 'test case'.ljust(32)
for width in (1, 2, 3, 4):
    header += ('width ' + str(width)).ljust(12)
print(header)

for testPath in testFiles:
    testName = os.path.basename(testPath)[:-4]
    rowText = testName.ljust(32)

    for width in (1, 2, 3, 4):
        result = run(testPath, width, quiet=True)

        # save the full output
        outText = io.StringIO()
        with redirect_stdout(outText):
            print_results(result)
        with open(os.path.join(outDir, '%s_w%d.txt' % (testName, width)), 'w') as f:
            f.write(outText.getvalue())

        errors = check(testPath, result)

        lastCommit = 0
        for row in get_table_rows(result['status']):
            if row['commit'][0] > lastCommit:
                lastCommit = row['commit'][0]

        if len(errors) == 0:
            rowText += ('%d OK' % lastCommit).ljust(12)
        else:
            rowText += ('%d FAIL' % lastCommit).ljust(12)
            nFailed += 1
            for err in errors:
                print('   %s width %d: %s' % (testName, width, err))

    print(rowText)

print()
if nFailed == 0:
    print('all runs passed')
else:
    print('%d runs FAILED' % nFailed)
    sys.exit(1)
sys.exit(0)
