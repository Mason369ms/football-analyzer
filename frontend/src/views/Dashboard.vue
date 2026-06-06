<template>
  <div class="dashboard">
    <!-- 赛事列表 -->
    <el-card class="match-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">赛事列表 ({{ matches.length }} 场)</span>
          <div class="card-actions">
            <el-button type="primary" :icon="Download" @click="fetchMatches" :loading="fetching">
              抓取赛事
            </el-button>
            <el-button :icon="Refresh" @click="refreshData">刷新</el-button>
          </div>
        </div>
      </template>

      <el-table
        :data="matches"
        stripe
        style="width: 100%"
        :max-height="tableHeight"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column prop="match_number" label="序号" width="80" />
        <el-table-column prop="league" label="联赛" min-width="120" show-overflow-tooltip />
        <el-table-column prop="home_team" label="主队" min-width="120" />
        <el-table-column prop="away_team" label="客队" min-width="120" />
        <el-table-column label="时间" width="100">
          <template #default="{ row }">
            {{ row.match_time ? row.match_time.substring(11, 16) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row)" size="small">
              {{ getStatusText(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewMatch(row.match_id)">详情</el-button>
            <el-button link type="success" @click="analyzeMatch(row.match_id)">分析</el-button>
            <el-button link type="danger" @click="deleteMatch(row.match_id, row.home_team, row.away_team)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-footer" v-if="selectedMatches.length > 0">
        <span>已选择 {{ selectedMatches.length }} 场</span>
        <div class="footer-actions">
          <el-button type="success" @click="batchAnalyze" :loading="analyzing">
            批量分析
          </el-button>
          <el-button type="danger" @click="batchDeleteMatches">
            批量删除
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 近期分析 -->
    <el-card class="analysis-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">近期分析</span>
          <div class="card-actions">
            <el-button type="primary" :icon="DataAnalysis" @click="fetchResults">获取结果</el-button>
            <el-button type="danger" :icon="Delete" @click="clearAnalyses">清除记录</el-button>
          </div>
        </div>
      </template>

      <el-table :data="analyses" stripe style="width: 100%" :max-height="400">
        <el-table-column prop="match_number" label="序号" width="80" />
        <el-table-column label="日期" width="100">
          <template #default="{ row }">
            {{ row.created_at?.substring(0, 10) }}
          </template>
        </el-table-column>
        <el-table-column prop="league" label="联赛" width="120" show-overflow-tooltip />
        <el-table-column label="对阵" min-width="160">
          <template #default="{ row }">
            {{ row.home_team }} vs {{ row.away_team }}
          </template>
        </el-table-column>
        <el-table-column label="预测" width="80">
          <template #default="{ row }">
            {{ row.prediction_outcome || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="比分" width="80">
          <template #default="{ row }">
            {{ row.prediction_score || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="进球" width="80">
          <template #default="{ row }">
            {{ row.prediction_goals || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="结果" width="80">
          <template #default="{ row }">
            {{ (row.home_score != null && row.away_score != null) ? `${row.home_score}-${row.away_score}` : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="命中" width="120">
          <template #default="{ row }">
            <el-tag :type="getHitType(row.hit_status)" size="small">
              {{ row.hit_status || '待开奖' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewAnalysis(row.id)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 进度显示 -->
    <el-card v-if="progress > 0 || progressText" class="progress-card">
      <div class="progress-info">
        <span class="progress-text">{{ progressText }}</span>
        <span class="progress-value">{{ progress }}%</span>
      </div>
      <el-progress
        :percentage="progress"
        :stroke-width="20"
        :text-inside="true"
        :status="progress === 100 ? 'success' : ''"
      />
    </el-card>

    <!-- 执行日志 -->
    <el-card class="log-card">
      <template #header>
        <span class="card-title">执行日志</span>
      </template>
      <div class="log-content" ref="logContainer">
        <pre>{{ logContent || '等待任务...' }}</pre>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Download, Refresh, Delete, DataAnalysis
} from '@element-plus/icons-vue'
import api from '@/utils/api'

const router = useRouter()

// 响应式数据
const matches = ref<any[]>([])
const analyses = ref<any[]>([])
const selectedMatches = ref<any[]>([])
const logContent = ref('')
const logContainer = ref<HTMLElement | null>(null)
const fetching = ref(false)
const analyzing = ref(false)
const progress = ref(0)
const progressTotal = ref(0)
const progressText = ref('')

const tableHeight = ref(400)

// 自动滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  })
}

// 获取数据
const refreshData = async () => {
  try {
    const [matchesRes, analysesRes] = await Promise.all([
      api.get('/api/matches', { params: { limit: 100 } }),
      api.get('/api/analyses', { params: { limit: 50 } })
    ])

    // 赛事列表按序号从小到大排序
    matches.value = (matchesRes.matches || []).sort((a, b) => {
      return (a.match_number || 0) - (b.match_number || 0)
    })

    // 分析列表按序号从小到大排序
    analyses.value = (analysesRes.analyses || []).sort((a, b) => {
      return (a.match_number || 0) - (b.match_number || 0)
    })
  } catch (error) {
    console.error('刷新数据失败:', error)
  }
}

// 抓取赛事
const fetchMatches = async () => {
  fetching.value = true
  logContent.value = ''
  progress.value = 0
  progressText.value = '准备抓取...'

  try {
    const eventSource = new EventSource('/api/run?action=fetch-all')

    eventSource.onmessage = (e) => {
      const data = JSON.parse(e.data)

      if (data.line) {
        logContent.value += data.line + '\n'
        scrollToBottom()

        // 解析进度信息
        if (data.line.includes('共') && data.line.includes('场比赛')) {
          const match = data.line.match(/共\s*(\d+)\s*场比赛/)
          if (match) {
            progressTotal.value = parseInt(match[1])
            progressText.value = `已获取 ${progressTotal.value} 场比赛`
          }
        }
      }

      if (data.done) {
        eventSource.close()
        fetching.value = false
        progress.value = 100
        progressText.value = '抓取完成'
        ElMessage.success('赛事抓取完成')

        // 延迟刷新，让用户看到完成信息
        setTimeout(() => {
          refreshData()
          progress.value = 0
          progressText.value = ''
        }, 1500)
      }
    }

    eventSource.onerror = () => {
      eventSource.close()
      fetching.value = false
      progressText.value = '连接断开'
      ElMessage.error('连接断开')
    }
  } catch (error) {
    fetching.value = false
    progressText.value = '抓取失败'
    ElMessage.error('抓取失败')
  }
}

// 分析单场比赛
const analyzeMatch = (matchId: string) => {
  router.push(`/match/${matchId}`)
}

// 删除单场比赛
const deleteMatch = async (matchId: string, homeTeam: string, awayTeam: string) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除比赛 "${homeTeam} vs ${awayTeam}" 吗？`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await api.delete(`/api/matches/${matchId}`)
    ElMessage.success('删除成功')
    refreshData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 批量删除比赛
const batchDeleteMatches = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedMatches.value.length} 场比赛吗？`,
      '确认批量删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const matchIds = selectedMatches.value.map(m => m.match_id)
    const response = await api.post('/api/matches/delete', { match_ids: matchIds })

    if (response.ok) {
      ElMessage.success(`成功删除 ${response.deleted_count} 场比赛`)
      refreshData()
    } else {
      ElMessage.error(response.error || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 批量分析
const batchAnalyze = async () => {
  if (selectedMatches.value.length === 0) {
    ElMessage.warning('请先选择要分析的比赛')
    return
  }

  analyzing.value = true
  logContent.value = ''
  progress.value = 0
  progressTotal.value = selectedMatches.value.length

  let completed = 0
  let success = 0

  for (const match of selectedMatches.value) {
    progressText.value = `正在分析 ${match.home_team} vs ${match.away_team} (${completed + 1}/${progressTotal.value})`
    logContent.value += `\n━━━ 开始分析: ${match.home_team} vs ${match.away_team} ━━━\n`
    scrollToBottom()

    try {
      const eventSource = new EventSource(`/api/run?action=analyze&match_id=${match.match_id}`)

      await new Promise((resolve, reject) => {
        eventSource.onmessage = (e) => {
          const data = JSON.parse(e.data)
          if (data.line) {
            logContent.value += data.line + '\n'
            scrollToBottom()
          }
          if (data.done) {
            eventSource.close()
            success++
            resolve(true)
          }
        }
        eventSource.onerror = () => {
          eventSource.close()
          reject(new Error('连接断开'))
        }
      })
    } catch (error) {
      logContent.value += `❌ 分析失败: ${match.match_id}\n`
      scrollToBottom()
    }

    completed++
    progress.value = Math.round((completed / progressTotal.value) * 100)
  }

  analyzing.value = false
  progressText.value = `完成: ${success}/${progressTotal.value} 场分析成功`
  ElMessage.success(`批量分析完成: ${success}/${progressTotal.value}`)

  // 延迟刷新
  setTimeout(() => {
    refreshData()
    progress.value = 0
    progressText.value = ''
  }, 2000)
}

// 获取比赛结果
const fetchResults = async () => {
  try {
    progressText.value = '正在获取比赛结果...'
    logContent.value += '\n━━━ 获取比赛结果 ━━━\n'
    scrollToBottom()

    const eventSource = new EventSource('/api/run?action=fetch-results')

    eventSource.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.line) {
        logContent.value += data.line + '\n'
        scrollToBottom()
      }
      if (data.done) {
        eventSource.close()
        progressText.value = '获取完成'
        ElMessage.success('结果获取完成')

        setTimeout(() => {
          refreshData()
          progressText.value = ''
        }, 1500)
      }
    }

    eventSource.onerror = () => {
      eventSource.close()
      progressText.value = '连接断开'
      ElMessage.error('获取失败')
    }
  } catch (error) {
    progressText.value = '获取失败'
    ElMessage.error('获取失败')
  }
}

// 清除分析记录
const clearAnalyses = async () => {
  try {
    await ElMessageBox.confirm('确定要清除所有分析记录吗？', '确认', {
      type: 'warning'
    })
    await api.post('/api/analyses/clear')
    ElMessage.success('清除成功')
    refreshData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('清除失败')
    }
  }
}

// 工具函数
const getStatusType = (row: any) => {
  if (row.has_analysis) return 'success'
  if (row.has_data) return 'warning'
  return 'info'
}

const getStatusText = (row: any) => {
  if (row.has_analysis) return '已分析'
  if (row.has_data) return '有数据'
  return '待抓取'
}

const getHitType = (status: string) => {
  if (status?.includes('3/3') || status?.includes('2/3')) return 'success'
  if (status?.includes('1/3')) return 'warning'
  if (status?.includes('未中')) return 'danger'
  return 'info'
}

const viewMatch = (matchId: string) => {
  router.push(`/match/${matchId}`)
}

const viewAnalysis = (id: number) => {
  router.push(`/analysis/${id}`)
}

const handleSelectionChange = (selection: any[]) => {
  selectedMatches.value = selection
}

// 生命周期
onMounted(() => {
  refreshData()

  // 响应式表格高度
  const updateHeight = () => {
    tableHeight.value = window.innerWidth < 768 ? 300 : 400
  }
  updateHeight()
  window.addEventListener('resize', updateHeight)
})
</script>

<style scoped lang="scss">
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.card-actions {
  display: flex;
  gap: 8px;
}

.progress-card {
  :deep(.el-card__body) {
    padding: 16px;
  }

  .progress-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    .progress-text {
      font-size: 14px;
      color: var(--text-color);
      font-weight: 500;
    }

    .progress-value {
      font-size: 18px;
      font-weight: 700;
      color: var(--primary-color);
    }
  }
}

.table-footer {
  margin-top: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: #f8f9fb;
  border-radius: 6px;

  .footer-actions {
    display: flex;
    gap: 8px;
  }
}

.log-content {
  background: #1e293b;
  color: #e2e8f0;
  padding: 16px;
  border-radius: 6px;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 13px;
  max-height: 300px;
  overflow-y: auto;

  pre {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-all;
  }
}

@media (max-width: 768px) {
  .card-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
