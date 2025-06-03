<template>
  <div class="app-container">
    <header class="header">
      <div class="header-content">
        <h1>GraphRAG Query System</h1>
        <p class="description">Ask questions about your documents</p>
      </div>
    </header>

    <main class="main-content">
      <div v-if="!activeView || activeView === 'search'" class="search-container">
        <div class="view-buttons">
          <button v-if="favorites.length > 0" class="view-favorites-btn" @click="activeView = 'favorites'">
            <i class="fas fa-star"></i> View Favorites
          </button>
          
          <button v-if="threads.length > 0" class="view-threads-btn" @click="activeView = 'threads'">
            <i class="fas fa-comments"></i> View Conversations
          </button>
          
          <button class="toggle-progress-btn" @click="toggleIngestionProgress">
            <i class="fas" :class="store.state.showIngestionProgress ? 'fa-eye-slash' : 'fa-eye'"></i>
            {{ store.state.showIngestionProgress ? 'Hide' : 'Show' }} Document Progress
          </button>
        </div>

        <IngestionProgress v-if="store.state.showIngestionProgress" />

        <div class="query-form">
          <input 
            type="text" 
            v-model="query" 
            placeholder="Ask a question..." 
            @keyup.enter="submitQuery"
            :disabled="isLoading"
            class="query-input"
          />
          <button 
            @click="submitQuery" 
            class="submit-btn"
            :disabled="isLoading || !query.trim()"
          >
            <span v-if="isLoading">
              <i class="fas fa-spinner fa-spin"></i>
            </span>
            <span v-else>
              <i class="fas fa-search"></i>
            </span>
          </button>
        </div>

        <div v-if="error" class="error-message">
          <i class="fas fa-exclamation-circle"></i>
          <span>{{ error }}</span>
        </div>

        <div v-if="result" class="results-section">
          <div class="results-card">
            <div class="answer-container">
              <div class="answer" v-html="formattedAnswer"></div>
              
              <div class="references" v-if="result.references && result.references.length > 0">
                <h3>References</h3>
                <ol>
                  <li v-for="(reference, index) in result.references" :key="index">
                    {{ reference }}
                  </li>
                </ol>
              </div>
              
              <ResultActions 
                :memory-id="result.memory_id || null" 
                :from-memory="result.from_memory"
                :initial-favorite="isFavorited"
                :has-thread="hasThread"
                @favorite-changed="updateFavoriteStatus"
                @create-thread="showCreateThreadModal = true"
              />
            </div>
            
            <div class="tabs-container">
              <div class="tabs">
                <button 
                  v-for="tab in tabs" 
                  :key="tab.id"
                  :class="['tab-btn', { 'active': activeTab === tab.id }]"
                  @click="activeTab = tab.id"
                >
                  {{ tab.label }}
                </button>
              </div>
              
              <div class="tab-content">
                <div v-if="activeTab === 'chunks'" class="chunks-tab">
                  <div 
                    v-for="(chunk, index) in result.chunks" 
                    :key="index"
                    class="chunk"
                  >
                    <div class="chunk-header">
                      <div class="chunk-source">{{ chunk.source }}</div>
                      <div class="chunk-similarity">Similarity: {{ (chunk.similarity * 100).toFixed(1) }}%</div>
                    </div>
                    <div class="chunk-content">{{ chunk.text }}</div>
                  </div>
                </div>
                
                <div v-if="activeTab === 'entities'" class="entities-tab">
                  <div v-if="result.entities && result.entities.length > 0" class="entities-list">
                    <div 
                      v-for="(entity, index) in result.entities" 
                      :key="index"
                      class="entity"
                    >
                      <div class="entity-name">{{ entity.entity }}</div>
                      <div class="entity-type">Type: {{ entity.entity_type }}</div>
                      <div class="entity-relevance">Relevance: {{ (entity.relevance * 100).toFixed(1) }}%</div>
                    </div>
                  </div>
                  <div v-else class="no-entities">No entities found</div>
                </div>
                
                <div v-if="activeTab === 'communities'" class="communities-tab">
                  <div v-if="result.communities && result.communities.length > 0" class="communities-list">
                    <div 
                      v-for="(community, index) in result.communities" 
                      :key="index"
                      class="community"
                    >
                      <div class="community-id">Community {{ community.community_id }}</div>
                      <div class="community-summary">{{ community.summary }}</div>
                      <div class="community-entities">
                        <div class="community-entities-header">Related Entities:</div>
                        <div class="entities-tags">
                          <span 
                            v-for="(entity, entityIndex) in community.entities" 
                            :key="entityIndex"
                            class="entity-tag"
                          >
                            {{ entity }}
                          </span>
                        </div>
                      </div>
                      <div class="community-relevance">Relevance: {{ (community.relevance * 100).toFixed(1) }}%</div>
                    </div>
                  </div>
                  <div v-else class="no-communities">No community insights found</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <FavoritesList 
        v-if="activeView === 'favorites'"
        @select-favorite="loadSavedQuery"
        @thread-created="openThread"
        @view-thread="openThread"
      />
      
      <ThreadsList 
        v-if="activeView === 'threads'"
        @select-thread="openThread"
      />
    </main>

    <footer class="footer">
      <div class="footer-content">
        <p>GraphRAG Query System &copy; {{ new Date().getFullYear() }}</p>
      </div>
    </footer>
    
    <!-- Modals -->
    <CreateThreadModal 
      :visible="showCreateThreadModal && result?.memory_id != null"
      :memory-id="result?.memory_id || 0"
      :query-text="query"
      @close="showCreateThreadModal = false"
      @created="(id, title) => openThread(id, title)"
      @existing="(id, title) => openThread(id, title)"
    />
    
    <ThreadDialog 
      :visible="!!activeThread"
      :thread-id="activeThread ? activeThread.id : null"
      :thread-title="activeThread ? activeThread.title : 'Conversation'"
      @close="closeThread"
    />
  </div>
