<template>
  <div class="favorites-list">
    <div class="favorites-header">
      <h2>Your Favorites</h2>
      <div class="view-options">
        <button 
          class="refresh-btn" 
          @click="loadFavorites"
          :disabled="isLoading"
          title="Refresh favorites"
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
        placeholder="Search favorites..." 
        class="search-input"
      />
    </div>
    
    <div class="favorites-container" v-if="!isLoading">
      <div v-if="filteredFavorites.length === 0" class="no-favorites">
        <i class="fas fa-star no-favorites-icon"></i>
        <p>No favorites found</p>
        <p class="no-favorites-hint" v-if="searchQuery">Try a different search term</p>
        <p class="no-favorites-hint" v-else>Questions you star will appear here</p>
      </div>
      
      <div v-else class="favorites-grid">
        <div 
          v-for="favorite in filteredFavorites" 
          :key="favorite.id"
          class="favorite-card"
          @click="$emit('select-favorite', favorite.query_cache_id)"
        >
          <div class="favorite-card-content">
            <div class="favorite-query">{{ favorite.query_text }}</div>
            
            <div class="favorite-answer" v-html="formatAnswer(favorite.answer_text)"></div>
            
            <div class="favorite-feedback" v-if="favorite.feedback_text">
              <div class="feedback-label">Your feedback:</div>
              <div class="feedback-text">{{ favorite.feedback_text }}</div>
            </div>
            
            <div class="favorite-details">
              <div class="rating" v-if="favorite.rating">
                <div class="stars">
                  <i 
                    v-for="i in 5" 
                    :key="i"
                    :class="[
                      'fas', 
                      i <= favorite.rating ? 'fa-star' : 'fa-star-o',
                      i <= favorite.rating ? 'filled' : ''
                    ]"
                  ></i>
                </div>
              </div>
              
              <div class="saved-date">
                <i class="fas fa-calendar-alt"></i>
                {{ formatDate(favorite.created_at) }}
              </div>
            </div>
            
            <div class="favorite-actions">
              <button 
                class="thread-btn" 
                v-if="!favorite.has_thread"
                @click.stop="createThread(favorite)"
                title="Create conversation thread"
              >
                <i class="fas fa-comments"></i>
                Create Thread
              </button>
              
              <button 
                class="thread-btn view" 
                v-else
                @click.stop="$emit('view-thread', favorite.thread_id)"
                title="View conversation thread"
              >
                <i class="fas fa-comments"></i>
                View Thread
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <div class="favorites-loading" v-else>
      <div class="loading-spinner">
        <i class="fas fa-spinner fa-spin"></i>
      </div>
      <p>Loading favorites...</p>
    </div>
    
    <!-- Thread creation dialog -->
    <div class="create-thread-dialog" v-if="showThreadDialog">
      <div class="dialog-overlay" @click="showThreadDialog = false"></div>
      <div class="dialog-content">
        <div class="dialog-header">
          <h3>Create Conversation Thread</h3>
          <button class="close-btn" @click="showThreadDialog = false">
            <i class="fas fa-times"></i>
          </button>
        </div>
        
        <div class="dialog-body">
          <div class="form-group">
            <label for="thread-title">Thread Title</label>
            <input 
              type="text" 
              id="thread-title" 
              v-model="threadTitle"
              placeholder="Enter a title for this conversation"
              class="thread-title-input"
            />
          </div>
        </div>
        
        <div class="dialog-footer">
          <button 
            class="cancel-btn" 
            @click="showThreadDialog = false"
          >
            Cancel
          </button>
          <button 
            class="create-btn" 
            @click="confirmCreateThread"
            :disabled="!threadTitle.trim() || isCreatingThread"
          >
            {{ isCreatingThread ? 'Creating...' : 'Create Thread' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { marked } from 'marked';

export default {
  name: 'FavoritesList',
  data() {
    return {
      favorites: [],
      isLoading: true,
      searchQuery: '',
      showThreadDialog: false,
      selectedFavorite: null,
      threadTitle: '',
      isCreatingThread: false
    }
  },
  computed: {
    filteredFavorites() {
      if (!this.searchQuery) return this.favorites;
      
      const query = this.searchQuery.toLowerCase();
      return this.favorites.filter(favorite => {
        return (
          favorite.query_text.toLowerCase().includes(query) ||
          favorite.answer_text.toLowerCase().includes(query) ||
          (favorite.feedback_text && favorite.feedback_text.toLowerCase().includes(query))
        );
      });
    }
  },
  mounted() {
    this.loadFavorites();
  },
  methods: {
    async loadFavorites() {
      this.isLoading = true;
      
      try {
        const response = await fetch('/api/favorites');
        if (response.ok) {
          const data = await response.json();
          const favoritesData = data.favorites || [];
          
          // Add has_thread and thread_id properties
          this.favorites = await this.enrichFavoritesWithThreadInfo(favoritesData);
        } else {
          console.error('Failed to load favorites');
        }
      } catch (error) {
        console.error('Error loading favorites:', error);
      } finally {
        this.isLoading = false;
      }
    },
    
    async enrichFavoritesWithThreadInfo(favorites) {
      try {
        // Get all threads
        const threadsResponse = await fetch('/api/threads');
        if (!threadsResponse.ok) {
          return favorites;
        }
        
        const threadsData = await threadsResponse.json();
        const threads = threadsData.threads || [];
        
        // Create a map of query_cache_id to thread
        const threadMap = {};
        threads.forEach(thread => {
          threadMap[thread.query_cache_id] = thread;
        });
        
        // Enrich favorites with thread info
        return favorites.map(favorite => ({
          ...favorite,
          has_thread: !!threadMap[favorite.query_cache_id],
          thread_id: threadMap[favorite.query_cache_id]?.id
        }));
      } catch (error) {
        console.error('Error enriching favorites with thread info:', error);
        return favorites;
      }
    },
    
    formatAnswer(answer) {
      if (!answer) return '';
      
      // Truncate to first paragraph
      let truncated = answer;
      const firstParagraphEnd = answer.indexOf('\n\n');
      if (firstParagraphEnd > 0) {
        truncated = answer.substring(0, firstParagraphEnd) + '...';
      } else if (answer.length > 200) {
        truncated = answer.substring(0, 200) + '...';
      }
      
      // Format citations with superscript numbers
      const formatted = truncated.replace(/\[(\d+)\]/g, '<sup class="citation">[$1]</sup>');
      
      // Convert markdown to HTML
      return marked(formatted);
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
      
      // Otherwise show date
      return date.toLocaleDateString([], {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    },
    
    createThread(favorite) {
      this.selectedFavorite = favorite;
      this.threadTitle = `Discussion: ${favorite.query_text.substring(0, 50)}${favorite.query_text.length > 50 ? '...' : ''}`;
      this.showThreadDialog = true;
    },
    
    async confirmCreateThread() {
      if (!this.threadTitle.trim() || !this.selectedFavorite || this.isCreatingThread) {
        return;
      }
      
      this.isCreatingThread = true;
      
      try {
        const response = await fetch('/api/thread/create', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            memory_id: this.selectedFavorite.query_cache_id,
            thread_title: this.threadTitle
          })
        });
        
        if (response.ok) {
          const data = await response.json();
          this.showThreadDialog = false;
          this.threadTitle = '';
          
          // Notify parent and reload favorites
          this.$emit('thread-created', data.thread_id);
          this.loadFavorites();
        } else {
          console.error('Failed to create thread');
        }
      } catch (error) {
        console.error('Error creating thread:', error);
      } finally {
        this.isCreatingThread = false;
      }
    }
  }
}
</script>

<style scoped>
.favorites-list {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding: 1.5rem;
}

.favorites-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.favorites-header h2 {
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

.favorites-container {
  flex-grow: 1;
}

.no-favorites {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 0;
  text-align: center;
  color: #666;
}

.no-favorites-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
  color: #ffca28;
}

.no-favorites p {
  margin: 0.5rem 0;
  font-size: 1.1rem;
}

.no-favorites-hint {
  color: #999;
  font-size: 0.9rem !important;
}

.favorites-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 1.5rem;
}

