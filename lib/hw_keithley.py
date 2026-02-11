from pymeasure.instruments.keithley import Keithley2400
import numpy as np



class KeithleyHW:
    def __init__(self, hardware: dict = {}):
        self.hardware = hardware
        self.GPIB = self.get_GPIB_parameters()
        try:
            self.keithleyhw = Keithley2400(self.GPIB)
        except Exception as e:
            print(f"Error connecting the Keithley: {e}")
        
        self.mode = f"{self.keithleyhw.source_mode} control"
        self.buffer = 10
    
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



    def set_mode(self):
        return

    def get_V(self, buffer = None):
        khw = self.keithleyhw

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

    def get_I(self, buffer = None):
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

    def echo(self):
        print("Hello from Keithley!")
        return

