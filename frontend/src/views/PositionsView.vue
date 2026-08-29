<script setup>
/** 持仓与委托:四个 Tab 覆盖完整交易闭环,3s 轮询观察撮合状态流转 */
import { ref, computed, onMounted, onBeforeUnmount, watch } from "vue";
import { useMarketStore } from "../stores/market";
import {
  fetchPositions, fetchOrders, fetchTrades, cancelOrder,
} from "../api";
import { fmtMoney, fmtSigned, fmtPct, fmtDateTime, trendClass, SIDE_LABEL } from "../utils/format";
import AnimatedNumber from "../components/AnimatedNumber.vue";
import StatusTag from "../components/StatusTag.vue";
import OrderModal from "../components/OrderModal.vue";
import EmptyState from "../components/EmptyState.vue";
import { toast } from "../composables/useToast";

const market = useMarketStore();

const tab = ref("positions");
const positionsData = ref(null);
const orders = ref([]);
const trades = ref([]);
const historyStatus = ref("");
const loading = ref(false);
const cancellingId = ref(0);

const orderVisible = ref(false);
const orderStock = ref(null);
const orderSide = ref("BUY");

let timer = null;

const summary = computed(() => positionsData.value || {
  cash: { balance: 0, frozen_cash: 0, is_vip: false },
  total_asset: 0,
  total_market_value: 0,
  total_unrealized_pl: 0,
  details: [],
});

const activeOrders = computed(() => orders.value.filter((o) => o.status === "PENDING" || o.status === "PARTIAL_FILLED"));
const historyOrders = computed(() => {
  if (!historyStatus.value) return orders.value;
  return orders.value.filter((o) => o.status === historyStatus.value);
});

async function loadPositions() {
  positionsData.value = await fetchPositions();
}
async function loadOrders() {
  orders.value = await fetchOrders({ status: "" });
}
async function loadTrades() {
  trades.value = await fetchTrades();
}
async function loadTab() {
  loading.value = true;
  try {
    if (tab.value === "positions") await loadPositions();
    else if (tab.value === "orders") await loadOrders();
    else if (tab.value === "trades") await loadTrades();
    else await loadOrders();
  } catch (e) {
    toast.error(e.friendlyMessage || "加载失败");
  } finally {
    loading.value = false;
  }
}

watch(tab, loadTab);

onMounted(() => {
  loadTab();
  loadOrders().catch(() => {});   // 预加载,保证 Tab 计数准确
  loadTrades().catch(() => {});
  timer = setInterval(() => {
    if (!document.hidden) loadTab(); // 轮询观察订单状态与资金变化
  }, 3000);
});
onBeforeUnmount(() => clearInterval(timer));

async function doCancel(order) {
  if (cancellingId.value) return;
  cancellingId.value = order.id;
  try {
    const data = await cancelOrder(order.id);
    toast.success(`已撤单:${SIDE_LABEL[order.side]} ${order.stock.name},资金/持仓已解冻`);
    orders.value = orders.value.map((o) => (o.id === order.id ? data.order : o));
    if (positionsData.value) loadPositions().catch(() => {});
  } catch (e) {
    toast.error(e.friendlyMessage || "撤单失败");
  } finally {
    cancellingId.value = 0;
  }
}

function openOrderModal(detail, side) {
  // 优先用行情 store 里的完整标的信息;缺失时降级拼装
  const full = market.stocks.find((s) => s.symbol === detail.symbol);
  if (full) {
    orderStock.value = full;
  } else {
    const symbol = detail.symbol || "";
    orderStock.value = {
      id: detail.stock_id ?? detail.id,
      symbol,
      name: detail.name,
      price: detail.market_price ?? detail.price ?? 0,
      change: 0,
      change_pct: 0,
      lot_size: symbol.startsWith("688") ? 200 : 100,
      limit_pct: symbol.startsWith("300") || symbol.startsWith("688") ? 20 : 10,
      prev_close: 0,
    };
  }
  orderSide.value = side;
  orderVisible.value = true;
}
</script>

