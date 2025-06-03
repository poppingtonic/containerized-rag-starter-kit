<template>
  <div class="cache-view">
    <h1>Query Cache</h1>
    <p class="subtitle">View all cached queries and their feedback</p>

    <div class="cache-stats" v-if="stats">
      <div class="stat-card">
        <h3>Total Entries</h3>
        <p class="stat-value">{{ stats.total }}</p>
      </div>
      <div class="stat-card">
        <h3>With Feedback</h3>
        <p class="stat-value">{{ stats.withFeedback }}</p>
      </div>
      <div class="stat-card">
        <h3>Favorites</h3>
        <p class="stat-value">{{ stats.favorites }}</p>
      </div>
      <div class="stat-card">
        <h3>Average Rating</h3>
        <p class="stat-value">{{ stats.avgRating ? stats.avgRating.toFixed(1) : 'N/A' }}</p>
      </div>
    </div>

    <div class="filters">
      <label>
        <input type="checkbox" v-model="includeFeedback" @change="loadCacheEntries">
        Include feedback data
      </label>
    </div>

    <div v-if="loading" class="loading">Loading cache entries...</div>
    <div v-else-if="error" class="error-message">{{ error }}</div>
    <div v-else-if="entries.length === 0" class="empty-state">No cache entries found</div>
    
    <div v-else class="cache-entries">
      <div v-for="entry in entries" :key="entry.id" class="cache-entry">
        <div class="entry-header">
          <h3>{{ entry.query }}</h3>
          <div class="entry-meta">
            <span class="entry-id">ID: {{ entry.id }}</span>
            <span class="entry-date">{{ formatDate(entry.created_at) }}</span>
            <span class="access-count">Accessed: {{ entry.access_count }} times</span>
          </div>
        </div>
        
        <div class="entry-answer">{{ truncate(entry.answer, 200) }}</div>
        
        <div v-if="entry.feedback" class="entry-feedback">
          <div class="feedback-rating" v-if="entry.feedback.rating">
            Rating: <span class="stars">{{ '★'.repeat(entry.feedback.rating) }}{{ '☆'.repeat(5 - entry.feedback.rating) }}</span>
          </div>
          <div v-if="entry.feedback.text" class="feedback-text">
            <strong>Feedback:</strong> {{ entry.feedback.text }}
          </div>
          <span v-if="entry.feedback.is_favorite" class="favorite-badge">⭐ Favorite</span>
        </div>
        
        <div class="entry-actions">
          <button @click="viewDetails(entry)" class="action-button">View Details</button>
          <button @click="deleteEntry(entry.id)" class="action-button delete">Delete</button>
        </div>
      </div>
    </div>

    <div v-if="hasMore" class="pagination">
      <button @click="loadMore" :disabled="loading" class="load-more-button">
        Load More
      </button>
    </div>

    <!-- Detail Modal -->
    <div v-if="selectedEntry" class="modal-overlay" @click="closeModal">
      <div class="modal-content" @click.stop>
        <button class="close-button" @click="closeModal">&times;</button>
        <h2>Query Details</h2>
        
        <div class="detail-section">
          <h3>Query</h3>
          <p>{{ selectedEntry.query }}</p>
        </div>
        
        <div class="detail-section">
          <h3>Answer</h3>
          <div v-html="formatAnswer(selectedEntry.answer)"></div>
        </div>
        
        <div v-if="selectedEntry.references.length > 0" class="detail-section">
          <h3>References</h3>
          <ul>
            <li v-for="(ref, index) in selectedEntry.references" :key="index">
              {{ ref }}
            </li>
          </ul>
        </div>
        
        <div class="detail-section">
          <h3>Metadata</h3>
          <p>Created: {{ formatDate(selectedEntry.created_at) }}</p>
          <p>Last accessed: {{ formatDate(selectedEntry.last_accessed) }}</p>
          <p>Access count: {{ selectedEntry.access_count }}</p>
          <p>Chunks used: {{ selectedEntry.chunks.length }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { marked } from 'marked'

export default {
  name: 'CacheView',
  setup() {
    const entries = ref([])
    const loading = ref(false)
    const error = ref('')
    const includeFeedback = ref(true)
    const offset = ref(0)
    const limit = ref(20)
    const hasMore = ref(true)
    const selectedEntry = ref(null)
    const stats = ref(null)

    const loadCacheEntries = async (append = false) => {
      loading.value = true
      error.value = ''
      
      try {
        const response = await fetch(`/api/cache/entries?limit=${limit.value}&offset=${offset.value}&include_feedback=${includeFeedback.value}`)
        
        if (!response.ok) {
          const text = await response.text()
          let message = 'Failed to load cache entries'
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
        
        if (append) {
          entries.value.push(...data.entries)
        } else {
          entries.value = data.entries
          // Calculate stats
          const withFeedback = data.entries.filter(e => e.feedback).length
          const favorites = data.entries.filter(e => e.feedback?.is_favorite).length
          const ratings = data.entries.filter(e => e.feedback?.rating).map(e => e.feedback.rating)
          const avgRating = ratings.length > 0 ? ratings.reduce((a, b) => a + b, 0) / ratings.length : null
          
          stats.value = {
            total: data.total,
            withFeedback,
            favorites,
            avgRating
          }
        }
        
        hasMore.value = entries.value.length < data.total
      } catch (err) {
        error.value = err.message
      } finally {
        loading.value = false
      }
    }

    const loadMore = () => {
      offset.value += limit.value
      loadCacheEntries(true)
    }

    const deleteEntry = async (entryId) => {
      if (!confirm('Are you sure you want to delete this cache entry?')) {
        return
      }
      
      try {
        const response = await fetch(`/api/memory/entry/${entryId}`, {
          method: 'DELETE'
        })
        
        if (!response.ok) {
          throw new Error('Failed to delete entry')
        }
        
        // Remove from local list
        entries.value = entries.value.filter(e => e.id !== entryId)
        if (stats.value) {
          stats.value.total--
        }
      } catch (err) {
        alert('Error deleting entry: ' + err.message)
      }
    }

    const viewDetails = (entry) => {
      selectedEntry.value = entry
    }

    const closeModal = () => {
      selectedEntry.value = null
    }

    const formatDate = (dateString) => {
      if (!dateString) return 'N/A'
      return new Date(dateString).toLocaleString()
    }

    const formatAnswer = (answer) => {
      return marked(answer)
    }

    const truncate = (text, length) => {
      if (text.length <= length) return text
      return text.substring(0, length) + '...'
    }

    onMounted(() => {
      loadCacheEntries()
    })

    return {
      entries,
      loading,
      error,
      includeFeedback,
      hasMore,
      selectedEntry,
      stats,
      loadCacheEntries,
      loadMore,
      deleteEntry,
      viewDetails,
      closeModal,
      formatDate,
      formatAnswer,
      truncate
    }
  }
}
</script>

<style scoped>
.cache-view {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.subtitle {
  color: #666;
  margin-bottom: 30px;
}

.cache-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.stat-card {
  background: #f5f5f5;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
}

.stat-card h3 {
  margin: 0 0 10px 0;
  font-size: 14px;
  color: #666;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #333;
  margin: 0;
}

.filters {
  margin-bottom: 20px;
}

.cache-entries {
  display: grid;
  gap: 20px;
}

.cache-entry {
  background: white;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 20px;
}

.entry-header {
  margin-bottom: 15px;
}

.entry-header h3 {
  margin: 0 0 10px 0;
  color: #333;
}

.entry-meta {
  display: flex;
  gap: 20px;
  font-size: 14px;
  color: #666;
}

.entry-answer {
  color: #555;
  margin-bottom: 15px;
  line-height: 1.6;
}

.entry-feedback {
  background: #f9f9f9;
  padding: 15px;
  border-radius: 5px;
  margin-bottom: 15px;
}

.feedback-rating {
  margin-bottom: 10px;
}

.stars {
  color: #ffa500;
  font-size: 18px;
}

.feedback-text {
  font-size: 14px;
  color: #666;
}

.favorite-badge {
  display: inline-block;
  background: #fff3cd;
  color: #856404;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 14px;
  margin-top: 10px;
}

.entry-actions {
  display: flex;
  gap: 10px;
}

.action-button {
  padding: 8px 16px;
  border: 1px solid #ddd;
  background: white;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.action-button:hover {
  background: #f5f5f5;
}

.action-button.delete {
  color: #dc3545;
  border-color: #dc3545;
}

.action-button.delete:hover {
  background: #dc3545;
  color: white;
}

.pagination {
  text-align: center;
  margin-top: 30px;
}

.load-more-button {
  padding: 10px 30px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  font-size: 16px;
}

.load-more-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  max-width: 800px;
  max-height: 90vh;
  overflow-y: auto;
  padding: 30px;
  border-radius: 8px;
  position: relative;
}

.close-button {
  position: absolute;
  top: 10px;
  right: 10px;
  background: none;
  border: none;
  font-size: 30px;
  cursor: pointer;
  color: #666;
}

.detail-section {
  margin-bottom: 25px;
}

.detail-section h3 {
  margin-bottom: 10px;
  color: #333;
}

.loading, .empty-state {
  text-align: center;
  padding: 50px;
  color: #666;
}

.error-message {
  background: #f8d7da;
  color: #721c24;
  padding: 15px;
  border-radius: 5px;
  margin-bottom: 20px;
}
</style>