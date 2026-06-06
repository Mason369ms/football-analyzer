# 赛事数据完整传递使用指南

## 📊 数据完整性验证结果

✅ **已验证：所有赛事数据都完整传递给 LLM**

| 数据字段 | 原始大小 | 保留率 | 状态 |
|---------|---------|--------|------|
| 历史交锋 | 13.5 KB | 99.7% | ✅ 完整 |
| 近期战绩 | 126.7 KB | 100% | ✅ 完整 |
| 队员情报 | 4.0 KB | 98.8% | ✅ 完整 |
| 阵容天气 | 4.1 KB | 98.9% | ✅ 完整 |
| 联赛积分 | 9.7 KB | 99.5% | ✅ 完整 |
| 赔率变化 | 28.7 KB | 99.8% | ✅ 完整 |
| **总计** | **186.9 KB** | **99.5%** | ✅ |

---

## 🚀 使用方式

### 方式 1：完整数据模式（默认，推荐）

**适用场景**：
- 使用支持大 context window 的 LLM 模型（如 GPT-4 Turbo, Claude 3, DeepSeek 等）
- 需要最精准的分析结果
- API 额度充足

**命令**：
```powershell
# 分析指定日期的所有比赛
$env:PYTHONPATH='src'
python -m football_sim.cli analyze --date 2026-06-04

# 分析单场比赛
python -m football_sim.cli analyze --match-dir "data/matches/2026-06-04/周四201_国际友谊_斯洛文尼亚_vs_塞浦路斯"
```

**数据量**：
- 每场比赛约 **180K-200K 字符**（约 180K-200K tokens）
- 包含所有原始数据，无截断

**优势**：
- ✅ 分析更精准
- ✅ 包含所有细节
- ✅ LLM 可以看到完整的历史数据和赔率变化

**注意事项**：
- ⚠️ 需要 LLM 模型支持 32K+ tokens 的 context window
- ⚠️ API 调用成本较高
- ⚠️ 分析时间较长

---

### 方式 2：截断模式

**适用场景**：
- LLM 模型的 context window 受限（如 4K-8K tokens）
- 需要快速分析
- API 额度有限

**命令**：
```powershell
$env:PYTHONPATH='src'
python -m football_sim.cli analyze --date 2026-06-04 --truncated
```

**数据量**：
- 每场比赛约 **17K 字符**（约 17K tokens）
- 数据截断到预设限制

**截断限制**：
- 历史交锋: 3,000 字符
- 近期战绩: 3,000 字符
- 队员情报: 2,000 字符
- 阵容天气: 2,000 字符
- 联赛积分: 2,000 字符
- 赔率变化: 5,000 字符

**优势**：
- ✅ 速度快
- ✅ 成本低
- ✅ 适用于小模型

**缺点**：
- ❌ 丢失约 90% 的数据
- ❌ 分析可能不够精准
- ❌ 可能遗漏重要细节

---

## 🌐 通过 Web 仪表盘使用

仪表盘默认使用**完整数据模式**。

### 启动仪表盘
```powershell
$env:PYTHONPATH='src'
python -m football_sim.cli dashboard --server fastapi --port 8766
```

### 操作步骤
1. 访问 http://127.0.0.1:8766
2. 登录账号（默认: admin/admin）
3. 选择日期和比赛
4. 点击「分析」按钮
5. 等待分析完成（完整模式可能需要 1-3 分钟）

---

## 📈 数据对比分析

### 测试结果（以"斯洛文尼亚 vs 塞浦路斯"为例）

| 模式 | Prompt 大小 | 数据保留率 | 适用场景 |
|-----|------------|-----------|---------|
| **完整模式** | 191,428 字符 (186.9 KB) | 99.5% | 精准分析 |
| **截断模式** | 17,273 字符 (16.9 KB) | 5.0% | 快速分析 |

**数据量差异**: 完整模式是截断模式的 **11.1 倍**

---

## 🔧 验证数据完整性

使用验证脚本检查数据是否完整传递：

```powershell
$env:PYTHONPATH='src'
python scripts/verify_full_data.py
```

验证内容：
- ✅ 检查所有数据字段是否包含在 prompt 中
- ✅ 计算数据保留率
- ✅ 显示 prompt 结构
- ✅ 保存 prompt 样本供检查

---

## 💡 使用建议

### 场景 1：重要比赛分析
**推荐**: 完整数据模式
**原因**: 需要最全面的数据支持精准预测

