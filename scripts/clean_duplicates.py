#!/usr/bin/env python3
"""清理重复的分析记录"""
import sqlite3
from pathlib import Path

def clean_duplicate_analyses():
    """清理重复的分析记录，只保留每个 match_id 的最新记录"""

    db_path = Path("data/users/default/history.sqlite3")

    if not db_path.exists():
        print("❌ 数据库文件不存在")
        return

    print("🔍 查找重复的分析记录...")

    conn = sqlite3.connect(str(db_path))

    # 统计重复记录
    cursor = conn.execute("""
        SELECT match_id, COUNT(*) as count
        FROM analyses
        GROUP BY match_id
        HAVING count > 1
    """)
    duplicates = cursor.fetchall()

    if not duplicates:
        print("✅ 没有发现重复记录")
        conn.close()
        return

    print(f"⚠️  发现 {len(duplicates)} 个比赛有重复分析记录:")
    total_to_delete = 0

    for match_id, count in duplicates:
        print(f"  - match_id={match_id}: {count} 条记录")
        total_to_delete += count - 1

    print(f"\n📊 需要删除 {total_to_delete} 条重复记录")

    confirm = input("确认清理？(y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消")
        conn.close()
        return

    # 删除重复记录，只保留每个 match_id 的最新记录（id 最大的）
    print("\n🧹 开始清理...")

    conn.execute("""
        DELETE FROM analyses
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM analyses
            GROUP BY match_id
        )
    """)
    conn.commit()

    # 验证结果
    cursor = conn.execute("SELECT COUNT(*) FROM analyses")
    remaining = cursor.fetchone()[0]

    print(f"✅ 清理完成！剩余 {remaining} 条分析记录")

    # 显示清理后的记录
    print("\n📋 当前分析记录:")
    cursor = conn.execute("""
        SELECT a.match_id, a.home_team, a.away_team, a.created_at
        FROM analyses a
        ORDER BY a.created_at DESC
    """)
    records = cursor.fetchall()

    for match_id, home, away, created_at in records:
        print(f"  • {home} vs {away} ({created_at[:10] if created_at else 'N/A'})")

    conn.close()


if __name__ == "__main__":
    clean_duplicate_analyses()
