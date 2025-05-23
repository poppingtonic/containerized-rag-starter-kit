<template>
  <div class="thread-dialog" v-if="visible">
    <div class="thread-overlay" @click="$emit('close')"></div>
    
    <div class="thread-container">
      <div class="thread-header">
        <h2>{{ threadTitle }}</h2>
        <button class="close-btn" @click="$emit('close')">
          <i class="fas fa-times"></i>
        </button>
      </div>
      
      <div class="thread-content" ref="messagesContainer">
        <div class="message-list">
          <div 
            v-for="message in messages" 
            :key="message.id"
            class="message"
            :class="{ 'user-message': message.is_user, 'assistant-message': !message.is_user }"
          >
            <div class="message-content">
              <div class="message-text" v-html="formatMessage(message.message)"></div>
              
              <div class="message-citations" v-if="message.references && message.references.length > 0">
                <div class="references-header">Sources:</div>
                <ul class="references-list">
                  <li v-for="(reference, index) in message.references" :key="index">
                    <span class="reference-number">[{{ index + 1 }}]</span> {{ reference }}
                  </li>
                </ul>
              </div>
              
              <div class="message-chunks" v-if="message.chunks && message.chunks.length > 0">
                <div class="chunks-header">
                  <span>Supporting Text</span>
                  <button class="toggle-chunks-btn" @click="toggleChunks(message.id)">
                    <i :class="expandedChunks[message.id] ? 'fas fa-chevron-up' : 'fas fa-chevron-down'"></i>
                  </button>
                </div>
                <div class="chunks-list" v-if="expandedChunks[message.id]">
                  <div 
                    v-for="(chunk, index) in message.chunks" 
                    :key="chunk.id"
                    class="chunk-item"
                  >
                    <div class="chunk-source">{{ chunk.source }}</div>
                    <div class="chunk-text">{{ chunk.text }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="thread-input">
        <div class="retrieval-toggle">
          <label class="toggle-label">
            <input 
              type="checkbox" 
              v-model="enhanceWithRetrieval" 
              class="toggle-input"
            >
            <span class="toggle-slider"></span>
            <span class="toggle-text">Enhance with document retrieval</span>
          </label>
        </div>
        
        <div class="input-container">
          <textarea 
            v-model="messageText" 
            placeholder="Type your message here..."
            class="message-textarea"
            ref="messageInput"
            @keydown.enter.ctrl="sendMessage"
            @keydown.enter.meta="sendMessage"
          ></textarea>
          
          <button 
            class="send-button" 
            @click="sendMessage"
            :disabled="!messageText.trim() || isSending"
          >
            <i :class="isSending ? 'fas fa-spinner fa-spin' : 'fas fa-paper-plane'"></i>
          </button>
        </div>
        
        <div class="input-hint">Press Ctrl+Enter (Cmd+Enter on Mac) to send</div>
      </div>
    </div>
  </div>
</template>

<script>
import { marked } from 'marked';

export default {
  name: 'ThreadDialog',
  props: {
    visible: {
      type: Boolean,
      default: false
    },
    threadId: {
      type: [Number, String],
      required: false,
      default: null
    },
    threadTitle: {
      type: String,
      default: 'Conversation'
    }
  },
  data() {
    return {
      messages: [],
      messageText: '',
      enhanceWithRetrieval: true,
      isSending: false,
      expandedChunks: {}
    }
  },
  watch: {
    visible(newVal) {
      console.log('ThreadDialog visible changed to:', newVal);
      console.log('ThreadDialog props:', {
        visible: this.visible,
        threadId: this.threadId,
        threadTitle: this.threadTitle
      });
      
      if (newVal) {
        this.loadThreadMessages();
        this.$nextTick(() => {
          if (this.$refs.messageInput) {
            this.$refs.messageInput.focus();
          } else {
            console.warn('messageInput ref not found when trying to focus');
          }
        });
      }
    },
    threadId(newVal) {
      console.log('ThreadDialog threadId changed to:', newVal);
      if (this.visible && newVal) {
        this.loadThreadMessages();
      }
    },
    messages() {
      this.$nextTick(() => {
        this.scrollToBottom();
      });
    }
  },
  methods: {
    async loadThreadMessages() {
      console.log('Loading thread messages for threadId:', this.threadId);
      if (!this.threadId) {
        console.warn('No threadId provided when trying to load messages');
        return;
      }
        
      try {
        const response = await fetch(`/api/thread/${this.threadId}`);
        console.log('API response status:', response.status);
        
        if (response.ok) {
          const data = await response.json();
          console.log('Thread data loaded:', data);
          this.messages = data.messages;
          
          // Initialize expanded state for each message
          this.messages.forEach(message => {
            if (message.chunks && message.chunks.length > 0) {
              this.$set(this.expandedChunks, message.id, false);
            }
          });
          
          this.$nextTick(() => {
            this.scrollToBottom();
          });
        } else {
          const errorText = await response.text();
          console.error('Failed to load thread messages. Status:', response.status, 'Error:', errorText);
        }
      } catch (error) {
        console.error('Error loading thread messages:', error);
      }
    },
    
    async sendMessage() {
      if (!this.messageText.trim() || this.isSending) return;
      
      try {
        this.isSending = true;
        
        // Add user message to the UI immediately
        const userMessage = {
          id: 'temp-' + Date.now(),
          message: this.messageText,
          is_user: true,
          references: [],
          created_at: new Date().toISOString()
        };
        
        this.messages.push(userMessage);
        
        // Send message to API
        const response = await fetch('/api/thread/message', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            feedback_id: this.threadId,
            message: this.messageText,
            enhance_with_retrieval: this.enhanceWithRetrieval,
            max_results: 3
          })
        });
        
        if (response.ok) {
          const data = await response.json();
          
          // Remove temporary message and add actual messages
          this.messages = this.messages.filter(m => m.id !== userMessage.id);
          
          this.messages.push({
            id: data.user_message.id,
            message: data.user_message.message,
            is_user: true,
            references: [],
            created_at: new Date().toISOString()
          });
          
          this.messages.push({
            id: data.assistant_message.id,
            message: data.assistant_message.message,
            is_user: false,
            references: data.assistant_message.references,
            chunks: data.assistant_message.chunks,
            created_at: new Date().toISOString()
          });
          
          // Initialize expanded state for the new message
          if (data.assistant_message.chunks && data.assistant_message.chunks.length > 0) {
            this.$set(this.expandedChunks, data.assistant_message.id, false);
          }
          
          this.messageText = '';
        } else {
          console.error('Failed to send message');
          // Remove the temporary message
          this.messages = this.messages.filter(m => m.id !== userMessage.id);
        }
      } catch (error) {
        console.error('Error sending message:', error);
      } finally {
        this.isSending = false;
      }
    },
    
    toggleChunks(messageId) {
      this.$set(this.expandedChunks, messageId, !this.expandedChunks[messageId]);
    },
    
    formatMessage(text) {
      // Format citations with superscript numbers
      const formattedText = text.replace(/\[(\d+)\]/g, '<sup class="citation">[$1]</sup>');
      
      // Convert markdown to HTML
      return marked(formattedText);
    },
    
    scrollToBottom() {
      if (this.$refs.messagesContainer) {
        this.$refs.messagesContainer.scrollTop = this.$refs.messagesContainer.scrollHeight;
      }
    }
  }
}
</script>

