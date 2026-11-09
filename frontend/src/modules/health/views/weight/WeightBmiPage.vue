<template>
  <div class="weight-sub-page">
    <WeightSubHeader title="⚖️ BMI" :subtitle="subtitle">
      <el-button size="small" :loading="loading" @click="reload">刷新</el-button>
    </WeightSubHeader>

    <div v-if="loading && !store.stats" class="loading-state">
      <el-skeleton :rows="6" animated />
    </div>
    <template v-else>
      <BMIStatus page-mode :stats="store.stats" />

      <div class="info-card">
        <div class="info-title">身体信息</div>
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">身高</span>
            <span class="info-value">{{ heightText }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">性别</span>
            <span class="info-value">{{ genderText }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">年龄</span>
            <span class="info-value">{{ ageText }}</span>
          </div>
        </div>
        <!-- 这里只读：录入入口只有「调整目标」那一处，避免同一事实两个录入口 -->
        <div class="info-hint">身高决定 BMI 的算法；要改请回体重管理页点「🎯 调整目标」。</div>
      </div>

      <div class="info-card">
        <div class="info-title">区间对照</div>
        <div class="range-table">
          <div class="range-row range-head">
            <span>区间</span>
            <span>BMI</span>
            <span>建议</span>
          </div>
          <div v-for="row in bmiRows" :key="row.label" class="range-row">
            <span class="range-label" :style="{ color: row.color }">{{ row.label }}</span>
            <span class="range-num">{{ row.range }}</span>
            <span class="range-advice">{{ row.advice }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useWeightStore } from '../../stores/healthStore'
import { BMI_RANGES } from '../../types/healthTypes'
import BMIStatus from '../../components/weight/BMIStatus.vue'
import WeightSubHeader from '../../components/weight/WeightSubHeader.vue'

const store = useWeightStore()
const loading = ref(false)

const GENDER_LABELS: Record<string, string> = { male: '男', female: '女' }

const subtitle = computed(() => {
  const bmi = store.stats?.bmi
  return bmi == null ? '还没有可计算的 BMI（缺身高或体重记录）' : `当前 ${bmi}，${store.stats?.bmi_status ?? '—'}`
})

const heightText = computed(() => {
  const h = store.bodyInfo?.height_cm
  if (h == null || h === '') return '未填写'
  const n = Number(h)
  return Number.isFinite(n) ? `${n} cm` : '未填写'
})

const genderText = computed(() => {
  const g = store.bodyInfo?.gender
  return g ? (GENDER_LABELS[g] ?? g) : '未填写'
})

const ageText = computed(() => {
  const a = store.bodyInfo?.age
  return a == null ? '未填写' : `${a} 岁`
})

/** 区间文字由 `max` 反推下界 —— 阈值只有 `BMI_RANGES` 一份，这里不另写一套数字 */
const bmiRows = computed(() =>
  BMI_RANGES.map((r, i) => {
    const lower = i === 0 ? null : BMI_RANGES[i - 1].max
    const upper = r.max === Infinity ? null : r.max
    let range: string
    if (lower == null) range = `< ${upper}`
    else if (upper == null) range = `≥ ${lower}`
    else range = `${lower} ~ ${upper}`
    return { label: r.label, color: r.color, advice: r.advice, range }
  })
)

async function reload() {
  loading.value = true
  try {
    await Promise.all([
      store.fetchStats(),
      store.fetchBodyInfo(),
    ])
  } finally {
    loading.value = false
  }
}

onMounted(reload)
</script>

<style scoped>
.weight-sub-page { max-width: 1000px; margin: 0 auto; padding: 24px; }
.loading-state { padding: 24px; background: #fff; border: 1px solid #E5E7EB; border-radius: 12px; }
.info-card {
  background: #fff; border: 1px solid #E5E7EB; border-radius: 12px;
  padding: 20px; margin-top: 16px;
}
.info-title { font-size: 15px; font-weight: 600; color: #1F2937; margin-bottom: 14px; }
.info-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.info-item { background: #F9FAFB; border-radius: 8px; padding: 12px 14px; }
.info-label { display: block; font-size: 12px; color: #6B7280; margin-bottom: 6px; }
.info-value { font-size: 16px; font-weight: 600; color: #1F2937; }
.info-hint { font-size: 12px; color: #9CA3AF; margin-top: 12px; }
.range-table { display: flex; flex-direction: column; }
.range-row {
  display: grid; grid-template-columns: 1fr 1.2fr 1.4fr;
  align-items: center; padding: 10px 12px; font-size: 13px;
  color: #374151; border-bottom: 1px solid #F3F4F6;
}
.range-row:last-child { border-bottom: none; }
.range-head { font-size: 12px; color: #9CA3AF; font-weight: 500; }
.range-label { font-weight: 600; }
.range-num { font-variant-numeric: tabular-nums; }
.range-advice { color: #6B7280; }
</style>
