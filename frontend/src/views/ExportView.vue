<template>
  <div class="export-view">
    <h1>Export Training Data</h1>
    <p class="subtitle">Export query-answer pairs with feedback for fine-tuning or analysis</p>

    <div class="export-options">
      <h2>Export Filters</h2>
      
      <div class="filter-group">
        <label>Minimum Rating:</label>
        <select v-model.number="filters.minRating">
          <option :value="null">All ratings</option>
          <option :value="5">5 stars only</option>
          <option :value="4">4+ stars</option>
          <option :value="3">3+ stars</option>
          <option :value="2">2+ stars</option>
          <option :value="1">1+ stars</option>
        </select>
      </div>

      <div class="filter-group">
        <label>
          <input type="checkbox" v-model="filters.onlyFavorites">
          Only export favorites
        </label>
      </div>

      <div class="filter-group">
        <label>
          <input type="checkbox" v-model="filters.includeChunks">
          Include retrieved chunks and entities
        </label>
      </div>

      <div class="filter-group">
        <label>Export Format:</label>
        <div class="format-options">
          <label>
            <input type="radio" v-model="exportFormat" value="jsonl">
            JSONL (for fine-tuning)
          </label>
          <label>
            <input type="radio" v-model="exportFormat" value="csv">
            CSV (for analysis)
          </label>
          <label>
            <input type="radio" v-model="exportFormat" value="json">
            JSON (preview)
          </label>
        </div>
      </div>
    </div>

    <div class="export-actions">
      <button @click="previewData" class="action-button preview">
        👁️ Preview Data
      </button>
      <button @click="exportData" class="action-button export" :disabled="exporting">
        {{ exporting ? 'Exporting...' : '📥 Export Data' }}
      </button>
    </div>

    <div v-if="preview" class="preview-section">
      <h2>Preview ({{ preview.count }} entries)</h2>
      <div v-if="preview.count === 0" class="empty-state">
        No data matches the selected filters
      </div>
      <div v-else class="preview-container">
        <div v-for="(item, index) in preview.data.slice(0, 5)" :key="index" class="preview-item">
          <div class="preview-header">
            <span class="preview-id">ID: {{ item.id }}</span>
            <span v-if="item.rating" class="preview-rating">
              {{ '★'.repeat(item.rating) }}{{ '☆'.repeat(5 - item.rating) }}
            </span>
            <span v-if="item.is_favorite" class="favorite-badge">⭐ Favorite</span>
          </div>
          <div class="preview-query">
            <strong>Query:</strong> {{ item.query }}
          </div>
          <div class="preview-answer">
            <strong>Answer:</strong> {{ truncate(item.answer, 200) }}
          </div>
          <div v-if="item.feedback" class="preview-feedback">
            <strong>Feedback:</strong> {{ item.feedback }}
          </div>
          <div v-if="filters.includeChunks && item.chunks" class="preview-meta">
            <span>{{ item.chunks.length }} chunks</span>
            <span v-if="item.entities">{{ item.entities.length }} entities</span>
          </div>
        </div>
        <div v-if="preview.count > 5" class="preview-more">
          ... and {{ preview.count - 5 }} more entries
        </div>
      </div>
    </div>

    <div class="info-section">
      <h2>Export Format Information</h2>
      <div class="format-info">
        <div class="format-card">
          <h3>JSONL Format</h3>
          <p>Best for fine-tuning language models. Each line contains a complete JSON object with query-answer pairs.</p>
          <pre>{"query": "...", "answer": "...", "rating": 5, ...}</pre>
        </div>
        <div class="format-card">
          <h3>CSV Format</h3>
          <p>Best for data analysis in Excel or pandas. Flattened structure with one row per entry.</p>
          <pre>id,query,answer,rating,is_favorite,...</pre>
        </div>
        <div class="format-card">
          <h3>JSON Format</h3>
          <p>Best for previewing data structure. Returns complete JSON array with all selected fields.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'