<style>
.thread-dialog {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 2000;
  display: flex;
  justify-content: center;
  align-items: center;
}

.thread-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
}

.thread-container {
  position: relative;
  width: 90%;
  max-width: 900px;
  height: 85vh;
  background-color: white;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.thread-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #eaeaea;
}

.thread-header h2 {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 600;
  color: #333;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.2rem;
  color: #666;
  cursor: pointer;
  padding: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: background-color 0.2s;
}

.close-btn:hover {
  background-color: #f0f0f0;
}

.thread-content {
  flex-grow: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.message {
  max-width: 85%;
  position: relative;
}

.user-message {
  align-self: flex-end;
}

.assistant-message {
  align-self: flex-start;
}

.message-content {
  border-radius: 12px;
  padding: 1rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.user-message .message-content {
  background-color: #e7f3ff;
  border: 1px solid #cce5ff;
}

.assistant-message .message-content {
  background-color: #f8f9fa;
  border: 1px solid #e9ecef;
}

.message-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.5;
}

.message-text a {
  color: #0066cc;
  text-decoration: none;
}

.message-text a:hover {
  text-decoration: underline;
}

.message-citations {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid rgba(0, 0, 0, 0.1);
}

.references-header {
  font-weight: 600;
  margin-bottom: 0.5rem;
  font-size: 0.9rem;
}

.references-list {
  list-style-type: none;
  padding-left: 0;
  margin: 0;
  font-size: 0.85rem;
}

.references-list li {
  margin-bottom: 0.25rem;
}

.reference-number {
  font-weight: 600;
  margin-right: 0.25rem;
}

.citation {
  color: #0066cc;
  font-weight: 600;
  font-size: 0.7em;
  padding: 0 0.15em;
}

.message-chunks {
  margin-top: 0.75rem;
  border-top: 1px solid rgba(0, 0, 0, 0.1);
  padding-top: 0.75rem;
}

.chunks-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
  font-weight: 600;
  font-size: 0.9rem;
}

