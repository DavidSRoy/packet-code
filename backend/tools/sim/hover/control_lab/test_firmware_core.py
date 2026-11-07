"""Native C++ implementation agrees with the Python observer/controller."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np

from lqg import LQG


class FirmwareCoreTest(unittest.TestCase):
    def test_hardware_build_is_rejected(self):
        header = Path(__file__).resolve().parent / 'firmware'
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            (p/'AC_CustomControl_config.h').write_text('#define CONFIG_HAL_BOARD 1\n#define HAL_BOARD_SITL 3\n#define AP_CUSTOMCONTROL_EMPTY_ENABLED 0\n')
            (p/'check.cpp').write_text('#include "AC_CustomControl_Empty.h"\n')
            result=subprocess.run(['c++','-E','-I',str(header),'-I',str(p),str(p/'check.cpp')],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Packet experimental LQG is simulation-only',result.stderr)

    def test_all_generated_banks_against_python(self):
        header = Path(__file__).resolve().parent / 'firmware'
        code = r'''
#include <iostream>
#include <iomanip>
#include "PacketLQGCore.h"
int main() {
    std::cout << std::setprecision(10);
    for (unsigned model=0;model<2;model++) for (unsigned bank=0;bank<3;bank++) {
        PacketLQG::Core c;
        c.reset(0.01f,-0.02f);
        for(int i=0;i<400;i++) {
            const float angle=.01f+.001f*std::sin(i*.03f);
            const float rate=.002f*std::cos(i*.03f);
            const float target=.01f+.002f*std::sin(i*.01f);
            std::cout << c.update(angle,rate,target,model,bank,.35f,.008f*std::cos(i*.01f)) << '\n';
        }
    }
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'test.cpp'
            binary = Path(tmp) / 'test'
            source.write_text(code)
            subprocess.run(['c++', '-std=c++17', '-O2', '-I', str(header),
                            str(source), '-o', str(binary)], check=True, capture_output=True)
            actual = np.fromstring(subprocess.check_output([str(binary)], text=True), sep='\n')
        metadata=json.loads((header / "matrices.json").read_text())
        expected = []
        for K, sigma in ((73.5, (.25,.4)), (8., (.08,.1))):
            for effort in (.01,.001,.0001):
                c = LQG(.0025, K=K, dist_sigma=sigma, effort=effort, rate_cost=.0001,gyro_delay=metadata["gyro_delay"],delay=metadata["delay"],tau=metadata["tau"])
                c.state[0]=.01
                c.state[1]=c.state[5]=-.02
                c.state[6+round(metadata["delay"]/.0025):]=-.02
                for i in range(400):
                    expected.append(c.update(.01+.001*np.sin(i*.03),
                                             .002*np.cos(i*.03),
                                             target=.01+.002*np.sin(i*.01),target_rate=.008*np.cos(i*.01)))
        np.testing.assert_allclose(actual, expected, atol=3e-6, rtol=2e-4)


if __name__ == '__main__':
    unittest.main()
