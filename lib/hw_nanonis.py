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

    def make_header(self, command_name, body_size, resp = True):
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
        connected = self.connect()
        if not connected == True: raise
        else: self.disconnect()



    def get_TCP_parameters(self) -> None:
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
        
        return
    
    def prepare_headers(self) -> dict:
        make_header = self.conv.make_header

        headers = {
            # Auto Approach
            "auto_approach": make_header('AutoApproach.OnOffSet', body_size = 2),

            # Util
            "get_path": make_header('Util.SessionPathGet', body_size = 0),
            
            # Bias
            "get_V": make_header('Bias.Get', body_size = 0),
            "set_V": make_header('Bias.Set', body_size = 4),
            "pulse": make_header('Bias.Pulse', body_size = 16),
            
            # BiasSpectr
            "open_spectroscopy": make_header('BiasSpectr.Open', body_size = 0),
            "get_spectrum": make_header('BiasSpectr.Start', body_size = 8),
            
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
            "get_v_scan": make_header('Scan.SpeedGet', body_size = 0),
            "set_v_scan": make_header('Scan.SpeedSet', body_size = 22),
            "scan_action": make_header('Scan.Action', body_size = 6),
            "get_scan_status": make_header('Scan.StatusGet', body_size = 0),
            "get_scan_frame": make_header('Scan.FrameGet', body_size = 0),
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
            "get_signal_names": make_header('Signals.NamesGet', body_size = 0),
            "get_signal_value": make_header('Signals.ValGet', body_size = 8),
            
            # Motor
            "get_motor_f_A": make_header('Motor.FreqAmpGet', body_size = 0),
            "set_motor_f_A": make_header('Motor.FreqAmpSet', body_size = 10),
            "coarse_move": make_header('Motor.StartMove', body_size = 14),
            
            # Piezo
            "get_range": make_header('Piezo.RangeGet', body_size = 0),

            # Tipshaper
            "shape_tip": make_header('TipShaper.Start', body_size = 8),
            "get_tip_shaper": make_header('TipShaper.PropsGet', body_size = 0),
            "set_tip_shaper": make_header('TipShaper.PropsSet', body_size = 44),

            # Lockin
            "set_lockin": make_header('LockIn.ModOnOffSet', body_size = 8),

            # Booleans
            "True": self.conv.to_hex(True, 4),
            "False": self.conv.to_hex(False, 4)
        }

        return headers

    def send_command(self, message) -> None:
        self.s.send(bytes.fromhex(message))

    def receive_response(self, error_index: int = -1, keep_header: bool = False) -> str:
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
    
    def check_error(self, response: str, error_index: int = 0) -> None:
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
            error_status = self.conv.hex_to_uint16(response[i : i + 2])  # 2-byte field
            i += 2

            if error_status != 0:
                # old protocol has no code or size prefix — remainder is message
                error_description = response[i:].decode(errors = 'replace')
                raise Exception(error_description)

            return
                               # raise the exception

    def connect(self) -> None:
        try:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Re-establish the socket object if it was lost
            self.s.settimeout(2)
            self.s.connect((self.ip, self.port)) # Open the TCP connection.
            return True
        except Exception as e:
            return e

    def disconnect(self) -> None:
        self.s.close()
        sleep(.05) # Give time to properly close the socket

    def __enter__(self) -> None:
        return self.connect()
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return self.disconnect()



    # Functions
    # Auto Approach
    def auto_approach(self, status: bool = True) -> None:
        command = self.headers["auto_approach"] + self.conv.to_hex(status, 2)
        
        self.send_command(command)
        self.receive_response(0)
        
        return

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

    def set_V(self, V: float) -> None:
        command = self.headers["set_V"] + self.conv.float32_to_hex(V)
        
        self.send_command(command)
        self.receive_response(0)
        
        return

    def pulse(self, V_pulse: float, t_pulse_ms: float, wait: bool = True) -> None:
        command = self.headers["pulse"] + self.headers[str(wait)] + self.conv.float32_to_hex(t_pulse_ms / 1000)
        command += self.conv.float32_to_hex(V_pulse) + self.conv.to_hex(1, 2) + self.conv.to_hex(0, 2)
        
        self.send_command(command)
        self.receive_response(0)
        
        return

    # BiasSpectr
    def open_spectroscopy(self) -> None:
        command = self.headers["open_spectroscopy"]
        self.send_command(command)
        self.receive_response(0)
        
        return
    
    def get_spectrum(self) -> dict:
        """
        Starts a bias spectroscopy in the Bias Spectroscopy module.
        
        Before using this function, select the channels to record in the Bias
        Spectroscopy module.

        Parameters
        ----------
        get_data        : defines if the function returns the spectroscopy data
                          True: return data from this function
                          False: don't return data
        save_base_name  : Base name used by the saved files. Empty string 
                          keeps settings unchanged in nanonis
                    

        Returns
        -------
        if get_data  = False, this function returns None
        
        if get_data != False, this function returns:
            
        data_dict{
            '<channel_name>' : data for this channel
            }
        parameters  : List of fixed parameters and parameters (in that order).
                      To see the names of the returned parameters, use the 
                      BiasSpectr.PropsGet function

        """
                
        command = self.headers["get_spectrum"] + self.headers["True"] + "0000" #self.conv.to_hex("", 4)        
        
        self.send_command(command)
        response = self.receive_response()
        
        number_of_channels  = self.conv.hex_to_int32(response[4 : 8])
        
        idx = 8
        channel_names = []
        for i in range(number_of_channels):
            channel_name_size = self.conv.hex_to_int32(response[idx : idx + 4])
            idx += 4
            channel_names.append(response[idx : idx + channel_name_size].decode())
            idx += channel_name_size
        
        data_rows = self.conv.hex_to_int32(response[idx : idx + 4])
        idx += 4
        data_cols = self.conv.hex_to_int32(response[idx : idx + 4])
        
        data_dict = {}
        for i in range(data_rows):
            data = []
            for j in range(data_cols):
                idx += 4
                data.append(self.conv.hex_to_float32(response[idx : idx + 4]))
            data_dict[channel_names[i]] = np.array(data)
        
        idx += 4
        parameters = []
        number_of_parameters = self.conv.hex_to_int32(response[idx : idx + 4])
        for i in range(number_of_parameters):
            idx += 4
            parameter = self.conv.hex_to_float32(response[idx : idx + 4])
            parameters.append(parameter)
        
        return {"data_dict" : data_dict, "parameters" : parameters}

    # Folme
    def get_xy(self, wait: bool = True) -> str:
        command = self.headers["get_xy"] + self.headers[str(wait)]
        self.send_command(command)
        response = self.receive_response(16)
        
        return response
    
    def get_xy_nm(self, wait: bool = True) -> list:
        xy = self.get_xy(wait = wait)
        x = self.conv.hex_to_float64(xy[0 : 8]) * 1E9
        y = self.conv.hex_to_float64(xy[8 : 16]) * 1E9
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
        setpoint_hex = self.conv.float32_to_hex(setpoint_pA * 1E-12)
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
            "p_gain (pm)": p_gain * 1E12,
            "t_const (us)": t_const * 1E6,
            "i_gain (nm/s)": i_gain * 1E9            
        }
        
        return parameters

    def set_gains(self, gains: dict) -> None:
        p_gain_pm = gains.get("p_gain (pm)", None)
        t_const_us = gains.get("t_const (us)", None)
        i_gain_nm_per_s = gains.get("i_gain (nm/s)", None)

        gains_dict = self.get_gains() # Get current gains to fill in any missing values
        if p_gain_pm: gains_dict.update({"p_gain (pm)": p_gain_pm})
        if t_const_us: gains_dict.update({"t_const (us)": t_const_us})
        if i_gain_nm_per_s: gains_dict.update({"i_gain (nm/s)": i_gain_nm_per_s})

        p_gain_pm = gains.get("p_gain (pm)", None)
        t_const_us = gains.get("t_const (us)", None)
        i_gain_nm_per_s = gains.get("i_gain (nm/s)", None)
        
        p_gain_hex = self.conv.float32_to_hex(p_gain_pm * 1E-12) if p_gain_pm is not None else "00000000"
        t_const_hex = self.conv.float32_to_hex(t_const_us * 1E-6) if t_const_us is not None else "00000000"
        i_gain_hex = self.conv.float32_to_hex(i_gain_nm_per_s * 1E-9) if i_gain_nm_per_s is not None else "00000000"
        
        command = self.headers["set_gains"] + p_gain_hex + t_const_hex + i_gain_hex
        
        self.send_command(command)
        self.receive_response(0)
        
        return

    def get_z_limits(self) -> str:
        command = self.headers["get_z_limits"]
        self.send_command(command)
        
        response = self.receive_response(8)
        
        return response[0 : 8]
    
    def get_z_limits_nm(self) -> list:
        limits_hex = self.get_z_limits()
        
        z_max_nm = self.conv.hex_to_float32(limits_hex[0 : 4]) * 1E9
        z_min_nm = self.conv.hex_to_float32(limits_hex[4 : 8]) * 1E9
        
        return [z_min_nm, z_max_nm]

    def withdraw(self, wait: bool = True, timeout: int = 60000) -> None:
        command = self.headers["withdraw"] + self.headers[str(wait)] + self.conv.to_hex(timeout, 4)
        
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
            "v_fwd (nm/s)": v_fwd * 1E9,
            "v_bwd (nm/s)": v_bwd * 1E9,
            "t_fwd (us)": t_fwd,
            "t_bwd (us)": t_bwd,
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
        
        frame = {"x (nm)": x, "y (nm)": y, "center (nm)": [x, y], "offset (nm)": [x, y], "width (nm)": w, "height (nm)": h, "scan_range (nm)": [w, h], "angle (deg)": angle, "aspect_ratio": h / w}
        
        return frame

    def set_scan_frame(self, frame_hex: str) -> None:
        command = self.headers["set_scan_frame"] + frame_hex
        
        self.send_command(command)
        self.receive_response(0)
        
        return
    
    def set_scan_frame_nm(self, frame: dict) -> None:
        if "width (nm)" in frame.keys():
            w_nm = frame.get("width (nm)")
            h_nm = frame.get("height (nm)", w_nm)
        elif "scan_range (nm)" in frame.keys():
            [w_nm, h_nm] = frame.get("scan_range (nm)")
        elif "size (nm)" in frame.keys():
            [w_nm, h_nm] = frame.get("size (nm)")
        
        if "x (nm)" in frame.keys():
            x_nm = frame.get("x (nm)", 0)
            y_nm = frame.get("y (nm)", 0)
        elif "offset (nm)" in frame.keys():
            [x_nm, y_nm] = frame.get("offset (nm)")
        elif "center (nm)" in frame.keys():
            [x_nm, y_nm] = frame.get("center (nm)")
        
        angle = frame.get("angle (deg)", 0)

        x_hex = self.conv.float32_to_hex(x_nm * 1E-9)
        y_hex = self.conv.float32_to_hex(y_nm * 1E-9)
        w_hex = self.conv.float32_to_hex(w_nm * 1E-9)
        h_hex = self.conv.float32_to_hex(h_nm * 1E-9)
        angle_hex = self.conv.float32_to_hex(angle)
        
        frame_hex = x_hex + y_hex + w_hex + h_hex + angle_hex
        
        self.set_scan_frame(frame_hex)
        
        return

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

    def start_scan(self, direction: str = "up") -> None:
        # action_dict = {"start": 0, "stop": 1, "pause" : 2, "resume": 3, "down": 0, "up": 1}

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
        signals_names_num = self.conv.hex_to_int32(response[4 : 8])
        
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

    def get_signal_names(self) -> list:
        command = self.headers["get_signal_names"]
        
        self.send_command(command)
        response = self.receive_response()

        signals_names_num  = self.conv.hex_to_int32(response[4 : 8])
        
        idx = 8
        signal_names = []
        for n in range(signals_names_num):
            size = self.conv.hex_to_int32(response[idx : idx + 4])
            idx += 4
            signal_name = response[idx:idx+size].decode()
            idx += size
            signal_names.append(signal_name)
        
        return signal_names

    def get_signal_value(self, signal_index: int, wait: bool = True) -> float:
        command = self.headers["get_signal_value"] + self.conv.to_hex(signal_index, 4) + self.headers[str(wait)]

        self.send_command(command)
        response = self.receive_response(4)

        signal_value = self.conv.hex_to_float32(response[0 : 4])

        return signal_value        

    # Motor
    def get_motor_f_A(self) -> dict:
        command = self.headers["get_motor_f_A"]        
        self.send_command(command)
        response = self.receive_response(8)

        result = {"f_motor (Hz)": self.conv.hex_to_float32(response[0 : 4]), "V_motor (V)": self.conv.hex_to_float32(response[4 : 8])}
        
        return result
        
    def set_motor_f_A(self, parameters: dict) -> None:
        old_parameters = self.get_motor_f_A()

        f_motor = parameters.get("f_motor (Hz)")
        if type(f_motor) == int or type(f_motor) == float:
            old_parameters.update({"f_motor (Hz)": f_motor})
        
        V_motor = parameters.get("V_motor (V)")
        if type(V_motor) == int or type(V_motor) == float:
            old_parameters.update({"V_motor (V)": V_motor})
        
        parameters = old_parameters
        if "axis" not in parameters.keys(): parameters.update({"axis": 0})

        command = self.headers["set_motor_f_A"] + self.conv.float32_to_hex(parameters.get("f_motor (Hz)")) + self.conv.float32_to_hex(parameters.get("V_motor (V)")) + self.conv.to_hex(parameters.get("axis", 0), 2)
        self.send_command(command)
        
        self.receive_response(0)
        
        return

    def coarse_move(self, parameters: dict = {}, wait: bool = True) -> None:
        direction_dict = {
            "x+": 0, "e": 0, "east": 0,
            "x-": 1, "w": 1, "west": 1,
            "y+": 2, "n": 2, "north": 2,
            "y-": 3, "s": 3, "south": 3,
            "z+": 4, "up": 4, "retract": 4, "away": 4, "higher": 4,
            "z-": 5, "down": 5, "approach": 5, "advance": 5, "toward": 5, "towards": 5, "lower": 5
            }
        direction_str = parameters.get("direction", "none").lower()

        if direction_str not in direction_dict.keys():
            raise ValueError(f"Invalid direction '{direction_str}'. Valid directions are: {list(direction_dict.keys())}")
        
        direction_int = direction_dict[direction_str]
        steps_int = int(parameters.get("steps", 0))

        group = 0 # Change this in the future?
        command = self.headers["coarse_move"] + self.conv.to_hex(direction_int, 4) + self.conv.to_hex(steps_int, 2) + self.conv.to_hex(group, 4) + self.headers[str(wait)]
        
        self.send_command(command)
        self.receive_response(0)
        
        return

    # Piezo
    def get_range(self) -> str:
        command = self.headers["get_range"]
        
        self.send_command(command)
        response = self.receive_response(12)
        
        return response

    def get_range_nm(self) -> list:
        range_str = self.get_range()

        xyz_nm = [self.conv.hex_to_float32(range_str[i : i + 4]) * 1E9 for i in range(0, 12, 4)]

        return xyz_nm

    # Tip shaper
    def shape_tip(self, wait: bool = True, timeout = 60000) -> None:
        command = self.headers["shape_tip"] + self.headers[str(wait)] + self.conv.to_hex(timeout, 4)
        
        self.send_command(command)
        self.receive_response(0)
        
        return

    # Lock-in
    def set_lockin(self, mod_number: int = 1, on: bool = True) -> None:
        command = self.headers["set_lockin"] + self.conv.to_hex(mod_number, 4) + self.conv.to_hex(int(on), 4)
        
        self.send_command(command)
        response = self.receive_response(0)

        return response



    # Work in progress
    def get_lockin_amp(self, mod_number: int = 1) -> float:

        return


