from nanonisTCP import nanonisTCP



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
        
        from nanonisTCP.Bias import Bias # V
        from nanonisTCP.FolMe import FolMe # x, y
        from nanonisTCP.ZController import ZController # z
        from nanonisTCP.Current import Current # I
        
        self.NTCP = nanonisTCP(self.ip, self.port, self.version)
        
        self.bias = Bias(self.NTCP)
        self.folme = FolMe(self.NTCP)
        self.zcontroller = ZController(self.NTCP)
        self.current = Current(self.NCTP)
    
    def connect_control(self): # Functions to control Nanonis
        if not hasattr(self, "ip"):
            raise Exception("Failed to connect to Nanonis")
        
        self.connect_log()        
        from nanonisTCP.Motor import Motor
        from nanonisTCP.AutoApproach import AutoApproach
        from nanonisTCP.Scan import Scan
        from nanonisTCP.Util import Util
        #from nanonisTCP.Signals import Signals
        #from nanonisTCP.BiasSpectr import BiasSpectr
        #from nanonisTCP.TipShaper import TipShaper
        
        self.NTCP = nanonisTCP(self.ip, self.port, self.version)
        
        self.motor = Motor(self.NTCP)
        self.autoapproach = AutoApproach(self.NTCP)
        self.scan = Scan(self.NTCP)
        self.util = Util(self.NTCP)

    def set_position(self, x, y):
        return self.folme.XYPosSet(x, y, Wait_end_of_move = True)
    
    def get_position(self):
        return self.folme.XYPosGet(Wait_for_newest_data = True)
    
    def set_current(self, I_fb):
        return self.zcontroller.SetpntSet(I_fb)
    
    def get_current(self):
        return self.current.Get()
    
    def get_bias(self):
        return self.bias.Get()
    
    def disconnect(self):
        if hasattr(self, "NTCP"):
            self.NTCP.close_connection()
            del self.NTCP   