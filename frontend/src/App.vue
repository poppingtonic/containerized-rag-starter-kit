<template>
  <div class="app">
    <header class="app-header">
      <div class="container">
        <h1 class="app-title">GraphRAG Query Interface</h1>
        <p>Ask questions about your documents with enhanced knowledge graph retrieval</p>
      </div>
    </header>
    
    <main class="container">
      <IngestionProgress />
      
      <div class="card query-form">
        <form @submit.prevent="submitQuery">
          <div class="form-group">
            <label for="query-input">Enter your question:</label>
            <input
              id="query-input"
              v-model="queryInput"
              type="text"
              class="form-control"
              placeholder="e.g., What are the key benefits of GraphRAG?">
          </div>
          <div class="form-actions">
            <button type="submit" class="btn btn-primary" :disabled="loading">
              <span v-if="loading" class="spinner"></span>
              <span v-else>Search</span>
            </button>
          </div>
        </form>
      </div>
      
      <div v-if="error" class="error-message card">
        <p>{{ error }}</p>
      </div>
      
      <div v-if="results" class="results">
        <div class="card results-card">
          <h2>Answer</h2>
          <div class="answer" v-html="formattedAnswer"></div>
          
          <div v-if="results.references && results.references.length" class="references">
            <h4>References:</h4>
            <ol>
              <li v-for="(reference, index) in results.references" :key="index">
                {{ reference }}
              </li>
            </ol>
          </div>
        </div>
        
        <div class="card">
          <div class="nav-tabs">
            <div :class="['nav-tab', { active: activeTab === 'chunks' }]" 
                 @click="activeTab = 'chunks'">
              Relevant Chunks
            </div>
            <div :class="['nav-tab', { active: activeTab === 'entities' }]" 
                 @click="activeTab = 'entities'">
              Entities
            </div>
            <div :class="['nav-tab', { active: activeTab === 'communities' }]" 
                 @click="activeTab = 'communities'">
              Community Insights
            </div>
          </div>
          
          <div class="tab-content">
            <!-- Chunks Tab -->
            <div v-if="activeTab === 'chunks'" class="chunks-tab">
              <div v-for="(chunk, index) in results.chunks" :key="index" 
                   class="chunk-item">
                <h4>Document Chunk {{ index + 1 }} 
                  <small>(Similarity: {{ (chunk.similarity * 100).toFixed(1) }}%)</small>
                </h4>
                <p class="chunk-text">{{ chunk.text }}</p>
                <p class="chunk-source">Source: {{ chunk.source }}</p>
              </div>
            </div>
            
            <!-- Entities Tab -->
            <div v-if="activeTab === 'entities'" class="entities-tab">
              <div v-if="results.entities && results.entities.length">
                <div v-for="(entity, index) in results.entities" :key="index" 
                     class="entity-item">
                  <h4>{{ entity.entity }} 
                    <small>({{ entity.entity_type }})</small>
                  </h4>
                  <p class="entity-relevance">Relevance: {{ (entity.relevance * 100).toFixed(1) }}%</p>
                </div>
              </div>
              <div v-else>
                <p>No entity information available.</p>
              </div>
            </div>
            
            <!-- Communities Tab -->
            <div v-if="activeTab === 'communities'" class="communities-tab">
              <div v-if="results.communities && results.communities.length">
                <div v-for="(community, index) in results.communities" :key="index" 
                     class="community-item">
                  <h4>Community {{ community.community_id }}</h4>
                  <p class="community-summary">{{ community.summary }}</p>
                  <p class="community-entities"><strong>Key entities:</strong> 
                    {{ community.entities.join(', ') }}
                  </p>
                  <p class="community-relevance">Relevance: {{ (community.relevance * 100).toFixed(1) }}%</p>
                </div>
              </div>
              <div v-else>
                <p>No community insights available.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
    
    <footer class="app-footer">
      <div class="container">
        <p>GraphRAG Query System &copy; {{ new Date().getFullYear() }}</p>
      </div>
    </footer>
  </div>
</template>

<script>
import { marked } from 'marked';
import { useStore } from 'vuex';
import { computed, ref } from 'vue';
import IngestionProgress from './components/IngestionProgress.vue';

export default {
  name: 'App',
  components: {
    IngestionProgress
  },
  setup() {
    const store = useStore();
    const queryInput = ref('');
    const activeTab = ref('chunks');
    
    // Computed properties from store state
    const results = computed(() => store.state.results);
    const loading = computed(() => store.state.loading);
    const error = computed(() => store.state.error);
    
    // Format answer with markdown
    const formattedAnswer = computed(() => {
      if (!results.value || !results.value.answer) return '';
      
      // Process citations in the format [1], [2], etc.
      let processedAnswer = results.value.answer.replace(
        /\[(\d+)\]/g, 
        (match, p1) => `<span class="citation">${match}</span>`
      );
      
      return marked.parse(processedAnswer);
    });
    
    // Submit query
    const submitQuery = () => {
      if (!queryInput.value.trim()) return;
      store.dispatch('submitQuery', queryInput.value);
    };
    
    return {
      queryInput,
      activeTab,
      results,
      loading,
      error,
      formattedAnswer,
      submitQuery
    };
  }
};
</script>

<style>
.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
}

.form-actions {
  margin-top: 1rem;
}

.chunk-item, .entity-item, .community-item {
  padding: 1rem;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  margin-bottom: 1rem;
}

.chunk-text {
  margin: 0.5rem 0;
  white-space: pre-line;
}

.chunk-source, .entity-relevance, .community-relevance {
  font-size: 0.85rem;
  color: var(--secondary-color);
}

.app-footer {
  margin-top: auto;
  padding: 1.5rem 0;
  background-color: var(--light-color);
  border-top: 1px solid var(--border-color);
  text-align: center;
  color: var(--secondary-color);
}

.error-message {
  background-color: #f8d7da;
  color: #721c24;
  border-color: #f5c6cb;
}

.citation {
  color: var(--primary-color);
  font-weight: 500;
}
</style>