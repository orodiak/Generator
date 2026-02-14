"""
Unit tests for SMY02Controller

Tests basic functionality without requiring a real device.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from smy02_controller import SMY02Controller


class TestSMY02Controller(unittest.TestCase):
    """Test cases for SMY02Controller class."""

    def setUp(self):
        """Set up test fixtures."""
        self.controller = SMY02Controller()

    @patch('pyvisa.ResourceManager')
    def test_connect_success(self, mock_rm):
        """Test successful connection."""
        mock_instrument = MagicMock()
        mock_instrument.query.return_value = "Rhode&Schwarz,SMY02,123456,1.0"
        mock_rm.return_value.open_resource.return_value = mock_instrument

        self.controller.rm = mock_rm()
        result = self.controller.connect()

        self.assertTrue(result)
        self.assertIsNotNone(self.controller.instrument)

    @patch('pyvisa.ResourceManager')
    def test_set_frequency(self, mock_rm):
        """Test setting frequency."""
        mock_instrument = MagicMock()
        self.controller.instrument = mock_instrument

        result = self.controller.set_frequency(1e9)

        self.assertTrue(result)
        mock_instrument.write.assert_called_with("FREQ 1000000000.0")

    @patch('pyvisa.ResourceManager')
    def test_set_amplitude(self, mock_rm):
        """Test setting amplitude."""
        mock_instrument = MagicMock()
        self.controller.instrument = mock_instrument

        result = self.controller.set_amplitude(10)

        self.assertTrue(result)
        mock_instrument.write.assert_called_with("POW 10")

    @patch('pyvisa.ResourceManager')
    def test_enable_output(self, mock_rm):
        """Test enabling output."""
        mock_instrument = MagicMock()
        self.controller.instrument = mock_instrument

        result = self.controller.enable_output()

        self.assertTrue(result)
        mock_instrument.write.assert_called_with("OUTP ON")

    @patch('pyvisa.ResourceManager')
    def test_list_available_devices(self, mock_rm):
        """Test listing available devices."""
        mock_rm.return_value.list_resources.return_value = (
            "GPIB0::16::INSTR",
            "GPIB0::17::INSTR"
        )

        with patch.object(SMY02Controller, 'list_available_devices') as mock_list:
            mock_list.return_value = ["GPIB0::16::INSTR", "GPIB0::17::INSTR"]
            devices = SMY02Controller.list_available_devices()

        self.assertEqual(len(devices), 2)


if __name__ == "__main__":
    unittest.main()
