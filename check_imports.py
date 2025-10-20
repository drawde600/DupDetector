import importlib
modules = ['dupdetector.services.repository','dupdetector.cli']
for m in modules:
    try:
        importlib.import_module(m)
        print('import ok:', m)
    except Exception as e:
        print('import FAILED:', m, e)
        raise
print('done')
