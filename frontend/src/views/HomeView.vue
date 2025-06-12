<template>
  <div class="home-view">
    <div class="query-section">
      <h1>AI Search</h1>
      <p class="subtitle">Query your documents with AI-powered search and knowledge graph enhancement</p>
      
      <form @submit.prevent="submitQuery" class="query-form">
        <input 
          v-model="queryInput" 
          type="text" 
          placeholder="Ask a question about your documents..."
          class="query-input"
          :disabled="loading"
        />
        <button type="submit" :disabled="loading || !queryInput.trim()" class="submit-button">
          {{ loading ? 'Searching...' : 'Search' }}
        </button>
      </form>
    </div>

    <IngestionProgress />

    <div v-if="error" class="error-message">
      {{ error }}
    </div>

    <div v-if="results && !loading" class="results-section">
      <div class="answer-card">
        <h2>Answer</h2>
        <div class="answer-text" v-html="formatAnswer(results.answer)"></div>
        <ResultActions 
          :memoryId="results.memory_id"
          :query="results.query"
          :answer="results.answer"
          @refresh="submitQuery"
        />
      </div>

      <RagasMetrics 
        v-if="results.memory_id && results.memory_id !== -1"
        :memoryId="results.memory_id"
        :userRating="userRating"
        @rate="handleRating"
      />

      <div class="metadata">
        <span v-if="results.from_memory" class="memory-badge">
          📚 From Memory (ID: {{ results.memory_id }})
        </span>
      </div>

      <div v-if="results.references && results.references.length > 0" class="references-section">
        <h3>References</h3>
        <ul class="references-list">
          <li v-for="(ref, index) in results.references" :key="index">
            [{{ index + 1 }}] {{ ref }}
          </li>
        </ul>
      </div>

      <div v-if="results.chunks && results.chunks.length > 0" class="chunks-section">
        <h3>Relevant Document Chunks</h3>
        <div v-for="chunk in results.chunks" :key="chunk.id" class="chunk-card">
          <div class="chunk-header">
            <span class="chunk-source">{{ chunk.source }}</span>
            <span class="chunk-similarity">{{ (chunk.similarity * 100).toFixed(1) }}% match</span>
          </div>
          <div class="chunk-text">{{ chunk.text }}</div>
        </div>
      </div>

      <div v-if="results.entities && results.entities.length > 0" class="entities-section">
        <h3>Key Entities</h3>
        <div class="entities-grid">
          <div v-for="entity in results.entities" :key="entity.entity" class="entity-card">
            <div class="entity-name">{{ entity.entity }}</div>
            <div class="entity-type">{{ entity.entity_type }}</div>
            <div class="entity-relevance">Relevance: {{ (entity.relevance * 100).toFixed(0) }}%</div>
          </div>
        </div>
      </div>
    </div>

    <FavoritesList />
    <ThreadsList />
  </div>
</template>

<script>
import { ref, computed } from 'vue'
import { useStore } from 'vuex'
import { marked } from 'marked'
import IngestionProgress from '../components/IngestionProgress.vue'
import ResultActions from '../components/ResultActions.vue'
import FavoritesList from '../components/FavoritesList.vue'
import ThreadsList from '../components/ThreadsList.vue'
import RagasMetrics from '../components/RagasMetrics.vue'

export default {
  name: 'HomeView',
  components: {
    IngestionProgress,
    ResultActions,
    FavoritesList,
    ThreadsList,
    RagasMetrics
  },
  setup() {
    const store = useStore()
    const queryInput = ref('')
    const userRating = ref(0)

    const results = computed(() => store.state.results)
    const loading = computed(() => store.state.loading)
    const error = computed(() => store.state.error)

    const submitQuery = async () => {
      if (queryInput.value.trim()) {
        await store.dispatch('submitQuery', queryInput.value)
      }
    }

    const formatAnswer = (answer) => {
      return marked(answer)
    }

    const handleRating = async (rating) => {
      userRating.value = rating
      
      // Submit feedback with rating
      if (results.value && results.value.memory_id && results.value.memory_id !== -1) {
        try {
          const response = await fetch('/api/feedback', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              memory_id: results.value.memory_id,
              rating: rating
            })
          })
          
          if (!response.ok) {
            throw new Error('Failed to save rating')
          }
        } catch (error) {
          console.error('Error saving rating:', error)
        }
      }
    }

    return {
      queryInput,
      results,
      loading,
      error,
      userRating,
      submitQuery,
      formatAnswer,
      handleRating
    }
  }
}
</script>

