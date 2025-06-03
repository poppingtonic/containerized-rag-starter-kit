<template>
  <div class="ragas-metrics">
    <div class="metrics-header" @click="toggleExpanded">
      <h3>
        <i class="fas fa-chart-line"></i> 
        Automatic Quality Metrics
        <span class="quality-badge" :class="qualityClass">
          {{ interpretation.quality_level || 'Evaluating...' }}
        </span>
      </h3>
      <button class="toggle-btn">
        <i class="fas" :class="expanded ? 'fa-chevron-up' : 'fa-chevron-down'"></i>
      </button>
    </div>

    <div v-if="expanded" class="metrics-content">
      <div v-if="loading" class="loading">
        <i class="fas fa-spinner fa-spin"></i> Evaluating response quality...
      </div>

      <div v-else-if="error" class="error-message">
        {{ error }}
      </div>

      <div v-else-if="scores" class="metrics-grid">
        <!-- Overall Score -->
        <div class="metric-card overall">
          <div class="metric-label">Overall Score</div>
          <div class="metric-value">
            <div class="score-circle" :style="{ '--score': scores.overall_score }">
              {{ formatScore(scores.overall_score) }}
            </div>
          </div>
        </div>

        <!-- Individual Metrics -->
        <div v-for="(value, metric) in filteredScores" :key="metric" class="metric-card">
          <div class="metric-label">{{ formatMetricName(metric) }}</div>
          <div class="metric-value">
            <div class="score-bar">
              <div class="score-fill" :style="{ width: (value * 100) + '%' }" :class="getScoreClass(value)"></div>
            </div>
            <span class="score-text">{{ formatScore(value) }}</span>
          </div>
          <div class="metric-hint">{{ getMetricHint(metric) }}</div>
        </div>
      </div>

      <!-- Interpretation Section -->
      <div v-if="interpretation && !loading" class="interpretation">
        <div v-if="interpretation.strengths.length > 0" class="strengths">
          <h4><i class="fas fa-check-circle"></i> Strengths</h4>
          <ul>
            <li v-for="(strength, index) in interpretation.strengths" :key="index">
              {{ strength }}
            </li>
          </ul>
        </div>

        <div v-if="interpretation.weaknesses.length > 0" class="weaknesses">
          <h4><i class="fas fa-exclamation-circle"></i> Areas for Improvement</h4>
          <ul>
            <li v-for="(weakness, index) in interpretation.weaknesses" :key="index">
              {{ weakness }}
            </li>
          </ul>
        </div>

        <div v-if="interpretation.recommendations.length > 0" class="recommendations">
          <h4><i class="fas fa-lightbulb"></i> Recommendations</h4>
          <ul>
            <li v-for="(rec, index) in interpretation.recommendations" :key="index">
              {{ rec }}
            </li>
          </ul>
        </div>
      </div>

      <!-- Manual Rating Integration -->
      <div class="manual-rating-prompt">
        <p>How would you rate this response?</p>
        <div class="rating-stars">
          <button 
            v-for="star in 5" 
            :key="star"
            @click="$emit('rate', star)"
            class="star-btn"
            :class="{ active: userRating >= star }"
          >
            {{ star <= userRating ? '★' : '☆' }}
          </button>
        </div>
        <p class="rating-hint">Your rating helps improve the system!</p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'

export default {
  name: 'RagasMetrics',
  props: {
    memoryId: {
      type: Number,
      required: true
    },
    userRating: {
      type: Number,
      default: 0
    }
  },
  emits: ['rate'],
  setup(props) {
    const expanded = ref(false)
    const loading = ref(false)
    const error = ref('')
    const scores = ref(null)
    const interpretation = ref(null)
    const explanations = ref({})

    const qualityClass = computed(() => {
      if (!interpretation.value) return ''
      const level = interpretation.value.quality_level
      return {
        'Excellent': 'excellent',
        'Good': 'good',
        'Fair': 'fair',
        'Poor': 'poor'
      }[level] || ''
    })

    const filteredScores = computed(() => {
      if (!scores.value) return {}
      const filtered = {}
      for (const [key, value] of Object.entries(scores.value)) {
        if (key !== 'overall_score' && key !== 'error' && typeof value === 'number') {
          filtered[key] = value
        }
      }
      return filtered
    })

    const toggleExpanded = () => {
      expanded.value = !expanded.value
      if (expanded.value && !scores.value && !loading.value) {
        evaluateQuery()
      }
    }

    const evaluateQuery = async () => {
      loading.value = true
      error.value = ''
      
      try {
        const response = await fetch(`/api/ragas/evaluate/memory/${props.memoryId}`, {
          method: 'POST'
        })
        
        const data = await response.json()
        
        if (!response.ok) {
          throw new Error(data.detail || 'Failed to evaluate')
        }
        
        scores.value = data.scores
        interpretation.value = data.interpretation
        explanations.value = data.explanations
      } catch (err) {
        error.value = 'Failed to evaluate response quality: ' + err.message
      } finally {
        loading.value = false
      }
    }

    const formatScore = (score) => {
      if (typeof score !== 'number') return 'N/A'
      return (score * 100).toFixed(0) + '%'
    }

    const formatMetricName = (metric) => {
      return metric
        .replace(/_/g, ' ')
        .replace(/\b\w/g, l => l.toUpperCase())
    }

    const getScoreClass = (score) => {
      if (score >= 0.8) return 'excellent'
      if (score >= 0.6) return 'good'
      if (score >= 0.4) return 'fair'
      return 'poor'
    }

    const getMetricHint = (metric) => {
      const hints = {
        'faithfulness': 'How well the answer sticks to the provided context',
        'answer_relevancy': 'How relevant the answer is to the question',
        'context_precision': 'Quality of retrieved context (signal vs noise)',
        'context_relevancy': 'How relevant the context is to the question'
      }
      return hints[metric] || ''
    }

    // Auto-expand if user has already rated
    watch(() => props.userRating, (newRating) => {
      if (newRating > 0 && !expanded.value) {
        expanded.value = true
        if (!scores.value && !loading.value) {
          evaluateQuery()
        }
      }
    })

    return {
      expanded,
      loading,
      error,
      scores,
      interpretation,
      qualityClass,
      filteredScores,
      toggleExpanded,
      formatScore,
      formatMetricName,
      getScoreClass,
      getMetricHint
    }
  }
}
</script>

