"""
Raspberry Pi PICO用 Intel Hex Loader (CircuitPython版)
CircuitPythonで動作し、USB CDC経由で受信したデータをGPIOに出力する
標準入出力とは独立してUSBシリアルを使用するため、print()でのデバッグが可能
"""

import board
import digitalio
import time
import usb_cdc

# GPIO設定（CircuitPythonのboard定義を使用）
ADDR_PINS = [board.GP0, board.GP1, board.GP2, board.GP3, 
             board.GP4, board.GP5, board.GP6, board.GP7]     # アドレスバス
DATA_PINS = [board.GP8, board.GP9, board.GP10, board.GP11,
             board.GP12, board.GP13, board.GP14, board.GP15]  # データバス
WE_PIN = board.GP16  # /WE (Write Enable) 信号 - Active Low
LED_PIN = board.LED  # PICO内蔵LED

# デバッグモード
DEBUG = True  # USB CDCを使うので、print()でのデバッグが可能

def error_led_blink(led_pin=LED_PIN, count=5, interval=1):
    """エラー時のLED点滅パターン（共通関数）"""
    led = digitalio.DigitalInOut(led_pin)
    led.direction = digitalio.Direction.OUTPUT
    for _ in range(count):
        led.value = True  # LED点灯
        time.sleep(interval)
        led.value = False  # LED消灯
        time.sleep(interval)

