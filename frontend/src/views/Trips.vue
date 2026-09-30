<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const trips = ref<any[]>([])
const events = ref<any[]>([])
const saving = ref<number | null>(null)
onMounted(async () => {
  trips.value = await api('/trips')
  await runDetection()
})
async function runDetection() {
  try {
    events.value = (await api('/reports/run?line_id=1', { method: 'POST' })).events || []
  } catch { events.value = [] }
}
async function saveVehicle(r: any) {
  saving.value = r.id
  try {
    const updated = await api(`/trips/${r.id}`, { method: 'PATCH', body: JSON.stringify({ vehicle_no: r.vehicle_no }) })
    r.vehicle_no = updated.vehicle_no
    await runDetection()
  } catch {
    // 保存失败：恢复成服务端现值，并按库里的车号重检，绝不用未落库的号配对。
    trips.value = await api('/trips')
    await runDetection()
  } finally { saving.value = null }
}
function blurTarget(e: Event) {
  (e.target as HTMLInputElement | null)?.blur()
}
function stripClass(s: string) {
  return s === 'bunching' ? 'bg-bunch' : s === 'large_gap' ? 'bg-large' : s === 'same_vehicle' ? 'bg-same' : ''
}
function badgeClass(s: string) {
  return s === 'bunching' ? 'badge-bad' : s === 'large_gap' ? 'badge-warn' : s === 'same_vehicle' ? 'badge-info' : 'badge-ok'
}
function label(s: string) {
  return s === 'bunching' ? '串车' : s === 'large_gap' ? '大间隔' : s === 'same_vehicle' ? '同车接续' : '正常'
}
</script>
<template>
  <h1>班次 · 间隔条带</h1>
  <p class="sub">左侧班次清单（车辆编号可改），右侧串车/间隔竖直条带</p>
  <p class="muted">车号按卡片现值检测：同车号邻班记同车接续，与串车/大间隔互斥</p>
  <div class="bg-split">
    <aside class="bg-trip-col">
      <h2>班次列表</h2>
      <div v-for="r in trips" :key="r.id ?? r.trip_no" class="bg-trip-row">
        <div>
          <div>{{ r.trip_no }}</div>
          <div class="bg-trip-meta">
            线路 {{ r.line_id }} · 车
            <input
              v-model="r.vehicle_no"
              class="bg-veh-input"
              :disabled="saving === r.id"
              placeholder="未填"
              @change="saveVehicle(r)"
              @keyup.enter="blurTarget"
            />
          </div>
        </div>
        <div class="bg-trip-meta">{{ r.planned_depart }}</div>
      </div>
    </aside>
    <div class="bg-strip-col">
      <article
        v-for="(e, i) in events"
        :key="i"
        class="bg-gap-strip"
        :class="stripClass(e.status)"
      >
        <header>{{ e.stop_name }}</header>
        <div class="bg-gap-body">
          <div class="bg-gap-val">{{ e.gap_min }}′</div>
          <div>计划 {{ e.planned_headway_min }}′</div>
          <div>{{ e.earlier_trip }} → {{ e.later_trip }}</div>
          <span class="badge" :class="badgeClass(e.status)">
            {{ label(e.status) }}
          </span>
        </div>
      </article>
      <p v-if="!events.length" class="muted">暂无间隔事件</p>
    </div>
  </div>
</template>
