import sys
import os
import traceback
import importlib

print("DIAG: CWD=", os.getcwd())
print("DIAG: sys.path:")
for p in sys.path:
    print("  ", p)

try:
    importlib.import_module('api.main')
    print("DIAG: IMPORT_OK api.main")
except Exception:
    print("DIAG: IMPORT FAILED — traceback:")
    traceback.print_exc()