```powershell
python -m football_sim.cli analyze --date 2026-06-04
```

### 场景 2：快速批量分析
**推荐**: 截断模式
**原因**: 速度快，成本低，适用于大批量处理

```powershell
python -m football_sim.cli analyze --date 2026-06-04 --truncated
```

### 场景 3：Token 受限的模型
**推荐**: 截断模式
**原因**: 避免超出 context window 限制

```powershell
python -m football_sim.cli analyze --date 2026-06-04 --truncated
```

### 场景 4：Web 仪表盘分析
**推荐**: 使用仪表盘
**原因**: 自动使用完整数据模式，无需手动配置

```powershell
python -m football_sim.cli dashboard --server fastapi --port 8766
```

---

## 📊 优化数据格式

完整数据模式使用压缩 JSON 格式减少 token 消耗：

```python
# 压缩格式（去除空格）
{"key1":"value1","key2":[1,2,3]}

# 标准格式（有空格）
{
  "key1": "value1",
  "key2": [1, 2, 3]
}
```

**节省效果**: 约减少 30-40% 的字符数

---

## 🎯 LLM 模型推荐

### 推荐使用完整数据模式的模型

| 模型 | Context Window | 推荐指数 | 备注 |
|-----|---------------|---------|------|
| **GPT-4 Turbo** | 128K | ⭐⭐⭐⭐⭐ | 最佳选择 |
| **Claude 3 Opus** | 200K | ⭐⭐⭐⭐⭐ | 强大推理 |
| **DeepSeek Chat** | 32K | ⭐⭐⭐⭐ | 性价比高 |
| **GPT-4** | 8K | ⭐⭐ | 建议截断模式 |
| **GPT-3.5 Turbo** | 16K | ⭐⭐⭐ | 可尝试完整模式 |

### 检查你的模型

运行诊断脚本查看当前配置：

```powershell
python scripts/diagnose_llm.py
```

---

## 🔍 查看分析结果

### 分析完成后

1. **命令行输出**: 分析结果直接打印到终端
2. **数据库记录**: 保存到 `data/users/<username>/history.sqlite3`
3. **Web 仪表盘**: 在"历史记录"中查看

### 查看 Prompt 样本

```powershell
# 查看完整 prompt 的前 5000 字符
cat test_output_full_prompt.txt
```

---

## ⚠️ 常见问题

### Q1: 分析超时怎么办？
**A**: 完整数据模式可能需要较长时间（1-3 分钟），建议：
- 检查网络连接
- 增加超时时间
- 使用更快的模型
- 或改用截断模式

### Q2: API 报错 token 超限？
**A**: 说明模型 context window 不够大，建议：
- 使用 `--truncated` 模式
- 或更换支持更大 context 的模型

### Q3: 如何知道数据是否完整传递？
**A**: 运行验证脚本：
```powershell
python scripts/verify_full_data.py
```

### Q4: 完整模式的成本高吗？
**A**: 是的，完整模式消耗更多 tokens，但分析更精准。可以根据需求选择：
- 重要比赛：完整模式
- 普通比赛：截断模式

---

## 📚 相关脚本

| 脚本 | 功能 | 使用方式 |
|-----|------|---------|
| `verify_full_data.py` | 验证数据完整性 | `python scripts/verify_full_data.py` |
| `analyze_data_size.py` | 分析数据大小 | `python scripts/analyze_data_size.py` |
| `diagnose_llm.py` | 诊断 LLM 配置 | `python scripts/diagnose_llm.py` |
| `test_llm_analysis.py` | 测试 LLM 调用 | `python scripts/test_llm_analysis.py` |
| `quick_setup.py` | 快速设置 API Key | `python scripts/quick_setup.py YOUR_KEY` |

---

## 🎉 总结

✅ **已完成**:
1. 修改代码支持完整数据传递
2. 默认使用完整数据模式
3. 提供 `--truncated` 选项兼容小模型
4. 验证脚本确认数据完整性（99.5%+ 保留率）
5. 仪表盘默认使用完整数据模式

✅ **验证结果**:
- 所有 6 个数据字段都完整传递
- 数据保留率 98.8% - 100%
- 完整模式是截断模式的 11.1 倍数据量

**现在可以放心使用 AI 分析了！** 所有抓取到的赛事数据都会完整传递给 LLM 进行分析。🎯
