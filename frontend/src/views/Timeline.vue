<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { markColor, unifyStatusLabel } from '../viewHints'
const data = ref<{ stop_name: string; marks: any[] }>({ stop_name: '', marks: [] })
onMounted(async () => { data.value = await api('/reports/timeline?line_id=1') })
</script>
<template>
  <h1>时间轴明细</h1>
  <p class="sub">站点「{{ data.stop_name }}」到站分布 · 颜色与报告同一次检测一致（同车接续不标红）</p>
  <div class="card">
    <div class="tl-track">
      <div v-for="m in data.marks" :key="m.trip_no" class="tl-mark"
        :style="{ left: m.pct + '%', background: markColor(m.status) }"
        :title="m.trip_no + ' ' + m.actual_arrive + (m.status && m.status !== 'first' ? ' ' + unifyStatusLabel(m.status) : '')" />
    </div>
    <table>
      <thead><tr><th>班次</th><th>车号</th><th>到站时间</th><th>相对位置</th><th>与前班判定</th></tr></thead>
      <tbody>
        <tr v-for="m in data.marks" :key="m.trip_no">
          <td>{{ m.trip_no }}</td>
          <td>{{ m.vehicle_no || '—' }}</td>
          <td>{{ m.actual_arrive }}</td>
          <td>{{ m.pct }}%</td>
          <td>
            <span v-if="m.paired_trip">{{ m.paired_trip }} → {{ m.trip_no }}：{{ unifyStatusLabel(m.status) }}（{{ m.gap_min }}′）</span>
            <span v-else class="muted">首班，无前班</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
