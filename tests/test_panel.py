import os
import shutil
import subprocess

import pytest

HERE = os.path.dirname(__file__)


@pytest.mark.skipif(not shutil.which('node'), reason='node is not installed')
def test_no_reverse_binding_without_our_firmware():
    subprocess.run(['node', os.path.join(HERE, 'panel_reverse.mjs')], check=True)


@pytest.mark.skipif(not shutil.which('node'), reason='node is not installed')
def test_calibration_buttons_per_line_and_per_room():
    subprocess.run(['node', os.path.join(HERE, 'panel_calibrate.mjs')], check=True)


@pytest.mark.skipif(not shutil.which('node'), reason='node is not installed')
def test_room_trigger_field_and_save_bar():
    subprocess.run(['node', os.path.join(HERE, 'panel_room_trigger.mjs')], check=True)
