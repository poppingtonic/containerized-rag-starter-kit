<template>
  <div class="ingestion-progress" :class="{ collapsed: !isExpanded }">
    <div class="progress-header" @click="toggleExpand">
      <h3>Document Ingestion Progress</h3>
      <button class="toggle-btn">{{ isExpanded ? '▲' : '▼' }}</button>
    </div>
    
    <div v-if="isExpanded" class="progress-content">
      <div v-if="loading" class="loading">
        <div class="spinner"></div>
        <p>Loading ingestion status...</p>
      </div>
      
      <div v-else-if="error" class="error">
        <p>Error loading ingestion status: {{ error }}</p>
        <button @click="fetchProgress" class="btn btn-primary">Retry</button>
      </div>
      
      <div v-else class="progress-data">
        <!-- Overall Progress -->
        <div class="progress-section">
          <h4>Overall Progress</h4>
          <div class="stats-grid">
            <div class="stat-item">
              <span class="stat-value">{{ progress.overall.unique_documents }}</span>
              <span class="stat-label">Documents</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ progress.overall.total_chunks }}</span>
              <span class="stat-label">Chunks</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ progress.ocr.documents_with_ocr }}</span>
              <span class="stat-label">OCR'd Documents</span>
            </div>
          </div>
        </div>
        
        <!-- Embedding Progress -->
        <div class="progress-section">
          <h4>Embedding Generation</h4>
          <div class="progress-bar-container">
            <div class="progress-bar" 
                 :style="{ width: progress.embeddings.completion_percentage + '%' }">
              {{ progress.embeddings.completion_percentage }}%
            </div>
          </div>
          <div class="progress-details">
            {{ progress.embeddings.chunks_with_embeddings }} of {{ progress.embeddings.total_chunks }} chunks
          </div>
        </div>
        
        <!-- Document Types -->
        <div class="progress-section">
          <h4>Document Types</h4>
          <div class="document-types">
            <div v-for="(type, index) in progress.document_types" :key="index" class="doc-type">
              <span class="doc-type-label">{{ formatFileType(type.file_type) }}</span>
              <span class="doc-type-count">{{ type.document_count }}</span>
            </div>
          </div>
        </div>

        <!-- Recently Processed -->
        <div class="progress-section">
          <h4>Recently Processed Documents</h4>
          <div class="recent-documents">
            <table>
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Processed At</th>
                  <th>OCR</th>
                  <th>Chunks</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(doc, index) in progress.recent_documents" :key="index">
                  <td class="doc-name">{{ doc.document }}</td>
                  <td>{{ formatDate(doc.processed_at) }}</td>
                  <td>{{ doc.ocr_applied === 'true' ? 'Yes' : 'No' }}</td>
                  <td>{{ doc.chunk_count }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        
        <!-- Action Buttons -->
        <div class="actions">
          <div class="button-group">
            <button @click="fetchProgress" class="btn btn-primary">Refresh Data</button>
            <button @click="triggerIngestion" class="btn btn-secondary" :disabled="triggeringIngestion">
              <span v-if="triggeringIngestion" class="spinner small-spinner"></span>
              <span v-else>Trigger Reprocessing</span>
            </button>
          </div>
          <div class="status-area">
            <span v-if="triggerStatus" class="trigger-status" :class="triggerStatus.status">
              {{ triggerStatus.message }}
            </span>
            <span class="last-updated">Last updated: {{ lastUpdated }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'IngestionProgress',
  data() {
    return {
      isExpanded: true,  // Start expanded to show progress initially
      loading: false,
      error: null,
      triggeringIngestion: false,
      triggerStatus: null,
      progress: {
        overall: { unique_documents: 0, total_chunks: 0 },
        embeddings: { total_chunks: 0, chunks_with_embeddings: 0, completion_percentage: 0 },
        ocr: { documents_with_ocr: 0 },
        recent_documents: [],
        ingestion_rate: [],
        document_types: []
      },
      lastUpdated: 'Never'
    };
  },
  mounted() {
    // Auto-fetch progress when component mounts
    this.fetchProgress();
    
    // Set up auto-refresh every 30 seconds
    this.refreshInterval = setInterval(() => {
      if (this.isExpanded) {
        this.fetchProgress();
      }
    }, 30000);
  },
  beforeUnmount() {
    // Clear interval when component is destroyed
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
    }
  },
  methods: {
    toggleExpand() {
      this.isExpanded = !this.isExpanded;
      if (this.isExpanded && this.lastUpdated === 'Never') {
        this.fetchProgress();
      }
    },
    async fetchProgress() {
      this.loading = true;
      this.error = null;
      
      try {
        const response = await fetch('/api/ingestion/progress');
        
        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }
        
        this.progress = await response.json();
        this.lastUpdated = new Date().toLocaleTimeString();
      } catch (error) {
        console.error('Error fetching ingestion progress:', error);
        this.error = error.message;
      } finally {
        this.loading = false;
      }
    },
    async triggerIngestion() {
      this.triggeringIngestion = true;
      this.triggerStatus = null;
      
      try {
        const response = await fetch('/api/ingestion/trigger', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          }
        });
        
        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }
        
        const result = await response.json();
        this.triggerStatus = {
          status: result.status,
          message: result.message
        };
        
        // Auto-refresh progress after trigger
        setTimeout(() => {
          this.fetchProgress();
        }, 3000);
      } catch (error) {
        console.error('Error triggering ingestion:', error);
        this.triggerStatus = {
          status: 'error',
          message: `Failed to trigger ingestion: ${error.message}`
        };
      } finally {
        this.triggeringIngestion = false;
      }
    },
    formatDate(dateString) {
      if (!dateString) return 'Unknown';
      
      try {
        const date = new Date(dateString);
        return date.toLocaleString();
      } catch (e) {
        return dateString;
      }
    },
    formatFileType(fileType) {
      if (!fileType) return 'Unknown';
      return fileType.replace('.', '').toUpperCase();
    }
  }
};
</script>

