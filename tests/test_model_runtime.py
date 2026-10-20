import fcntl
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from scripts import model_runtime as runtime


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.scope = patch.object(runtime, 'STATE', Path(self.folder.name))
        self.scope.start()
        self.addCleanup(self.scope.stop)

    def test_missing_runtime_fails_without_inference(self):
        emit = Mock()
        with patch.object(runtime, 'health', return_value={'h2o': False, 'qwen': False}), \
             patch.object(runtime, 'active', return_value=False), \
             patch.object(runtime.subprocess, 'run'):
            with self.assertRaisesRegex(RuntimeError, 'automatic startup'):
                with runtime.model_session(emit):
                    self.fail('Inference must not run offline')
        self.assertEqual(emit.call_args.kwargs['phase'], 'starting')

    def test_warming_waits_then_holds_lease_during_request(self):
        emit = Mock()
        with patch.object(runtime, 'health', side_effect=[{'qwen': False}, {'qwen': True}]), \
             patch.object(runtime, 'active', return_value=True), \
             patch.object(runtime.subprocess, 'run'), patch.object(runtime.time, 'sleep'):
            with runtime.model_session(emit):
                with (runtime.STATE/'models.lock').open('a') as other:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with (runtime.STATE/'models.lock').open('a') as other:
            fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_recovery_never_stops_active_inference(self):
        with (runtime.STATE/'models.lock').open('a') as lease:
            fcntl.flock(lease, fcntl.LOCK_SH)
            with patch.object(runtime.subprocess, 'run') as run:
                self.assertFalse(runtime.recover(Path('/model/control')))
                run.assert_not_called()

    def test_healthy_pair_is_adopted_without_restart(self):
        with patch.object(runtime, 'health', return_value={'qwen': True, 'h2o': True}), \
             patch.object(runtime.subprocess, 'run') as run:
            self.assertTrue(runtime.recover(Path('/model/control')))
            run.assert_not_called()

    def test_partial_failure_restarts_only_owned_pair(self):
        with patch.object(runtime, 'health', side_effect=[{'h2o': False}, {'h2o': True}]), \
             patch.object(runtime, 'active', return_value=True), \
             patch.object(runtime.subprocess, 'run') as run:
            self.assertTrue(runtime.recover(Path('/model/control')))
        self.assertEqual([c.args[0] for c in run.call_args_list],
                         [['/model/control', 'stop'], ['/model/control', 'start']])

    def test_wait_timeout_does_not_reach_inference(self):
        with patch.object(runtime, 'health', return_value={'h2o': False}), \
             patch.object(runtime, 'active', return_value=True), \
             patch.object(runtime.subprocess, 'run'):
            with self.assertRaisesRegex(RuntimeError, 'did not become ready'):
                with runtime.model_session(Mock(), timeout=0):
                    self.fail('Inference must not run before readiness')