class PicoHexLoader:
    def __init__(self):
        """GPIOとシリアル通信の初期化"""
        # LEDの初期化
        self.led = digitalio.DigitalInOut(LED_PIN)
        self.led.direction = digitalio.Direction.OUTPUT
        self.led.value = False  # LED消灯
        
        # Write Enable期間の設定（デフォルト: 0.3ms）
        self.we_pulse_ms = 0.3
        
        # USB CDCシリアルポートを取得
        try:
            if not usb_cdc.data:
                raise ValueError("USB CDC data port not available. Please enable it in boot.py")
            self.serial = usb_cdc.data
            self.serial.timeout = 0.1  # 100msタイムアウト
        except Exception as e:
            print(f"Error: USB CDC initialization failed: {e}")
            print("Please ensure boot.py contains: usb_cdc.enable(console=True, data=True)")
            # エラー時はLEDを点滅させる
            error_led_blink()
            raise
        
        # 受信バッファ
        self.rx_buffer = bytearray()
        
        # アドレスバスの設定
        self.addr_pins = []
        for pin in ADDR_PINS:
            p = digitalio.DigitalInOut(pin)
            p.direction = digitalio.Direction.OUTPUT
            p.value = False
            self.addr_pins.append(p)
        
        # データバスの設定
        self.data_pins = []
        for pin in DATA_PINS:
            p = digitalio.DigitalInOut(pin)
            p.direction = digitalio.Direction.OUTPUT
            p.value = False
            self.data_pins.append(p)
        
        # /WE信号の設定（初期値はHigh = 非アクティブ）
        self.we_pin = digitalio.DigitalInOut(WE_PIN)
        self.we_pin.direction = digitalio.Direction.OUTPUT
        self.we_pin.value = True
        
        if DEBUG:
            print("[DEBUG] GPIO and USB CDC initialized")
    
    
    def write_byte(self, address, data):
        """1バイトをGPIOに出力"""
        
        # アドレスを設定
        for i in range(8):
            self.addr_pins[i].value = bool((address >> i) & 1)
        
        # データを設定
        for i in range(8):
            self.data_pins[i].value = bool((data >> i) & 1)
        
        # WEを有効にする前にAddressとDataを設定した後に、ほんの少しだけ待つ
        time.sleep(0.001)

        # /WE信号をLow（アクティブ）にして書き込み
        # WEが有効な間は、LEDを点灯させる
        self.led.value = True
        self.we_pin.value = False
        time.sleep(self.we_pulse_ms / 1000.0)  # WEパルス幅
        self.led.value = False
        
        # /WE信号をHigh（非アクティブ）に戻す
        self.we_pin.value = True
        # 次の書き込みまでの待機時間
        time.sleep(self.we_pulse_ms / 1000.0)  # WEパルス幅
        
        if DEBUG:
            print(f"[DEBUG] Write: ADDR=0x{address:02X}, DATA=0x{data:02X}, /WE=0 (active)")
    
    def parse_command(self, line):
        """コマンドを解析"""
        line = line.strip()
        
        # 単一文字コマンド
        if len(line) == 1:
            if line in ['P', 'E']:
                return {'cmd': line}
            else:
                return {'error': 'COMMAND', 'message': f'Unknown command: {line}'}
        
        # Timingコマンド（WE期間設定）
        if line.startswith('T:'):
            try:
                parts = line.split(':', 1)
                if len(parts) != 2:
                    return {'error': 'FORMAT', 'message': 'Invalid timing format'}
                
                pulse_ms = float(parts[1])
                
                # 範囲チェック（0.1-1000ms）
                if not (0.1 <= pulse_ms <= 1000):
                    return {'error': 'RANGE', 'message': 'Timing must be 0.1-1000ms'}
                
                return {
                    'cmd': 'T',
                    'pulse_ms': pulse_ms
                }
                
            except Exception as e:
                return {'error': 'FORMAT', 'message': str(e)}
        
        # Writeコマンド
        if line.startswith('W:'):
            try:
                parts = line.split(':', 3)
                if len(parts) != 4:
                    return {'error': 'FORMAT', 'message': 'Invalid write format'}
                
                start_address = int(parts[1], 16)
                length = int(parts[2], 16)
                hex_data = parts[3]
                
                # データ長チェック
                if length == 0 or length > 255:
                    return {'error': 'LENGTH', 'message': f'Invalid length: {length}'}
                
                if len(hex_data) != length * 2:
                    return {'error': 'LENGTH', 'message': f'Expected {length*2} hex chars, got {len(hex_data)}'}
                
                # 16進数文字列をバイト配列に変換
                data = []
                for i in range(0, len(hex_data), 2):
                    data.append(int(hex_data[i:i+2], 16))
                
                return {
                    'cmd': 'W',
                    'start_address': start_address,
                    'length': length,
                    'data': data
                }
                
            except Exception as e:
                return {'error': 'FORMAT', 'message': str(e)}
        
        return {'error': 'COMMAND', 'message': f'Unknown command: {line}'}
    
    def send_response(self, status, message):
        """レスポンスを送信"""
        response = f"{status}:{message}\n"
        self.serial.write(response.encode())
        if DEBUG:
            print(f"[DEBUG] Sent: {response.strip()}")
    
    def handle_write_command(self, start_address, length, data):
        """Writeコマンドを処理"""
        if DEBUG:
            print(f"[DEBUG] Write command: START_ADDR=0x{start_address:02X}, LENGTH={length}")
        
        # 各バイトを書き込み
        for i in range(length):
            address = (start_address + i) & 0xFF  # 8ビットアドレスに制限
            self.write_byte(address, data[i])
            
            if DEBUG:
                print(f"[DEBUG] Writing byte {i+1}/{length}: ADDR=0x{address:02X}, DATA=0x{data[i]:02X}")
        
        self.send_response("OK", "WRITE")
    
    def read_line(self):
        """シリアルから1行読み込み（CRLF/LF対応）- ノンブロッキング"""
        MAX_LINE_LENGTH = 1024  # 最大行長
        
        # 新しいデータを読み込み
        data = self.serial.read()
        if data:
            self.rx_buffer.extend(data)
        
        # バッファサイズチェック
        if len(self.rx_buffer) > MAX_LINE_LENGTH:
            # 長すぎる行は破棄
            self.rx_buffer = bytearray()
            return None
        
        # 改行文字を探す（\n or \r\n）
        newline_pos = self.rx_buffer.find(b'\n')
        if newline_pos >= 0:
            # 改行までのデータを取得
            line_data = self.rx_buffer[:newline_pos]
            # CRLFの場合、CRを削除
            if line_data.endswith(b'\r'):
                line_data = line_data[:-1]
            
            try:
                line = line_data.decode('utf-8')
            except UnicodeDecodeError:
                # デコードエラーは無視
                self.rx_buffer = self.rx_buffer[newline_pos + 1:]
                return None
            
            # バッファから削除
            self.rx_buffer = self.rx_buffer[newline_pos + 1:]
            return line
        
        # 完全な行がまだない
        return None
    
    def run(self):
        """メインループ"""
        print("PICO Hex Loader (USB CDC) started")
        self.send_response("OK", "READY")
        
        # 待機中はLEDを点灯
        self.led.value = True
        
        while True:
            try:
                # 待機中はLEDを点灯
                self.led.value = True
                
                # シリアルからの入力を読み込む（ノンブロッキング）
                line = self.read_line()
                if not line:
                    # データがない場合は少し待つ
                    time.sleep(0.01)
                    continue
                
                # コマンドを受信したらLEDを消灯（処理中）
                self.led.value = False
                
                if DEBUG:
                    print(f"[DEBUG] Received: {line}")
                
                # コマンドを解析
                result = self.parse_command(line)
                
                if 'error' in result:
                    self.send_response("ERR", result['error'])
                    continue
                
                cmd = result['cmd']
                
                # コマンドごとの処理
                if cmd == 'P':
                    self.send_response("OK", "READY")
                
                elif cmd == 'T':
                    # タイミング設定
                    self.we_pulse_ms = result['pulse_ms']
                    if DEBUG:
                        print(f"[DEBUG] Timing set: pulse={self.we_pulse_ms}ms")
                    self.send_response("OK", f"TIMING:{self.we_pulse_ms}")
                
                elif cmd == 'W':
                    self.handle_write_command(
                        result['start_address'],
                        result['length'],
                        result['data']
                    )
                
                elif cmd == 'E':
                    self.send_response("OK", "END")
                    # 必要に応じてGPIOをリセット
                    for pin in self.addr_pins + self.data_pins:
                        pin.value = False
                    self.we_pin.value = True
                
            except Exception as e:
                if DEBUG:
                    print(f"[DEBUG] Error: {e}")
                self.send_response("ERR", "FORMAT")


# メイン実行
if __name__ == "__main__":
    try:
        loader = PicoHexLoader()
        loader.run()
    except Exception as e:
        # 初期化エラーの場合、LEDで通知（CDCが使えない場合に備えて）
        print(f"Error: {e}")
        # 高速点滅でエラーを示す
        error_led_blink(LED_PIN, count=20, interval=0.3)
