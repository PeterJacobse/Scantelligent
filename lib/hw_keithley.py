from pymeasure.instruments.keithley import Keithley2400
import numpy as np



class KeithleyHW:
    def __init__(self, hardware: dict = {}):
        self.hardware = hardware
        self.GPIB = self.get_GPIB_parameters()
        self.V_max = 200
        self.I_max = 1E-9
        self.buffer = 10
        try:
            self.keithleyhw = Keithley2400(self.GPIB)
            self.mode = self.keithleyhw.source_mode
        except Exception as e:
            print(f"Error connecting the Keithley: {e}")
    
    def get_GPIB_parameters(self) -> str:
        self.visa_no = False
        self.address = False

        print(self.hardware)

        visa_no_tags = ["keithley_visa_no", "visa_no", "visa_number", "board", "board_no", "board_number"]
        address_tags = ["keithley_address", "address", "device_address", "device_no", "device_number"]
        for key, value in self.hardware.items():
            if key.lower() in visa_no_tags: self.visa_no = value
            if key.lower() in address_tags: self.address = value
                
        if not isinstance(self.visa_no, int) or not isinstance(self.address, int):
            raise Exception("Could not extract the required GPIB parameters from the provided hardware dictionary")

        return f"GPIB{self.visa_no}::{self.address}::INSTR"



    def connect(self, terminal_side: str = "front") -> None:
        khw = self.keithleyhw
        khw.reset()
        
        match terminal_side:
            case "front":
                khw.use_front_terminals()
            case "rear":
                khw.use_rear_terminals()
            case _:
                pass

        khw.source_voltage = 0
        khw.source_current = 0

        khw.enable_source()

        return

    def disconnect(self) -> None:
        khw = self.keithleyhw

        khw.shutdown()

        return

    def set_I_max(self, I_max: float = 0) -> None:
        khw = self.keithleyhw
        
        self.I_max = I_max

        match khw.source_mode:
            case "voltage":
                self.set_mode("voltage", cc = I_max)
            case _:
                pass

        return

    def set_mode(self, mode: str = "voltage", cc = None, cv = None) -> str:
        khw = self.keithleyhw

        match mode.lower():
            case "voltage":
                if not cc == None:
                    khw.apply_voltage(compliance_current = cc)
                else:
                    khw.apply_voltage()
                khw.measure_voltage()
            case "current":
                if not cv == None:
                    khw.apply_current(compliance_voltage = cv)
                else:
                    khw.apply_current()
                khw.measure_current()
            case _:
                pass

        self.mode = khw.source_mode

        return self.mode

    def get_V(self, buffer = None) -> float:
        khw = self.keithleyhw
        v_avg = False

        if khw.source_mode == "voltage":
            return khw.source_voltage
        
        elif khw.source_mode == "current":
            if isinstance(buffer, int): self.buffer = buffer
            khw.config_buffer(self.buffer)
            khw.start_buffer()
            khw.wait_for_buffer()
            voltages = khw.voltage
            v_avg = np.mean(voltages)
            return v_avg
        
        return khw.source_mode

    def set_V(self):
        return

    def get_I(self, buffer = None) -> float:
        khw = self.keithleyhw

        if khw.source_mode == "current":
            return khw.source_current
        
        elif khw.source_mode == "voltage":
            if isinstance(buffer, int): self.buffer = buffer
            khw.config_buffer(self.buffer)
            khw.start_buffer()
            khw.wait_for_buffer()
            currents = khw.current
            i_avg = np.mean(currents)
            return i_avg
        
        return khw.source_mode

    def set_I(self) -> float:
        return

    def echo(self):
        print("Hello from Keithley!")
        return

