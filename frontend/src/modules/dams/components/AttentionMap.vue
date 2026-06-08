<template>
  <div class="attention-map">
    <el-row :gutter="16">
      <el-col v-for="(zone, key) in zones" :key="key" :span="6">
        <div
          class="zone-card"
          :style="{ borderLeft: `4px solid ${zone.color}` }"
        >
          <div class="zone-count" :style="{ color: zone.color }">
            {{ zone.count }}
          </div>
          <div class="zone-label">{{ zone.label }}</div>
          <div class="zone-percent">
            {{ total > 0 ? ((zone.count / total) * 100).toFixed(1) : 0 }}%
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ATTENTION_ZONE_CONFIG } from '../types/damsTypes'
import type { AttentionMapData } from '../types/damsTypes'

const props = defineProps<{
  data: AttentionMapData | null
}>()

const total = computed(() => props.data?.total ?? 0)

const zones = computed(() => ({
  red: {
    count: props.data?.red?.count ?? 0,
    label: ATTENTION_ZONE_CONFIG.red.label,
    color: ATTENTION_ZONE_CONFIG.red.color,
  },
  blue: {
    count: props.data?.blue?.count ?? 0,
    label: ATTENTION_ZONE_CONFIG.blue.label,
    color: ATTENTION_ZONE_CONFIG.blue.color,
  },
  green: {
    count: props.data?.green?.count ?? 0,
    label: ATTENTION_ZONE_CONFIG.green.label,
    color: ATTENTION_ZONE_CONFIG.green.color,
  },
  gray: {
    count: props.data?.gray?.count ?? 0,
    label: ATTENTION_ZONE_CONFIG.gray.label,
    color: ATTENTION_ZONE_CONFIG.gray.color,
  },
}))
</script>

<style scoped lang="scss">
.attention-map {
  margin-bottom: 20px;
}

.zone-card {
  background: var(--el-bg-color-overlay);
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  transition: transform 0.2s;

  &:hover {
    transform: translateY(-2px);
  }
}

.zone-count {
  font-size: 36px;
  font-weight: 700;
  line-height: 1.2;
}

.zone-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-top: 8px;
}

.zone-percent {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  margin-top: 4px;
}
</style>
