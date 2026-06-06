# LLM API 配置指南

## 问题诊断

你遇到的错误：
```
Illegal header value b'Bearer '
```

**原因**: API Key 为空，导致 Authorization header 格式错误。

---

## 解决方案

### 方案 1：通过仪表盘配置（推荐）

1. **启动仪表盘**:
   ```powershell
   $env:PYTHONPATH='src'
   python -m football_sim.cli dashboard --server fastapi --port 8766
   ```

2. **访问仪表盘**:
   - 打开浏览器访问 http://127.0.0.1:8766
   - 使用账号登录（默认: admin/admin）

3. **配置 AI**:
   - 点击导航栏的「AI 配置」
   - 填写以下信息：
     - **Provider**: `openai` 或 `deepseek`
     - **Base URL**: `https://token-plan-cn.xiaomimimo.com/v1`
     - **Model**: `mimo-v2.5-pro`
     - **API Key**: 你的 API 密钥 ⚠️ **必填**

4. **保存配置**:
   - 点击「保存配置」按钮
   - 看到"配置已保存"提示即可

---

### 方案 2：使用命令行脚本

```powershell
# 运行设置脚本
$env:PYTHONPATH='src'
python scripts/set_api_key.py
```

按提示输入你的 API Key 即可。

---

### 方案 3：直接修改数据库（高级用户）

```powershell
# 使用 SQLite 工具直接更新
$env:PYTHONPATH='src'
python -c "
import sqlite3
conn = sqlite3.connect('data/users/default/history.sqlite3')
cursor = conn.cursor()
cursor.execute(
    \"UPDATE dashboard_config SET value = '你的API_KEY' WHERE key = 'llm_api_key'\"
)
conn.commit()
conn.close()
print('API Key 已更新')
"
```

---

## 验证配置

设置完成后，运行以下命令验证：

```powershell
# 1. 诊断配置
$env:PYTHONPATH='src'
python scripts/diagnose_llm.py

# 2. 测试 LLM 调用
python scripts/test_llm_analysis.py

# 3. 分析比赛
python -m football_sim.cli analyze --date 2026-06-01
```

---

## 获取 API Key

### Token Plan (当前使用的服务)

1. 访问 https://token-plan-cn.xiaomimimo.com
2. 登录你的账号
3. 在控制台找到 API Key
4. 复制完整的 Key（通常以 `tp-` 开头）

### 其他常见 API 提供商

- **OpenAI**: https://platform.openai.com/api-keys
- **DeepSeek**: https://platform.deepseek.com/api_keys
- **其他 OpenAI 兼容 API**: 查看对应平台的文档

---

## 常见问题

### Q1: API Key 格式是什么？
A: 通常是字符串，如：
- `tp-csh1abzgxw20t8g4opl5u1dhyn4oi7g9n8nk8ybe1sn0vmj8`
- `sk-xxxxxxxxxxxxxxxxxxxxxxxx`
- `sk-ant-xxxxxxxxxxxxxxxx`

### Q2: 保存后仍然提示未配置？
A: 检查以下几点：
1. 确认已点击「保存配置」按钮
2. 刷新页面重新查看配置
3. 运行 `python scripts/diagnose_llm.py` 检查数据库

### Q3: API Key 是否有权限要求？
A: 需要确保：
1. Key 有效且未过期
2. 有足够额度/配额
3. 有访问 chat/completions 接口的权限

### Q4: 如何测试 API Key 是否有效？
A: 使用诊断脚本：
```powershell
PYTHONPATH='src' python scripts/diagnose_llm.py
```

---

## 技术细节

### 配置存储位置

LLM 配置存储在 SQLite 数据库中：

- **默认用户**: `data/users/default/history.sqlite3`
- **管理员用户**: `data/users/admin/history.sqlite3`

数据库表 `dashboard_config` 中的字段：
- `llm_provider`: 提供商名称
- `llm_base_url`: API 基础 URL
- `llm_model`: 模型名称
- `llm_api_key`: API 密钥

### 代码改进

已在 `llm_analyzer.py` 中添加：

1. **参数验证**: 检查 API Key 是否为空
2. **自动清理**: 使用 `.strip()` 移除首尾空格
3. **友好错误提示**: 明确指出缺少哪个配置项
4. **详细错误信息**: 捕获 HTTP 错误并显示具体原因

---

## 快速开始脚本

```powershell
# 一键设置和测试
$env:PYTHONPATH='src'

# 1. 设置 API Key
python scripts/set_api_key.py

# 2. 验证配置
python scripts/diagnose_llm.py

# 3. 测试调用
python scripts/test_llm_analysis.py

# 4. 分析比赛
python -m football_sim.cli analyze --date 2026-06-01
```

---

## 获取帮助

如果仍有问题：

1. **查看详细日志**: 启动仪表盘后查看控制台输出
2. **运行诊断脚本**: `python scripts/diagnose_llm.py`
3. **检查 API 文档**: 确认使用的模型和参数是否正确
4. **查看源码**: `src/football_sim/analysis/llm_analyzer.py`

---

**最后更新**: 2026-06-04
**维护者**: Claude Code Assistant
