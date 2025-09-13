<template>
  <div class="home-view">
    <div class="query-section">
      <h1>ILRI Animal Health Answers</h1>
      <p class="subtitle">Ask questions about animal health, diseases, pathogens, or veterinary care. This is a pilot project using AI to unearth answers to animal health questions from both ILRI's own body of published work as well as related materials. For more information please contact the Data and Research Methods Unit.</p>
      
      <form @submit.prevent="submitQuery" class="query-form">
        <input 
          v-model="queryInput" 
          type="text" 
          placeholder="Ask a question about animal health..."
          class="query-input"
          :disabled="loading"
        />
        <button type="submit" :disabled="loading || !queryInput.trim()" class="submit-button">
          {{ loading ? 'Searching...' : 'Ask' }}
        </button>
      </form>
    </div>

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

      <div v-if="results.chunks && results.chunks.length > 0" class="chunks-section">
        <h3>Relevant Document Chunks</h3>
        <div v-for="(chunk, index) in results.chunks" :key="chunk.id" class="chunk-card" :id="`chunk-${index + 1}`">
          <div class="chunk-header">
            <div class="chunk-title">
              <span class="chunk-number">[chunk {{ index + 1 }}]</span>
              <span 
                v-if="getChunkReference(index)" 
                @click="openReference(getChunkReference(index))" 
                class="chunk-reference-link"
                v-html="formatChunkReference(getChunkReference(index))"
              ></span>
              <span 
                v-else-if="chunk.doi" 
                @click="openDoi(chunk.doi)" 
                class="chunk-doi-link"
              >
                {{ chunk.doi }}
              </span>
              <span v-else class="chunk-no-reference">Document excerpt</span>
            </div>
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
      // Make [chunk X] citations clickable
      let formattedAnswer = marked(answer)
      formattedAnswer = formattedAnswer.replace(/\[chunk(\d+)\]/g, '<a href="#chunk-$1" class="chunk-citation-link" onclick="document.getElementById(\'chunk-$1\').scrollIntoView({behavior: \'smooth\'}); return false;">[chunk$1]</a>')
      return formattedAnswer
    }
    
    const isValidUrl = (ref) => {
      // Check if reference contains a URL (DOI links, https links)
      const urlPattern = /(https?:\/\/[^\s]+|doi:10\.\d+\/[^\s]+)/i
      return urlPattern.test(ref)
    }
    
    const openReference = (ref) => {
      // Extract URL from reference text
      const urlMatch = ref.match(/(https?:\/\/[^\s]+)/i)
      const doiMatch = ref.match(/doi:(10\.\d+\/[^\s]+)/i)
      
      let url = null
      if (urlMatch) {
        url = urlMatch[1]
      } else if (doiMatch) {
        url = `https://doi.org/${doiMatch[1]}`
      }
      
      if (url) {
        window.open(url, '_blank')
      }
    }
    
    const getChunkReference = (index) => {
      if (results.value && results.value.references && results.value.references[index]) {
        return results.value.references[index]
      }
      return null
    }
    
    const openDoi = (doi) => {
      const url = doi.startsWith('http') ? doi : `https://doi.org/${doi}`
      window.open(url, '_blank')
    }
    
    const formatChunkReference = (reference) => {
      if (!reference) return ''
      
      // Check if it's a URL (DOI link)
      if (reference.startsWith('http')) {
        return `<span class="reference-link">Link to paper</span>`
      }
      
      // Parse academic citation: Author(s) (year). Title. Journal/Publication
      // Title is between (year). and the next period
      const titleMatch = reference.match(/(\(\d{4}\)\.)\s*([^.]+\.)\s*(.+)/)
      
      if (titleMatch) {
        const beforeTitle = reference.substring(0, titleMatch.index + titleMatch[1].length + 1) // include space after (year).
        const title = titleMatch[2].replace(/\.$/, '') // remove trailing period from title
        const afterTitle = titleMatch[3]
        
        return `${beforeTitle}<em>${title}</em>. ${afterTitle}`
      }
      
      // If no pattern matches, return as-is
      return reference
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
      isValidUrl,
      openReference,
      handleRating,
      getChunkReference,
      formatChunkReference,
      openDoi
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

.chunk-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.chunk-number {
  font-weight: 600;
  color: #007bff;
  font-size: 14px;
}

.chunk-reference-link {
  cursor: pointer;
  color: #007bff;
  text-decoration: none;
  font-size: 14px;
  line-height: 1.4;
  transition: color 0.2s;
}

.chunk-reference-link:hover {
  color: #0056b3;
  text-decoration: underline;
}

.chunk-no-reference {
  color: #666;
  font-size: 14px;
  font-style: italic;
}

.chunk-doi-link {
  cursor: pointer;
  color: #28a745;
  text-decoration: none;
  font-size: 14px;
  font-family: monospace;
  transition: color 0.2s;
}

.chunk-doi-link:hover {
  color: #1e7e34;
  text-decoration: underline;
}

.reference-link {
  color: #007bff;
  font-weight: 500;
}

.chunk-citation-link {
  color: #007bff;
  text-decoration: none;
  font-weight: 600;
  padding: 2px 4px;
  border-radius: 4px;
  transition: all 0.2s;
}

.chunk-citation-link:hover {
  background-color: #e7f3ff;
  text-decoration: none;
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

.chunk-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
  gap: 16px;
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