<template>
  <div class="filter-bar">
    <el-select v-model="localBank" placeholder="全部银行" clearable size="small" style="width: 130px" @change="$emit('change')">
      <el-option v-for="b in banks" :key="b" :label="b || '未知'" :value="b" />
    </el-select>
    <el-select v-model="localFlag" placeholder="全部状态" size="small" style="width: 110px" @change="$emit('change')">
      <el-option
        v-for="o in FLAG_OPTIONS"
        :key="o.value"
        :label="o.label"
        :value="o.value"
      />
    </el-select>
    <el-input
      v-model="localKeyword"
      placeholder="搜索银行/备注..."
      size="small"
      clearable
      style="width: 180px"
      @input="$emit('change')"
    />
    <el-button size="small" @click="$emit('reset')">重置</el-button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { FLAG_OPTIONS } from '../../types/wealthTypes'

const props = defineProps<{
  bank: string
  flag: number
  keyword: string
  banks: string[]
}>()

const emit = defineEmits<{
  'update:bank': [value: string]
  'update:flag': [value: number]
  'update:keyword': [value: string]
  change: []
  reset: []
}>()

const localBank = computed({
  get: () => props.bank,
  set: (val) => emit('update:bank', val),
})

const localFlag = computed({
  get: () => props.flag,
  set: (val) => emit('update:flag', val),
})

const localKeyword = computed({
  get: () => props.keyword,
  set: (val) => emit('update:keyword', val),
})
</script>

<style scoped>
.filter-bar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 16px;
}
</style>
