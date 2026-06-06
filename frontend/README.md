# Football Analyzer Frontend

足球赛事分析系统前端 - Vue 3 + Element Plus + ECharts

## 技术栈

- **框架**: Vue 3.4 + TypeScript
- **UI 组件**: Element Plus 2.5
- **图表**: ECharts 5.4
- **构建工具**: Vite 5
- **状态管理**: Pinia
- **路由**: Vue Router 4
- **PWA**: vite-plugin-pwa

## 功能特性

- 响应式设计，支持移动端
- 实时数据更新（SSE）
- 赔率变化图表
- 命中率统计可视化
- PDF/Excel 报告导出
- PWA 离线支持

## 开发

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 访问 http://localhost:3000
```

## 构建

```bash
# 构建生产版本
npm run build

# 构建产物会输出到 ../src/football_sim/static/
```

## 项目结构

```
frontend/
├── public/              # 静态资源
├── src/
│   ├── assets/          # 样式资源
│   ├── components/      # 公共组件
│   ├── layouts/         # 布局组件
│   ├── router/          # 路由配置
│   ├── stores/          # Pinia 状态
│   ├── utils/           # 工具函数
│   ├── views/           # 页面视图
│   ├── App.vue          # 根组件
│   └── main.ts          # 入口文件
├── index.html           # HTML 模板
├── package.json         # 依赖配置
├── vite.config.ts       # Vite 配置
└── tsconfig.json        # TypeScript 配置
```

## 页面说明

| 路径 | 页面 | 功能 |
|------|------|------|
| `/` | 仪表盘 | 赛事列表、统计卡片、图表 |
| `/match/:id` | 比赛详情 | 赛事信息、赔率、分析 |
| `/analysis/:id` | 分析详情 | 预测结果、完整分析 |
| `/statistics` | 统计 | 命中率、预测分布、导出 |
| `/settings` | 设置 | AI 配置、系统监控、缓存 |

## 开发说明

- 使用 Vue 3 Composition API
- 组件采用 `<script setup>` 语法
- 样式使用 SCSS，支持响应式
- API 请求统一封装在 `utils/api.ts`
