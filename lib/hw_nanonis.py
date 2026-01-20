from time import sleep
import struct, socket
import numpy as np



# Taken from Julian Cedda's nanonisTCP, used for creating headers upon init instead of on each TCP command
class Conversions:
    def __init__(self):
        pass

    def to_hex(self, conv, num_bytes):
        if(conv >= 0): return hex(conv)[2:].zfill(2 * num_bytes)
        if(conv < 0):  return hex((conv + (1 << 8 * num_bytes)) % (1 << 8 * num_bytes))[2:]

    def hex_to_uint16(self, h16):
        return struct.unpack("<H",struct.pack("H",int("0x" + h16.hex(),16)))[0]

    def hex_to_int32(self, h32):
        return struct.unpack("<i", struct.pack("I", int("0x" + h32.hex(), 16)))[0]

    def hex_to_uint32(self, h32):
        return struct.unpack("<I", struct.pack("I",int("0x" + h32.hex(), 16)))[0]

    def hex_to_float32(self, h32):
        return struct.unpack("<f", struct.pack("I", int("0x" + h32.hex(), 16)))[0]

    def hex_to_float64(self, h64):
        return struct.unpack("<d", struct.pack("Q",int("0x" + h64.hex(), 16)))[0]

    def float32_to_hex(self, f32):
        if(f32 == 0): return "00000000"                                         # workaround for zero. look into this later
        return hex(struct.unpack('<I', struct.pack('<f', f32))[0])[2:]          # float32 to hex

    def float64_to_hex(self, f64):
        if(f64 == 0): return "0000000000000000"
        return hex(struct.unpack('<Q', struct.pack('<d', f64))[0])[2:]

    def float64_micro_to_hex(self, f64):
        if(f64 == 0): return "0000000000000000"
        f64_conv = f64 * 1E-6
        return hex(struct.unpack('<Q', struct.pack('<d', f64_conv))[0])[2:] # float64 to hex

    def float64_nano_to_hex(self, f64):
        if(f64 == 0): return "0000000000000000"
        f64_conv = f64 * 1E-9
        return hex(struct.unpack('<Q', struct.pack('<d', f64_conv))[0])[2:] # float64 to hex

    def float64_pico_to_hex(self, f64):
        if(f64 == 0): return "0000000000000000"
        f64_conv = f64 * 1E-12
        return hex(struct.unpack('<Q', struct.pack('<d', f64_conv))[0])[2:] # float64 to hex

    def make_header(self, command_name, body_size, resp = True):
        """
        Parameters
        command_name : name of the Nanonis function
        body_size    : size of the message body in bytes
        resp         : tell nanonis to send a response. response contains error
                       message so will nearly always want to receive it

        Returns
        hex_rep : hex representation of the header string
        """
        hex_rep = command_name.encode('utf-8').hex()                            # command name
        hex_rep += "{0:#0{1}}".format(0,(64 - len(hex_rep)))                    # command name (fixed 32)
        hex_rep += self.to_hex(body_size, 4)                                    # Body size (fixed 4)
        hex_rep += self.to_hex(resp, 2)                                         # Send response (fixed 2)
        hex_rep += "{0:#0{1}}".format(0, 4)                                     # not used (fixed 2)
        
        return hex_rep



