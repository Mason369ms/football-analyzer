"""数据备份模块 - 提供数据库和数据文件的备份与恢复功能"""

import gzip
import json
import shutil
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from football_sim.logger import get_logger

logger = get_logger(__name__)


class BackupManager:
    """备份管理器"""

    def __init__(self, data_dir: Path, backup_dir: Optional[Path] = None):
        """
        初始化备份管理器

        Args:
            data_dir: 数据目录
            backup_dir: 备份目录，默认为 data_dir/backups
        """
        self.data_dir = Path(data_dir)
        self.backup_dir = backup_dir or (self.data_dir / "backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # 备份配置
        self.max_backups = 30  # 保留最近 30 天的备份
        self.compress = True  # 启用压缩

    def create_backup(
        self,
        name: Optional[str] = None,
        include_databases: bool = True,
        include_json: bool = True,
        include_reports: bool = False
    ) -> Dict[str, Any]:
        """
        创建备份

        Args:
            name: 备份名称，默认使用时间戳
            include_databases: 是否包含数据库
            include_json: 是否包含 JSON 数据文件
            include_reports: 是否包含报告文件

        Returns:
            备份信息字典
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = name or f"backup_{timestamp}"
        backup_path = self.backup_dir / backup_name
        backup_path.mkdir(parents=True, exist_ok=True)

        backup_info = {
            "name": backup_name,
            "timestamp": datetime.now().isoformat(),
            "files": [],
            "size_bytes": 0,
            "compressed": self.compress
        }

        try:
            # 备份数据库
            if include_databases:
                db_files = list(self.data_dir.glob("**/*.sqlite3"))
                for db_file in db_files:
                    self._backup_database(db_file, backup_path)
                    backup_info["files"].append(str(db_file.relative_to(self.data_dir)))

            # 备份 JSON 数据文件
            if include_json:
                json_files = list(self.data_dir.glob("**/*.json"))
                for json_file in json_files:
                    if "backups" not in str(json_file):  # 排除备份目录
                        self._backup_file(json_file, backup_path)
                        backup_info["files"].append(str(json_file.relative_to(self.data_dir)))

            # 备份报告
            if include_reports:
                reports_dir = self.data_dir.parent / "reports"
                if reports_dir.exists():
                    report_files = list(reports_dir.glob("**/*"))
                    for report_file in report_files:
                        if report_file.is_file():
                            self._backup_file(report_file, backup_path / "reports")
                            backup_info["files"].append(str(report_file))

            # 计算备份大小
            backup_info["size_bytes"] = self._get_directory_size(backup_path)
            backup_info["size_mb"] = round(backup_info["size_bytes"] / (1024 * 1024), 2)

            # 保存备份元数据
            metadata_path = backup_path / "backup_metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(backup_info, f, ensure_ascii=False, indent=2)

            logger.info(
                f"备份创建成功: {backup_name}, "
                f"文件数: {len(backup_info['files'])}, "
                f"大小: {backup_info['size_mb']}MB"
            )

            # 清理旧备份
            self._cleanup_old_backups()

            return backup_info

        except Exception as e:
            logger.error(f"备份创建失败: {e}")
            # 清理失败的备份
            if backup_path.exists():
                shutil.rmtree(backup_path)
            raise

    def _backup_database(self, db_path: Path, backup_path: Path):
        """备份 SQLite 数据库"""
        try:
            db_name = db_path.name
            backup_file = backup_path / db_name

            # 使用 SQLite 的备份 API
            source_conn = sqlite3.connect(str(db_path))
            dest_conn = sqlite3.connect(str(backup_file))

            source_conn.backup(dest_conn)

            source_conn.close()
            dest_conn.close()

            # 压缩
            if self.compress:
                compressed_file = backup_file.with_suffix('.sqlite3.gz')
                with open(backup_file, 'rb') as f_in:
                    with gzip.open(compressed_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                backup_file.unlink()  # 删除未压缩的文件

            logger.debug(f"数据库备份完成: {db_name}")

        except Exception as e:
            logger.error(f"数据库备份失败 {db_path}: {e}")
            raise

    def _backup_file(self, file_path: Path, backup_path: Path):
        """备份单个文件"""
        try:
            # 保持相对路径结构
            relative_path = file_path.relative_to(self.data_dir)
            dest_file = backup_path / relative_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            # 复制文件
            shutil.copy2(file_path, dest_file)

            # 压缩（可选）
            if self.compress and file_path.suffix in ['.json', '.txt', '.csv']:
                compressed_file = dest_file.with_suffix(dest_file.suffix + '.gz')
                with open(dest_file, 'rb') as f_in:
                    with gzip.open(compressed_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                dest_file.unlink()

            logger.debug(f"文件备份完成: {relative_path}")

        except Exception as e:
            logger.error(f"文件备份失败 {file_path}: {e}")
            raise

    def restore_backup(self, backup_name: str, overwrite: bool = False) -> bool:
        """
        恢复备份

        Args:
            backup_name: 备份名称
            overwrite: 是否覆盖现有数据

        Returns:
            是否恢复成功
        """
        backup_path = self.backup_dir / backup_name

        if not backup_path.exists():
            logger.error(f"备份不存在: {backup_name}")
            return False

        metadata_path = backup_path / "backup_metadata.json"
        if not metadata_path.exists():
            logger.error(f"备份元数据不存在: {backup_name}")
            return False

        try:
            # 读取备份元数据
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            # 恢复数据库
            for db_file in backup_path.glob("*.sqlite3*"):
                self._restore_database(db_file, overwrite)

            # 恢复 JSON 文件
            for json_file in backup_path.rglob("*.json*"):
                if json_file.name == "backup_metadata.json":
                    continue
                self._restore_file(json_file, overwrite)

            logger.info(f"备份恢复成功: {backup_name}")
            return True

        except Exception as e:
            logger.error(f"备份恢复失败: {e}")
            return False

    def _restore_database(self, backup_file: Path, overwrite: bool):
        """恢复数据库"""
        try:
            db_name = backup_file.name.replace('.gz', '')
            dest_path = self.data_dir / db_name

            if dest_path.exists() and not overwrite:
                logger.warning(f"数据库已存在，跳过: {db_name}")
                return

            # 解压缩
            if backup_file.suffix == '.gz':
                temp_file = backup_file.with_suffix('')
                with gzip.open(backup_file, 'rb') as f_in:
                    with open(temp_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                backup_file = temp_file

            # 恢复
            shutil.copy2(backup_file, dest_path)
            logger.debug(f"数据库恢复完成: {db_name}")

        except Exception as e:
            logger.error(f"数据库恢复失败: {e}")
            raise

    def _restore_file(self, backup_file: Path, overwrite: bool):
        """恢复单个文件"""
        try:
            # 计算目标路径
            relative_path = backup_file.relative_to(self.backup_dir)
            # 移除 .gz 后缀
            if relative_path.suffix == '.gz':
                relative_path = relative_path.with_suffix('')

            dest_path = self.data_dir / relative_path

            if dest_path.exists() and not overwrite:
                logger.warning(f"文件已存在，跳过: {relative_path}")
                return

            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # 解压缩
            if backup_file.suffix == '.gz':
                with gzip.open(backup_file, 'rb') as f_in:
                    with open(dest_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                shutil.copy2(backup_file, dest_path)

            logger.debug(f"文件恢复完成: {relative_path}")

        except Exception as e:
            logger.error(f"文件恢复失败: {e}")
            raise

    def list_backups(self) -> List[Dict[str, Any]]:
        """列出所有备份"""
        backups = []

        for backup_dir in sorted(self.backup_dir.iterdir(), reverse=True):
            if not backup_dir.is_dir():
                continue

            metadata_path = backup_dir / "backup_metadata.json"
            if metadata_path.exists():
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    backups.append(metadata)
                except Exception as e:
                    logger.warning(f"读取备份元数据失败 {backup_dir.name}: {e}")
            else:
                # 没有元数据的备份
                backups.append({
                    "name": backup_dir.name,
                    "timestamp": datetime.fromtimestamp(
                        backup_dir.stat().st_mtime
                    ).isoformat(),
                    "size_bytes": self._get_directory_size(backup_dir),
                    "files": []
                })

        return backups

    def delete_backup(self, backup_name: str) -> bool:
        """删除备份"""
        backup_path = self.backup_dir / backup_name

        if not backup_path.exists():
            logger.warning(f"备份不存在: {backup_name}")
            return False

        try:
            shutil.rmtree(backup_path)
            logger.info(f"备份已删除: {backup_name}")
            return True
        except Exception as e:
            logger.error(f"删除备份失败: {e}")
            return False

    def _cleanup_old_backups(self):
        """清理旧备份"""
        backups = self.list_backups()

        if len(backups) > self.max_backups:
            backups_to_delete = backups[self.max_backups:]
            for backup in backups_to_delete:
                self.delete_backup(backup["name"])
                logger.info(f"清理旧备份: {backup['name']}")

    def _get_directory_size(self, path: Path) -> int:
        """计算目录大小"""
        total = 0
        try:
            for item in path.rglob("*"):
                if item.is_file():
                    total += item.stat().st_size
        except Exception as e:
            logger.warning(f"计算目录大小失败: {e}")
        return total

    def get_backup_stats(self) -> Dict[str, Any]:
        """获取备份统计"""
        backups = self.list_backups()
        total_size = sum(b.get("size_bytes", 0) for b in backups)

        return {
            "total_backups": len(backups),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "max_backups": self.max_backups,
            "backup_dir": str(self.backup_dir),
            "latest_backup": backups[0] if backups else None
        }


class AutoBackupScheduler:
    """自动备份调度器"""

    def __init__(
        self,
        backup_manager: BackupManager,
        interval_hours: int = 24,
        backup_time: str = "03:00"  # 默认凌晨 3 点
    ):
        self.backup_manager = backup_manager
        self.interval_hours = interval_hours
        self.backup_time = backup_time
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self):
        """启动自动备份"""
        if self._thread and self._thread.is_alive():
            logger.warning("自动备份已在运行")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"自动备份已启动 (间隔: {self.interval_hours}小时, 时间: {self.backup_time})")

    def stop(self):
        """停止自动备份"""
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join(timeout=10)
            logger.info("自动备份已停止")

    def _run(self):
        """运行自动备份"""
        while not self._stop_event.is_set():
            try:
                # 计算下次备份时间
                now = datetime.now()
                target_time = datetime.strptime(self.backup_time, "%H:%M").time()
                target_datetime = now.replace(
                    hour=target_time.hour,
                    minute=target_time.minute,
                    second=0,
                    microsecond=0
                )

                if target_datetime <= now:
                    target_datetime += timedelta(days=1)

                wait_seconds = (target_datetime - now).total_seconds()
                logger.info(f"下次自动备份: {target_datetime.isoformat()}")

                # 等待到备份时间
                if self._stop_event.wait(timeout=wait_seconds):
                    break

                # 执行备份
                logger.info("开始自动备份...")
                backup_info = self.backup_manager.create_backup(
                    name=f"auto_backup_{datetime.now().strftime('%Y%m%d')}"
                )
                logger.info(f"自动备份完成: {backup_info['name']}")

            except Exception as e:
                logger.error(f"自动备份失败: {e}")
                # 出错后等待 1 小时再重试
                if self._stop_event.wait(timeout=3600):
                    break


# 全局备份管理器实例
_backup_manager: Optional[BackupManager] = None


def get_backup_manager(data_dir: Optional[Path] = None) -> BackupManager:
    """获取全局备份管理器"""
    global _backup_manager
    if _backup_manager is None:
        from football_sim.user_workspace import workspace_for_user
        if data_dir is None:
            workspace = workspace_for_user(Path("."), "default")
            data_dir = workspace.data_dir
        _backup_manager = BackupManager(data_dir)
    return _backup_manager


def create_backup(name: Optional[str] = None) -> Dict[str, Any]:
    """创建备份的快捷函数"""
    return get_backup_manager().create_backup(name)


def list_backups() -> List[Dict[str, Any]]:
    """列出备份的快捷函数"""
    return get_backup_manager().list_backups()


def restore_backup(backup_name: str, overwrite: bool = False) -> bool:
    """恢复备份的快捷函数"""
    return get_backup_manager().restore_backup(backup_name, overwrite)
