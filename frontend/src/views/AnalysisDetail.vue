<template>
  <div class="analysis-detail">
    <el-page-header @back="$router.back()" :content="`${analysis.home_team} vs ${analysis.away_team}`" />

    <!-- 预测结果卡片 -->
    <el-card class="prediction-card">
      <div class="prediction-grid">
        <div class="prediction-item outcome">
          <div class="pred-icon">🎯</div>
          <div class="pred-label">胜平负</div>
          <div class="pred-value">{{ analysis.prediction_outcome }}</div>
        </div>
        <div class="prediction-item score">
          <div class="pred-icon">⚽</div>
          <div class="pred-label">比分</div>
          <div class="pred-value">{{ analysis.prediction_score }}</div>
        </div>
        <div class="prediction-item goals">
          <div class="pred-icon">🥅</div>
          <div class="pred-label">进球数</div>
          <div class="pred-value">{{ analysis.prediction_goals }}</div>
        </div>
        <div class="prediction-item confidence">
          <div class="pred-icon">📊</div>
          <div class="pred-label">置信度</div>
          <div class="pred-value">
            <el-progress
              :percentage="analysis.confidence"
              :stroke-width="20"
              :text-inside="true"
            />
          </div>
        </div>
      </div>
    </el-card>

    <!-- 分析详情 -->
    <el-card class="analysis-content-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">完整分析</span>
          <el-button type="primary" @click="exportPDF">
            <el-icon><Download /></el-icon>
            导出 PDF
          </el-button>
        </div>
      </template>
      <div class="analysis-text" v-html="formattedAnalysis"></div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import api from '@/utils/api'

const route = useRoute()
const analysisId = route.params.id

const analysis = ref<any>({})

const formattedAnalysis = computed(() => {
  const text = analysis.value.analysis_text || ''
  return text
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/#{1,3}\s(.+)/g, '<h3>$1</h3>')
})

const fetchAnalysis = async () => {
  try {
    const data = await api.get(`/api/analysis/${analysisId}`)

    if (!data.ok) {
      ElMessage.error(data.error || '获取分析详情失败')
      return
    }

    analysis.value = data.analysis
  } catch (error) {
    console.error('获取分析详情失败:', error)
    ElMessage.error('获取分析详情失败')
  }
}

const exportPDF = async () => {
  try {
    const response = await fetch(`/api/export/pdf/${analysisId}`)
    if (response.ok) {
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `analysis_${analysisId}.pdf`
      a.click()
      window.URL.revokeObjectURL(url)
      ElMessage.success('PDF 导出成功')
    } else {
      ElMessage.error('PDF 导出失败')
    }
  } catch (error) {
    ElMessage.error('PDF 导出失败')
  }
}

onMounted(() => {
  fetchAnalysis()
})
</script>

<style scoped lang="scss">
.analysis-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 1000px;
  margin: 0 auto;
}

.prediction-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
}

.prediction-item {
  text-align: center;
  padding: 30px 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  color: #fff;

  .pred-icon {
    font-size: 36px;
    margin-bottom: 12px;
  }

  .pred-label {
    font-size: 14px;
    opacity: 0.9;
    margin-bottom: 8px;
  }

  .pred-value {
    font-size: 28px;
    font-weight: 700;
  }

  &.outcome {
    background: linear-gradient(135deg, #1d4ed8 0%, #3b82f6 100%);
  }

  &.score {
    background: linear-gradient(135deg, #16835f 0%, #34d399 100%);
  }

  &.goals {
    background: linear-gradient(135deg, #d97706 0%, #fbbf24 100%);
  }

  &.confidence {
    background: linear-gradient(135deg, #6366f1 0%, #a78bfa 100%);

    .pred-value {
      background: rgba(255, 255, 255, 0.2);
      border-radius: 10px;
      padding: 10px;
    }
  }
}

.analysis-content-card {
  :deep(.el-card__body) {
    padding: 24px;
  }
}

.analysis-text {
  line-height: 1.8;
  font-size: 15px;

  :deep(h3) {
    margin: 20px 0 12px;
    color: var(--primary-color);
  }

  :deep(strong) {
    color: var(--text-color);
  }
}

@media (max-width: 768px) {
  .prediction-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .prediction-item {
    padding: 20px 12px;

    .pred-icon {
      font-size: 28px;
    }

    .pred-value {
      font-size: 22px;
    }
  }
}
</style>
