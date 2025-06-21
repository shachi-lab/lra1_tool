# LRA1 Tool (Python版)

**LRA1 Tool** は、**LRA1** モジュールデバイスのファームウェア更新、検証、初期化を実行するためのコマンドラインツールです。  
シリアル通信を利用して、ファームウェアファイル（または初期化データ）をデバイスに転送します。  
※**LRA1**は [i2-electronics,Inc.](https://www.i2-ele.co.jp/)のLoRa通信モジュールです。

## 特徴

- **アップデートモード (-u, --update):**  
  指定したファームウェアファイルを用いて、デバイスのファームウェアを更新します。（デフォルトモード）

- **検証モード (-v, --verify):**  
  指定したファームウェアファイルとデバイス内のファームウェアを比較します。

- **初期化モード (-i, --init):**  
  各種設定値を出荷時の設定に戻します。（ファームウェアファイル不要）

## システム要件

- **Python:**  
  Python 3.x が必要です。  
- **OS:**  
  Windows / macOS / Linux
- **必要パッケージ:**  
  [pySerial](https://pyserial.readthedocs.io/)  

## インストール

1. このリポジトリをクローンまたはダウンロードしてください。  
**lra1_tool.py** のみでも構いません。
2. [pySerial](https://pyserial.readthedocs.io/) をインストールします:
    ```bash
    pip install pyserial
    ```

## 使い方

基本の実行形式は以下の通りです：

```bash
python lra1_tool.py -p <シリアルポート> [オプション]
```

### 主要オプション

- **`-p, --port`**  
  使用するシリアルポートを指定します。  
  例: `/dev/ttyS0`、`COM3`

- **`-r, --reset`**  
  転送前に DTR リセットを実行します。

- **`-s, --swreset`**  
  転送前に ソフトウェアリセットを実行します。

- **`-b, --baud`**  
  ボーレートを指定可能ですが、実際は常に 115200 が使用されます。

- **モード選択**  
  - `-u, --update` (ファームウェアファイル必須)  
  - `-v, --verify` (ファームウェアファイル必須)  
  - `-i, --init` (ファームウェアファイル不要)  
  ※モードが指定されない場合、デフォルトでアップデートモードとなります。

- **`-f, --file`**  
  アップデートまたは検証モードの場合、使用するファームウェアファイルのパスを指定します。

### 使用例

- アップデートモード:
  ```bash
  python lra1_tool.py -p /dev/ttyS0 -u -f firmware.bin
  ```

- 検証モード:
  ```bash
  python lra1_tool.py -p COM3 -v -f firmware.bin
  ```

- 初期化モード:
  ```bash
  python lra1_tool.py -p /dev/ttyS0 -i
  ```

## ヘルプ

使い方がわからない場合は、以下のコマンドでヘルプ情報が表示されます：

```bash
python lra1_tool.py --help
```

## ライセンス

本ソフトウェアは **MITライセンス** の下で提供されています。  
***© 2025 shachi-lab.com***

## 詳細情報

詳しい操作方法やトラブルシューティングについては、[USER_MANUAL.md](USER_MANUAL.md) をご参照ください。

---

## 📡 このプロジェクトについて

このリポジトリは、個人プロジェクト「[しゃちらぼ｜Shachi-lab](https://shachi-lab.com)」で進めている  
LoRaモジュール「LRA1」に関する開発・実験の一部です。

ブログでは、LRA1の使い方やTipsに加えて、  
AIアシスタント「ろらたん」が技術と遊び心を交えながら解説してくれます。

🎀「正式には“しゃちらぼ”だけど、“シャチラボ”でもいいよ〜♪」

## 📡 About this project (English)

This repository is part of a personal project from [Shachi-lab](https://shachi-lab.com),  
which focuses on the development and experimentation of the Japanese LoRa module “LRA1”.

The blog introduces how to use LRA1, practical tips, and fun insights —  
with the help of an AI assistant named *Roratan* who adds a friendly and playful touch.

🎀 “It's officially called ‘Shachi-lab’, but feel free to call it ‘Shachilab’ too!”

## 🔗 関連リンク

- 📘 [しゃちらぼ｜Shachi-lab 技術ブログ](https://blog.shachi-lab.com)
- 🛠 LRA1関連の記事一覧：https://blog.shachi-lab.com/tag/lra1
- 🐦 X（旧Twitter）： [@shachi_lab](https://x.com/shachi_lab)
- 🐙 GitHub：[@shachi-lab](https://github.com/shachi-lab)
- 📗 Qiita： [@shachi-lab](https://qiita.com/shachi-lab)