<template>
  <div class="page">
    <!-- 资金总览 -->
    <section class="stat-row">
      <div class="panel stat-card">
        <span class="stat-label">总资产</span>
        <AnimatedNumber class="stat-value" :value="Number(summary.total_asset ?? 0)" />
      </div>
      <div class="panel stat-card">
        <span class="stat-label">可用资金</span>
        <AnimatedNumber class="stat-value" :value="Number(summary.cash?.balance ?? 0)" />
      </div>
      <div class="panel stat-card">
        <span class="stat-label">冻结资金</span>
        <AnimatedNumber class="stat-value flat" :value="Number(summary.cash?.frozen_cash ?? 0)" />
      </div>
      <div class="panel stat-card">
        <span class="stat-label">持仓市值</span>
        <AnimatedNumber class="stat-value" :value="Number(summary.total_market_value ?? 0)" />
      </div>
      <div class="panel stat-card">
        <span class="stat-label">浮动盈亏</span>
        <AnimatedNumber class="stat-value" :class="trendClass(summary.total_unrealized_pl)"
          :value="Number(summary.total_unrealized_pl ?? 0)" />
      </div>
    </section>

    <section class="panel section-gap">
      <div class="tabs" role="tablist">
        <button class="tab" :class="{ active: tab === 'positions' }" role="tab" @click="tab = 'positions'">
          持仓 <span class="count">{{ summary.details.length }}</span>
        </button>
        <button class="tab" :class="{ active: tab === 'orders' }" role="tab" @click="tab = 'orders'">
          当前委托 <span class="count">{{ activeOrders.length }}</span>
        </button>
        <button class="tab" :class="{ active: tab === 'trades' }" role="tab" @click="tab = 'trades'">
          成交记录 <span class="count">{{ trades.length }}</span>
        </button>
        <button class="tab" :class="{ active: tab === 'history' }" role="tab" @click="tab = 'history'">
          历史委托
        </button>
        <span class="live-hint"><span class="spinner"></span> 3s 自动刷新</span>
      </div>

      <!-- 持仓 -->
      <div v-if="tab === 'positions'" class="table-wrap">
        <table class="data" v-if="summary.details.length">
          <thead>
            <tr>
              <th>代码 / 名称</th><th>持仓</th><th>可用</th><th>摊薄成本</th>
              <th>现价</th><th>市值</th><th>浮动盈亏</th><th>收益率</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in summary.details" :key="p.position_id">
              <td><span class="symbol-badge">{{ p.symbol }}</span> {{ p.name }}</td>
              <td class="num">{{ p.quantity }}</td>
              <td class="num">{{ p.available_quantity }}</td>
              <td class="num">{{ fmtMoney(p.avg_price) }}</td>
              <td class="num">{{ fmtMoney(p.market_price) }}</td>
              <td class="num">{{ fmtMoney(p.market_value) }}</td>
              <td class="num" :class="trendClass(p.unrealized_pl)">{{ fmtSigned(p.unrealized_pl) }}</td>
              <td>
                <span class="pct-pill" :class="trendClass(p.unrealized_pl)">
                  {{ fmtPct((p.unrealized_pl / Math.max(p.avg_price * p.quantity, 0.01)) * 100) }}
                </span>
              </td>
              <td>
                <div class="actions">
                  <button class="btn btn-sm btn-down" @click="openOrderModal(p, 'SELL')">卖出</button>
                  <button class="btn btn-sm btn-up" @click="openOrderModal(p, 'BUY')">加仓</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-else glyph="📊" title="暂无持仓" sub="到行情总览挑选标的,开启第一笔模拟交易">
          <router-link class="btn btn-primary" :to="{ name: 'home' }">去看看行情</router-link>
        </EmptyState>
      </div>

      <!-- 当前委托 -->
      <div v-if="tab === 'orders'" class="table-wrap">
        <table class="data" v-if="activeOrders.length">
          <thead>
            <tr>
              <th>时间</th><th>代码 / 名称</th><th>方向</th><th>类型</th>
              <th>委托价</th><th>数量</th><th>已成交</th><th>冻结</th><th>状态</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="o in activeOrders" :key="o.id">
              <td class="num dim">{{ fmtDateTime(o.created_at) }}</td>
              <td><span class="symbol-badge">{{ o.stock.symbol }}</span> {{ o.stock.name }}</td>
              <td><span :class="o.side === 'BUY' ? 'up' : 'down'" class="bold">{{ SIDE_LABEL[o.side] }}</span></td>
              <td>{{ o.order_type === "LIMIT" ? "限价" : "市价" }}</td>
              <td class="num">{{ o.price === null ? "市价" : fmtMoney(o.price) }}</td>
              <td class="num">{{ o.quantity }}</td>
              <td class="num">{{ o.filled_quantity }}</td>
              <td class="num dim">
                {{ o.frozen_amount > 0 ? fmtMoney(o.frozen_amount) : o.frozen_quantity > 0 ? `${o.frozen_quantity} 股` : "--" }}
              </td>
              <td><StatusTag :status="o.status" /></td>
              <td>
                <button class="btn btn-sm btn-danger" :disabled="cancellingId === o.id" @click="doCancel(o)">
                  {{ cancellingId === o.id ? "撤单中…" : "撤单" }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-else glyph="⏳" title="没有在途委托" sub="限价单未即时成交时会挂在这里,可随时撤单" />
      </div>

      <!-- 成交记录 -->
      <div v-if="tab === 'trades'" class="table-wrap">
        <table class="data" v-if="trades.length">
          <thead>
            <tr><th>时间</th><th>代码 / 名称</th><th>方向</th><th>数量</th><th>成交价</th><th>金额</th><th>费用</th></tr>
          </thead>
          <tbody>
            <tr v-for="t in trades" :key="t.id">
              <td class="num dim">{{ fmtDateTime(t.created_at) }}</td>
              <td><span class="symbol-badge">{{ t.stock.symbol }}</span> {{ t.stock.name }}</td>
              <td><span :class="t.side === 'BUY' ? 'up' : 'down'" class="bold">{{ SIDE_LABEL[t.side] }}</span></td>
              <td class="num">{{ t.quantity }}</td>
              <td class="num">{{ fmtMoney(t.price) }}</td>
              <td class="num">{{ fmtMoney(t.amount) }}</td>
              <td class="num dim">{{ fmtMoney(t.fee) }}</td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-else glyph="🧾" title="暂无成交" sub="订单成交后,逐笔回报会出现在这里" />
      </div>

      <!-- 历史委托 -->
      <div v-if="tab === 'history'">
        <div class="chips">
          <button class="btn btn-sm" :class="{ 'chip-on': historyStatus === '' }" @click="historyStatus = ''">全部</button>
          <button class="btn btn-sm" :class="{ 'chip-on': historyStatus === 'FILLED' }" @click="historyStatus = 'FILLED'">已成交</button>
          <button class="btn btn-sm" :class="{ 'chip-on': historyStatus === 'PARTIAL_FILLED' }" @click="historyStatus = 'PARTIAL_FILLED'">部分成交</button>
          <button class="btn btn-sm" :class="{ 'chip-on': historyStatus === 'CANCELLED' }" @click="historyStatus = 'CANCELLED'">已撤单</button>
        </div>
        <div class="table-wrap">
          <table class="data" v-if="historyOrders.length">
            <thead>
              <tr>
                <th>时间</th><th>代码 / 名称</th><th>方向</th><th>委托价</th>
                <th>数量</th><th>已成交</th><th>成交均价</th><th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="o in historyOrders" :key="o.id">
                <td class="num dim">{{ fmtDateTime(o.created_at) }}</td>
                <td><span class="symbol-badge">{{ o.stock.symbol }}</span> {{ o.stock.name }}</td>
                <td><span :class="o.side === 'BUY' ? 'up' : 'down'" class="bold">{{ SIDE_LABEL[o.side] }}</span></td>
                <td class="num">{{ o.price === null ? "市价" : fmtMoney(o.price) }}</td>
                <td class="num">{{ o.quantity }}</td>
                <td class="num">{{ o.filled_quantity }}</td>
                <td class="num">{{ o.avg_fill_price > 0 ? fmtMoney(o.avg_fill_price) : "--" }}</td>
                <td><StatusTag :status="o.status" /></td>
              </tr>
            </tbody>
          </table>
          <EmptyState v-else glyph="🗂" title="没有符合条件的委托" />
        </div>
      </div>
    </section>

    <OrderModal v-model="orderVisible" :stock="orderStock" :initial-side="orderSide" @placed="loadTab" />
  </div>
</template>

<style scoped>
.stat-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
.stat-card { padding: 14px 16px; }
.stat-label { display: block; font-size: 12px; color: var(--text-3); margin-bottom: 5px; }
.stat-value { font-size: 20px; font-weight: 800; }
.live-hint { margin-left: auto; align-self: center; color: var(--text-3); font-size: 11.5px; display: inline-flex; gap: 6px; align-items: center; }
.actions { display: flex; gap: 7px; }
.dim { color: var(--text-3); }
.bold { font-weight: 700; }
.chips { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.chip-on { border-color: var(--brand-a); color: var(--brand-a); box-shadow: var(--glow-brand); }
@media (max-width: 1000px) {
  .stat-row { grid-template-columns: repeat(2, 1fr); }
}
</style>