export default {
  name: 'ExportView',
  setup() {
    const filters = ref({
      minRating: null,
      onlyFavorites: false,
      includeChunks: true
    })
    
    const exportFormat = ref('jsonl')
    const exporting = ref(false)
    const preview = ref(null)

    const buildQueryParams = () => {
      const params = new URLSearchParams()
      params.append('format', exportFormat.value)
      
      if (filters.value.minRating !== null) {
        params.append('min_rating', filters.value.minRating)
      }
      
      if (filters.value.onlyFavorites) {
        params.append('only_favorites', 'true')
      }
      
      params.append('include_chunks', filters.value.includeChunks ? 'true' : 'false')
      
      return params.toString()
    }

    const previewData = async () => {
      try {
        const queryParams = buildQueryParams()
        const response = await fetch(`/api/export/training-data?${queryParams}&format=json`)
        const data = await response.json()
        
        if (!response.ok) {
          throw new Error(data.message || 'Failed to preview data')
        }
        
        preview.value = data
      } catch (err) {
        alert('Error previewing data: ' + err.message)
      }
    }

    const exportData = async () => {
      exporting.value = true
      
      try {
        const queryParams = buildQueryParams()
        const response = await fetch(`/api/export/training-data?${queryParams}`)
        
        if (!response.ok) {
          const error = await response.json()
          throw new Error(error.message || 'Export failed')
        }
        
        if (exportFormat.value === 'json') {
          // For JSON, parse and download
          const data = await response.json()
          const blob = new Blob([JSON.stringify(data.data, null, 2)], { type: 'application/json' })
          downloadBlob(blob, `training_data.json`)
        } else {
          // For JSONL and CSV, download directly
          const blob = await response.blob()
          const extension = exportFormat.value === 'jsonl' ? 'jsonl' : 'csv'
          downloadBlob(blob, `training_data.${extension}`)
        }
      } catch (err) {
        alert('Error exporting data: ' + err.message)
      } finally {
        exporting.value = false
      }
    }

    const downloadBlob = (blob, filename) => {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    }

    const truncate = (text, length) => {
      if (!text) return ''
      if (text.length <= length) return text
      return text.substring(0, length) + '...'
    }

    return {
      filters,
      exportFormat,
      exporting,
      preview,
      previewData,
      exportData,
      truncate
    }
  }
}
</script>

<style scoped>
.export-view {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.subtitle {
  color: #666;
  margin-bottom: 30px;
}

.export-options {
  background: white;
  padding: 25px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  margin-bottom: 30px;
}

.export-options h2 {
  margin: 0 0 20px 0;
  color: #333;
}

.filter-group {
  margin-bottom: 20px;
}

.filter-group label {
  display: block;
  margin-bottom: 5px;
  color: #555;
  font-weight: 500;
}

.filter-group select {
  width: 200px;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.format-options {
  display: flex;
  gap: 20px;
  margin-top: 10px;
}

.format-options label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-weight: normal;
}

.export-actions {
  display: flex;
  gap: 15px;
  margin-bottom: 30px;
}

.action-button {
  padding: 12px 24px;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  font-size: 16px;
  transition: all 0.2s;
}

.action-button.preview {
  background: #6c757d;
  color: white;
}

.action-button.preview:hover {
  background: #5a6268;
}

.action-button.export {
  background: #28a745;
  color: white;
}

.action-button.export:hover {
  background: #218838;
}

.action-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.preview-section {
  background: white;
  padding: 25px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  margin-bottom: 30px;
}

.preview-section h2 {
  margin: 0 0 20px 0;
  color: #333;
}

.preview-container {
  border: 1px solid #e9ecef;
  border-radius: 4px;
  overflow: hidden;
}

.preview-item {
  padding: 15px;
  border-bottom: 1px solid #e9ecef;
}

.preview-item:last-child {
  border-bottom: none;
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 10px;
}

.preview-id {
  font-size: 12px;
  color: #666;
  background: #f8f9fa;
  padding: 2px 6px;
  border-radius: 3px;
}

.preview-rating {
  color: #ffa500;
}

.favorite-badge {
  font-size: 12px;
  background: #fff3cd;
  color: #856404;
  padding: 2px 6px;
  border-radius: 3px;
}

.preview-query,
.preview-answer,
.preview-feedback {
  margin-bottom: 8px;
  font-size: 14px;
  line-height: 1.5;
}

.preview-meta {
  display: flex;
  gap: 15px;
  margin-top: 10px;
  font-size: 12px;
  color: #666;
}

.preview-more {
  padding: 15px;
  text-align: center;
  color: #666;
  font-style: italic;
  background: #f8f9fa;
}

.info-section {
  background: white;
  padding: 25px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.info-section h2 {
  margin: 0 0 20px 0;
  color: #333;
}

.format-info {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
}

.format-card {
  padding: 20px;
  background: #f8f9fa;
  border-radius: 6px;
}

.format-card h3 {
  margin: 0 0 10px 0;
  color: #495057;
}

.format-card p {
  margin: 0 0 15px 0;
  font-size: 14px;
  color: #666;
  line-height: 1.5;
}

.format-card pre {
  background: #e9ecef;
  padding: 10px;
  border-radius: 4px;
  font-size: 12px;
  overflow-x: auto;
  margin: 0;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: #666;
}
</style>