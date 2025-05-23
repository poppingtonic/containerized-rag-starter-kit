import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import CacheView from '../views/CacheView.vue'
import EvaluationView from '../views/EvaluationView.vue'
import ExportView from '../views/ExportView.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: HomeView
  },
  {
    path: '/cache',
    name: 'Cache',
    component: CacheView
  },
  {
    path: '/evaluation',
    name: 'Evaluation',
    component: EvaluationView
  },
  {
    path: '/export',
    name: 'Export',
    component: ExportView
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router