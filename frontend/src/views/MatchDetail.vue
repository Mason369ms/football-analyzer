<template>
  <div class="match-detail">
    <el-page-header @back="$router.back()" :content="`${match.home_team} vs ${match.away_team}`" />

    <!-- 赛事信息 -->
    <el-card class="info-card">
      <div class="match-header">
        <div class="teams">
          <div class="team home">
            <div class="team-name">{{ match.home_team }}</div>
            <div class="team-label">主队</div>
          </div>
          <div class="vs">VS</div>
          <div class="team away">
            <div class="team-name">{{ match.away_team }}</div>
            <div class="team-label">客队</div>
          </div>
        </div>
        <div class="match-meta">
          <el-tag>{{ match.league }}</el-tag>
          <span>{{ match.match_time }}</span>
        </div>
      </div>

      <el-button
        type="primary"
        size="large"
        :loading="analyzing"
        @click="doAnalyze"
        style="margin-top: 20px"
      >
        <el-icon><Cpu /></el-icon>
        分析此赛事
      </el-button>
    </el-card>

    <!-- 赔率摘要 -->
    <el-card v-if="oddsSummary.euro_implied" class="odds-card">
      <template #header>
        <span class="card-title">赔率摘要</span>
      </template>
      <el-descriptions :column="isMobile ? 1 : 3" border>
        <el-descriptions-item label="欧赔隐含概率">
          主胜 {{ oddsSummary.euro_implied.p_home }}% |
          平局 {{ oddsSummary.euro_implied.p_draw }}% |
          客胜 {{ oddsSummary.euro_implied.p_away }}%
        </el-descriptions-item>
        <el-descriptions-item label="亚盘方向">
          <el-tag :type="oddsSummary.asian_direction === '主队' ? 'primary' : 'warning'">
            {{ oddsSummary.asian_direction }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="大小球方向">
          <el-tag :type="oddsSummary.ou_direction === '大球' ? 'danger' : 'success'">
            {{ oddsSummary.ou_direction }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 赔率变化图表 -->
    <el-card v-if="oddsHistory.length > 0" class="chart-card">
      <template #header>
        <span class="card-title">赔率变化趋势</span>
      </template>
      <div ref="oddsChart" class="odds-chart"></div>
    </el-card>

    <!-- 已有分析 -->
    <el-card v-if="analysis" class="analysis-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">分析结果</span>
          <el-button type="primary" link @click="viewFullAnalysis">查看完整分析</el-button>
        </div>
      </template>

      <div class="prediction-summary">
        <div class="prediction-item">
          <div class="pred-label">胜平负</div>
          <div class="pred-value">{{ analysis.prediction_outcome }}</div>
        </div>
        <div class="prediction-item">
          <div class="pred-label">比分</div>
          <div class="pred-value">{{ analysis.prediction_score }}</div>
        </div>
        <div class="prediction-item">
          <div class="pred-label">进球数</div>
          <div class="pred-value">{{ analysis.prediction_goals }}</div>
        </div>
        <div class="prediction-item">
          <div class="pred-label">置信度</div>
          <div class="pred-value">
            <el-progress :percentage="analysis.confidence" :stroke-width="10" />
          </div>
        </div>
      </div>

      <el-divider />
      <div class="analysis-brief">
        <h4>精简摘要</h4>
        <p>{{ analysis.brief_text }}</p>
      </div>
    </el-card>

    <!-- 执行日志 -->
    <el-card class="log-card">
      <template #header>
        <span class="card-title">执行日志</span>
      </template>
      <div class="log-content">
        <pre>{{ logContent || '等待分析...' }}</pre>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Cpu } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import api from '@/utils/api'

const route = useRoute()
const router = useRouter()
const matchId = route.params.id as string

const match = ref<any>({})
const analysis = ref<any>(null)
const oddsSummary = ref<any>({})
const oddsHistory = ref<any[]>([])
const logContent = ref('')
const analyzing = ref(false)
const isMobile = ref(window.innerWidth < 768)

const oddsChart = ref<HTMLElement>()

// 获取赛事详情
const fetchMatchDetail = async () => {
  try {
    const data = await api.get(`/api/match/${matchId}`)

    if (!data.ok) {
      ElMessage.error(data.error || '获取赛事详情失败')
      return
    }

    match.value = data.match || {}
    analysis.value = data.analysis
    oddsSummary.value = data.odds_summary || {}

    // 处理赔率历史数据
    const matchData = data.match_data || {}
    const oddsChanges = matchData['赔率变化数据'] || {}
    oddsHistory.value = parseOddsHistory(oddsChanges)

    nextTick(() => {
      if (oddsChart.value && oddsHistory.value.length > 0) {
        initOddsChart()
      }
    })
  } catch (error) {
    console.error('获取赛事详情失败:', error)
    ElMessage.error('获取赛事详情失败')
  }
}

// 解析赔率历史数据
const parseOddsHistory = (oddsChanges: any) => {
  const history: any[] = []

  // 从各公司赔率变化中提取数据
  for (const [company, types] of Object.entries(oddsChanges)) {
    const euroList = (types as any)['欧指'] || []
    for (const item of euroList.slice(0, 20)) {  // 最多取20条
      history.push({
        time: item.update_time || '',
        home: parseFloat(item.home_win_odds || item.current_left || 0),
        draw: parseFloat(item.draw_odds || item.current_middle || 0),
        away: parseFloat(item.away_win_odds || item.current_right || 0)
      })
    }
  }

  // 按时间排序
  return history.sort((a, b) => a.time.localeCompare(b.time))
}

// 初始化赔率图表
const initOddsChart = () => {
  const chart = echarts.init(oddsChart.value!)

  const times = oddsHistory.value.map(item => item.time)
  const homeOdds = oddsHistory.value.map(item => item.home)
  const drawOdds = oddsHistory.value.map(item => item.draw)
  const awayOdds = oddsHistory.value.map(item => item.away)

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['主胜', '平局', '客胜'] },
    xAxis: { type: 'category', data: times },
    yAxis: { type: 'value' },
    series: [
      { name: '主胜', type: 'line', data: homeOdds, smooth: true },
      { name: '平局', type: 'line', data: drawOdds, smooth: true },
      { name: '客胜', type: 'line', data: awayOdds, smooth: true }
    ]
  })

  window.addEventListener('resize', () => chart.resize())
}

