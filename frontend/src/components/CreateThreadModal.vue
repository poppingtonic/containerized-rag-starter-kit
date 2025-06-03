<template>
  <div class="create-thread-modal" v-if="visible">
    <div class="modal-overlay" @click="$emit('close')"></div>
    
    <div class="modal-container">
      <div class="modal-header">
        <h3>Create Conversation Thread</h3>
        <button class="close-btn" @click="$emit('close')">
          <i class="fas fa-times"></i>
        </button>
      </div>
      
      <div class="modal-body">
        <p class="description">
          Start a conversation based on this query. You'll be able to chat and get document-grounded responses.
        </p>
        
        <div class="form-group">
          <label for="thread-title">Thread Title</label>
          <input 
            type="text" 
            id="thread-title" 
            v-model="title"
            placeholder="Enter a title for this conversation"
            class="thread-title-input"
            @keyup.enter="createThread"
            ref="titleInput"
          />
        </div>
      </div>
      
      <div class="modal-footer">
        <button 
          class="cancel-btn" 
          @click="$emit('close')"
          :disabled="isCreating"
        >
          Cancel
        </button>
        <button 
          class="create-btn" 
          @click="createThread"
          :disabled="!title.trim() || isCreating"
        >
          {{ isCreating ? 'Creating...' : 'Create Thread' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'CreateThreadModal',
  props: {
    visible: {
      type: Boolean,
      default: false
    },
    memoryId: {
      type: Number,
      required: true
    },
    queryText: {
      type: String,
      default: ''
    }
  },
  data() {
    return {
      title: '',
      isCreating: false
    }
  },
  watch: {
    visible(newVal) {
      if (newVal) {
        // Pre-populate title with query
        if (this.queryText) {
          this.title = `Discussion: ${this.queryText.substring(0, 50)}${this.queryText.length > 50 ? '...' : ''}`;
        }
        // Focus the title input
        this.$nextTick(() => {
          if (this.$refs.titleInput) {
            this.$refs.titleInput.focus();
          }
        });
      } else {
        // Reset form
        this.title = '';
        this.isCreating = false;
      }
    }
  },
  methods: {
    async createThread() {
      console.log('Creating thread with title:', this.title, 'memory ID:', this.memoryId);
      if (!this.title.trim() || this.isCreating) {
        console.warn('Aborting thread creation: title is empty or already creating');
        return;
      }
      
      if (!this.memoryId || this.memoryId < 0) {
        console.error('Cannot create thread: Invalid memory ID provided', this.memoryId);
        alert('Unable to create thread: The query must be saved to memory first.');
        this.$emit('close');
        return;
      }
      
      this.isCreating = true;
      
      try {
        const requestBody = {
          memory_id: this.memoryId,
          thread_title: this.title
        };
        console.log('Sending create thread request:', requestBody);
        
        const response = await fetch('/api/thread/create', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(requestBody)
        });
        
        console.log('Create thread response status:', response.status);
        
        if (response.ok) {
          const data = await response.json();
          console.log('Thread created successfully:', data);
          this.$emit('created', data.thread_id, this.title);
        } else {
          const errorText = await response.text();
          try {
            const errorData = JSON.parse(errorText);
            console.log('API returned error data:', errorData);
            
            if (errorData.thread_id) {
              // Thread already exists, notify parent
              console.log('Thread already exists, using existing ID:', errorData.thread_id);
              this.$emit('existing', errorData.thread_id, this.title);
            } else {
              console.error('Failed to create thread:', errorData.message);
            }
          } catch (e) {
            console.error('Failed to parse error response:', errorText);
          }
        }
      } catch (error) {
        console.error('Error creating thread:', error);
      } finally {
        this.isCreating = false;
        this.$emit('close');
      }
    }
  }
}
</script>

<style scoped>
.create-thread-modal {
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

.modal-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
}

.modal-container {
  position: relative;
  width: 90%;
  max-width: 500px;
  background-color: white;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #eaeaea;
}

.modal-header h3 {
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

.modal-body {
  padding: 1.5rem;
}

.description {
  margin-top: 0;
  margin-bottom: 1.5rem;
  color: #666;
  font-size: 0.95rem;
  line-height: 1.5;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #333;
}

.thread-title-input {
  width: 100%;
  padding: 0.75rem;
  border-radius: 4px;
  border: 1px solid #ced4da;
  font-size: 1rem;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.thread-title-input:focus {
  outline: none;
  border-color: #0066cc;
  box-shadow: 0 0 0 2px rgba(0, 102, 204, 0.2);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  padding: 1rem 1.5rem;
  border-top: 1px solid #eaeaea;
  gap: 1rem;
}

.cancel-btn, .create-btn {
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
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

.create-btn:disabled, .cancel-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>