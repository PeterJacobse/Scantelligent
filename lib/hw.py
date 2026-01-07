from nanonisTCP import nanonisTCP
from time import sleep



class NanonisHardware:
    def __init__(self, hardware: dict):
        hardware_keys = hardware.keys()
        if "nanonis_ip" in hardware_keys and "nanonis_port" in hardware_keys and "nanonis_version" in hardware_keys:
            self.ip = hardware["nanonis_ip"]
            self.port = hardware["nanonis_port"]
            self.version = hardware["nanonis_version"]
        else:
            raise Exception("Could not establish the TCP-IP parameters for Nanonis")



    def connect_log(self): # Functions to do simple measurements / logging
        if not hasattr(self, "ip"):
            raise Exception("Failed to connect to Nanonis")
        if hasattr(self, "NTCP"): # If the TCP connection alread exists, kill it before reestablishing
            self.disconnect()
            sleep(.2)
        
        from nanonisTCP.Bias import Bias # V
        from nanonisTCP.FolMe import FolMe # x, y
        from nanonisTCP.ZController import ZController # z
        from nanonisTCP.Current import Current # I
        
        self.NTCP = nanonisTCP(self.ip, self.port, self.version)
        
        self.bias = Bias(self.NTCP)
        self.folme = FolMe(self.NTCP)
        self.zcontroller = ZController(self.NTCP)
        self.current = Current(self.NTCP)

    # Simple functions    
    def get_xy(self):
        return list(self.folme.XYPosGet(Wait_for_newest_data = True))

    def set_xy(self, x, y):
        return self.folme.XYPosSet(x, y, Wait_end_of_move = True)

    def get_z(self):
        return self.zcontroller.ZPosGet()

    def set_z(self, z):
        return self.zcontroller.ZPosSet(z)
    
    def get_setpoint(self):
        return self.zcontroller.SetpntGet()

    def set_setpoint(self, I_fb):
        return self.zcontroller.SetpntSet(I_fb)
    
    def get_I(self):
        return self.current.Get()

    def get_V(self):
        return self.bias.Get()
    
    def set_V(self, V):
        return self.bias.Set(V)

    def get_speed(self):
        return list(self.folme.SpeedGet())

    def get_feedback(self):
        return bool(self.zcontroller.OnOffGet())

    def set_feedback(self, boolean: bool = True):
        return self.zcontroller.OnOffSet(boolean)

    def get_gains(self):
        return list(self.zcontroller.GainGet())



    def connect_control(self): # Functions to control Nanonis
        
        self.connect_log() # Import the libraries from the simpler connect_log
        
        from nanonisTCP.Motor import Motor
        from nanonisTCP.AutoApproach import AutoApproach
        from nanonisTCP.Scan import Scan
        from nanonisTCP.Util import Util
        from nanonisTCP.Signals import Signals
        #from nanonisTCP.BiasSpectr import BiasSpectr
        #from nanonisTCP.TipShaper import TipShaper

        self.motor = Motor(self.NTCP)
        self.autoapproach = AutoApproach(self.NTCP)
        self.scan = Scan(self.NTCP)
        self.util = Util(self.NTCP)
        self.signals = Signals(self.NTCP)

    def get_path(self):
        return self.util.SessionPathGet()
    
    def start_scan(self, direction: str = "up"):
        return self.scan.Action("start", scan_direction = direction)

    def stop_scan(self):
        return self.scan.Action("stop")

    def pause_scan(self):
        return self.scan.Action("pause")
    
    def resume_scan(self):
        return self.scan.Action("resume")



    def disconnect(self):
        if hasattr(self, "NTCP"):
            self.NTCP.close_connection()
            del self.NTCP   