class NanonisHardware:
    def __init__(self, hardware: dict):
        self.hardware = hardware
        self.get_TCP_parameters() # Extract the TCP parameters from the provided hardware dict
        self.conv = Conversions() # Load the conversions
        self.headers = self.prepare_headers() # Make the headers
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Make the socket object

    def get_TCP_parameters(self):
        """
        Extract the IP, port and version from the provided hardware dict
        """
        
        self.ip = False
        self.port = False
        self.version = False
        self.max_buf_size = 200

        ip_tags = ["tcp_ip", "ip", "ip_address", "nanonis_ip"]
        port_tags = ["tcp_port", "port", "nanonis_port"]
        version_tags = ["version", "nanonis_version", "version_number"]
        for key, value in self.hardware.items():
            if key.lower() in ip_tags: self.ip = value
            if key.lower() in port_tags: self.port = value
            if key.lower() in version_tags: self.version = value
        
        if not (self.ip and self.port and self.version):
            raise Exception("Could not extract the required TCP-IP parameters from the provided hardware dictionary")
    
    def prepare_headers(self):
        make_header = self.conv.make_header
        
        headers = {
            # Util
            "get_path": make_header('Util.SessionPathGet', body_size = 0),
            
            # Bias
            "get_V": make_header('Bias.Get', body_size = 0),
            "set_V": make_header('Bias.Set', body_size = 4),
            
            # Folme
            "get_xy": make_header('FolMe.XYPosGet', body_size = 4),
            "set_xy": make_header('FolMe.XYPosSet', body_size = 20),
            "get_v_xy": make_header('FolMe.SpeedGet', body_size = 0),
            "set_v_xy": make_header('FolMe.SpeedSet', body_size = 8),
            
            # Current
            "get_I": make_header('Current.Get', body_size = 0),
            "get_I_gain": make_header('Current.GainsGet', body_size = 0),
            "set_I_gain_old": make_header('Current.GainSet', body_size = 2),
            "set_I_gain_new": make_header('Current.GainSet', body_size = 8),
            
            ##
            "Get100": make_header('Current.100Get', body_size = 0),
            "BEEMGet": make_header('Current.BEEMGet', body_size = 0),
            "CalibrSet_old": make_header('Current.CalibrSet', body_size = 16),
            "CalibrSet_new": make_header('Current.CalibrSet', body_size = 20),
            "CalibrGet_old": make_header('Current.CalibrGet', body_size = 0),
            "CalibrGet_new": make_header('Current.CalibrGet', body_size = 4),
    
            # ZController
            "get_z": make_header('ZCtrl.ZPosGet', body_size = 0),
            "set_z": make_header('ZCtrl.ZPosSet', body_size = 4),
            "get_fb": make_header('ZCtrl.OnOffGet', body_size = 0),
            "set_fb": make_header('ZCtrl.OnOffSet', body_size = 4),
            "get_I_fb": make_header('ZCtrl.SetpntGet', body_size = 0),
            "set_I_fb": make_header('ZCtrl.SetpntSet', body_size = 4),
            "get_gains": make_header('ZCtrl.GainGet', body_size = 0),
            "set_gains": make_header('ZCtrl.GainSet', body_size = 12),
            "set_z_home": make_header('ZCtrl.Home', body_size = 0),
            "withdraw": make_header('ZCtrl.Withdraw', body_size = 8),
            "get_z_limits": make_header('ZCtrl.LimitsGet', body_size = 0),
            
            ##
            "ZSwitchOffDelaySet": make_header('ZCtrl.SwitchOffDelaySet', body_size = 4),
            "ZSwitchOffDelayGet": make_header('ZCtrl.SwitchOffDelayGet', body_size = 0),
            "ZTipLiftSet": make_header('ZCtrl.TipLiftSet', body_size = 4),
            "ZTipLiftGet": make_header('ZCtrl.TipLiftGet', body_size = 0),
            "ZHomePropsSet": make_header('ZCtrl.HomePropsSet', body_size = 6),
            "ZHomePropsGet": make_header('ZCtrl.HomePropsGet', body_size = 0),
            "ZActiveCtrlSet": make_header('ZCtrl.ActiveCtrlSet', body_size = 4),
            "ZCtrlListGet": make_header('ZCtrl.CtrlListGet', body_size = 0),
            "WithdrawRateSet": make_header('ZCtrl.WithdrawRateSet', body_size = 4),
            "WithdrawRateGet": make_header('ZCtrl.WithdrawRateGet', body_size = 0),
            "ZLimitsEnabledSet": make_header('ZCtrl.LimitsEnabledSet', body_size = 4),
            "ZLimitsEnabledGet": make_header('ZCtrl.LimitsEnabledGet', body_size = 0),
            "ZLimitsSet": make_header('ZCtrl.LimitsSet', body_size = 8),
            "ZStatusGet": make_header('ZCtrl.StatusGet', body_size = 0),
            
            # Scan
            "get_v_scan": make_header('Scan.SpeedSet', body_size = 0),
            "set_v_scan": make_header('Scan.SpeedGet', body_size = 0),
            "scan_action": make_header('Scan.Action', body_size = 6),
            "get_scan_status": make_header('Scan.StatusGet', body_size = 0),
            "get_scan_frame": make_header('Scan.FrameGet', body_size=0),
            "set_scan_frame": make_header('Scan.FrameSet', body_size = 20),
            "get_scan_buffer": make_header('Scan.BufferGet', body_size = 0),
            #"set_scan_buffer": make_header('Scan.BufferSet', body_size = body_size)
            "get_scan_props": make_header('Scan.PropsGet', body_size = 0),
            #"set_scan_props": make_header('Scan.PropsSet', body_size = body_size),
            "scan_wait_line": make_header('Scan.WaitEndOfLine', body_size = 4),
            "scan_wait_scan": make_header('Scan.WaitEndOfScan', body_size = 4),
            "get_scan_data": make_header('Scan.FrameDataGrab', body_size = 8),

            # Signals
            "get_signals_in_slots": make_header('Signals.InSlotsGet', body_size = 0),
            
            # Motor
            "get_motor_f_A": make_header('Motor.FreqAmpGet', body_size = 0),
            "set_motor_f_A": make_header('Motor.FreqAmpSet', body_size = 10),
            "coarse_move": make_header('Motor.StartMove', body_size = 14),
            
            # Tipshaper
            "shape_tip": make_header('TipShaper.Start', body_size = 8),
            "get_tip_shaper": make_header('TipShaper.PropsGet', body_size = 0),
            "set_tip_shaper": make_header('TipShaper.PropsSet', body_size = 44),

            # Booleans
            "True": self.conv.to_hex(True, 4),
            "False": self.conv.to_hex(False, 4)
        }

        return headers

    def send_command(self, message):
        self.s.send(bytes.fromhex(message))

    def receive_response(self, error_index = -1, keep_header = False):
        """
        Parameters
        error_index : index of 'error status' within the body. -1 skip check
        keep_header : if true: return entire response. if false: return body
        
        Returns
        response    : either header + body or body only (keep_header)
        
        """
        response = self.s.recv(self.max_buf_size)                               # Read the response
        body_size = self.conv.hex_to_int32(response[32 : 36])
        while(True): 
            if(len(response) == body_size + 40): break                          # body_size + header size (40)
            response += self.s.recv(self.max_buf_size)
        
        if(error_index > -1): self.check_error(response[40:],error_index)       # error_index < 0 skips error check
        
        if(not keep_header):
            return response[40:]                                                # Header is fixed to 40 bytes - drop it
        
        return response
    
    def check_error(self, response, error_index):
        """
        Checks the response from nanonis for error messages

        Parameters
        ----------
        response : response body (not inc. header) from nanonis (bytes)
        error_index : index of error status within the body

        Raises
        ------
        Exception : error message returned from Nanonis
        """
        i = error_index  # error_index points into the body, after the 40-byte header

        if self.version > 14000:
            # error_status (int32)
            error_status = self.conv.hex_to_int32(response[i : i + 4])
            i += 4

            # error_code (int32) – we don't use it but must skip it
            error_code = self.conv.hex_to_int32(response[i : i + 4])
            i += 4

            if error_status != 0:
                # msg_size (int32)
                msg_size = self.conv.hex_to_int32(response[i : i + 4])
                i += 4

                # error message itself
                error_description = response[i : i + msg_size].decode(errors = 'replace')
                raise Exception(error_description)

            return
        else:
            error_status = self.hex_to_uint16(response[i : i + 2])  # 2-byte field
            i += 2

            if error_status != 0:
                # old protocol has no code or size prefix — remainder is message
                error_description = response[i:].decode(errors = 'replace')
                raise Exception(error_description)

            return
                               # raise the exception

    def connect(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Re-establish the socket object if it was lost
        self.s.connect((self.ip, self.port)) # Open the TCP connection.
        
    def disconnect(self):
        self.s.close()
        sleep(.1)

    def __enter__(self):
        return self.connect()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.disconnect()



    # Functions
    # Util
    def get_path(self) -> str:
        command = self.headers["get_path"]
        self.send_command(command)
        
        response = self.receive_response()
        
        session_path_size = self.conv.hex_to_int32(response[0 : 4])
        session_path = response[4 : 4 + session_path_size].decode()
        
        return session_path
    
    # Bias
    def get_V(self) -> float:
        command = self.headers["get_V"]        
        self.send_command(command)
        
        response = self.receive_response(4)        
        bias = self.conv.hex_to_float32(response[0 : 4])
        
        return bias

    def set_V(self, V: float):
        command = self.headers["set_V"] + self.conv.float32_to_hex(V)
        
        self.send_command(command)
        self.receive_response(0)
        
        return

    # Folme
    def get_xy(self, wait: bool = True) -> str:
        command = self.headers["get_xy"] + self.headers[str(wait)]
        self.send_command(command)
        response = self.receive_response(16)
        
        return response
    
    def get_xy_nm(self, wait: bool = True) -> list:
        xy = self.get_xy(wait = wait)
        x = self.conv.hex_to_float64(xy[0 : 8]) * 1E9
        y = self.conv.hex_to_float64(xy[0 : 8]) * 1E9
        return [x, y]
    
    def set_xy(self, xy_hex: str, wait: bool = False) -> None:
        command = self.headers["set_xy"] + xy_hex + self.headers[str(wait)]
        
        self.send_command(command)
        self.receive_response(0)
        
        return

    def set_xy_nm(self, xy_nm: list, wait: bool = False) -> None:
        [x_hex, y_hex] = [self.conv.float64_to_hex(dim * 1E-9) for dim in xy_nm]
        xy_hex = x_hex + y_hex
        
        self.set_xy(xy_hex, wait = wait)
        
        return

    def get_v_xy(self) -> str:
        command = self.headers["get_v_xy"]
        
        self.send_command(command)
        response = self.receive_response(8)
        
        return response

    def get_v_xy_nm_per_s(self) -> float:
        speed_hex = self.get_v_xy()
        speed = self.conv.hex_to_float32(speed_hex[0 : 4]) * 1E9
        
        return speed

    def set_v_xy(self, v_xy_hex: str) -> None:
        command = self.headers["set_v_xy"] + v_xy_hex + self.headers["True"]
        self.send_command(command)
        self.receive_response(0)

        return
        
    def set_v_xy_nm_per_s(self, v_xy_nm_per_s: float) -> None:
        v_xy_hex = self.conv.float32_to_hex(v_xy_nm_per_s * 1E-9)
        self.set_v_xy(v_xy_hex)
        
        return 

    # Current
    def get_I(self) -> str:
        command = self.headers["get_I"]
        self.send_command(command)
        response = self.receive_response(4)
        
        return response[0 : 4]

    def get_I_pA(self) -> float:
        current = self.get_I()
        I_pA = self.conv.hex_to_float32(current) * 1E12
        
        return I_pA

    # ZController
    def get_z(self) -> str:
        command = self.headers["get_z"]
        self.send_command(command)
        
        response = self.receive_response(4)
        z = response[0 : 4]        
        
        return z

    def get_z_nm(self) -> float:
        z = self.get_z()
        z_nm = self.conv.hex_to_float32(z) * 1E9
        
        return z_nm

    def set_z(self, z_hex: str) -> None:
        command = self.headers["set_z"] + z_hex
        
        self.send_command(command)
        self.receive_response(0)
        
        return
    
    def set_z_nm(self, z_nm: float) -> None:
        z_hex = self.conv.float32_to_hex(z_nm * 1E-9)
        self.set_z(z_hex)
        
        return

    def set_fb(self, status: bool = True) -> None:
        command = self.headers["set_fb"] + self.headers[str(status)]
        
        self.send_command(command)        
        self.receive_response(0)
        
        return
    
    def get_fb(self) -> bool:
        command = self.headers["get_fb"]
        
        self.send_command(command)
        response = self.receive_response(4)
        z_status = bool(self.conv.hex_to_uint32(response[0 : 4]))
        
        return z_status

    def get_I_fb(self) -> str:
        command = self.headers["get_I_fb"]
        
        self.send_command(command)
        response = self.receive_response(4)
        
        return response[0 : 4]
    
    def get_I_fb_pA(self) -> float:
        I_fb_hex = self.get_I_fb()
        I_fb_pA = self.conv.hex_to_float32(I_fb_hex) * 1E12
        
        return I_fb_pA

    def set_I_fb(self, setpoint_hex: str) -> None:
        command = self.headers["set_I_fb"] + setpoint_hex
        
        self.send_command(command)        
        self.receive_response(0)
        
        return

    def set_I_fb_pA(self, setpoint_pA: float) -> None:
        setpoint_hex = self.conv.float_32_to_hex(setpoint_pA * 1E12)
        self.set_I_fb(setpoint_hex)

        return

    def get_gains(self) -> dict:
        command = self.headers["get_gains"]
        
        self.send_command(command)        
        response = self.receive_response()
        
        p_gain = self.conv.hex_to_float32(response[0 : 4])
        t_const = self.conv.hex_to_float32(response[4 : 8])
        i_gain = self.conv.hex_to_float32(response[8 : 12])
        
        parameters = {
            "p_gain_pm": p_gain * 1E12,
            "t_const_us": t_const * 1E6,
            "i_gain_nm_per_s": i_gain * 1E9            
        }
        
        return parameters

    def get_z_limits(self) -> str:
        command = self.headers["get_z_limits"]
        self.send_command(command)
        
        response = self.receive_response(8)
        
        return response[0 : 8]
    
    def get_z_limits_nm(self) -> list:
        limits_hex = self.get_z_limits()
        
        z_max_nm = self.conv.hex_to_float32(limits_hex[0 : 4]) * 1E9
        z_min_nm = self.conv.hex_to_float32(limits_hex[0 : 4]) * 1E9
        
        return [z_min_nm, z_max_nm]

    def withdraw(self, wait: bool = True, timeout: int = 60000) -> None:
        command = self.headers["withdraw"] + self.conv.to_hex(self.headers[str(wait)], 4) + self.conv.to_hex(timeout, 4)
        
        self.send_command(command)
        self.receive_response(0)
        
        return

    # Scan
    def get_v_scan(self) -> str:
        command = self.headers["get_v_scan"]
        
        self.send_command(command)
        response = self.receive_response()
        
        return response
    
    def get_v_scan_nm_per_s(self) -> list:
        response = self.get_v_scan()
        
        v_fwd = self.conv.hex_to_float32(response[0 : 4])
        v_bwd = self.conv.hex_to_float32(response[4 : 8])
        t_fwd = self.conv.hex_to_float32(response[8 : 12])
        t_bwd = self.conv.hex_to_float32(response[12 : 16])
        const_param = self.conv.hex_to_uint16(response[16 : 18])
        v_ratio = self.conv.hex_to_float32(response[18 : 22])
        
        speeds = {
            "v_fwd_nm_per_s": v_fwd * 1E9,
            "v_bwd_nm_per_s": v_bwd * 1E9,
            "t_fwd": t_fwd,
            "t_bwd": t_bwd,
            "const_param": const_param,
            "v_ratio": v_ratio            
        }
        
        return speeds

    def get_scan_frame(self) -> str:
        command = self.headers["get_scan_frame"]
        
        self.send_command(command)
        response = self.receive_response(20)
        
        return response
    
    def get_scan_frame_nm(self) -> dict:
        h_to_f = self.conv.hex_to_float32
        response = self.get_scan_frame()
        
        x = h_to_f(response[0 : 4]) * 1E9
        y = h_to_f(response[4 : 8]) * 1E9
        w = h_to_f(response[8 : 12]) * 1E9
        h = h_to_f(response[12 : 16]) * 1E9
        angle = h_to_f(response[16 : 20])
        
        frame = {"x_nm": x, "y_nm": y, "center": [x, y], "offset": [x, y], "width_nm": w, "height_nm": h, "scan_range_nm": [w, h], "angle_deg": angle, "aspect_ratio": h / w}
        
        return frame
        
    def get_scan_buffer(self) -> dict:
        command = self.headers["get_scan_buffer"]
        self.send_command(command)
        
        # Receive Response
        response = self.receive_response()
        
        index = 0
        channel_indices = []
        num_channels = self.conv.hex_to_int32(response[index : index + 4])
        for _ in range(num_channels):
            index += 4
            channel_indices.append(self.conv.hex_to_int32(response[index : index + 4]))
        
        index += 4
        pixels = self.conv.hex_to_int32(response[index : index + 4])        
        index += 4
        lines = self.conv.hex_to_int32(response[index : index + 4])
        pixel_ratio = lines / pixels
        
        parameters = {
            "num_channels": num_channels,
            "channel_indices": channel_indices,
            "pixels": pixels,
            "lines": lines,
            "pixel_ratio": pixel_ratio
        }
        
        return parameters

    def get_scan_props(self) -> dict:
        command = self.headers["get_scan_props"]        
        
        self.send_command(command)
        response = self.receive_response()
        
        continuous_scan = self.conv.hex_to_uint32(response[0 : 4])
        bouncy_scan = self.conv.hex_to_uint32(response[4 : 8])
        auto_save = self.conv.hex_to_uint32(response[8 : 12])
        
        series_name = ""
        series_name_size = self.conv.hex_to_int32(response[12 : 16])
        if(series_name_size > 0): series_name = response[16 : 16 + series_name_size].decode()        
        
        comment = ""
        index = 16 + series_name_size
        comment_size = self.conv.hex_to_int32(response[index : index + 4])
        if(comment_size > 0):
            index += 4
            comment = response[index : index + comment_size].decode()
        
        index = 16 + series_name_size + 4 + comment_size
        modules_names = []
        auto_paste = 0
        
        if(self.version > 14000):
            modules_names_total = self.conv.hex_to_int32(response[index : index+4])
            index += 4

            modules_count = self.conv.hex_to_int32(response[index : index + 4])
            index += 4

            for _ in range(modules_count):
                name_size = self.conv.hex_to_int32(response[index : index + 4])
                index += 4
                modules_names.append(response[index : index + name_size].decode())
                index += name_size

            # auto_paste = self.conv.hex_to_int32(response[index : index + 4])
            auto_paste = 1
            
        parameters = {"continuous": bool(continuous_scan), "bouncy": bool(bouncy_scan), "auto_save": bool(auto_save), "series_name": series_name, "comment": comment, "modules_names": modules_names, "auto_paste": bool(auto_paste)}

        return parameters

    def get_scan_data(self, channel_index: int, backward: bool = False) -> dict:
        """
        Returns the scan data of the selected frame

        Parameters
        channel_index   : selects which channel to get the data from. The 
                          channel must be one of the acquired channels. The 
                          list of acquired channels while scanning can be 
                          configured by the function Scan.BufferSet or read by
                          the function Scan.BufferGet
        data_direction : selects the data direction to be read.
                         0: backward
                         1: forward

        """
        command = self.headers["get_scan_data"] + self.conv.to_hex(channel_index, 4) + self.headers[str(backward)]
                
        self.send_command(command)
        response = self.receive_response()
        
        channel_name_size = self.conv.hex_to_int32(response[0 : 4])
        cns = channel_name_size
        
        channel_name = response[4 : 4 + cns].decode()
        n_rows = self.conv.hex_to_int32(response[4 + cns : 8 + cns])
        n_columns = self.conv.hex_to_int32(response[8 + cns : 12 + cns])
        
        index = 12 + cns
        scan_data = np.empty((n_rows, n_columns))
        for i in range(n_rows):
            for j in range(n_columns):
                index += 4
                scan_data[i, j] = self.conv.hex_to_float32(response[index : index + 4])

        index += 4
        scan_direction = self.conv.hex_to_int32(response[index : index + 4])
        scan_direction = ["down", "up"][scan_direction]
        
        parameters = {"scan_data": scan_data, "channel_name": channel_name, "scan_direction": scan_direction}
        
        return parameters

    def scan_action(self, parameters: dict) -> None:
        direction = parameters.get("direction", "down")
        
        if "start" in parameters.items(): self.start_scan(direction)
        elif "stop" in parameters.items(): self.stop_scan()
        elif "resume" in parameters.items(): self.resume_scan()
        else: self.pause_scan()
        
        return

    def start_scan(self, direction: str = "up") -> None:
        action_dict = {"start": 0, "stop": 1, "pause" : 2, "resume": 3, "down": 0, "up": 1}

        if direction == "up": dir_command = self.conv.to_hex(1, 4)
        else: dir_command = self.conv.to_hex(0, 4)
        command = self.headers["scan_action"] + self.conv.to_hex(0, 2) + dir_command
        
        self.send_command(command)
        self.receive_response(0)
        
        return

    def pause_scan(self) -> None:
        action_dict = {"start": 0, "stop": 1, "pause" : 2, "resume": 3, "down": 0, "up": 1}

        dir_command = self.conv.to_hex(0, 4)
        command = self.headers["scan_action"] + self.conv.to_hex(2, 2) + dir_command
        
        self.send_command(command)
        self.receive_response(0)
        
        return

    def stop_scan(self) -> None:
        dir_command = self.conv.to_hex(0, 4)
        command = self.headers["scan_action"] + self.conv.to_hex(1, 2) + dir_command
        
        self.send_command(command)
        self.receive_response(0)
        
        return

    def resume_scan(self) -> None:
        dir_command = self.conv.to_hex(0, 4)
        command = self.headers["scan_action"] + self.conv.to_hex(3, 2) + dir_command
        
        self.send_command(command)
        self.receive_response(0)
        
        return

    # Signals
    def get_signals_in_slots(self) -> dict:
        command = self.headers["get_signals_in_slots"]
        
        self.send_command(command)        
        response = self.receive_response()
        
        signals_names_num  = self.conv.hex_to_int32(response[4 : 8])
        
        index = 8
        signal_names = []
        for _ in range(signals_names_num):
            size = self.conv.hex_to_int32(response[index : index + 4])
            index += 4
            signal_name = response[index : index + size].decode()
            index += size
            signal_names.append(signal_name)
        
        signal_indices = []
        signal_indices_size = self.conv.hex_to_int32(response[index : index + 4])
        for _ in range(signal_indices_size):
            index += 4
            signal_index = self.conv.hex_to_int32(response[index : index + 4])
            signal_indices.append(signal_index)
        
        parameters = {
            "names": signal_names,
            "indices": signal_indices
        }
            
        return parameters

    # Motor
    def get_motor_f_A(self) -> dict:
        command = self.headers["get_motor_f_A"]        
        self.send_command(command)
        response = self.receive_response(8)

        result = {"frequency": self.conv.hex_to_float32(response[0 : 4]), "amplitude": self.conv.hex_to_float32(response[4 : 8])}
        
        return result
        
    def set_motor_f_A(self, parameters: dict) -> None:
        standard_parameters = {"frequency": 1000, "amplitude": 150, "axis": 0}
        standard_parameters.update(parameters)
        parameters = standard_parameters
        
        command = self.headers["set_motor_f_A"] + self.conv.float32_to_hex(parameters.get("frequency")) + self.conv.float32_to_hex(parameters.get("amplitude")) + self.conv.to_hex(parameters.get("axis", 0), 2)
        self.send_command(command)
        
        self.receive_response(0)
        
        return

    def coarse_move(self, parameters: dict = {}) -> None:
        standard_parameters = {"direction": "up", "steps": 3, "wait": True, "group": 1}
        standard_parameters.update(parameters)
        parameters = standard_parameters        
        
        direction_dict = {
            "x+": 0, "e": 0, "east": 0,
            "x-": 1, "w": 1, "west": 1,
            "y+": 2, "n": 2, "north": 2,
            "y-": 3, "s": 3, "south": 3,
            "z+": 4, "up": 4, "retract": 4, "away": 4, "higher": 4,
            "z-": 5, "down": 5, "approach": 5, "advance": 5, "toward": 5, "towards": 5, "lower": 5
            }
        direction_str = parameters.get("direction").lower()
        direction_int = direction_dict[direction_str]
        steps_int = parameters.get("steps", 0)
        
        group = 0 # Change this in the future?        

        command = self.headers["coarse_move"] + self.conv.to_hex(direction_int, 4) +  self.conv.to_hex(steps_int, 2) + self.conv.to_hex(group, 4) + self.headers[str(parameters.get("wait"))]
        
        self.send_command(command)
        self.receive_response(0)
        
        return

    # Tip shaper
    def shape_tip(self, wait: bool = True, timeout = 60000) -> None:
        command = self.headers["shape_tip"] + self.headers[str(wait)] + self.conv.to_hex(timeout, 4)
        
        self.send_command(command)
        self.receive_response(0)
        
        return


