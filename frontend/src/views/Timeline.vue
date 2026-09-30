<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const data = ref<{ stop_name: string; marks: any[] }>({ stop_name: '', marks: [] })
onMounted(async () => { data.value = await api('/reports/timeline?line_id=1') })
function markColor(m: any) {
  if (m.pair_status === 'bunching') return 'var(--bg-red)'
  if (m.pair_status === 'large_gap') return 'var(--bg-amber)'
  if (m.pair_status === 'same_vehicle') return 'var(--bg-dim)'
  return 'var(--bg-cyan)'
}
function pairLabel(s: string) {
  if (s === 'bunching') return '串车'
  if (s === 'large_gap') return '大间隔'
  if (s === 'same_vehicle') return '同车接续'
  if (s === 'normal') return '正常'
  return '—'
}
</script>
<template>
  <h1>时间轴明细</h1>
  <p class="sub">站点「{{ data.stop_name }}」到站分布（按与前一班的实际配对状态着色：同车接续为灰，不计串车/大间隔）</p>
  <div class="card">
    <div class="tl-track">
      <div v-for="m in data.marks" :key="m.trip_no" class="tl-mark"
        :style="{ left: m.pct + '%', background: markColor(m) }"
        :title="m.trip_no + ' ' + (m.vehicle_no || '未填车号') + ' ' + m.actual_arrive" />
    </div>
    <table>
      <thead><tr><th>班次</th><th>车号</th><th>到站时间</th><th>相对位置</th><th>与前一班</th></tr></thead>
      <tbody>
        <tr v-for="m in data.marks" :key="m.trip_no">
          <td>{{ m.trip_no }}</td>
          <td>{{ m.vehicle_no || '未填' }}</td>
          <td>{{ m.actual_arrive }}</td>
          <td>{{ m.pct }}%</td>
          <td>{{ pairLabel(m.pair_status) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
