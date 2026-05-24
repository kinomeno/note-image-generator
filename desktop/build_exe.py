"""
note画像生成アプリをEXE化するスクリプト

【実行方法】
  python build_exe.py

【生成されるファイル】
  - dist/note画像生成アプリ.exe
"""

import subprocess
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def install_dependencies():
    """必要なパッケージをインストール"""
    packages = [
        "PyInstaller>=6.0",
        "Pillow>=10.0",
        "numpy>=1.24",
        "tkinterdnd2>=0.3.0"
    ]

    print("📦 依存パッケージをインストール中...\n")
    for pkg in packages:
        print(f"  → {pkg}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])
    print("\n✓ インストール完了\n")

def build_exe():
    """PyInstallerでEXEを生成"""
    print("EXEファイルを生成中...\n")

    subprocess.check_call([
        sys.executable, "-m", "PyInstaller",
        "note画像生成アプリ.py",
        "--onefile",
        "-w",
        "--hidden-import=tkinterdnd2"
    ])

    exe_path = "dist/note画像生成アプリ.exe"
    if os.path.exists(exe_path):
        print(f"\n✓ EXE生成完了！")
        print(f"  保存先: {os.path.abspath(exe_path)}")
        return True
    else:
        print("\n✗ EXE生成に失敗しました")
        return False

if __name__ == "__main__":
    try:
        install_dependencies()
        if build_exe():
            print("\n🎉 全て完了！")
        else:
            print("\n⚠ エラーが発生しました")
            sys.exit(1)
    except Exception as e:
        print(f"\n✗ エラー: {e}")
        sys.exit(1)