.favorite-card {
  background-color: white;
  border-radius: 10px;
  border: 1px solid #eaeaea;
  overflow: hidden;
  transition: box-shadow 0.2s, transform 0.2s;
  cursor: pointer;
  height: 100%;
}

.favorite-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 12px rgba(0, 0, 0, 0.1);
}

.favorite-card-content {
  padding: 1.5rem;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.favorite-query {
  font-weight: 600;
  font-size: 1rem;
  margin-bottom: 1rem;
  color: #333;
  position: relative;
  padding-left: 1.5rem;
  line-height: 1.4;
}

.favorite-query::before {
  content: "Q:";
  position: absolute;
  left: 0;
  color: #0066cc;
  font-weight: 700;
}

.favorite-answer {
  font-size: 0.95rem;
  color: #444;
  line-height: 1.5;
  margin-bottom: 1rem;
  position: relative;
  padding-left: 1.5rem;
  flex-grow: 1;
}

.favorite-answer::before {
  content: "A:";
  position: absolute;
  left: 0;
  color: #0066cc;
  font-weight: 700;
}

.favorite-answer :deep(.citation) {
  color: #0066cc;
  font-weight: 600;
  font-size: 0.7em;
  padding: 0 0.15em;
}

.favorite-feedback {
  margin: 1rem 0;
  background-color: #f8f9fa;
  border-radius: 6px;
  padding: 0.75rem;
  border-left: 3px solid #ddd;
}

.feedback-label {
  font-weight: 600;
  font-size: 0.85rem;
  margin-bottom: 0.5rem;
  color: #555;
}

.feedback-text {
  font-size: 0.9rem;
  color: #666;
  font-style: italic;
}

.favorite-details {
  display: flex;
  justify-content: space-between;
  color: #777;
  font-size: 0.8rem;
  margin-top: auto;
  padding-top: 1rem;
  border-top: 1px solid #f0f0f0;
}

.rating .stars {
  color: #d1d1d1;
}

.rating .stars .filled {
  color: #ffca28;
}

.saved-date {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.favorite-actions {
  margin-top: 1rem;
  display: flex;
  justify-content: flex-end;
}

.thread-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background-color: #e0f2ff;
  border: 1px solid #60b0ff;
  color: #0066cc;
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.thread-btn:hover {
  background-color: #cce7ff;
}

.thread-btn.view {
  background-color: #0066cc;
  border-color: #0055b3;
  color: white;
}

.thread-btn.view:hover {
  background-color: #0055b3;
}

.favorites-loading {
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

.favorites-loading p {
  color: #666;
}

/* Create thread dialog */
.create-thread-dialog {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  display: flex;
  justify-content: center;
  align-items: center;
}

.dialog-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
}

.dialog-content {
  position: relative;
  width: 90%;
  max-width: 500px;
  background-color: white;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
  overflow: hidden;
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #eaeaea;
}

.dialog-header h3 {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 600;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.2rem;
  color: #666;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.dialog-body {
  padding: 1.5rem;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
}

.thread-title-input {
  width: 100%;
  padding: 0.75rem;
  border-radius: 4px;
  border: 1px solid #ced4da;
  font-size: 1rem;
}

.thread-title-input:focus {
  outline: none;
  border-color: #0066cc;
  box-shadow: 0 0 0 2px rgba(0, 102, 204, 0.2);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  padding: 1rem 1.5rem;
  border-top: 1px solid #eaeaea;
  gap: 1rem;
}

.cancel-btn, .create-btn {
  padding: 0.5rem 1rem;
  border-radius: 4px;
  font-weight: 500;
  cursor: pointer;
}

.cancel-btn {
  background-color: #f8f9fa;
  border: 1px solid #dee2e6;
  color: #495057;
}

.cancel-btn:hover {
  background-color: #e9ecef;
}

.create-btn {
  background-color: #0066cc;
  border: 1px solid #0055b3;
  color: white;
}

.create-btn:hover {
  background-color: #0055b3;
}

.create-btn:disabled {
  background-color: #a0c4e4;
  border-color: #a0c4e4;
  cursor: not-allowed;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .favorites-grid {
    grid-template-columns: 1fr;
  }
  
  .favorites-list {
    padding: 1rem;
  }
}
</style>