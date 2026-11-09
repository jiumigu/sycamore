<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useShowroomStore } from '../stores/showroomStore'
import MediaGallery from '@/shared/components/MediaGallery.vue'

const store = useShowroomStore()
const router = useRouter()

onMounted(() => {
  store.fetchPreview()
})

const hasContact = computed(() => {
  const p = store.preview?.profile
  return !!(p && (p.email || p.wechat || p.other_contact))
})

const isEmpty = computed(() => {
  const p = store.preview
  if (!p) return false
  return !p.profile.ip_name && !p.cases.length && !p.skills.length && !p.works.length
})
</script>

<template>
  <div class="showroom-preview">
    <!-- 内部提示条：正式展厅（静态快照）里不会有这一栏 -->
    <div class="preview-bar">
      <span>预览模式 —— 此栏不会出现在正式展厅</span>
      <el-button size="small" @click="router.push('/showroom/edit')">去策展</el-button>
    </div>

    <!-- 🔴 「取不到」不能说成「空」：接口挂了要显式说出来 -->
    <el-alert
      v-if="store.loadError"
      class="hub-alert"
      type="error"
      :closable="false"
      show-icon
      title="展厅没取到（这不是「还没策展」）—— 若刚升级过，先确认数据库迁移已执行"
    />

    <div v-loading="store.loading" class="showroom-content">
      <template v-if="store.preview">
        <!-- 第一屏 · 品牌层 -->
        <section class="hero">
          <h1 class="hero-name">{{ store.preview.profile.ip_name || '（未填 IP 名）' }}</h1>
          <p class="hero-tagline">{{ store.preview.profile.tagline || '（未填一句话定位）' }}</p>
          <p v-if="store.preview.profile.positioning" class="hero-positioning">
            {{ store.preview.profile.positioning }}
          </p>
          <p v-if="store.preview.profile.bio" class="hero-bio">{{ store.preview.profile.bio }}</p>
        </section>

        <!-- 第二屏 · 能力馆 -->
        <section v-if="store.preview.cases.length || store.preview.skills.length" class="hall">
          <h2 class="hall-title">我做过的事</h2>
          <div class="case-list">
            <article v-for="c in store.preview.cases" :key="c.id" class="case-card">
              <h3 class="case-title">{{ c.title }}</h3>
              <p v-if="c.client || c.time_label" class="case-meta">
                {{ [c.client, c.time_label].filter(Boolean).join(' · ') }}
              </p>
              <p v-if="c.problem" class="case-block">
                <span class="case-label">问题</span>{{ c.problem }}
              </p>
              <p v-if="c.result" class="case-block">
                <span class="case-label">成果</span>{{ c.result }}
              </p>
              <MediaGallery :media="c.media" />
            </article>
          </div>
          <div v-if="store.preview.skills.length" class="skill-list">
            <span v-for="s in store.preview.skills" :key="s.id" class="skill-tag">{{ s.name }}</span>
          </div>
        </section>

        <!-- 第三屏 · 作品馆 -->
        <section v-if="store.preview.works.length" class="hall">
          <h2 class="hall-title">我的作品</h2>
          <div class="work-list">
            <article v-for="w in store.preview.works" :key="w.id" class="work-card">
              <h3 class="work-name">{{ w.work_name ?? w.title_snapshot }}</h3>
              <p v-if="w.curator_note || w.work_summary" class="work-note">
                {{ w.curator_note || w.work_summary }}
              </p>
              <MediaGallery :media="w.media" />
            </article>
          </div>
        </section>

        <!-- 底栏 · 联系 -->
        <section v-if="hasContact" class="contact">
          <h2 class="hall-title">联系我</h2>
          <p v-if="store.preview.profile.email" class="contact-line">
            {{ store.preview.profile.email }}
          </p>
          <p v-if="store.preview.profile.wechat" class="contact-line">
            微信：{{ store.preview.profile.wechat }}
          </p>
          <p v-if="store.preview.profile.other_contact" class="contact-line">
            {{ store.preview.profile.other_contact }}
          </p>
        </section>

        <el-empty
          v-if="isEmpty"
          description="展厅还是空的 —— 去策展，填上你是谁、你做过什么"
          :image-size="120"
        >
          <el-button type="primary" @click="router.push('/showroom/edit')">去策展</el-button>
        </el-empty>
      </template>
    </div>
  </div>
</template>

<style scoped>
.showroom-preview {
  min-height: 100vh;
  background: var(--el-bg-color-page);
}
.preview-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  background: var(--el-color-warning-light-9);
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.hub-alert {
  margin: 16px auto 0;
  max-width: 640px;
}
.showroom-content {
  max-width: 640px;
  margin: 0 auto;
  padding: 48px 24px 72px;
}
.hero {
  text-align: center;
  padding: 32px 0 40px;
}
.hero-name {
  margin: 0 0 12px;
  font-size: 30px;
  font-weight: 500;
  letter-spacing: 0.08em;
}
.hero-tagline {
  margin: 0 0 8px;
  font-size: 17px;
  line-height: 1.8;
  color: var(--el-text-color-primary);
}
.hero-positioning {
  margin: 0 0 12px;
  font-size: 15px;
  color: var(--el-text-color-secondary);
}
.hero-bio {
  margin: 0;
  font-size: 15px;
  line-height: 1.8;
  color: var(--el-text-color-secondary);
  white-space: pre-wrap;
}
.hall {
  margin-top: 40px;
}
.hall-title {
  margin: 0 0 20px;
  font-size: 15px;
  font-weight: 500;
  letter-spacing: 0.05em;
}
.case-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.case-card {
  padding: 20px 0;
  border-top: 1px solid var(--el-border-color-lighter);
}
.case-title {
  margin: 0 0 6px;
  font-size: 16px;
  font-weight: 500;
  line-height: 1.6;
}
.case-meta {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.case-block {
  margin: 8px 0 0;
  font-size: 15px;
  line-height: 1.8;
  color: var(--el-text-color-regular);
}
.case-label {
  display: inline-block;
  margin-right: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.skill-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 20px;
}
.skill-tag {
  padding: 4px 12px;
  border-radius: 999px;
  background: var(--el-fill-color-light);
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.work-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.work-card {
  padding: 16px 0;
  border-top: 1px solid var(--el-border-color-lighter);
}
.work-name {
  margin: 0 0 6px;
  font-size: 16px;
  font-weight: 500;
}
.work-note {
  margin: 0;
  font-size: 15px;
  line-height: 1.8;
  color: var(--el-text-color-regular);
}
.contact {
  margin-top: 40px;
}
.contact-line {
  margin: 8px 0 0;
  font-size: 15px;
  line-height: 1.8;
}
</style>
