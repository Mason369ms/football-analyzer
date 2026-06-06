import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      children: [
        {
          path: '',
          name: 'Dashboard',
          component: () => import('@/views/Dashboard.vue')
        },
        {
          path: 'match/:id',
          name: 'MatchDetail',
          component: () => import('@/views/MatchDetail.vue'),
          props: true
        },
        {
          path: 'analysis/:id',
          name: 'AnalysisDetail',
          component: () => import('@/views/AnalysisDetail.vue'),
          props: true
        }
      ]
    }
  ]
})

export default router