.toggle-chunks-btn {
  background: none;
  border: none;
  color: #666;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  font-size: 0.8rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.toggle-chunks-btn:hover {
  background-color: rgba(0, 0, 0, 0.05);
}

.chunks-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 0.5rem;
  border-left: 3px solid #ddd;
  padding-left: 1rem;
}

.chunk-item {
  font-size: 0.85rem;
  line-height: 1.5;
  background-color: rgba(0, 0, 0, 0.02);
  border-radius: 4px;
  padding: 0.75rem;
}

.chunk-source {
  font-weight: 600;
  margin-bottom: 0.5rem;
  color: #0066cc;
}

.chunk-text {
  color: #555;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 150px;
  overflow-y: auto;
}

.thread-input {
  padding: 1rem 1.5rem;
  border-top: 1px solid #eaeaea;
}

.retrieval-toggle {
  margin-bottom: 0.75rem;
}

.toggle-label {
  display: flex;
  align-items: center;
  cursor: pointer;
  font-size: 0.9rem;
}

.toggle-input {
  display: none;
}

.toggle-slider {
  position: relative;
  display: inline-block;
  width: 36px;
  height: 20px;
  background-color: #ccc;
  border-radius: 20px;
  margin-right: 0.75rem;
  transition: 0.2s;
}

.toggle-slider:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 2px;
  bottom: 2px;
  background-color: white;
  border-radius: 50%;
  transition: 0.2s;
}

.toggle-input:checked + .toggle-slider {
  background-color: #0066cc;
}

.toggle-input:checked + .toggle-slider:before {
  transform: translateX(16px);
}

.toggle-text {
  user-select: none;
}

.input-container {
  display: flex;
  gap: 0.75rem;
}

.message-textarea {
  flex-grow: 1;
  min-height: 80px;
  max-height: 150px;
  border-radius: 8px;
  border: 1px solid #ccc;
  padding: 0.75rem;
  resize: vertical;
  font-family: inherit;
  font-size: 0.95rem;
  line-height: 1.5;
  transition: border-color 0.2s;
}

.message-textarea:focus {
  outline: none;
  border-color: #0066cc;
}

.send-button {
  align-self: flex-end;
  background-color: #0066cc;
  color: white;
  border: none;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.2s;
}

.send-button:hover {
  background-color: #0055b3;
}

.send-button:disabled {
  background-color: #a0c4e4;
  cursor: not-allowed;
}

.input-hint {
  margin-top: 0.5rem;
  font-size: 0.8rem;
  color: #666;
  text-align: right;
}
</style>