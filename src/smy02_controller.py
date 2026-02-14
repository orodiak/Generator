"""
SMY02 Signal Generator Controller

Module for controlling Rhode Schwarz SMY02 signal generator via GPIB/USB interface.
"""

import pyvisa
from typing import Optional, List, Dict
import logging
import threading
from time import sleep

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SMY02Controller:
    """Controller for Rhode Schwarz SMY02 signal generator."""

    def __init__(self, resource_name: str = "GPIB0::28::INSTR"):
        """
        Initialize the SMY02 controller.

        Args:
            resource_name: VISA resource identifier (e.g., "GPIB0::28::INSTR")
        """
        self.resource_name = resource_name
        self.instrument = None
        self.idn = ""
        self.model = ""
        self._fm_initialized = False
        self._modulation_mode = None
        self.rm = pyvisa.ResourceManager()
        self._io_lock = threading.RLock()

    def connect(self) -> bool:
        """
        Connect to the signal generator.

        Returns:
            True if connection successful, False otherwise
        """
        with self._io_lock:
            try:
                self.instrument = self.rm.open_resource(self.resource_name)
                # Use a longer timeout for queries from this device
                self.instrument.timeout = 5000  # 5 second timeout
                # Use CRLF terminations which are commonly expected by instruments
                self.instrument.read_termination = '\r\n'
                self.instrument.write_termination = '\r\n'
                
                # Verify connection
                idn = self.instrument.query("*IDN?").strip()
                self.idn = idn
                parts = [p.strip() for p in idn.split(",")]
                self.model = parts[1] if len(parts) > 1 else "Unknown"
                logger.info(f"Connected to device: {idn}")
                return True
            except Exception as e:
                logger.error(f"Failed to connect: {e}")
                return False

    def disconnect(self):
        """Disconnect from the signal generator."""
        with self._io_lock:
            if self.instrument:
                self.instrument.close()
                logger.info("Disconnected from device")
                self.instrument = None
                self._fm_initialized = False
                self._modulation_mode = None

    def set_frequency(self, frequency: float) -> bool:
        """
        Set output frequency in Hz.

        Args:
            frequency: Frequency in Hz (e.g., 1e9 for 1 GHz)

        Returns:
            True if successful, False otherwise
        """
        if not self.instrument:
            return False
        
        with self._io_lock:
            cmd = f"RF {int(frequency)}"
            is_smy02 = "SMY02" in (self.model or "").upper() or "SMY02" in (self.idn or "").upper()
            
            try:
                logger.debug(f"Setting frequency with: {cmd}")
                self.instrument.write(cmd)
                sleep(0.05 if is_smy02 else 0.2)
                if is_smy02:
                    # SMY02 can raise transient panel errors if ESR is queried for every RF change.
                    # Use write-only path for stable hopping/sweeps.
                    logger.info(f"Frequency set to {frequency} Hz")
                    return True

                # Non-SMY02 fallback: keep ESR safety check.
                esr = self.get_esr()
                logger.debug(f"*ESR? after RF command: {esr}")
                if esr is not None and esr == 0:
                    logger.info(f"Frequency set to {frequency} Hz")
                    return True
                logger.error(f"Frequency set failed. ESR: {esr}")
                return False
            except Exception as e:
                logger.error(f"Failed to set frequency: {e}")
                return False

    def set_amplitude(self, amplitude: float) -> bool:
        """
        Set output amplitude in dBm.

        Args:
            amplitude: Amplitude in dBm

        Returns:
            True if successful, False otherwise
        """
        if not self.instrument:
            return False
        
        with self._io_lock:
            cmd = f"LEVEL {amplitude}"
            is_smy02 = "SMY02" in (self.model or "").upper() or "SMY02" in (self.idn or "").upper()
            
            try:
                logger.debug(f"Setting amplitude with: {cmd}")
                self.instrument.write(cmd)
                sleep(0.05 if is_smy02 else 0.2)
                if is_smy02:
                    logger.info(f"Amplitude set to {amplitude} dBm")
                    return True

                esr = self.get_esr()
                logger.debug(f"*ESR? after LEVEL command: {esr}")
                if esr is not None and esr == 0:
                    logger.info(f"Amplitude set to {amplitude} dBm")
                    return True
                logger.error(f"Amplitude set failed. ESR: {esr}")
                return False
            except Exception as e:
                logger.error(f"Failed to set amplitude: {e}")
                return False

    def enable_output(self) -> bool:
        """
        Enable RF output.

        Returns:
            True if successful, False otherwise
        """
        if not self.instrument:
            return False
        
        with self._io_lock:
            try:
                is_smy02 = "SMY02" in (self.model or "").upper() or "SMY02" in (self.idn or "").upper()
                # For SMY02 prefer strict vendor command only, to avoid generating
                # extra command errors from unsupported SCPI aliases.
                candidates = ["OUTP ON"] if is_smy02 else ["OUTP ON", "OUTP:STAT ON", "OUTPON", "LEVEL:ON", "RF:ON"]
                last_esr = None
                for cmd in candidates:
                    self.clear_status()
                    sleep(0.1)
                    logger.debug(f"Sending: {cmd}")
                    self.instrument.write(cmd)
                    sleep(0.2)

                    esr = self.get_esr()
                    last_esr = esr
                    if esr is None or esr == 0:
                        logger.info("RF output enabled")
                        return True
                    # On some SMY02 firmware revisions OUTP ON can report command/status
                    # bits despite RF path being enabled; avoid retrying invalid aliases.
                    if is_smy02 and esr in (32, 53):
                        logger.warning("Enable output returned ESR=%s on SMY02; treating as non-fatal", esr)
                        return True

                # Some SMY02 configurations report command error (ESR=32) for OUTP
                # while still allowing RF via level/modulation path.
                if last_esr in (32, 53):
                    logger.warning(
                        "Enable output command reported ESR=%s; continuing as non-fatal for SMY02 compatibility",
                        last_esr,
                    )
                    return True

                logger.error(f"Enable output failed. ESR: {last_esr}")
                return False
            except Exception as e:
                logger.error(f"Failed to enable output: {e}")
                return False

    def disable_output(self) -> bool:
        """
        Disable RF output.

        Returns:
            True if successful, False otherwise
        """
        if not self.instrument:
            return False
        
        with self._io_lock:
            try:
                self.clear_status()
                sleep(0.1)
                
                # Send disable commands
                for cmd in ["OUTP OFF", "LEVEL:OFF"]:
                    logger.debug(f"Sending: {cmd}")
                    self.instrument.write(cmd)
                    sleep(0.15)
                
                logger.info("RF output disabled")
                return True
            except Exception as e:
                logger.error(f"Failed to disable output: {e}")
                return False

    def set_modulation_fm(self, deviation: float = 5000) -> bool:
        """
        Enable FM modulation with 1 kHz tone.

        Args:
            deviation: FM deviation in Hz (default 5 kHz)

        Returns:
            True if successful, False otherwise
        """
        if not self.instrument:
            return False
        
        with self._io_lock:
            try:
                is_smy02 = "SMY02" in (self.model or "").upper() or "SMY02" in (self.idn or "").upper()
                if is_smy02:
                    # Keep command set minimal on SMY02 to avoid front-panel ERR spam.
                    # Initialize tone source once; during hopping only deviation is updated.
                    try:
                        if not self._fm_initialized:
                            for cmd in ["FM:INT 1.000E+3", "AF 1000", "FM:ON"]:
                                logger.debug(f"Sending (init FM): {cmd}")
                                self.instrument.write(cmd)
                                sleep(0.06)
                            self._fm_initialized = True
                        elif self._modulation_mode != "FM":
                            # Ensure we actually switch back from AM to FM.
                            for cmd in ["AM:OFF", "FM:ON"]:
                                logger.debug(f"Sending (switch to FM): {cmd}")
                                self.instrument.write(cmd)
                                sleep(0.05)
                        cmd = f"FM {int(deviation)}"
                        logger.debug(f"Sending (SMY02 deviation): {cmd}")
                        self.instrument.write(cmd)
                        sleep(0.06)
                        self._modulation_mode = "FM"
                        logger.info(f"FM deviation set to {deviation} Hz via '{cmd}'")
                        return True
                    except Exception as e:
                        logger.error(f"Failed SMY02 FM set: {e}")
                        return False

                # Non-SMY02 fallback with ESR probing.
                self.clear_status()
                sleep(0.1)
                for cmd in ["FM:INT 1.000E+3", "AF 1000"]:
                    logger.debug(f"Sending: {cmd}")
                    self.instrument.write(cmd)
                    sleep(0.15)
                deviation_cmds = [
                    f"FM {int(deviation)}",
                    f"FM:DEV {int(deviation)}",
                    f"FM:DEV {float(deviation):.3E}",
                    f"FM:DEVIATION {int(deviation)}",
                    f"FM:INT:DEV {int(deviation)}",
                ]
                deviation_set = False
                for cmd in deviation_cmds:
                    try:
                        self.clear_status()
                        sleep(0.05)
                        logger.debug(f"Trying deviation command: {cmd}")
                        self.instrument.write(cmd)
                        sleep(0.15)
                        esr = self.get_esr()
                        if esr is None or esr == 0:
                            deviation_set = True
                            logger.info(f"FM deviation set to {deviation} Hz via '{cmd}'")
                            break
                    except Exception:
                        continue

                if not deviation_set:
                    logger.warning(
                        "Could not verify FM deviation command for %s Hz; bandwidth may remain unchanged.",
                        deviation
                    )

                self.instrument.write("FM:ON")
                sleep(0.15)
                self._modulation_mode = "FM"
                logger.info("FM modulation enabled")
                return True
            except Exception as e:
                logger.error(f"Failed to set modulation: {e}")
                return False

    def set_modulation_am(self) -> bool:
        """
        Enable AM modulation mode.

        For SMY02 this uses a minimal command path to reduce panel errors.
        """
        if not self.instrument:
            return False

        with self._io_lock:
            try:
                is_smy02 = "SMY02" in (self.model or "").upper() or "SMY02" in (self.idn or "").upper()
                if is_smy02:
                    for cmd in ["FM:OFF", "AM:ON"]:
                        logger.debug(f"Sending (SMY02 AM): {cmd}")
                        self.instrument.write(cmd)
                        sleep(0.06)
                    self._modulation_mode = "AM"
                    logger.info("AM modulation enabled")
                    return True

                # Generic fallback variants for non-SMY02.
                for cmd in ["FM:OFF", "AM:ON", "AM ON", "AM:STAT ON"]:
                    try:
                        self.instrument.write(cmd)
                        sleep(0.08)
                    except Exception:
                        continue
                self._modulation_mode = "AM"
                logger.info("AM modulation enabled")
                return True
            except Exception as e:
                logger.error(f"Failed to set AM modulation: {e}")
                return False

    def set_lfo_frequency(self, frequency: float) -> bool:
        """
        Set LFO (Low Frequency Oscillator) frequency for modulation tone.

        Args:
            frequency: LFO frequency in Hz (e.g., 1000 for 1 kHz tone)

        Returns:
            True if successful, False otherwise
        """
        candidates = [
            f"LFO:FREQ {frequency}",
            f"SOUR:LFO:FREQ {frequency}",
            f"SOUR:MOD:LFO:FREQ {frequency}",
        ]
        if not self._try_commands_with_check(candidates):
            logger.error("Failed to set LFO frequency")
            return False
        logger.info(f"LFO frequency set to {frequency} Hz")
        return True

    def enable_lfo(self) -> bool:
        """
        Enable the LFO for tone generation.

        Returns:
            True if successful, False otherwise
        """
        candidates = ["LFO:STAT ON", "LFO:STATE ON", "SOUR:LFO:STAT ON", "SOUR:MOD:LFO:STAT ON"]
        if not self._try_commands_with_check(candidates):
            logger.error("Failed to enable LFO")
            return False
        logger.info("LFO enabled")
        return True

    def disable_lfo(self) -> bool:
        """
        Disable the LFO.

        Returns:
            True if successful, False otherwise
        """
        candidates = ["LFO:STAT OFF", "LFO:STATE OFF", "SOUR:LFO:STAT OFF", "SOUR:MOD:LFO:STAT OFF"]
        if not self._try_commands_with_check(candidates):
            logger.error("Failed to disable LFO")
            return False
        logger.info("LFO disabled")
        return True

    def get_frequency(self) -> Optional[float]:
        """
        Query current frequency setting.

        Returns:
            Frequency in Hz, or None if query fails
        """
        # Prefer the vendor-specific RF? query which returns a formatted string
        with self._io_lock:
            try:
                resp = self.instrument.query("RF?")
                # Expect something like: 'RF  144.000000E+6'
                parts = resp.strip().split()
                for tok in parts:
                    try:
                        # try parsing token as float (scientific notation)
                        val = float(tok)
                        return val
                    except Exception:
                        continue
            except Exception:
                pass

        # fallback to generic queries
        for query in ("SOUR:FREQ?", "FREQ?"):
            try:
                response = self.instrument.query(query)
                return float(response)
            except Exception:
                continue

        logger.error("Failed to get frequency: no response to known queries")
        return None

    def get_amplitude(self) -> Optional[float]:
        """
        Query current amplitude setting.

        Returns:
            Amplitude in dBm, or None if query fails
        """
        # Prefer vendor-specific LEVEL? response like 'LEVEL  -20.0'
        with self._io_lock:
            try:
                resp = self.instrument.query("LEVEL?")
                parts = resp.strip().split()
                for tok in parts:
                    try:
                        return float(tok)
                    except Exception:
                        continue
            except Exception:
                pass

        for query in ("SOUR:POW?", "POW?"):
            try:
                response = self.instrument.query(query)
                return float(response)
            except Exception:
                continue

        logger.error("Failed to get amplitude: no response to known queries")
        return None

    def get_device_state(self) -> Dict[str, str]:
        """
        Read current instrument state for GUI display.

        Returns:
            Dict with keys: rf, level, fm, af
        """
        state = {"rf": "N/A", "level": "N/A", "fm": "N/A", "af": "N/A"}
        if not self.instrument:
            return state

        with self._io_lock:
            old_timeout = self.instrument.timeout
            try:
                # Keep GUI state reads snappy.
                self.instrument.timeout = 1000
                state["rf"] = self._query_first(["RF?", "FREQ?", "SOUR:FREQ?"]) or "N/A"
                state["level"] = self._query_first(["LEVEL?", "POW?", "SOUR:POW?"]) or "N/A"
                state["fm"] = self._query_first(["FM?", "FM:STAT?"]) or "N/A"
                state["af"] = self._query_first(["AF?", "FM:INT?"]) or "N/A"
            except Exception as e:
                logger.debug(f"Failed to read device state: {e}")
            finally:
                self.instrument.timeout = old_timeout
        return state

    def _query_first(self, queries: List[str]) -> Optional[str]:
        """Return first successful query response, stripped."""
        for query in queries:
            try:
                response = self.instrument.query(query)
                if response is not None:
                    return response.strip()
            except Exception:
                continue
        return None

    def reset(self) -> bool:
        """
        Reset the device to default settings.

        Returns:
            True if successful, False otherwise
        """
        with self._io_lock:
            try:
                self.instrument.write("*RST")
                logger.info("Device reset to defaults")
                return True
            except Exception as e:
                logger.error(f"Failed to reset device: {e}")
                return False

    def get_esr(self) -> Optional[int]:
        """
        Query the Standard Event Status Register (*ESR?) and return its integer value.
        Uses a short timeout to prevent hangs.

        Returns:
            Integer ESR value, or None if query fails/times out
        """
        if not self.instrument:
            return None
        with self._io_lock:
            try:
                # Set a very short timeout for this query
                old_timeout = self.instrument.timeout
                self.instrument.timeout = 500  # 500 ms timeout
                try:
                    resp = self.instrument.query("*ESR?")
                    val = int(resp.strip().split()[-1])  # Extract numeric value
                    return val
                finally:
                    self.instrument.timeout = old_timeout
            except Exception as e:
                logger.debug(f"*ESR? query failed: {e}")
                return None

    def clear_status(self) -> bool:
        """Clear status/error queues on the instrument."""
        if not self.instrument:
            return False
        with self._io_lock:
            try:
                self.instrument.write("*CLS")
                sleep(0.05)
                return True
            except Exception as e:
                logger.debug(f"Failed to clear status: {e}")
                return False

    def _try_commands_with_check(self, commands: List[str], verify_queries: Optional[List[str]] = None) -> bool:
        """
        Try a list of command candidates and check ESR only (no blocking query verification).
        
        Args:
            commands: List of commands to try
            verify_queries: Ignored (for backward compatibility)
        
        Returns True if any command succeeds (ESR = 0)
        """
        if not self.instrument:
            return False

        with self._io_lock:
            for cmd in commands:
                try:
                    # clear previous errors
                    try:
                        self.clear_status()
                    except Exception:
                        pass

                    logger.debug(f"Trying command: {cmd}")
                    self.instrument.write(cmd)
                    sleep(0.15)

                    # Only check ESR, never query command values (they can timeout)
                    esr = self.get_esr()
                    logger.debug(f"*ESR? after {cmd}: {esr}")

                    if esr is not None and esr == 0:
                        logger.debug(f"Command successful: {cmd}")
                        return True
                    elif esr is not None:
                        logger.debug(f"Command '{cmd}' returned ESR={esr}, trying next")
                        continue
                    else:
                        logger.debug(f"ESR check inconclusive for '{cmd}', assuming success")
                        return True
                        
                except Exception as e:
                    logger.debug(f"Command {cmd!r} failed with exception: {e}")
                    continue

        logger.error("All command candidates failed or produced errors")
        return False

    @staticmethod
    def list_available_devices() -> List[str]:
        """
        List all available GPIB/USB devices.

        Returns:
            List of VISA resource names
        """
        rm = pyvisa.ResourceManager()
        devices = rm.list_resources()
        logger.info(f"Available devices: {devices}")
        return list(devices)


if __name__ == "__main__":
    # Example usage
    devices = SMY02Controller.list_available_devices()
    print(f"Available devices: {devices}")
    
    if devices:
        controller = SMY02Controller(devices[0])
        if controller.connect():
            controller.set_frequency(1e9)
            controller.set_amplitude(0)
            controller.enable_output()
            controller.disconnect()