<style scoped>
.ragas-metrics {
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  margin: 20px 0;
  overflow: hidden;
}

.metrics-header {
  padding: 15px 20px;
  background: #f8f9fa;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: background 0.2s;
}

.metrics-header:hover {
  background: #e9ecef;
}

.metrics-header h3 {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  color: #333;
}

.quality-badge {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 500;
}

.quality-badge.excellent { background: #d4edda; color: #155724; }
.quality-badge.good { background: #d1ecf1; color: #0c5460; }
.quality-badge.fair { background: #fff3cd; color: #856404; }
.quality-badge.poor { background: #f8d7da; color: #721c24; }

.toggle-btn {
  background: none;
  border: none;
  font-size: 16px;
  color: #666;
}

.metrics-content {
  padding: 20px;
}

.loading {
  text-align: center;
  padding: 30px;
  color: #666;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
  margin-bottom: 20px;
}

.metric-card {
  padding: 15px;
  background: #f8f9fa;
  border-radius: 6px;
}

.metric-card.overall {
  grid-column: 1 / -1;
  text-align: center;
  background: #e7f3ff;
}

.metric-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
}

.metric-value {
  display: flex;
  align-items: center;
  gap: 10px;
}

.score-circle {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: bold;
  margin: 0 auto;
  background: conic-gradient(
    #28a745 calc(var(--score) * 360deg),
    #e9ecef calc(var(--score) * 360deg)
  );
  position: relative;
}

.score-circle::before {
  content: '';
  position: absolute;
  width: 60px;
  height: 60px;
  background: white;
  border-radius: 50%;
  z-index: 0;
}

.score-circle::after {
  content: attr(data-score);
  position: relative;
  z-index: 1;
}

.score-bar {
  flex: 1;
  height: 20px;
  background: #e9ecef;
  border-radius: 10px;
  overflow: hidden;
}

.score-fill {
  height: 100%;
  transition: width 0.3s ease;
}

.score-fill.excellent { background: #28a745; }
.score-fill.good { background: #17a2b8; }
.score-fill.fair { background: #ffc107; }
.score-fill.poor { background: #dc3545; }

.score-text {
  font-weight: 600;
  min-width: 45px;
  text-align: right;
}

.metric-hint {
  font-size: 12px;
  color: #888;
  margin-top: 5px;
}

.interpretation {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #e0e0e0;
}

.interpretation h4 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 15px 0 10px 0;
  font-size: 15px;
}

.strengths h4 { color: #28a745; }
.weaknesses h4 { color: #ffc107; }
.recommendations h4 { color: #17a2b8; }

.interpretation ul {
  margin: 0;
  padding-left: 25px;
}

.interpretation li {
  margin: 5px 0;
  font-size: 14px;
  color: #555;
}

.manual-rating-prompt {
  margin-top: 20px;
  padding: 20px;
  background: #f0f7ff;
  border-radius: 8px;
  text-align: center;
}

.manual-rating-prompt p {
  margin: 0 0 15px 0;
  color: #333;
}

.rating-stars {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-bottom: 10px;
}

.star-btn {
  background: none;
  border: none;
  font-size: 32px;
  color: #ddd;
  cursor: pointer;
  transition: all 0.2s;
}

.star-btn:hover {
  color: #ffa500;
  transform: scale(1.1);
}

.star-btn.active {
  color: #ffa500;
}

.rating-hint {
  font-size: 13px;
  color: #666;
  margin: 0;
}

.error-message {
  background: #f8d7da;
  color: #721c24;
  padding: 10px;
  border-radius: 5px;
  font-size: 14px;
}

/* Icon fallbacks */
.fa-chart-line::before { content: "📈"; }
.fa-chevron-up::before { content: "⌃"; }
.fa-chevron-down::before { content: "⌄"; }
.fa-spinner::before { content: "⏳"; }
.fa-check-circle::before { content: "✅"; }
.fa-exclamation-circle::before { content: "⚠️"; }
.fa-lightbulb::before { content: "💡"; }
</style>