<style scoped>
.home-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
}

.query-section {
  text-align: center;
  margin-bottom: 40px;
}

.query-section h1 {
  font-size: 36px;
  color: #333;
  margin-bottom: 10px;
}

.subtitle {
  color: #666;
  font-size: 18px;
  margin-bottom: 30px;
}

.query-form {
  display: flex;
  gap: 10px;
  max-width: 700px;
  margin: 0 auto;
}

.query-input {
  flex: 1;
  padding: 16px 24px;
  font-size: 16px;
  border: 2px solid #e0e0e0;
  border-radius: 50px;
  transition: all 0.3s ease;
  background: white;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);
}

.query-input:focus {
  outline: none;
  border-color: #007bff;
  box-shadow: 0 4px 12px rgba(0, 123, 255, 0.15);
}

.query-input:disabled {
  background-color: #f5f5f5;
  cursor: not-allowed;
}

.submit-button {
  padding: 16px 32px;
  font-size: 16px;
  font-weight: 600;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 50px;
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
}

.submit-button:hover:not(:disabled) {
  background: #0056b3;
  box-shadow: 0 4px 12px rgba(0, 123, 255, 0.25);
  transform: translateY(-1px);
}

.submit-button:disabled {
  background: #6c757d;
  cursor: not-allowed;
  opacity: 0.7;
}

.results-section {
  margin-top: 40px;
}

.answer-card {
  background: white;
  padding: 30px;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  margin-bottom: 24px;
}

.answer-card h2 {
  color: #333;
  margin-bottom: 20px;
  font-size: 24px;
}

.answer-text {
  color: #555;
  line-height: 1.8;
  font-size: 16px;
}

.metadata {
  margin: 20px 0;
  text-align: center;
}

.memory-badge {
  display: inline-block;
  background: #e7f3ff;
  color: #007bff;
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 500;
}

.references-section {
  background: white;
  padding: 24px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  margin-bottom: 24px;
}

.references-section h3 {
  color: #333;
  margin-bottom: 16px;
}

.references-list {
  list-style: none;
  padding: 0;
}

.references-list li {
  padding: 8px 0;
  color: #666;
  font-size: 14px;
  border-bottom: 1px solid #f0f0f0;
}

.references-list li:last-child {
  border-bottom: none;
}

.chunks-section {
  margin-top: 24px;
}

.chunks-section h3 {
  color: #333;
  margin-bottom: 16px;
}

.chunk-card {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
  margin-bottom: 16px;
}

.chunk-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.chunk-source {
  font-weight: 600;
  color: #007bff;
  font-size: 14px;
}

.chunk-similarity {
  background: #28a745;
  color: white;
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 12px;
  font-weight: 500;
}

.chunk-text {
  color: #555;
  line-height: 1.6;
  font-size: 14px;
}

.entities-section {
  margin-top: 24px;
}

.entities-section h3 {
  color: #333;
  margin-bottom: 16px;
}

.entities-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.entity-card {
  background: white;
  padding: 16px;
  border-radius: 8px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
  text-align: center;
}

.entity-name {
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}

.entity-type {
  color: #666;
  font-size: 12px;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.entity-relevance {
  color: #28a745;
  font-size: 14px;
  font-weight: 500;
}

.error-message {
  background: #f8d7da;
  color: #721c24;
  padding: 16px;
  border-radius: 8px;
  margin: 20px 0;
  text-align: center;
}

/* Responsive design */
@media (max-width: 768px) {
  .query-form {
    flex-direction: column;
  }
  
  .submit-button {
    width: 100%;
  }
  
  .entities-grid {
    grid-template-columns: 1fr;
  }
}
</style>