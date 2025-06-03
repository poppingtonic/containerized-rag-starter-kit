<template>
  <div class="result-actions">
    <div class="actions-bar">
      <div class="action-buttons">
        <button 
          class="action-btn favorite-btn" 
          :class="{ 'active': isFavorite }"
          @click="toggleFavorite"
          title="Favorite this answer"
        >
          <span class="icon">
            <i :class="isFavorite ? 'fas fa-star' : 'far fa-star'"></i>
          </span>
        </button>
        
        <button 
          class="action-btn thread-btn" 
          @click="createThread"
          :disabled="hasThread || !memoryId"
          :title="getThreadButtonTitle()"
        >
          <span class="icon">
            <i class="fas fa-comments"></i>
          </span>
        </button>
        
        <button 
          class="action-btn feedback-btn" 
          @click="showFeedback = !showFeedback"
          :class="{ 'active': showFeedback }"
          title="Provide feedback"
        >
          <span class="icon">
            <i class="fas fa-comment-dots"></i>
          </span>
        </button>
      </div>
      
      <div class="memory-indicator" v-if="fromMemory">
        <span class="from-memory-badge" title="Answer retrieved from memory">
          <i class="fas fa-memory"></i> From memory
        </span>
      </div>
    </div>
    
    <div class="feedback-container" v-if="showFeedback">
      <div class="feedback-form">
        <h3>Provide Feedback</h3>
        
        <div class="rating-container">
          <label>Rating:</label>
          <div class="stars">
            <span 
              v-for="i in 5" 
              :key="i"
              @click="rating = i"
              :class="{ 'active': rating >= i }"
              class="star"
            >
              <i class="fas fa-star"></i>
            </span>
          </div>
        </div>
        
        <div class="feedback-text">
          <label for="feedback">Comment (optional):</label>
          <textarea 
            id="feedback" 
            v-model="feedbackText"
            placeholder="What did you think of this answer?"
            rows="3"
          ></textarea>
        </div>
        
        <div class="feedback-actions">
          <button 
            class="cancel-btn"
            @click="showFeedback = false"
          >
            Cancel
          </button>
          <button 
            class="submit-btn"
            @click="submitFeedback"
            :disabled="isSubmitting"
          >
            {{ isSubmitting ? 'Submitting...' : 'Submit Feedback' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ResultActions',
  props: {
    memoryId: {
      type: Number,
      required: false,
      default: null
    },
    fromMemory: {
      type: Boolean,
      default: false
    },
    initialFavorite: {
      type: Boolean,
      default: false
    },
    hasThread: {
      type: Boolean,
      default: false
    }
  },
  data() {
    return {
      showFeedback: false,
      rating: 0,
      feedbackText: '',
      isFavorite: this.initialFavorite,
      isSubmitting: false
    }
  },
  methods: {
    async toggleFavorite() {
      try {
        this.isSubmitting = true;
        // Save to API
        const response = await fetch('/api/feedback', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            memory_id: this.memoryId,
            is_favorite: !this.isFavorite
          })
        });
        
        if (response.ok) {
          this.isFavorite = !this.isFavorite;
          this.$emit('favorite-changed', this.isFavorite);
        } else {
          console.error('Failed to update favorite status');
        }
      } catch (error) {
        console.error('Error updating favorite:', error);
      } finally {
        this.isSubmitting = false;
      }
    },
    
    async submitFeedback() {
      if (this.rating === 0) {
        alert('Please provide a rating');
        return;
      }
      
      try {
        this.isSubmitting = true;
        
        // Submit feedback to API
        const response = await fetch('/api/feedback', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            memory_id: this.memoryId,
            rating: this.rating,
            feedback_text: this.feedbackText || null,
            is_favorite: this.isFavorite
          })
        });
        
        if (response.ok) {
          this.showFeedback = false;
          this.feedbackText = '';
          this.$emit('feedback-submitted');
        } else {
          console.error('Failed to submit feedback');
        }
      } catch (error) {
        console.error('Error submitting feedback:', error);
      } finally {
        this.isSubmitting = false;
      }
    },
    
    createThread() {
      // Only emit the event if we have a valid memory ID
      if (this.memoryId) {
        this.$emit('create-thread');
      }
    },
    
    getThreadButtonTitle() {
      if (this.hasThread) {
        return 'Thread already exists';
      } else if (!this.memoryId) {
        return 'Cannot create thread without a valid memory ID';
      } else {
        return 'Create conversation thread';
      }
    }
  }
}
</script>

<style scoped>
.result-actions {
  margin-top: 1rem;
  border-top: 1px solid #eaeaea;
  padding-top: 0.75rem;
}

.actions-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.action-buttons {
  display: flex;
  gap: 0.5rem;
}

.action-btn {
  background-color: #f5f5f5;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn:hover {
  background-color: #e8e8e8;
}

.action-btn.active {
  background-color: #e0f2ff;
  border-color: #60b0ff;
  color: #0066cc;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.favorite-btn.active {
  background-color: #fff8e0;
  border-color: #ffca28;
  color: #ff9800;
}

.memory-indicator {
  display: flex;
  align-items: center;
}

.from-memory-badge {
  background-color: #e0f7fa;
  color: #00838f;
  border-radius: 20px;
  padding: 0.25rem 0.75rem;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.feedback-container {
  margin-top: 1rem;
  padding: 1rem;
  background-color: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #e9ecef;
}

.feedback-form h3 {
  margin-top: 0;
  margin-bottom: 1rem;
  font-size: 1.1rem;
  font-weight: 500;
}

.rating-container {
  display: flex;
  align-items: center;
  margin-bottom: 1rem;
  gap: 1rem;
}

.stars {
  display: flex;
  gap: 0.25rem;
}

.star {
  cursor: pointer;
  color: #d1d1d1;
  font-size: 1.5rem;
  transition: color 0.2s ease;
}

.star:hover,
.star.active {
  color: #ffca28;
}

.feedback-text {
  display: flex;
  flex-direction: column;
  margin-bottom: 1rem;
}

.feedback-text label {
  margin-bottom: 0.5rem;
}

.feedback-text textarea {
  padding: 0.5rem;
  border-radius: 4px;
  border: 1px solid #ced4da;
  resize: vertical;
  font-family: inherit;
}

.feedback-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.cancel-btn,
.submit-btn {
  padding: 0.5rem 1rem;
  border-radius: 4px;
  border: none;
  cursor: pointer;
  font-weight: 500;
  transition: background-color 0.2s ease;
}

.cancel-btn {
  background-color: #e9ecef;
  color: #495057;
}

.cancel-btn:hover {
  background-color: #dee2e6;
}

.submit-btn {
  background-color: #0066cc;
  color: white;
}

.submit-btn:hover {
  background-color: #0055b3;
}

.submit-btn:disabled {
  background-color: #a0c4e4;
  cursor: not-allowed;
}
</style>