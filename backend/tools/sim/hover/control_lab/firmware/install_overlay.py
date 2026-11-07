"""Install the experimental controller in an explicitly selected SITL source copy.

No firmware upload or hardware connection. Original ArduPilot checkout is not used.
"""
import argparse
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_SHA = 'fb773567896014da007bca58358704d4a0d8516f'


def install(root):
    root = root.resolve()
    original = Path.home() / 'ardupilot-x650/ardupilot'
    if root == original.resolve():
        raise ValueError('Use a separate source copy, not the live baseline checkout')
    sha = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if sha != BASE_SHA:
        raise ValueError(f'Overlay was tested against {BASE_SHA}, got {sha}')
    destination = root / 'libraries/AC_CustomControl'
    front = destination / 'AC_CustomControl.cpp'
    content = front.read_text()
    replacements = {
        '// #include "AC_CustomControl_Empty.h"': '#include "AC_CustomControl_Empty.h"',
        '// AP_SUBGROUPVARPTR(_backend, "1_", 6, AC_CustomControl, _backend_var_info[0]),':
            'AP_SUBGROUPVARPTR(_backend, "1_", 6, AC_CustomControl, _backend_var_info[0]),',
        '// _backend = NEW_NOTHROW AC_CustomControl_Empty': '_backend = NEW_NOTHROW AC_CustomControl_Empty',
        '// _backend_var_info[get_type()] = AC_CustomControl_Empty::var_info;':
            '_backend_var_info[get_type()] = AC_CustomControl_Empty::var_info;',
    }
    for old, new in replacements.items():
        if old not in content and new not in content:
            raise ValueError(f'Unexpected frontend: missing {old}')
        content = content.replace(old, new)
    guard = '''    // Packet SITL matrices require 400 Hz; refuse activation before motor_set.
    if (enabled && _controller_type == CustomControlType::CONT_EMPTY && fabsf(_dt - 0.0025f) > 0.000001f) {
        GCS_SEND_TEXT(MAV_SEVERITY_WARNING, "Packet LQG requires 400 Hz");
        return;
    }

'''
    anchor = '    if (enabled && _controller_type > CustomControlType::CONT_NONE) {'
    if guard not in content:
        if anchor not in content:
            raise ValueError('Missing custom activation insertion point')
        content = content.replace(anchor, guard + anchor)
    for name in ('AC_CustomControl_Empty.h', 'AC_CustomControl_Empty.cpp',
                 'PacketLQGCore.h', 'PacketLQGMatrices.h'):
        shutil.copy2(HERE / name, destination / name)
    front.write_text(content)
    print(f'Installed simulation-only overlay in {root}; baseline {sha}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source_copy', type=Path)
    install(parser.parse_args().source_copy)