// 执行分析
const doAnalyze = async () => {
  analyzing.value = true
  logContent.value = ''

  try {
    const eventSource = new EventSource(`/api/run?action=analyze&match_id=${matchId}`)

    eventSource.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.line) {
        logContent.value += data.line + '\n'
      }
      if (data.done) {
        eventSource.close()
        analyzing.value = false
        ElMessage.success('分析完成')
        fetchMatchDetail()
      }
    }

    eventSource.onerror = () => {
      eventSource.close()
      analyzing.value = false
      ElMessage.error('分析连接断开')
    }
  } catch (error) {
    analyzing.value = false
    ElMessage.error('分析失败')
  }
}

// 查看完整分析
const viewFullAnalysis = () => {
  if (analysis.value?.id) {
    router.push(`/analysis/${analysis.value.id}`)
  }
}

onMounted(() => {
  fetchMatchDetail()

  window.addEventListener('resize', () => {
    isMobile.value = window.innerWidth < 768
  })
})
</script>

<style scoped lang="scss">
.match-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 1000px;
  margin: 0 auto;
}

.info-card {
  :deep(.el-card__body) {
    text-align: center;
  }
}

.match-header {
  .teams {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 40px;
    margin-bottom: 20px;
  }

  .team {
    text-align: center;

    .team-name {
      font-size: 24px;
      font-weight: 700;
      margin-bottom: 8px;
    }

    .team-label {
      color: var(--text-muted);
      font-size: 14px;
    }
  }

  .vs {
    font-size: 20px;
    font-weight: 700;
    color: var(--text-muted);
  }

  .match-meta {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 16px;
    color: var(--text-muted);
  }
}

.odds-chart {
  height: 300px;
  width: 100%;
}

.prediction-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 20px;
}

.prediction-item {
  text-align: center;
  padding: 20px;
  background: #f8f9fb;
  border-radius: 8px;

  .pred-label {
    color: var(--text-muted);
    font-size: 14px;
    margin-bottom: 8px;
  }

  .pred-value {
    font-size: 20px;
    font-weight: 700;
    color: var(--primary-color);
  }
}

.analysis-brief {
  h4 {
    margin-bottom: 12px;
    color: var(--text-color);
  }

  p {
    color: var(--text-muted);
    line-height: 1.8;
  }
}

.log-content {
  background: #1e293b;
  color: #e2e8f0;
  padding: 16px;
  border-radius: 6px;
  font-family: 'Monaco', monospace;
  font-size: 13px;
  max-height: 300px;
  overflow-y: auto;

  pre {
    margin: 0;
    white-space: pre-wrap;
  }
}

@media (max-width: 768px) {
  .match-header {
    .teams {
      gap: 20px;
    }

    .team .team-name {
      font-size: 18px;
    }
  }

  .prediction-summary {
    grid-template-columns: repeat(2, 1fr);
  }

  .odds-chart {
    height: 200px;
  }
}
</style>
