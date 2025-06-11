#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LRA1 Tool (Python edition)
      _               _     _     _      _                        
 ____| |__  ____  ___| |__ |_|   | |____| |_      ___  ___  ____  
/ ___)  _ \(___ \/ __)  _ \ _  _ | |___ \ _ \    / __)/ _ \|    \ 
\___ \ | | | __ | (__| | | | ||_|| | __ |(_) | _| (__| (_) | | | |
(____/_| |_|____|\___)_| |_|_|   |_|____|____/|_|\___)\___/|_|_|_|
Copyright (c) 2025 shachi-lab.com
License: MIT License

author : ponta@shachi-lab.com

[Note]
This script requires:
    - pySerial (install via: pip install pyserial)
Standard libraries used:
    - argparse, os, sys, time, struct, binascii 
"""

import argparse
import os
import sys
import time
import serial    # Requires pySerial: pip install pyserial
import binascii

# 定数定義
VERSION         = "1.01"
INIT_TIMEOUT    = 0.05     # DFU初期化待ちタイムアウト (50 ms)
RESP_TIMEOUT    = 1.0      # レスポンス待ちタイムアウト (1000 ms)
FILE_MIN_SIZE   = 4096     # ファームウェアファイル最小サイズ (4kB)
FILE_MAX_SIZE   = 120000   # ファームウェアファイル最大サイズ (120kB)

UPDATE_ADRS = 0x002000     # アップデート用フラッシュアドレス
INIT_ADRS   = 0x01fe00     # 初期化用フラッシュアドレス
INIT_SIZE   = 256 + 256    # 初期化モードで書き込むサイズ

# ブートローダー用コマンド等の定数
BSL_HEADER                     = 0x80
BSL_CMD_RX_DATA_BLOCK          = 0x10
BSL_CMD_RX_DATA_BLOCK_VERIFY   = 0x12
BSL_CMD_LOAD_PC                = 0x17
BSL_CMD_RX_DATA_BLOCK_FAST     = 0x1b

# ファイル内に含まれるべきマジックバイト ("i2-ele ")
MAGIC_BYTES = bytes([0x69, 0x32, 0x2d, 0x65, 0x6c, 0x65, 0x20])

class LRA1Tool:
    def __init__(self, port: str, use_reset: bool, sw_reset: bool, mode: str, filename: str = None):
        """
        コンストラクタ
          port      : 使用するシリアルポート
          use_reset : DTRリセットを使用するかどうか
          mode      : 動作モード ('update', 'verify', 'init')
          filename  : ファームウェアファイル名（initモード以外で必須）
        """
        self.port = port
        self.use_reset = use_reset
        self.sw_reset = sw_reset
        self.mode = mode
        self.filename = filename
        # update または verify の場合はアップデート用アドレスを、initの場合は初期化用アドレスを設定
        self.flash_adrs = UPDATE_ADRS if mode in ('update', 'verify') else INIT_ADRS
        self.file_buff = None  # ファイル内容（bytearray）
        self.file_size = 0     # ファイルサイズ
        self.mode_flag = None  # ファームウェア転送モードを格納
        if mode == 'update':
            self.mode_flag = BSL_CMD_RX_DATA_BLOCK
        elif mode == 'verify':
            self.mode_flag = BSL_CMD_RX_DATA_BLOCK_VERIFY

    # --- シリアル通信・CRC計算・タイムアウト付き読み出し関連 ---
    @staticmethod
    def reset_dtr(ser: serial.Serial):
        """シリアルポートのDTR信号を用いたリセット処理"""
        ser.dtr = False
        time.sleep(0.10)  # 100ms 待機
        ser.dtr = True
        time.sleep(0.05)  # 50ms 待機

    @staticmethod
    def reset_cmd(ser: serial.Serial):
        """シリアルポートに"RESET"コマンドを送信する"""
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        ser.send_break(duration=0.001)  # 1ms ブレーク信号を送信
        ser.write(b"\x03RESET\r\n")
        time.sleep(0.10)  # 100ms 待機

    @staticmethod
    def calc_crc(data: bytes) -> int:
        """CRC-CCITT (0x1021) を初期値0xffffで計算"""
        return binascii.crc_hqx(data, 0xffff)

    @staticmethod
    def serial_getchar_to(ser: serial.Serial, timeout_sec: float) -> int:
        """指定したタイムアウト内でシリアルから1バイト読み出す"""
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if ser.in_waiting > 0:
                return ser.read(1)[0]
            time.sleep(0.001)
        return -1

    @staticmethod
    def recv_response(ser: serial.Serial, expected_len: int) -> int:
        """
        指定した長さのレスポンスを受信し、レスポンスコードを返す
          - エラーの場合は負の値を返す
        """
        buff = bytearray()
        for _ in range(expected_len):
            c = LRA1Tool.serial_getchar_to(ser, RESP_TIMEOUT)
            if c < 0:
                return -2
            buff.append(c)
        # ヘッダーチェック
        if expected_len >= 2 and buff[1] != BSL_HEADER:
            return -3
        res = (buff[0] << 8)
        if expected_len > 5:
            res |= buff[5]
        return res

    @staticmethod
    def send_command(ser: serial.Serial, cmd: bytes):
        """
        コマンド送信:
          - ヘッダ、長さ、コマンド本体、CRC を付加して送信
        """
        ser.reset_input_buffer()
        length = len(cmd)
        data = bytearray([BSL_HEADER, length & 0xFF, (length >> 8) & 0xFF]) + cmd
        crc = LRA1Tool.calc_crc(cmd)
        data += bytearray([crc & 0xFF, (crc >> 8) & 0xFF])
        ser.write(data)

    # --- ファームウェア転送関連 ---
    def send_rx_data_block(self, ser: serial.Serial, cmd: bytearray, adrs: int, num: int) -> int:
        """
        データブロック送信:
          - 転送モードに応じたコマンドをセットし、ブロック送信後にレスポンスを取得する
        """
        if self.mode_flag in (BSL_CMD_RX_DATA_BLOCK_VERIFY, BSL_CMD_RX_DATA_BLOCK_FAST):
            cmd[0] = self.mode_flag
        else:
            cmd[0] = BSL_CMD_RX_DATA_BLOCK
        # アドレス設定
        cmd[1] = adrs & 0xFF
        cmd[2] = (adrs >> 8) & 0xFF
        cmd[3] = (adrs >> 16) & 0xFF
        length = num + 4
        self.send_command(ser, cmd[:length])
        if self.mode_flag == BSL_CMD_RX_DATA_BLOCK_FAST:
            return self.serial_getchar_to(ser, RESP_TIMEOUT)
        return self.recv_response(ser, 8)

    @staticmethod
    def update_progress(total: int, remain: int):
        """
        プログレスバーの表示更新:
          - 転送進捗を50文字幅のバーで表示
        """
        percent = int(((total - remain) * 50) / total)
        bar = '[' + '#' * percent + '-' * (50 - percent) + ']'
        sys.stdout.write('\r' + bar)
        sys.stdout.flush()

    def load_firmware(self):
        """
        ファームウェアファイルの読み込み:
          - ファイルサイズチェック、読み込み、マジックバイトチェックを実施
          - 成功時は (buffer, size) を返す
          - 失敗時は (None, エラーコード) を返す
        """
        try:
            st = os.stat(self.filename)
        except Exception:
            return None, -1

        if st.st_size < FILE_MIN_SIZE or st.st_size > FILE_MAX_SIZE:
            return None, -2

        with open(self.filename, "rb") as fp:
            buff = bytearray(fp.read())
        # マジックバイトチェック（ファイルの特定オフセットから）
        offset = 0xb8
        if buff[offset:offset+len(MAGIC_BYTES)] != MAGIC_BYTES:
            return None, -2
        return buff, len(buff)

    def loRa_update(self, ser: serial.Serial) -> int:
        """
        ファームウェア転送処理:
          - DFUモード待ち、プログレスバー表示、各ブロック送信、最終コマンド送信を実施
          - エラーが発生した場合はそのエラーコードを返す
        """
        checksum = 0
        adrs = self.flash_adrs
        ser.reset_input_buffer()
        wait_flag = False
        # DFUモード待ちループ
        while True:
            ser.write(bytes([0xaa]))
            if self.serial_getchar_to(ser, INIT_TIMEOUT) == 0x55:
                ser.write(b"i2LoRa")
                if self.serial_getchar_to(ser, INIT_TIMEOUT) == 0xaa:
                    break
            if not wait_flag:
                print("Wait for DFU mode. Please reset LRA1.", end='', flush=True)
                wait_flag = True

        total_size = self.file_size
        index = 0
        # 256バイト単位で送信
        while self.file_size > 0:
            self.update_progress(total_size, self.file_size)
            num = 256 if self.file_size >= 256 else self.file_size
            cmd_block = bytearray(256 + 16)
            # 転送ブロック作成とチェックサム更新
            for i in range(num):
                cmd_block[i+4] = self.file_buff[index + i]
                checksum = (checksum + self.file_buff[index + i]) & 0xFFFF
            ret = self.send_rx_data_block(ser, cmd_block, adrs, num)
            if ret != 0:
                return ret
            adrs += num
            index += num
            self.file_size -= num

        self.update_progress(1, 0)
        # 最終コマンド: PCロード
        final_cmd = bytearray(4)
        final_cmd[0] = BSL_CMD_LOAD_PC
        final_cmd[1] = 0x00
        final_cmd[2] = checksum & 0xFF
        final_cmd[3] = (checksum >> 8) & 0xFF
        self.send_command(ser, final_cmd)
        return self.recv_response(ser, 8)

    def run(self):
        """
        ツールのメイン処理:
          - モードに応じたファイル読み込みまたは初期化データの生成
          - シリアルポートのオープンと必要なリセット
          - ファームウェア転送の実行と結果表示
        """
        if self.mode == "init":
            # 初期化モード: 固定サイズのゼロバイト配列を使用
            self.file_size = INIT_SIZE
            self.file_buff = bytearray([0] * self.file_size)
            print("Initializing")
        else:
            # update/verify モード: ファームウェアファイルの読み込み
            self.file_buff, self.file_size = self.load_firmware()
            if self.file_buff is None:
                if self.file_size == -1:
                    print(f"Could not open file {self.filename}!")
                else:
                    print("The file is not an update file for LRA1.")
                sys.exit(self.file_size)
            msg = "Verifying" if self.mode_flag == BSL_CMD_RX_DATA_BLOCK_VERIFY else "Updating"
            print(msg)
        try:
            # シリアルポートのオープン（baud は指定があっても115200固定）
            ser = serial.Serial(self.port, 115200, timeout=0)
        except Exception:
            print(f"{self.port} device not open.")
            sys.exit(-1)
        ser.dtr = True  # 初期状態に設定
        if self.sw_reset:
            self.reset_cmd(ser)
        if self.use_reset:
            self.reset_dtr(ser)
        # 転送処理を実施
        ret = self.loRa_update(ser)
        ser.close()
        if ret:
            print(f"\nError occurred. ({ret})")
            sys.exit(ret)
        print("\nSuccessful.")

# --- コマンドライン引数解析 ---
def parse_arguments():
    parser = argparse.ArgumentParser(
        usage="%(prog)s [options]",
        description=f"LRA1 Tool\nVersion: {VERSION}"
    )
    parser.add_argument('-p', '--port', type=str, required=True, help='Specify the serial port (e.g. com0, /dev/ttyS0)')
    parser.add_argument('-r', '--reset', action='store_true', help='Use DTR to reset before transfer')
    parser.add_argument('-s', '--swreset', action='store_true', help='Softwere reset before transfer')
    parser.add_argument('-b', '--baud', type=int, default=115200, help='Specify baud rate (default 115200; value is ignored)')
    # モードオプション（必須ではなく、指定がなければデフォルトで update とする）
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-u', '--update', action='store_true', help='Update LRA1 firmware (default mode)')
    group.add_argument('-v', '--verify', action='store_true', help='Verify LRA1 firmware')
    group.add_argument('-i', '--init', action='store_true', help='Initialize the settings (No file needed)')
    parser.add_argument('-f', '--file', type=str, help='Firmware file name (required for update/verify modes)')
    
    if len(sys.argv) == 1:
        parser.error("Use --help option to see usage")
    args = parser.parse_args()

    # デフォルトモードは update（-u）とする
    if not (args.update or args.verify or args.init):
        args.update = True

    # update/verify モードの場合、-f が必要
    if not args.init and not args.file:
        parser.error("No update file specified. Use -f or --file to specify the firmware file.")
    return args

def main():
    args = parse_arguments()
    # モード判定
    if args.update:
        mode = "update"
    elif args.verify:
        mode = "verify"
    else:
        mode = "init"
    # LRA1Toolオブジェクト生成して実行
    tool = LRA1Tool(port=args.port, use_reset=args.reset, sw_reset=args.swreset, mode=mode, filename=args.file)
    tool.run()

if __name__ == '__main__':
    main()
