<template>
  <div class="threads-list">
    <div class="threads-header">
      <h2>Your Conversations</h2>
      <div class="view-options">
        <button 
          class="refresh-btn" 
          @click="loadThreads"
          :disabled="isLoading"
          title="Refresh threads"
        >
          <i :class="isLoading ? 'fas fa-sync fa-spin' : 'fas fa-sync'"></i>
        </button>
      </div>
    </div>
    
    <div class="search-bar">
      <i class="fas fa-search search-icon"></i>
      <input 
        type="text" 
        v-model="searchQuery" 
        placeholder="Search conversations..." 
        class="search-input"
      />
    </div>
    
    <div class="threads-container" v-if="!isLoading">
      <div v-if="filteredThreads.length === 0" class="no-threads">
        <i class="fas fa-comment-slash no-threads-icon"></i>
        <p>No conversations found</p>
        <p class="no-threads-hint" v-if="searchQuery">Try a different search term</p>
        <p class="no-threads-hint" v-else>Conversations you start will appear here</p>
      </div>
      
      <div v-else class="threads-grid">
        <div 
          v-for="thread in filteredThreads" 
          :key="thread.id"
          class="thread-card"
          @click="selectThread(thread)"
        >
          <div class="thread-card-content">
            <h3 class="thread-title">{{ thread.thread_title || 'Conversation' }}</h3>
            
            <div class="thread-query">
              <div class="query-label">Question:</div>
              <div class="query-text">{{ thread.query_text }}</div>
            </div>
            
            <div class="thread-details">
              <div class="message-count">
                <i class="fas fa-comment-dots"></i>
                {{ thread.message_count }} messages
              </div>
              
              <div class="created-date">
                <i class="fas fa-calendar-alt"></i>
                {{ formatDate(thread.created_at) }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <div class="threads-loading" v-else>
      <div class="loading-spinner">
        <i class="fas fa-spinner fa-spin"></i>
      </div>
      <p>Loading conversations...</p>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ThreadsList',
  data() {
    return {
      threads: [],
      isLoading: true,
      searchQuery: ''
    }
  },
  computed: {
    filteredThreads() {
      if (!this.searchQuery) return this.threads;
      
      const query = this.searchQuery.toLowerCase();
      return this.threads.filter(thread => {
        return (
          (thread.thread_title && thread.thread_title.toLowerCase().includes(query)) ||
          thread.query_text.toLowerCase().includes(query)
        );
      });
    }
  },
  mounted() {
    this.loadThreads();
  },
  methods: {
    async loadThreads() {
      this.isLoading = true;
      
      try {
        const response = await fetch('/api/threads');
        if (response.ok) {
          const data = await response.json();
          this.threads = data;
        } else {
          console.error('Failed to load threads');
        }
      } catch (error) {
        console.error('Error loading threads:', error);
      } finally {
        this.isLoading = false;
      }
    },
    
    selectThread(thread) {
      console.log('Thread selected:', thread);
      // Emit event with ID and title
      this.$emit('select-thread', thread.id, thread.thread_title || 'Conversation');
    },
    
    formatDate(dateString) {
      if (!dateString) return 'Unknown date';
      
      const date = new Date(dateString);
      
      // Check if date is valid
      if (isNaN(date.getTime())) return 'Invalid date';
      
      // If today, show time
      const today = new Date();
      if (date.getDate() === today.getDate() && 
          date.getMonth() === today.getMonth() && 
          date.getFullYear() === today.getFullYear()) {
        return `Today at ${date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`;
      }
      
      // If yesterday, show "Yesterday"
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      if (date.getDate() === yesterday.getDate() && 
          date.getMonth() === yesterday.getMonth() && 
          date.getFullYear() === yesterday.getFullYear()) {
        return 'Yesterday';
      }
      
      // If within last 7 days, show day name
      const oneWeekAgo = new Date();
      oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
      if (date > oneWeekAgo) {
        return date.toLocaleDateString([], {weekday: 'long'});
      }
      
      // Otherwise show date
      return date.toLocaleDateString([], {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    }
  }
}
</script>

<style scoped>
.threads-list {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding: 1.5rem;
}

.threads-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.threads-header h2 {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: #333;
}

.refresh-btn {
  background-color: #f5f5f5;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
}

.refresh-btn:hover {
  background-color: #e8e8e8;
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.search-bar {
  position: relative;
  margin-bottom: 2rem;
}

.search-icon {
  position: absolute;
  left: 1rem;
  top: 50%;
  transform: translateY(-50%);
  color: #666;
}

.search-input {
  width: 100%;
  padding: 1rem 1rem 1rem 3rem;
  border-radius: 8px;
  border: 1px solid #ddd;
  font-size: 1rem;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.search-input:focus {
  outline: none;
  border-color: #0066cc;
  box-shadow: 0 0 0 2px rgba(0, 102, 204, 0.2);
}

.threads-container {
  flex-grow: 1;
}

.no-threads {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 0;
  text-align: center;
  color: #666;
}

.no-threads-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
  color: #aaa;
}

.no-threads p {
  margin: 0.5rem 0;
  font-size: 1.1rem;
}

.no-threads-hint {
  color: #999;
  font-size: 0.9rem !important;
}

.threads-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 1.5rem;
}

.thread-card {
  background-color: white;
  border-radius: 10px;
  border: 1px solid #eaeaea;
  overflow: hidden;
  transition: box-shadow 0.2s, transform 0.2s;
  cursor: pointer;
  display: flex;
  flex-direction: column;
}

.thread-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 12px rgba(0, 0, 0, 0.1);
}

.thread-card-content {
  padding: 1.5rem;
  flex-grow: 1;
  display: flex;
  flex-direction: column;
}

.thread-title {
  margin: 0 0 1rem 0;
  font-size: 1.2rem;
  color: #0066cc;
  word-break: break-word;
}

.thread-query {
  margin-bottom: 1.5rem;
  flex-grow: 1;
}

.query-label {
  font-weight: 600;
  font-size: 0.85rem;
  margin-bottom: 0.5rem;
  color: #555;
}

.query-text {
  font-size: 0.95rem;
  color: #333;
  line-height: 1.5;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  word-break: break-word;
}

.thread-details {
  display: flex;
  justify-content: space-between;
  color: #777;
  font-size: 0.8rem;
  margin-top: auto;
  padding-top: 1rem;
  border-top: 1px solid #f0f0f0;
}

.message-count, .created-date {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.threads-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 0;
}

.loading-spinner {
  font-size: 2rem;
  color: #0066cc;
  margin-bottom: 1rem;
}

.threads-loading p {
  color: #666;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .threads-grid {
    grid-template-columns: 1fr;
  }
  
  .threads-list {
    padding: 1rem;
  }
}
</style>