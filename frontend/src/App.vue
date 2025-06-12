<template>
  <div id="app">
    <nav class="navbar">
      <div class="nav-container">
        <router-link to="/" class="nav-brand">
          <h1>AI Search</h1>
        </router-link>
        
        <div class="nav-links">
          <router-link to="/" class="nav-link" :class="{ active: $route.path === '/' }">
            <i class="fas fa-search"></i> Search
          </router-link>
          <router-link to="/cache" class="nav-link" :class="{ active: $route.path === '/cache' }">
            <i class="fas fa-database"></i> Cache
          </router-link>
          <router-link to="/evaluation" class="nav-link" :class="{ active: $route.path === '/evaluation' }">
            <i class="fas fa-chart-bar"></i> Evaluation
          </router-link>
          <router-link to="/export" class="nav-link" :class="{ active: $route.path === '/export' }">
            <i class="fas fa-download"></i> Export
          </router-link>
        </div>
      </div>
    </nav>
    
    <main class="main-container">
      <router-view />
    </main>
  </div>
</template>

<script>
export default {
  name: 'App'
}
</script>

<style>
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
  background-color: #f5f7fa;
  color: #333;
}

#app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.navbar {
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 60px;
}

.nav-brand {
  text-decoration: none;
  color: #333;
}

.nav-brand h1 {
  font-size: 24px;
  font-weight: 600;
}

.nav-links {
  display: flex;
  gap: 30px;
}

.nav-link {
  text-decoration: none;
  color: #666;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 5px;
  transition: all 0.2s;
}

.nav-link:hover {
  color: #007bff;
  background: #f0f7ff;
}

.nav-link.active {
  color: #007bff;
  background: #e7f3ff;
}

.nav-link i {
  font-size: 16px;
}

.main-container {
  flex: 1;
  padding: 20px 0;
}

/* Global utility classes */
.error-message {
  background: #f8d7da;
  color: #721c24;
  padding: 15px;
  border-radius: 5px;
  margin: 20px 0;
}

.loading {
  text-align: center;
  padding: 50px;
  color: #666;
}

button {
  cursor: pointer;
  transition: all 0.2s;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

input[type="text"],
input[type="number"],
select,
textarea {
  font-family: inherit;
  font-size: 14px;
}

/* Font Awesome icons fallback */
.fas::before {
  font-family: monospace;
  font-weight: normal;
}

.fa-search::before { content: "🔍"; }
.fa-database::before { content: "💾"; }
.fa-chart-bar::before { content: "📊"; }
.fa-download::before { content: "📥"; }
.fa-star::before { content: "⭐"; }
.fa-spinner::before { content: "⏳"; }
.fa-times::before { content: "✕"; }
</style>