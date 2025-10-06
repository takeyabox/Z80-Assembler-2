#!/usr/bin/env python3
"""
Intel Hex Loader
Intel Hexフォーマットのファイルを読み込み、解析、変換するためのライブラリ
"""

import os
import re
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass
from enum import IntEnum


class RecordType(IntEnum):
    """Intel Hexレコードタイプ"""
    DATA = 0x00                    # データレコード
    END_OF_FILE = 0x01            # ファイル終了レコード
    EXT_SEGMENT_ADDR = 0x02       # 拡張セグメントアドレスレコード
    START_SEGMENT_ADDR = 0x03     # スタートセグメントアドレスレコード
    EXT_LINEAR_ADDR = 0x04        # 拡張リニアアドレスレコード
    START_LINEAR_ADDR = 0x05      # スタートリニアアドレスレコード


@dataclass
class HexRecord:
    """Intel Hexレコードを表すデータクラス"""
    length: int
    address: int
    record_type: RecordType
    data: bytes
    checksum: int
    line_number: int


class IntelHexLoader:
    """Intel Hexファイルのローダークラス"""
    
    def __init__(self):
        self.records: List[HexRecord] = []
        self.memory: Dict[int, int] = {}
        self.start_address: Optional[int] = None
        self.extended_linear_address: int = 0
        self.extended_segment_address: int = 0
        
    def load_file(self, filepath: str) -> None:
        """
        Intel Hexファイルを読み込む
        
        Args:
            filepath: 読み込むファイルのパス
            
        Raises:
            FileNotFoundError: ファイルが存在しない場合
            ValueError: ファイルフォーマットが不正な場合
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"ファイルが見つかりません: {filepath}")
            
        with open(filepath, 'r') as f:
            self._parse_file(f)
            
    def load_string(self, hex_string: str) -> None:
        """
        Intel Hex形式の文字列を読み込む
        
        Args:
            hex_string: Intel Hex形式の文字列
        """
        lines = hex_string.strip().split('\n')
        self._parse_lines(lines)
        
    def _parse_file(self, file) -> None:
        """ファイルオブジェクトから読み込み"""
        lines = [line.strip() for line in file if line.strip()]
        self._parse_lines(lines)
        
    def _parse_lines(self, lines: List[str]) -> None:
        """行のリストを解析"""
        self.records.clear()
        self.memory.clear()
        self.extended_linear_address = 0
        self.extended_segment_address = 0
        
        for line_num, line in enumerate(lines, 1):
            record = self._parse_line(line, line_num)
            self.records.append(record)
            self._process_record(record)
            
    def _parse_line(self, line: str, line_number: int) -> HexRecord:
        """
        Intel Hex形式の1行を解析
        
        Args:
            line: 解析する行
            line_number: 行番号（エラー報告用）
            
        Returns:
            HexRecord: 解析されたレコード
            
        Raises:
            ValueError: フォーマットが不正な場合
        """
        # 基本的なフォーマットチェック
        if not line.startswith(':'):
            raise ValueError(f"行 {line_number}: 開始文字 ':' がありません")
            
        # 最小長チェック（:LLAAAATTCC = 11文字）
        if len(line) < 11:
            raise ValueError(f"行 {line_number}: 行が短すぎます")
            
        # 16進数文字のみかチェック
        hex_pattern = re.compile(r'^:[0-9A-Fa-f]+$')
        if not hex_pattern.match(line):
            raise ValueError(f"行 {line_number}: 無効な文字が含まれています")
            
        # フィールドの抽出
        try:
            length = int(line[1:3], 16)
            address = int(line[3:7], 16)
            record_type = RecordType(int(line[7:9], 16))
            
            # データ部分の抽出
            data_end = 9 + (length * 2)
            if len(line) < data_end + 2:
                raise ValueError(f"行 {line_number}: データ長が不正です")
                
            data_hex = line[9:data_end]
            data = bytes.fromhex(data_hex)
            
            checksum = int(line[data_end:data_end + 2], 16)
            
        except ValueError as e:
            raise ValueError(f"行 {line_number}: 解析エラー - {str(e)}")
            
        # チェックサムの検証
        calculated_checksum = self._calculate_checksum(length, address, record_type, data)
        if calculated_checksum != checksum:
            raise ValueError(
                f"行 {line_number}: チェックサムエラー "
                f"(期待値: {calculated_checksum:02X}, 実際: {checksum:02X})"
            )
            
        return HexRecord(
            length=length,
            address=address,
            record_type=record_type,
            data=data,
            checksum=checksum,
            line_number=line_number
        )
        
    def _calculate_checksum(self, length: int, address: int, record_type: RecordType, data: bytes) -> int:
        """チェックサムを計算"""
        sum_value = length
        sum_value += (address >> 8) & 0xFF
        sum_value += address & 0xFF
        sum_value += record_type
        sum_value += sum(data)
        
        # 2の補数を取る
        checksum = (-sum_value) & 0xFF
        return checksum
        
    def _process_record(self, record: HexRecord) -> None:
        """レコードを処理してメモリに格納"""
        if record.record_type == RecordType.DATA:
            # データレコード
            base_address = (self.extended_linear_address << 16) + self.extended_segment_address + record.address
            for i, byte in enumerate(record.data):
                self.memory[base_address + i] = byte
                
        elif record.record_type == RecordType.EXT_LINEAR_ADDR:
            # 拡張リニアアドレス
            if len(record.data) != 2:
                raise ValueError(f"行 {record.line_number}: 拡張リニアアドレスレコードのデータ長が不正です")
            self.extended_linear_address = (record.data[0] << 8) | record.data[1]
            
        elif record.record_type == RecordType.EXT_SEGMENT_ADDR:
            # 拡張セグメントアドレス
            if len(record.data) != 2:
                raise ValueError(f"行 {record.line_number}: 拡張セグメントアドレスレコードのデータ長が不正です")
            self.extended_segment_address = ((record.data[0] << 8) | record.data[1]) << 4
            
        elif record.record_type == RecordType.START_LINEAR_ADDR:
            # スタートリニアアドレス
            if len(record.data) != 4:
                raise ValueError(f"行 {record.line_number}: スタートリニアアドレスレコードのデータ長が不正です")
            self.start_address = (record.data[0] << 24) | (record.data[1] << 16) | (record.data[2] << 8) | record.data[3]
            
    def to_binary(self, fill_byte: int = 0xFF, start_address: Optional[int] = None, 
                  end_address: Optional[int] = None) -> bytes:
        """
        メモリデータをバイナリ形式に変換
        
        Args:
            fill_byte: 空き領域を埋めるバイト値（デフォルト: 0xFF）
            start_address: 開始アドレス（省略時は最小アドレス）
            end_address: 終了アドレス（省略時は最大アドレス）
            
        Returns:
            bytes: バイナリデータ
        """
        if not self.memory:
            return b''
            
        # アドレス範囲の決定
        min_addr = min(self.memory.keys()) if start_address is None else start_address
        max_addr = max(self.memory.keys()) if end_address is None else end_address
        
        # バイナリデータの生成
        binary_data = bytearray()
        for addr in range(min_addr, max_addr + 1):
            binary_data.append(self.memory.get(addr, fill_byte))
            
        return bytes(binary_data)
        
    def get_memory_map(self) -> List[Tuple[int, int]]:
        """
        メモリマップを取得（連続したデータ領域のリスト）
        
        Returns:
            List[Tuple[int, int]]: (開始アドレス, 終了アドレス)のリスト
        """
        if not self.memory:
            return []
            
        sorted_addresses = sorted(self.memory.keys())
        regions = []
        region_start = sorted_addresses[0]
        prev_addr = sorted_addresses[0]
        
        for addr in sorted_addresses[1:]:
            if addr != prev_addr + 1:
                # 不連続な領域
                regions.append((region_start, prev_addr))
                region_start = addr
            prev_addr = addr
            
        # 最後の領域を追加
        regions.append((region_start, prev_addr))
        
        return regions
        
    def print_memory_map(self) -> None:
        """メモリマップを表示"""
        regions = self.get_memory_map()
        if not regions:
            print("メモリデータがありません")
            return
            
        print("メモリマップ:")
        print("-" * 50)
        print(f"{'開始アドレス':>12} | {'終了アドレス':>12} | {'サイズ':>10}")
        print("-" * 50)
        
        total_size = 0
        for start, end in regions:
            size = end - start + 1
            total_size += size
            print(f"{start:>12X} | {end:>12X} | {size:>10} bytes")
            
        print("-" * 50)
        print(f"{'合計':>27} | {total_size:>10} bytes")
        
        if self.start_address is not None:
            print(f"\nエントリポイント: 0x{self.start_address:08X}")
            
    def get_statistics(self) -> Dict[str, Union[int, List[int]]]:
        """
        統計情報を取得
        
        Returns:
            Dict: 統計情報を含む辞書
        """
        stats = {
            'total_records': len(self.records),
            'data_records': sum(1 for r in self.records if r.record_type == RecordType.DATA),
            'total_bytes': len(self.memory),
            'memory_regions': len(self.get_memory_map()),
            'record_types': {}
        }
        
        # レコードタイプ別の集計
        for record in self.records:
            type_name = record.record_type.name
            stats['record_types'][type_name] = stats['record_types'].get(type_name, 0) + 1
            
        return stats


# 使用例とテスト用のコード
if __name__ == "__main__":
    # サンプルのIntel Hexデータ
    sample_hex = """
:020000040000FA
:10000000214601360121470136007EFE09D2194002
:100010002146017E17C20001FF5F16002148011929
:10002000194E79234623965778239EDA3F01B2CAA8
:100030003F0156702B5E712B722B732146013421C8
:00000001FF
"""
    
    # ローダーのインスタンスを作成
    loader = IntelHexLoader()
    
    try:
        # 文字列から読み込み
        loader.load_string(sample_hex)
        
        # メモリマップを表示
        loader.print_memory_map()
        
        # 統計情報を表示
        print("\n統計情報:")
        stats = loader.get_statistics()
        for key, value in stats.items():
            if key != 'record_types':
                print(f"  {key}: {value}")
        print("  レコードタイプ:")
        for record_type, count in stats['record_types'].items():
            print(f"    {record_type}: {count}")
            
        # バイナリデータに変換
        binary = loader.to_binary()
        print(f"\nバイナリデータサイズ: {len(binary)} bytes")
        
    except ValueError as e:
        print(f"エラー: {e}")
