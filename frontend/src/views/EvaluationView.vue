<template>
  <div class="evaluation-view">
    <h1>Evaluation Metrics</h1>
    <p class="subtitle">Analyze feedback and system performance</p>

    <div v-if="loading" class="loading">Loading evaluation metrics...</div>
    <div v-else-if="error" class="error-message">{{ error }}</div>
    
    <div v-else-if="metrics" class="metrics-container">
      <!-- Overall Statistics -->
      <div class="metrics-section">
        <h2>Overall Statistics</h2>
        <div class="stats-grid">
          <div class="stat-box">
            <div class="stat-label">Total Feedback</div>
            <div class="stat-value">{{ metrics.overall.total_feedback }}</div>
          </div>
          <div class="stat-box">
            <div class="stat-label">Rated Queries</div>
            <div class="stat-value">{{ metrics.overall.rated_count }}</div>
          </div>
          <div class="stat-box">
            <div class="stat-label">Average Rating</div>
            <div class="stat-value">
              {{ metrics.overall.average_rating ? metrics.overall.average_rating.toFixed(2) : 'N/A' }}
              <span v-if="metrics.overall.average_rating" class="stars">
                {{ getStars(metrics.overall.average_rating) }}
              </span>
            </div>
          </div>
          <div class="stat-box">
            <div class="stat-label">Favorites</div>
            <div class="stat-value">{{ metrics.overall.favorites_count }}</div>
          </div>
          <div class="stat-box">
            <div class="stat-label">Text Feedback</div>
            <div class="stat-value">{{ metrics.overall.text_feedback_count }}</div>
          </div>
        </div>
      </div>

      <!-- Rating Distribution -->
      <div class="metrics-section">
        <h2>Rating Distribution</h2>
        <div class="rating-distribution">
          <div v-for="rating in [5, 4, 3, 2, 1]" :key="rating" class="rating-bar">
            <div class="rating-label">
              {{ rating }} {{ '★'.repeat(rating) }}{{ '☆'.repeat(5 - rating) }}
            </div>
            <div class="bar-container">
              <div 
                class="bar-fill" 
                :style="{ width: getRatingPercentage(rating) + '%' }"
                :class="'rating-' + rating"
              ></div>
            </div>
            <div class="rating-count">
              {{ getRatingCount(rating) }}
            </div>
          </div>
        </div>
      </div>

      <!-- Feedback Timeline -->
      <div class="metrics-section">
        <h2>Feedback Timeline (Last 30 Days)</h2>
        <div class="timeline-chart">
          <div v-for="day in metrics.timeline" :key="day.date" class="timeline-bar">
            <div class="bar-wrapper">
              <div 
                class="timeline-bar-fill" 
                :style="{ height: getTimelineBarHeight(day.feedback_count) + '%' }"
                :title="`${day.feedback_count} feedback on ${formatDate(day.date)}`"
              ></div>
            </div>
            <div class="timeline-date">{{ formatShortDate(day.date) }}</div>
          </div>
        </div>
      </div>

      <!-- RAGAS Metrics Summary -->
      <div class="metrics-section">
        <h2>Automatic Quality Metrics (RAGAS)</h2>
        <div v-if="ragasMetrics" class="ragas-summary">
          <div class="ragas-stat">
            <div class="stat-label">Average Faithfulness</div>
            <div class="stat-value">{{ formatPercent(ragasMetrics.faithfulness_avg) }}</div>
          </div>
          <div class="ragas-stat">
            <div class="stat-label">Average Answer Relevancy</div>
            <div class="stat-value">{{ formatPercent(ragasMetrics.answer_relevancy_avg) }}</div>
          </div>
          <div class="ragas-stat">
            <div class="stat-label">Average Context Precision</div>
            <div class="stat-value">{{ formatPercent(ragasMetrics.context_precision_avg) }}</div>
          </div>
          <div class="ragas-stat">
            <div class="stat-label">Overall RAGAS Score</div>
            <div class="stat-value">{{ formatPercent(ragasMetrics.overall_score_avg) }}</div>
          </div>
        </div>
        <div v-else class="ragas-info">
          <p>RAGAS metrics will appear here as queries are evaluated automatically.</p>
          <button @click="evaluateSample" class="action-button">
            Evaluate Sample Queries
          </button>
        </div>
      </div>

      <!-- Actions -->
      <div class="metrics-section">
        <h2>Export Options</h2>
        <div class="export-actions">
          <button @click="downloadReport" class="export-button">
            📊 Download Evaluation Report
          </button>
          <button @click="goToExport" class="export-button">
            📥 Export Training Data
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'