<style>
.ingestion-progress {
  background-color: var(--card-bg);
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
  margin-bottom: 1.5rem;
  transition: all 0.3s ease;
  overflow: hidden;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  cursor: pointer;
  border-bottom: 1px solid var(--border-color);
}

.progress-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: var(--primary-color);
}

.toggle-btn {
  border: none;
  background: none;
  color: var(--secondary-color);
  cursor: pointer;
  font-size: 1.2rem;
}

.progress-content {
  padding: 1.5rem;
}

.loading, .error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
}

.spinner {
  display: inline-block;
  width: 2rem;
  height: 2rem;
  border: 3px solid rgba(74, 108, 247, 0.2);
  border-radius: 50%;
  border-top-color: var(--primary-color);
  animation: spin 1s ease infinite;
  margin-bottom: 1rem;
}

.progress-section {
  margin-bottom: 2rem;
}

.progress-section h4 {
  margin-bottom: 1rem;
  font-size: 1rem;
  color: var(--dark-color);
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 0.5rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 1rem;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 1rem;
  background-color: #f8f9fa;
  border-radius: 8px;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--primary-color);
}

.stat-label {
  font-size: 0.85rem;
  color: var(--secondary-color);
  margin-top: 0.5rem;
}

.progress-bar-container {
  height: 24px;
  background-color: #e9ecef;
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 0.5rem;
}

.progress-bar {
  height: 100%;
  background-color: var(--primary-color);
  border-radius: 12px;
  color: white;
  text-align: center;
  line-height: 24px;
  font-size: 0.85rem;
  font-weight: 500;
  transition: width 0.3s ease;
  min-width: 2rem;
}

.progress-details {
  font-size: 0.85rem;
  color: var(--secondary-color);
  text-align: right;
}

.document-types {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 0.5rem;
}

.doc-type {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 0.75rem;
  background-color: #f8f9fa;
  border-radius: 4px;
}

.doc-type-label {
  font-size: 0.85rem;
  font-weight: 600;
}

.doc-type-count {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--primary-color);
  margin-top: 0.25rem;
}

.recent-documents {
  overflow-x: auto;
}

.recent-documents table {
  width: 100%;
  border-collapse: collapse;
}

.recent-documents th, 
.recent-documents td {
  padding: 0.75rem;
  text-align: left;
  border-bottom: 1px solid var(--border-color);
}

.recent-documents th {
  font-weight: 600;
  background-color: #f8f9fa;
}

.doc-name {
  max-width: 300px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 1rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.button-group {
  display: flex;
  gap: 0.5rem;
}

.status-area {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.last-updated {
  font-size: 0.85rem;
  color: var(--secondary-color);
}

.trigger-status {
  font-size: 0.9rem;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  margin-bottom: 0.25rem;
}

.trigger-status.success {
  background-color: #d4edda;
  color: #155724;
}

.trigger-status.error {
  background-color: #f8d7da;
  color: #721c24;
}

.btn-secondary {
  background-color: #6c757d;
  color: white;
}

.small-spinner {
  width: 1rem;
  height: 1rem;
  border-width: 2px;
}

.collapsed .progress-content {
  display: none;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>