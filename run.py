#!/usr/bin/env python3
"""
SmartTravels — One-Click Start Script
Run: python run.py
Works on Windows, Mac, and Linux.
"""
import sys, os, subprocess
from pathlib import Path

ROOT     = Path(__file__).parent
LIB      = ROOT.parent / 'lib'
PYTHON   = sys.executable

env = os.environ.copy()
env['PYTHONPATH']               = str(LIB) + os.pathsep + env.get('PYTHONPATH', '')
env['DJANGO_SETTINGS_MODULE']   = 'smarttravels.settings'

BAR = '=' * 62

def run(cmd, **kwargs):
    return subprocess.run([PYTHON] + cmd, cwd=ROOT, env=env, **kwargs)

def main():
    print(BAR)
    print('  🚀  SmartTravels — Kenya Unified Transport Platform')
    print(BAR)
    print()
    print('  Checking database…')
    run(['manage.py', 'migrate', '--run-syncdb'], check=True, capture_output=True)
    print('  ✅  Database ready')
    print()
    print('  📋  Test Accounts:')
    print('      System Admin   →  admin        /  Admin1234!')
    print('      Bus Admin      →  bus_admin    /  BusAdmin1!')
    print('      Train Admin    →  train_admin  /  TrainAdmin1!')
    print('      Flight Admin   →  flight_admin /  FlightAdmin1!')
    print('      Driver         →  driver01     /  Driver1234!')
    print('      Passenger      →  passenger    /  Pass1234!')
    print()
    print('  🌐  Opening:  http://127.0.0.1:8000')
    print('  🔑  Login at: http://127.0.0.1:8000/accounts/login/')
    print()
    print('  Press Ctrl+C to stop the server')
    print(BAR)
    run(['manage.py', 'runserver', '0.0.0.0:8000'])

if __name__ == '__main__':
    main()