export default {
  name: 'EvaluationView',
  setup() {
    const router = useRouter()
    const metrics = ref(null)
    const loading = ref(false)
    const error = ref('')
    const ragasMetrics = ref(null)

    const loadMetrics = async () => {
      loading.value = true
      error.value = ''
      
      try {
        const response = await fetch('/api/evaluation/metrics')
        
        if (!response.ok) {
          const text = await response.text()
          let message = 'Failed to load metrics'
          try {
            const data = JSON.parse(text)
            message = data.message || data.detail || message
          } catch (e) {
            // If not JSON, use status text
            message = `${response.status} ${response.statusText}`
          }
          throw new Error(message)
        }
        
        const data = await response.json()
        metrics.value = data.metrics
      } catch (err) {
        error.value = err.message
      } finally {
        loading.value = false
      }
    }

    const getRatingCount = (rating) => {
      if (!metrics.value) return 0
      const item = metrics.value.rating_distribution.find(r => r.rating === rating)
      return item ? item.count : 0
    }

    const getRatingPercentage = (rating) => {
      if (!metrics.value || metrics.value.overall.rated_count === 0) return 0
      const count = getRatingCount(rating)
      return (count / metrics.value.overall.rated_count) * 100
    }

    const maxFeedbackCount = computed(() => {
      if (!metrics.value || !metrics.value.timeline.length) return 1
      return Math.max(...metrics.value.timeline.map(d => d.feedback_count))
    })

    const getTimelineBarHeight = (count) => {
      if (maxFeedbackCount.value === 0) return 0
      return (count / maxFeedbackCount.value) * 100
    }

    const getStars = (rating) => {
      const full = Math.floor(rating)
      const partial = rating - full
      let stars = '★'.repeat(full)
      if (partial >= 0.75) stars += '★'
      else if (partial >= 0.25) stars += '½'
      return stars.padEnd(5, '☆')
    }

    const formatDate = (dateStr) => {
      return new Date(dateStr).toLocaleDateString()
    }

    const formatShortDate = (dateStr) => {
      const date = new Date(dateStr)
      return `${date.getMonth() + 1}/${date.getDate()}`
    }

    const downloadReport = async () => {
      try {
        const response = await fetch('/api/export/evaluation-report')
        const data = await response.json()
        
        if (!response.ok) {
          throw new Error(data.message || 'Failed to generate report')
        }
        
        // Create and download JSON file
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `evaluation_report_${new Date().toISOString().split('T')[0]}.json`
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
      } catch (err) {
        alert('Error downloading report: ' + err.message)
      }
    }

    const goToExport = () => {
      router.push('/export')
    }

    const formatPercent = (value) => {
      if (typeof value !== 'number') return 'N/A'
      return (value * 100).toFixed(1) + '%'
    }

    const evaluateSample = async () => {
      try {
        // Get top-rated queries for evaluation
        const response = await fetch('/api/cache/entries?limit=10&include_feedback=true')
        
        if (!response.ok) {
          const text = await response.text()
          let message = 'Failed to load cache entries'
          try {
            const errorData = JSON.parse(text)
            message = errorData.message || errorData.detail || message
          } catch (e) {
            message = `${response.status} ${response.statusText}`
          }
          throw new Error(message)
        }
        
        const data = await response.json()
        
        if (!data.entries) {
          throw new Error('No cache entries found')
        }
        
        // Filter for entries with high ratings
        const highRatedEntries = data.entries
          .filter(e => e.feedback && e.feedback.rating >= 4)
          .slice(0, 5)
          .map(e => e.id)
        
        if (highRatedEntries.length === 0) {
          alert('No high-rated queries found for evaluation')
          return
        }
        
        // Evaluate them with RAGAS
        const evalResponse = await fetch('/api/ragas/evaluate/batch', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            memory_ids: highRatedEntries,
            include_ground_truth: false
          })
        })
        
        const evalData = await evalResponse.json()
        
        if (!evalResponse.ok) {
          throw new Error(evalData.detail || 'Failed to evaluate')
        }
        
        ragasMetrics.value = evalData.results
      } catch (err) {
        alert('Error evaluating sample: ' + err.message)
      }
    }

    onMounted(() => {
      loadMetrics()
    })

    return {
      metrics,
      loading,
      error,
      ragasMetrics,
      getRatingCount,
      getRatingPercentage,
      getTimelineBarHeight,
      getStars,
      formatDate,
      formatShortDate,
      formatPercent,
      downloadReport,
      goToExport,
      evaluateSample
    }
  }
}
</script>

