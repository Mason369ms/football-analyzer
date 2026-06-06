#!/usr/bin/env python3
"""一键启动仪表盘并验证改进效果"""
import os
import sys
import subprocess
import time
import webbrowser
from pathlib import Path

def main():
    """主函数"""

    print("=" * 70)
    print("🚀 仪表盘改进 - 一键启动和验证")
    print("=" * 70)

    # 检查 Python 环境
    print("\n🔍 检查环境...")

    # 设置 PYTHONPATH
    src_path = Path(__file__).parent.parent / "src"
    os.environ["PYTHONPATH"] = str(src_path)
    print(f"  ✅ PYTHONPATH: {src_path}")

    # 检查虚拟环境
    venv_python = Path(__file__).parent.parent / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        print(f"  ❌ 虚拟环境不存在: {venv_python}")
        return
    print(f"  ✅ Python: {venv_python}")

    # 运行测试
    print("\n🧪 运行测试验证...")
    test_script = Path(__file__).parent / "test_dashboard.py"

    try:
        result = subprocess.run(
            [str(venv_python), str(test_script)],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
            timeout=30,
        )

        if result.returncode == 0:
            print(result.stdout)
            print("✅ 测试通过！")
        else:
            print(f"❌ 测试失败:\n{result.stderr}")
            return

    except subprocess.TimeoutExpired:
        print("⚠️  测试超时，继续启动仪表盘...")
    except Exception as e:
        print(f"⚠️  测试异常: {e}")

    # 启动仪表盘
    print("\n🚀 启动仪表盘...")
    dashboard_script = Path(__file__).parent.parent / "src" / "football_sim" / "cli.py"

    try:
        # 启动仪表盘进程
        process = subprocess.Popen(
            [str(venv_python), "-m", "football_sim.cli", "dashboard", "--server", "fastapi", "--port", "8766"],
            cwd=str(Path(__file__).parent.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # 等待启动
        print("  等待仪表盘启动...")
        time.sleep(3)

        # 检查是否启动成功
        if process.poll() is None:
            print("  ✅ 仪表盘启动成功！")
            print("\n" + "=" * 70)
            print("🌐 访问地址: http://127.0.0.1:8766")
            print("=" * 70)
            print("\n📋 改进效果:")
            print("  1. 赛事列表 - 新增"序号"列（201, 202, 203 等）")
            print("  2. 近期分析 - 新增"序号"列，无重复记录")
            print("  3. 重新分析 - 更新记录而非新增")
            print("\n💡 提示:")
            print("  - 按 Ctrl+C 停止仪表盘")
            print("  - 如果看不到序号列，请清除浏览器缓存")
            print("  - 预览页面: http://127.0.0.1:8888/preview_improvements.html")
            print("\n📄 文档:")
            print("  - 快速开始: QUICK_START_IMPROVEMENTS.md")
            print("  - 技术详情: docs/DASHBOARD_IMPROVEMENTS.md")

            # 自动打开浏览器
            try:
                webbrowser.open("http://127.0.0.1:8766")
                print("\n🌐 已自动打开浏览器")
            except:
                pass

            # 等待用户中断
            try:
                process.wait()
            except KeyboardInterrupt:
                print("\n\n⏹️  正在停止仪表盘...")
                process.terminate()
                process.wait()
                print("✅ 仪表盘已停止")
        else:
            stdout, stderr = process.communicate()
            print(f"❌ 仪表盘启动失败:")
            if stdout:
                print(f"stdout: {stdout.decode()}")
            if stderr:
                print(f"stderr: {stderr.decode()}")

    except KeyboardInterrupt:
        print("\n\n⏹️  正在停止仪表盘...")
        if 'process' in locals():
            process.terminate()
            process.wait()
        print("✅ 仪表盘已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")


if __name__ == "__main__":
    main()