</template>

<script>
import { marked } from 'marked';
import { onMounted, ref, computed, watch } from 'vue';
import { useStore } from 'vuex';
import IngestionProgress from './components/IngestionProgress.vue';
import ResultActions from './components/ResultActions.vue';
import ThreadDialog from './components/ThreadDialog.vue';
import CreateThreadModal from './components/CreateThreadModal.vue';
import ThreadsList from './components/ThreadsList.vue';
import FavoritesList from './components/FavoritesList.vue';

export default {
  name: 'App',
  components: {
    IngestionProgress,
    ResultActions,
    ThreadDialog,
    CreateThreadModal,
    ThreadsList,
    FavoritesList
  },
  setup() {
    const store = useStore();
    const query = ref('');
    const result = ref(null);
    const error = ref('');
    const isLoading = ref(false);
    const activeTab = ref('chunks');
    const activeView = ref('search');
    const showCreateThreadModal = ref(false);
    const activeThread = ref(null);
    const favorites = ref([]);
    const threads = ref([]);
    const isFavorited = ref(false);
    const hasThread = ref(false);
    
    // Make sure store state is accessible
    console.log("Store state:", store.state);

    const tabs = [
      { id: 'chunks', label: 'Relevant Chunks' },
      { id: 'entities', label: 'Entities' },
      { id: 'communities', label: 'Community Insights' }
    ];
    
    const formattedAnswer = computed(() => {
      if (!result.value || !result.value.answer) return '';
      
      // Replace citation markers with superscript
      const textWithCitations = result.value.answer.replace(/\[(\d+)\]/g, '<sup class="citation">[$1]</sup>');
      
      // Use marked to render markdown
      return marked(textWithCitations);
    });

    const submitQuery = async () => {
      if (!query.value.trim() || isLoading.value) return;
      
      isLoading.value = true;
      error.value = '';
      
      try {
        const response = await fetch('/api/query', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            query: query.value,
            max_results: 5
          })
        });
        
        if (response.ok) {
          result.value = await response.json();
          activeTab.value = 'chunks';
          checkFavoriteStatus();
          checkThreadStatus();
        } else {
          error.value = 'Failed to process query';
        }
      } catch (err) {
        error.value = 'Error: ' + err.message;
      } finally {
        isLoading.value = false;
      }
    };
    
    const loadSavedQuery = async (memoryId) => {
      try {
        const response = await fetch(`/api/memory/entry/${memoryId}`);
        if (response.ok) {
          const data = await response.json();
          query.value = data.query;
          result.value = {
            query: data.query,
            answer: data.answer,
            chunks: await Promise.all(data.chunk_ids.map(fetchChunk)),
            entities: data.entity_count > 0 ? data.entities : [],
            communities: data.community_count > 0 ? data.communities : [],
            references: data.references,
            from_memory: true,
            memory_id: memoryId
          };
          
          // Update status
          isFavorited.value = data.is_favorite;
          hasThread.value = data.has_thread;
          
          // Switch view
          activeView.value = 'search';
          activeTab.value = 'chunks';
        }
      } catch (error) {
        console.error('Error loading saved query:', error);
      }
    };
    
    const fetchChunk = async (chunkId) => {
      // This would normally fetch from API, but for simplicity we'll return a placeholder
      return {
        id: chunkId,
        text: "Content loaded from memory",
        source: "Document reference",
        similarity: 1.0
      };
    };
    
    const updateFavoriteStatus = (status) => {
      isFavorited.value = status;
      loadFavorites();
    };
    
    const checkFavoriteStatus = async () => {
      if (!result.value || !result.value.memory_id) {
        isFavorited.value = false;
        return;
      }
      
      try {
        const response = await fetch(`/api/memory/entry/${result.value.memory_id}`);
        if (response.ok) {
          const data = await response.json();
          isFavorited.value = data.is_favorite || false;
        }
      } catch (error) {
        console.error('Error checking favorite status:', error);
        isFavorited.value = false;
      }
    };
    
    const checkThreadStatus = async () => {
      if (!result.value || !result.value.memory_id) {
        hasThread.value = false;
        return;
      }
      
      try {
        const response = await fetch(`/api/memory/entry/${result.value.memory_id}`);
        if (response.ok) {
          const data = await response.json();
          hasThread.value = data.has_thread || false;
        }
      } catch (error) {
        console.error('Error checking thread status:', error);
        hasThread.value = false;
      }
    };
    
    const loadFavorites = async () => {
      try {
        const response = await fetch('/api/favorites');
        if (response.ok) {
          favorites.value = await response.json();
        }
      } catch (error) {
        console.error('Error loading favorites:', error);
      }
    };
    
    const loadThreads = async () => {
      try {
        const response = await fetch('/api/threads');
        if (response.ok) {
          threads.value = await response.json();
        }
      } catch (error) {
        console.error('Error loading threads:', error);
      }
    };
    
    const openThread = async (threadId, threadTitle = 'Conversation') => {
      console.log('Opening thread:', threadId, threadTitle);
      activeThread.value = {
        id: threadId,
        title: threadTitle
      };
      
      // Log active thread value after setting it
      console.log('activeThread value set to:', activeThread.value);
      
      // Refresh threads list
      loadThreads();
    };
    
    const closeThread = () => {
      console.log('Closing thread dialog');
      activeThread.value = null;
      
      // Reset view to thread list if we're in a thread
      if (activeView.value === 'threads') {
        // Just reload the threads to refresh the list
        loadThreads();
      }
    };

    onMounted(() => {
      loadFavorites();
      loadThreads();
    });
    
    watch(activeView, () => {
      if (activeView.value === 'favorites') {
        loadFavorites();
      } else if (activeView.value === 'threads') {
        loadThreads();
      }
    });

    // Function to toggle ingestion progress visibility
    const toggleIngestionProgress = () => {
      store.commit('setShowIngestionProgress', !store.state.showIngestionProgress);
    };
    
    return {
      store,
      query,
      result,
      error,
      isLoading,
      activeTab,
      activeView,
      formattedAnswer,
      submitQuery,
      tabs,
      showCreateThreadModal,
      activeThread,
      favorites,
      threads,
      isFavorited,
      hasThread,
      updateFavoriteStatus,
      loadSavedQuery,
      openThread,
      closeThread,
      toggleIngestionProgress
    };
  }
};
</script>