<style scoped>
.evaluation-view {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.subtitle {
  color: #666;
  margin-bottom: 30px;
}

.metrics-container {
  display: grid;
  gap: 30px;
}

.metrics-section {
  background: white;
  padding: 25px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.metrics-section h2 {
  margin: 0 0 20px 0;
  color: #333;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
}

.stat-box {
  text-align: center;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 8px;
}

.stat-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 10px;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #333;
}

.stars {
  display: block;
  color: #ffa500;
  font-size: 20px;
  margin-top: 5px;
}

.rating-distribution {
  display: grid;
  gap: 15px;
}

.rating-bar {
  display: grid;
  grid-template-columns: 120px 1fr 60px;
  align-items: center;
  gap: 15px;
}

.rating-label {
  color: #666;
  font-size: 14px;
}

.bar-container {
  background: #e9ecef;
  height: 30px;
  border-radius: 15px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  transition: width 0.3s ease;
}

.rating-5 { background: #28a745; }
.rating-4 { background: #17a2b8; }
.rating-3 { background: #ffc107; }
.rating-2 { background: #fd7e14; }
.rating-1 { background: #dc3545; }

.rating-count {
  text-align: right;
  font-weight: bold;
  color: #333;
}

.timeline-chart {
  display: flex;
  align-items: flex-end;
  height: 200px;
  gap: 5px;
  padding: 20px 0;
  overflow-x: auto;
}

.timeline-bar {
  flex: 1;
  min-width: 30px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.bar-wrapper {
  flex: 1;
  width: 100%;
  display: flex;
  align-items: flex-end;
}

.timeline-bar-fill {
  width: 100%;
  background: #007bff;
  border-radius: 4px 4px 0 0;
  transition: height 0.3s ease;
  cursor: pointer;
}

.timeline-bar-fill:hover {
  background: #0056b3;
}

.timeline-date {
  font-size: 12px;
  color: #666;
  margin-top: 5px;
  transform: rotate(-45deg);
  white-space: nowrap;
}

.export-actions {
  display: flex;
  gap: 15px;
}

.export-button {
  padding: 12px 24px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  font-size: 16px;
  transition: background 0.2s;
}

.export-button:hover {
  background: #0056b3;
}

.loading {
  text-align: center;
  padding: 50px;
  color: #666;
}

.error-message {
  background: #f8d7da;
  color: #721c24;
  padding: 15px;
  border-radius: 5px;
}

.ragas-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
}

.ragas-stat {
  text-align: center;
  padding: 20px;
  background: #e7f3ff;
  border-radius: 8px;
}

.ragas-info {
  text-align: center;
  padding: 30px;
  background: #f8f9fa;
  border-radius: 8px;
}

.ragas-info p {
  margin: 0 0 20px 0;
  color: #666;
}

.action-button {
  padding: 10px 20px;
  background: #17a2b8;
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  font-size: 14px;
}

.action-button:hover {
  background: #138496;
}
</style>