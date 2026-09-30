<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const tips = ref<any[]>([])
const turnovers = ref<any[]>([])
onMounted(async () => {
  const res = await api('/reports/suggestions?line_id=1')
  // 同车接续与串车/大间隔互斥：后端只把真正异常放进 suggestions，
  // 同车接续单放 turnovers，不会再以串车名义点名这对班次。
  tips.value = res.suggestions || []
  turnovers.value = res.turnovers || []
})
</script>
<template>
  <h1>建议</h1>
  <p class="sub">串车 / 大间隔异常建议（同车接续周转不计入异常）</p>
  <div class="card" v-for="(t,i) in tips" :key="'tip-'+i">
    <div><strong>{{ t.stop_name }}</strong> · {{ t.earlier_trip }} → {{ t.later_trip }} · 间隔 {{ t.gap_min }} 分</div>
    <p class="muted">{{ t.suggestion }}</p>
  </div>
  <p v-if="!tips.length" class="muted">暂无异常建议</p>
  <h2 v-if="turnovers.length" style="font-size:1rem;margin-top:1.2rem">同车接续（不参与串车/大间隔对打）</h2>
  <div class="card" v-for="(t,i) in turnovers" :key="'turn-'+i">
    <div><strong>{{ t.stop_name }}</strong> · {{ t.earlier_trip }} → {{ t.later_trip }} · 间隔 {{ t.gap_min }} 分</div>
    <p class="muted">{{ t.suggestion }}</p>
  </div>
</template>
