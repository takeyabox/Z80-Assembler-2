"""
Raspberry Pi PICO boot.py
CircuitPython環境用の起動設定
USB CDCを有効化してデータ通信用のシリアルポートを作成
"""

import usb_cdc
import storage

# USB CDCを有効化
# console: REPL用（デバッグ出力）
# data: データ通信用（プロトコル通信）
usb_cdc.enable(console=True, data=True)

# ストレージを読み取り専用にする場合はコメントを外す
# storage.remount("/", readonly=False)

print("PICO Boot: CircuitPython Ready")
