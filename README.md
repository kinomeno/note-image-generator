# ととのえ — note画像ととのえツール（v0.10）

画像を**1920×1006px**（note推奨サイズ）へ、モチーフを中央に整えて変換するツール。
シンプルな **Web版「ととのえ」** と、フォルダ一括・高機能な **デスクトップ版** の2系統があります。

## 🚀 ウェブ版（すぐに使える）

ブラウザだけで利用可能 → **[ウェブ版を開く](https://kinomeno.github.io/note-image-generator/)**

- インストール不要
- ドラッグ&ドロップ対応
- JPG/PNG/WebP出力
- 個別またはZIP一括ダウンロード

## 💻 デスクトップ版（高機能）

Windows用デスクトップアプリ。ウェブ版以上の機能を搭載。

### 📦 インストール

1. **EXEファイルをダウンロード**
   - [最新版をダウンロード](https://github.com/kinomeno/note-image-generator/releases)
   - ファイルを解凍して起動するだけ（インストール不要）

### ⚡ 主な機能

✅ **複数サイズ対応**
  - note標準（1920×1006）
  - X/Twitter（1024×512）
  - Instagram（1080×1080）
  - YouTube（1280×720）
  - カスタムサイズ

✅ **高度な処理**
  - ドラッグ&ドロップ
  - リアルタイムプレビュー
  - テキスト追加（タイトル・キャプション）
  - 背景色カスタマイズ
  - 出力形式選択（PNG/JPG/WebP）

✅ **バッチ処理**
  - サブフォルダ対応
  - フォルダ構造維持
  - 複数ファイル同時処理

## 📖 使い方

### ウェブ版
1. ウェブ版を開く
2. 画像をドラッグ&ドロップ（または「クリックして選択」）
3. 必要に応じてサイズ・色・テキストを設定
4. 「▶ 変換開始」をクリック
5. 完了後、ダウンロード

### デスクトップ版
1. **note画像生成アプリ.exe** をダブルクリック
2. 「ソースフォルダ」を選択（変換元の画像フォルダ）
3. 「出力フォルダ」を選択（保存先）
4. サイズ・形式・背景色などを設定
5. 「▶ 変換開始」をクリック
6. 完了！

## 🔧 開発者向け

### ローカルで開発・ビルド

```bash
# リポジトリをクローン
git clone https://github.com/kinomeno/note-image-generator.git
cd note-image-generator

# EXEをビルド（Pythonが必要）
cd desktop
python build_exe.py

# 出力ファイル: desktop/dist/note画像生成アプリ.exe
```

Web版は `docs/index.html` 単一ファイル。ローカルで開くか、GitHub Pages で公開できます。

### 必要な環境
- Python 3.10+
- Pillow 10.0+
- numpy 1.24+
- tkinterdnd2 0.3.0+

## 📂 プロジェクト構成

```
note画像生成/
├─ docs/         Web版「ととのえ」開発正本（index.html / OGP / favicon）
├─ 公開版/        テスト要素を除いたクリーン公開版スナップショット
├─ desktop/      デスクトップ版（Python / build_exe.py / dist）
├─ design/       デザインモックアップ
├─ ドキュメント/  各種ドキュメント（下記）
└─ README.md
```
※ `docs/` が開発の正本。公開時は `TEST_MODE=false`（または `公開版/`）を配信。

## 📚 ドキュメント

- [更新情報（CHANGELOG）](ドキュメント/更新情報.md)
- [詳細説明書（ヘビーユーザー向け）](ドキュメント/詳細説明書.md)
- [アプリ仕様書](ドキュメント/アプリ仕様書.md)
- [開発経緯](ドキュメント/開発経緯.md)

## 📝 ライセンス

MIT License

## 💬 サポート

バグ報告・機能リクエスト → [Issues](https://github.com/kinomeno/note-image-generator/issues)

---

**note での公開記事**: https://note.com/(公開後にリンク更新)
