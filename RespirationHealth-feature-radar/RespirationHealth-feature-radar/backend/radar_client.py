import serial
import time
import struct
import numpy as np

class RadarClient:
    def __init__(self, config_port, data_port, baud_rate=921600):
        self.config_port = config_port
        self.data_port = data_port
        self.baud_rate = baud_rate
        self.ser_config = None
        self.ser_data = None
        self.is_connected = False
        
    def connect(self):
        try:
            self.disconnect()
            self.ser_config = serial.Serial(self.config_port, 115200, timeout=1)
            self.ser_data = serial.Serial(self.data_port, self.baud_rate, timeout=1)
            self.is_connected = True
            print(f"Connected to Radar on {self.config_port} and {self.data_port}")
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
            
    def disconnect(self):
        try:
            if self.ser_config and self.ser_config.is_open:
                self.ser_config.close()
            if self.ser_data and self.ser_data.is_open:
                self.ser_data.close()
        except:
            pass
        self.is_connected = False

    def send_command(self, command):
        if not self.is_connected: return False
        try:
            self.ser_config.write((command + '\r\n').encode())
            time.sleep(0.1)
            return True
        except:
            return False

    def send_config(self, config_path):
        if not self.is_connected: return False
        try:
            with open(config_path, 'r') as f:
                lines = f.readlines()
            
            print(f"Uploading {len(lines)} lines from {config_path}...")
            for line in lines:
                clean_line = line.strip()
                if not clean_line or clean_line.startswith('%'): continue
                
                self.ser_config.write((clean_line + '\r\n').encode())
                time.sleep(0.1)
                
                if self.ser_config.in_waiting:
                    self.ser_config.read(self.ser_config.in_waiting)
            
            print("Configuration upload complete.")
            return True
        except Exception as e:
            print(f"Config upload error: {e}")
            return False

    def read_frame(self):
        """Parses TLV Type 6 (Vital Signs) from TI mmWave Radar."""
        if not self.is_connected or self.ser_data.in_waiting < 40:
            return None
            
        try:
            # Magic Word: 02 01 04 03 06 05 08 07
            magic = self.ser_data.read(8)
            if magic != b'\x02\x01\x04\x03\x06\x05\x08\x07':
                return None
                
            header = self.ser_data.read(32)
            if len(header) < 32: return None
            
            total_len = struct.unpack('<I', header[4:8])[0]
            num_tlvs = struct.unpack('<I', header[28:32])[0]
            
            payload_len = total_len - 40
            payload = self.ser_data.read(payload_len)
            
            output = {
                "heart_rate": 0,
                "resp_rate": 0,
                "range": 0,
                "heart_wf": 0,
                "resp_wf": 0,
                "heart_fft": 0,
                "resp_fft": 0
            }
            
            offset = 0
            for _ in range(num_tlvs):
                if offset + 8 > len(payload): break
                tlv_type, tlv_len = struct.unpack_from('<II', payload, offset)
                offset += 8
                
                if tlv_type == 6: # Vital Signs TLV
                    tlv_data = payload[offset:offset+tlv_len]
                    
                    # Offsets based on TI Vital Signs lab documentation
                    output["resp_wf"] = struct.unpack_from('<f', tlv_data, 28)[0]
                    output["heart_wf"] = struct.unpack_from('<f', tlv_data, 32)[0]
                    output["heart_fft"] = struct.unpack_from('<f', tlv_data, 36)[0]
                    output["resp_fft"] = struct.unpack_from('<f', tlv_data, 52)[0]
                    
                    # Try to extract range (Multi-method attempt from user code)
                    # Often found at offset 64 if the lab config supports it
                    try:
                        r_val = struct.unpack_from('<f', tlv_data, 64)[0]
                        if 0.2 < r_val < 3.0:
                            output["range"] = r_val
                    except:
                        pass
                
                offset += tlv_len
            
            return output
        except Exception as e:
            return None
