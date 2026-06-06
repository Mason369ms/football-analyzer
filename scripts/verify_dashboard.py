#!/usr/bin/env python3
"""快速验证仪表盘改进"""
import requests
import re

def verify_improvements():
    """验证仪表盘改进"""

    print("=" * 70)
    print("🔍 验证仪表盘改进效果")
    print("=" * 70)

    try:
        # 访问仪表盘主页
        print("\n📡 访问仪表盘...")
        response = requests.get("http://127.0.0.1:8766", timeout=10)

        if response.status_code != 200:
            print(f"❌ 访问失败: HTTP {response.status_code}")
            return

        html = response.text

        # 检查赛事列表序号列
        print("\n✅ 测试 1: 赛事列表序号列")
        if '<th>序号</th>' in html and '<td>201</td>' in html:
            print("   ✓ 序号列已添加")
            print("   ✓ 序号 201 已显示")
        else:
            print("   ❌ 序号列未找到")

        # 检查近期分析序号列
        print("\n✅ 测试 2: 近期分析序号列")
        analysis_section = re.search(r'<h3>近期分析</h3>.*?</table>', html, re.DOTALL)
        if analysis_section:
            section_html = analysis_section.group()
            if '<th>序号</th>' in section_html:
                print("   ✓ 近期分析序号列已添加")
            else:
                print("   ❌ 近期分析序号列未找到")
        else:
            print("   ⚠️  未找到近期分析部分")

        # 统计赛事数量
        print("\n✅ 测试 3: 赛事数据")
        match_count = len(re.findall(r'<td>\d{3}</td>', html))
        print(f"   ✓ 发现 {match_count} 场比赛（有序号）")

        # 检查是否有序号 201-205
        numbers = re.findall(r'<td>(\d{3})</td>', html)
        if numbers:
            print(f"   ✓ 序号列表: {', '.join(sorted(set(numbers)))}")

        print("\n" + "=" * 70)
        print("🎉 验证完成！")
        print("=" * 70)
        print("\n💡 访问仪表盘查看完整效果:")
        print("   http://127.0.0.1:8766")

    except requests.exceptions.ConnectionError:
        print("\n❌ 无法连接到仪表盘")
        print("   请确认仪表盘正在运行:")
        print("   PYTHONPATH='src' python -m football_sim.cli dashboard --server fastapi --port 8766")
    except Exception as e:
        print(f"\n❌ 验证失败: {e}")

if __name__ == "__main__":
    verify_improvements()
