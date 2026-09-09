<template>
  <div class="legend-card">
    <div class="legend-card__title">收支等级</div>
    <div class="legend-card__items">
      <div v-for="item in items" :key="item.key" class="legend-card__item">
        <span class="legend-card__color" :style="{ background: item.color }" />
        <span class="legend-card__label">{{ item.label }}</span>
      </div>
    </div>
    <div class="legend-card__coverage">
      <span class="legend-card__coverage-box" />
      <span class="legend-card__coverage-label">蓝色边框 = 现金流覆盖</span>
    </div>
  </div>
</template>

<script setup lang="ts">
const items = [
  { key: 'surplus_high', label: '结余较高 >1500', color: '#1b5e20' },
  { key: 'surplus_mid', label: '结余中等 500~1500', color: '#388e3c' },
  { key: 'surplus_low', label: '结余较低 0~500', color: '#81c784' },
  { key: 'zero', label: '收支平衡 =0', color: '#9e9e9e' },
  { key: 'deficit_low', label: '赤字较低 -500~0', color: '#e57373' },
  { key: 'deficit_mid', label: '赤字中等 -1500~-500', color: '#d32f2f' },
  { key: 'deficit_high', label: '赤字较高 <-1500', color: '#b71c1c' },
]
</script>

<style scoped lang="scss">
.legend-card {
  padding: 20px;

  &__title {
    font-size: 16px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    margin-bottom: 16px;
  }

  &__items {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }

  &__item {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  &__color {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    flex-shrink: 0;
  }

  &__label {
    font-size: 12px;
    color: var(--el-text-color-regular);
    white-space: nowrap;
  }

  &__coverage {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 14px;
    padding-top: 12px;
    border-top: 1px solid var(--el-border-color-light);
  }

  &__coverage-box {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 2px solid #2196f3;
    background: rgba(33, 150, 243, 0.08);
    flex-shrink: 0;
  }

  &__coverage-label {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
}
</style>