<style>
.app-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
}

.header {
  background-color: var(--primary-color);
  color: white;
  padding: 2rem 0;
  text-align: center;
}

.header-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 1.5rem;
}

.header h1 {
  margin: 0;
  font-size: 2.5rem;
  font-weight: 700;
}

.description {
  margin-top: 0.5rem;
  font-size: 1.1rem;
  opacity: 0.9;
}

.main-content {
  flex-grow: 1;
  padding: 2rem 0;
  background-color: var(--bg-color);
}

.search-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 2rem;
  position: relative;
}

.view-buttons {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 1rem;
  gap: 0.75rem;
}

.view-favorites-btn,
.view-threads-btn,
.toggle-progress-btn {
  background-color: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 0.5rem 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.view-favorites-btn {
  color: #ff9800;
}

.view-threads-btn {
  color: #0066cc;
}

.toggle-progress-btn {
  color: #6c757d;
}

.view-favorites-btn:hover,
.view-threads-btn:hover,
.toggle-progress-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.query-form {
  display: flex;
  gap: 0.5rem;
  width: 100%;
  max-width: 800px;
  margin: 0 auto;
}

.query-input {
  flex-grow: 1;
  padding: 1rem 1.5rem;
  border-radius: 8px;
  border: 1px solid #ddd;
  font-size: 1rem;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.query-input:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(0, 102, 204, 0.2);
}

.submit-btn {
  background-color: var(--primary-color);
  color: white;
  border: none;
  border-radius: 8px;
  padding: 0 1.5rem;
  font-size: 1rem;
  cursor: pointer;
  transition: background-color 0.2s;
}

.submit-btn:hover {
  background-color: var(--primary-dark-color);
}

.submit-btn:disabled {
  background-color: #a0c4e4;
  cursor: not-allowed;
}

.error-message {
  color: var(--error-color);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem;
  background-color: #fff5f5;
  border-radius: 8px;
  border-left: 4px solid var(--error-color);
}

.results-section {
  margin-top: 1rem;
}

.results-card {
  background-color: white;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.answer-container {
  padding: 2rem;
  border-bottom: 1px solid #efefef;
}

.answer {
  line-height: 1.6;
  font-size: 1.1rem;
  color: #333;
}

.answer :deep(p) {
  margin-bottom: 1rem;
}

.answer :deep(a) {
  color: var(--primary-color);
  text-decoration: none;
}

.answer :deep(a:hover) {
  text-decoration: underline;
}

.answer :deep(.citation) {
  color: var(--primary-color);
  font-weight: 600;
  font-size: 0.7em;
  padding: 0 0.15em;
}

.references {
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px solid #eaeaea;
}

.references h3 {
  font-size: 1.1rem;
  margin-top: 0;
  margin-bottom: 0.75rem;
  color: #444;
}

.references ol {
  padding-left: 1.5rem;
  margin: 0;
}

.references li {
  margin-bottom: 0.5rem;
  color: #555;
  font-size: 0.95rem;
}

.tabs-container {
  display: flex;
  flex-direction: column;
}

.tabs {
  display: flex;
  background-color: #f8f9fa;
  padding: 0 1rem;
  border-bottom: 1px solid #eaeaea;
}

.tab-btn {
  padding: 1rem 1.5rem;
  background: none;
  border: none;
  font-weight: 500;
  color: #666;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
}

.tab-btn.active {
  color: var(--primary-color);
}

.tab-btn.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background-color: var(--primary-color);
}

.tab-btn:hover {
  color: var(--primary-dark-color);
}

.tab-content {
  padding: 1.5rem;
  max-height: 400px;
  overflow-y: auto;
}

.chunks-tab, .entities-tab, .communities-tab {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.chunk, .entity, .community {
  padding: 1.5rem;
  border-radius: 8px;
  border: 1px solid #eaeaea;
  background-color: #fcfcfc;
}

.chunk-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.chunk-source {
  font-weight: 600;
  color: var(--primary-color);
}

.chunk-similarity {
  font-size: 0.9rem;
  color: #666;
}

.chunk-content {
  font-size: 0.95rem;
  line-height: 1.5;
  color: #333;
  white-space: pre-wrap;
}

.entity-name {
  font-weight: 600;
  font-size: 1.1rem;
  margin-bottom: 0.5rem;
}

.entity-type {
  font-size: 0.9rem;
  color: #666;
  margin-bottom: 0.5rem;
}

.entity-relevance {
  font-size: 0.9rem;
  color: #666;
}

.community-id {
  font-weight: 600;
  font-size: 1.1rem;
  margin-bottom: 0.75rem;
  color: var(--primary-color);
}

.community-summary {
  font-size: 0.95rem;
  line-height: 1.5;
  margin-bottom: 1rem;
}

.community-entities {
  margin-bottom: 0.75rem;
}

.community-entities-header {
  font-weight: 600;
  font-size: 0.9rem;
  margin-bottom: 0.5rem;
  color: #555;
}

.entities-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.entity-tag {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  background-color: #e0f2ff;
  color: #0066cc;
  border-radius: 16px;
  font-size: 0.85rem;
}

.community-relevance {
  font-size: 0.9rem;
  color: #666;
}

.no-entities, .no-communities {
  padding: 2rem;
  text-align: center;
  color: #666;
  font-style: italic;
}

.footer {
  background-color: #f8f9fa;
  padding: 1.5rem 0;
  border-top: 1px solid #eaeaea;
}

.footer-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 1.5rem;
  text-align: center;
  color: #666;
  font-size: 0.9rem;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .header h1 {
    font-size: 2rem;
  }
  
  .description {
    font-size: 1rem;
  }
  
  .main-content {
    padding: 1.5rem 0;
  }
  
  .search-container {
    padding: 0 1rem;
  }
  
  .query-form {
    flex-direction: column;
  }
  
  .submit-btn {
    width: 100%;
    padding: 1rem;
  }
  
  .tabs {
    overflow-x: auto;
  }
  
  .tab-btn {
    padding: 1rem;
    white-space: nowrap;
  }
}
</style>