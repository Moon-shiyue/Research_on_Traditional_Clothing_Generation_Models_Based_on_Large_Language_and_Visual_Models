"""Setup diagnostics distinguish stale partial servers from current capabilities."""
import unittest
from tools.check_studio import health_capabilities, REQUIRED_COMPONENTS, REQUIRED_PAIRS, REQUIRED_ENSEMBLES


class SetupCheckTests(unittest.TestCase):
    def test_complete_capabilities_accept_additions_but_reject_old_partial_backend(self):
        health = {'status':'ok', 'components':dict.fromkeys(REQUIRED_COMPONENTS, 'name'),
            'outfits':[{'components':sorted(p)} for p in REQUIRED_PAIRS],
            'ensembles':[{'components':sorted(p)} for p in REQUIRED_ENSEMBLES]}
        self.assertTrue(health_capabilities(health)[0])
        health['components']['future-type']='新增'
        self.assertTrue(health_capabilities(health)[0])
        health['ensembles'] = []
        ready, detail = health_capabilities(health)
        self.assertFalse(ready)
        self.assertIn('重新运行run-backend.cmd', detail)
        health['outfits'] = [{'components':'invalid'}]
        self.assertFalse(health_capabilities(health)[0])


if __name__ == '__main__':
    unittest.main()
