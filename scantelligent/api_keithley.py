import time
from PyQt6 import QtCore
from pymeasure.instruments.keithley import Keithley2400
import numpy as np



class KeithleyAPI(QtCore.QObject):
    parameters = QtCore.pyqtSignal(dict)

    def __init__(self, hw_config: dict[str, object] = {}, visa_no: int | None = None, address: int | None = None):
        super().__init__()
        
        self.buffer = 8
        
        if isinstance(visa_no, int) and isinstance(address, int):
            self.visa_no = visa_no
            self.address = address
        elif isinstance(hw_config, dict):
            self.visa_no, self.address = self.get_visa_from_dict(hw_config)
        else:
            raise Exception("KeithleyAPI: Neither a valid configuration dict nor explicit visa number and address were provided.")
        
        self.GPIB_string = f"GPIB{self.visa_no}::{self.address}::INSTR"
        self.core = Keithley2400(self.GPIB_string)



    def get_visa_from_dict(self, hw_config: dict[str, object]) -> tuple[int, int]:
        self.visa_no = -1
        self.address = -1

        if "keithley" in [key.lower() for key in hw_config.keys()] and isinstance(hw_config["keithley"], dict): keithley_config = hw_config["keithley"]
        else: keithley_config = hw_config

        visa_no_tags = ["keithley_visa_no", "visa_no", "visa_number", "board", "board_no", "board_number"]
        address_tags = ["keithley_address", "address", "device_address", "device_no", "device_number"]
        for key, value in keithley_config.items():
            if key.lower() in visa_no_tags: self.visa_no = value
            if key.lower() in address_tags: self.address = value
                
        if not isinstance(self.visa_no, int) or not isinstance(self.address, int): raise Exception("Could not extract the required GPIB parameters from the provided hardware dictionary")
        return self.visa_no, self.address

    def link(self) -> None:
        try:
            self.core.reset()

            self.core.source_voltage = 0
            self.core.source_current = 0

            self.core.stop_buffer()
            self.core.disable_buffer()
            self.core.enable_source()
            self.parameters.emit({"dict_name": "keithley_status", "status": "running"})
        except:
            pass
        return

    def use_front_terminals(self, value: bool = True) -> None:
        if value: self.core.use_front_terminals()
        else: self.core.use_rear_terminals()
        return

    def use_rear_terminals(self, value: bool = True) -> None:
        if value: self.core.use_rear_terminals()
        else: self.core.use_front_terminals()
        return

    def unlink(self) -> None:
        self.core.shutdown()
        self.parameters.emit({"dict_name": "keithley_status", "status": "offline"})
        return

    def initialize(self) -> None:
        self.parameters.emit({"dict_name": "keithley_status", "status": "online"})
        return



    def beep(self, frequency: float | int = 600., duration_s: float = 1.) -> None:
        if duration_s < 0 or duration_s > 7.9:
            print("Beep duration should be between 0 and 7.9 seconds.")
            return
        self.core.beep(frequency = frequency, duration = duration_s)
        return

    def source_mode(self) -> str:        
        return str(self.core.source_mode)

    def set_mode(self, source: str = "voltage", nplc: int = 1, compliance_current_nA: float | int | None = 1000, compliance_voltage_V: float | int | None = None, buffer: int | None = None) -> str:
        match source.lower():
            case "voltage":
                if isinstance(compliance_current_nA, (float, int)):
                    compliance_current_A = compliance_current_nA * 1e-9
                    self.core.apply_voltage(compliance_current = compliance_current_A)
                else:
                    self.core.apply_voltage()
                self.core.measure_current(nplc = nplc, auto_range = True)
            case "current":
                if isinstance(compliance_voltage_V, (float, int)):
                    self.core.apply_current(compliance_voltage=compliance_voltage_V)
                else:
                    self.core.apply_current()
                self.core.measure_voltage(nplc = nplc, auto_range = True)
            case _:
                pass

        self.set_buffer(buffer)
        return self.source_mode()

    def set_buffer(self, number: int | None = 1) -> None:
        if isinstance(number, int) and 0 < number < 1000:
            self.core.write(":TRAC:FEED:CONT NEV") 
            self.core.disable_buffer()
            self.core.stop_buffer()
            self.core.reset_buffer()
            self.core.config_buffer(points = number)
            self.core.buffer_points = number
            self.buffer = number
        return

    def get_V(self, buffer: int | None = None) -> float:
        match self.source_mode():
            case "voltage":
                V_avg = self.core.source_voltage
                return float(V_avg) if isinstance(V_avg, float | int) else 0.
            case "current":
                source_current = self.core.source_current
                if not isinstance(source_current, float | int): return 0.
                V_avg = self.set_I(source_current, get_V = True)
                return V_avg
            case _:
                return 0.

    def set_V(self, voltage_V: float | int | None = None, get_I: bool = False) -> float | None:
        if not isinstance(voltage_V, float | int): return
        
        match self.source_mode():
            case "voltage":
                if get_I:
                    self.core.source_voltage = voltage_V
                    self.core.start_buffer()
                    self.core.wait_for_buffer()
                    I_avg = self.core.mean_current
                    return I_avg
                else:
                    self.core.source_voltage = voltage_V
                    self.core.stop_buffer()
            case _: 
                print(f"Warning. Cannot set voltage while source mode is {self.source_mode()}. Use KeithleyAPI.set_mode(mode = \"voltage\") to switch.")
        return

    def get_I(self, buffer: int | None = None, unit: str = "A") -> float:
        match self.source_mode():
            case "current":
                I_avg = self.core.source_current
                return float(I_avg) if isinstance(I_avg, float | int) else 0.
            case "voltage":
                source_voltage = self.core.source_voltage
                if not isinstance(source_voltage, float | int): return 0.
                I_avg = self.set_V(source_voltage, get_I = True)
            case _: 
                return 0.
        
        match unit:
            case "A": return I_avg
            case "nA": return I_avg * 1e9
            case _:
                print(f"Unit {unit} not yet implemented. Returning current in A")
                return I_avg

    def set_I(self, current: float | int | None = None, unit: str = "A", get_V: bool = False) -> float | None:
        if not isinstance(current, float | int): return
        
        current_A = current * 1e-9 if unit == "nA" else current
        
        match self.source_mode():
            case "current":
                if get_V:
                    self.core.source_current = current_A
                    self.core.start_buffer()
                    self.core.wait_for_buffer()
                    V_avg = self.core.mean_voltage
                    return V_avg
                else:
                    self.core.source_current = current_A
                    self.core.stop_buffer()
            case _: 
                print(f"Warning. Cannot set current while source mode is {self.source_mode()}. Use KeithleyAPI.set_mode(mode=\"current\") to switch.")
        return


