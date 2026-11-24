<script setup>
/** 全站唯一的下单弹窗:限价/市价 + 整手校验 + 冻结预估 + 成交反馈 */
import { ref, computed, watch } from "vue";
import AppModal from "./AppModal.vue";
import { placeOrder, fetchPositions } from "../api";
import { lotError, priceError, estimateFee, parseQuantity } from "../utils/validate";
import { fmtMoney } from "../utils/format";
import { toast } from "../composables/useToast";

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  stock: { type: Object, default: null },
  initialSide: { type: String, default: "BUY" },
});
const emit = defineEmits(["update:modelValue", "placed"]);

const side = ref("BUY");
const orderType = ref("LIMIT");
const price = ref("");
const quantity = ref("");
const submitting = ref(false);
const formError = ref("");

const cash = ref(null);        // { balance, frozen_cash }
const holding = ref(null);     // { quantity, available_quantity }

const lot = computed(() => props.stock?.lot_size || 100);
const limitLow = computed(() => {
  const pc = Number(props.stock?.prev_close || 0);
  const pct = Number(props.stock?.limit_pct || 10);
  return pc > 0 ? +(pc * (1 - pct / 100)).toFixed(2) : 0;
});
const limitHigh = computed(() => {
  const pc = Number(props.stock?.prev_close || 0);
  const pct = Number(props.stock?.limit_pct || 10);
  return pc > 0 ? +(pc * (1 + pct / 100)).toFixed(2) : 0;
});

const qtyNum = computed(() => parseQuantity(quantity.value) || 0);
const estAmount = computed(() => (orderType.value === "LIMIT" ? Number(price.value || 0) : Number(props.stock?.price || 0)) * qtyNum.value);
const feeInfo = computed(() => estimateFee(estAmount.value, side.value));

const availableCash = computed(() => (cash.value ? Number(cash.value.balance) : null));
const availableShares = computed(() => (holding.value ? holding.value.available_quantity : 0));

const quickLots = computed(() => [1, 2, 3, 5, 10].map((n) => n * lot.value));

watch(
  () => [props.modelValue, props.stock?.id],
  ([open]) => {
    if (!open || !props.stock) return;
    formError.value = "";
    submitting.value = false;
    side.value = props.initialSide === "SELL" ? "SELL" : "BUY";
    orderType.value = "LIMIT";
    price.value = String(props.stock.price ?? "");
    quantity.value = "";
    cash.value = null;
    holding.value = null;
    refreshAccount();
  },
  { immediate: true }
);

async function refreshAccount() {
  try {
    const data = await fetchPositions();
    cash.value = data.cash;
    holding.value = data.details.find((d) => d.stock_id === props.stock?.id) || null;
  } catch { /* 未登录等场景静默 */ }
}

function setPrice(pct) {
  // 按涨跌停幅度快速改价
  if (!props.stock) return;
  const pc = Number(props.stock.price);
  price.value = (pc * pct).toFixed(2);
}

function validate() {
  if (!props.stock) return "未选择标的";
  const qtyErr = lotError(quantity.value, lot.value, {
    side: side.value,
    available: availableShares.value,
  });
  if (qtyErr) return qtyErr;
  const priceErr = priceError(price.value, {
    required: orderType.value === "LIMIT",
    low: limitLow.value,
    high: limitHigh.value,
  });
  if (priceErr) return priceErr;
  if (side.value === "BUY" && availableCash.value !== null) {
    const need = feeInfo.value.total;
    if (need > availableCash.value) return `可用资金不足:预计需 ${fmtMoney(need)},可用 ${fmtMoney(availableCash.value)}`;
  }
  if (side.value === "SELL" && holding.value && qtyNum.value > availableShares.value) {
    return `可用持仓不足:可用 ${availableShares.value} 股(含在途卖出)`;
  }
  return null;
}

async function submit() {
  formError.value = validate();
  if (formError.value) return;
  submitting.value = true;
  try {
    const data = await placeOrder({
      stock_id: props.stock.id,
      side: side.value,
      quantity: qtyNum.value,
      order_type: orderType.value,
      price: orderType.value === "LIMIT" ? Number(price.value) : undefined,
    });
    const status = data.order.status;
    if (status === "FILLED") {
      toast.success(`已成交:${side.value === "BUY" ? "买入" : "卖出"} ${props.stock.name} ${qtyNum.value} 股 @ ${fmtMoney(data.order.avg_fill_price)}`);
    } else if (status === "PARTIAL_FILLED") {
      toast.info(`部分成交 ${data.order.filled_quantity}/${qtyNum.value} 股,余量等待撮合`);
    } else {
      toast.success("委托已提交,等待撮合 · 可在「持仓与委托 → 当前委托」撤单");
    }
    emit("update:modelValue", false);
    emit("placed", data);
  } catch (e) {
    formError.value = e.friendlyMessage || "下单失败";
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <AppModal :model-value="modelValue" title="委托下单" @update:model-value="emit('update:modelValue', $event)">
    <div v-if="stock" class="order-body">
      <div class="stock-line">
        <span class="symbol-badge">{{ stock.symbol }}</span>
        <strong>{{ stock.name }}</strong>
        <span class="price num" :class="stock.change >= 0 ? 'up' : 'down'">{{ fmtMoney(stock.price) }}</span>
        <span class="hint">每手 {{ lot }} 股 · 涨跌停 {{ limitLow.toFixed(2) }} ~ {{ limitHigh.toFixed(2) }}</span>
      </div>

      <div class="seg-row">
        <div class="seg" role="tablist" aria-label="方向">
          <button :class="{ on: side === 'BUY', buy: side === 'BUY' }" @click="side = 'BUY'">买入</button>
          <button :class="{ on: side === 'SELL', sell: side === 'SELL' }" @click="side = 'SELL'">卖出</button>
        </div>
        <div class="seg" role="tablist" aria-label="类型">
          <button :class="{ on: orderType === 'LIMIT' }" @click="orderType = 'LIMIT'">限价</button>
          <button :class="{ on: orderType === 'MARKET' }" @click="orderType = 'MARKET'">市价</button>
        </div>
      </div>

      <div class="field">
        <label :for="`price-${stock.id}`">委托价格</label>
        <input :id="`price-${stock.id}`" v-model="price" class="input num" type="number" step="0.01" min="0"
          :disabled="orderType === 'MARKET'" :placeholder="orderType === 'MARKET' ? '以当前市价成交' : '输入价格'" />
        <div v-if="orderType === 'LIMIT'" class="quick-price">
          <button class="btn btn-sm btn-ghost" @click="setPrice(0.98)">跌2%</button>
          <button class="btn btn-sm btn-ghost" @click="setPrice(1)">现价</button>
          <button class="btn btn-sm btn-ghost" @click="setPrice(1.02)">涨2%</button>
          <button class="btn btn-sm btn-ghost" @click="price = limitHigh.toFixed(2)">涨停</button>
        </div>
      </div>

      <div class="field">
        <label :for="`qty-${stock.id}`">数量(股)</label>
        <input :id="`qty-${stock.id}`" v-model="quantity" class="input num" type="number" step="1" min="0"
          :placeholder="`整手 ${lot} 的倍数`" />
        <div class="quick-price">
          <button v-for="q in quickLots" :key="q" class="btn btn-sm btn-ghost" @click="quantity = String(q)">
            {{ q / lot }}手
          </button>
          <button v-if="side === 'SELL' && availableShares > 0" class="btn btn-sm btn-ghost"
            @click="quantity = String(availableShares)">清仓{{ availableShares }}</button>
          <button class="btn btn-sm btn-ghost" @click="quantity = ''">清空</button>
        </div>
        <div v-if="side === 'SELL'" class="field-hint">可用持仓:{{ availableShares }} 股</div>
        <div v-else class="field-hint">
          可用资金:{{ availableCash === null ? "--" : fmtMoney(availableCash) }}
        </div>
      </div>

      <div class="estimate num">
        <span>预计金额 {{ fmtMoney(estAmount) }}</span>
        <span>费用 {{ fmtMoney(feeInfo.fee) }}(佣金{{ side === 'SELL' ? '+印花税' : '' }})</span>
        <span :class="side === 'BUY' ? 'up' : 'down'">
          {{ side === "BUY" ? "冻结" : "到账" }} ≈ {{ fmtMoney(feeInfo.total) }}
        </span>
      </div>

      <div v-if="formError" class="field-error" role="alert">⚠ {{ formError }}</div>

      <button class="btn btn-block" :class="side === 'BUY' ? 'btn-up' : 'btn-down'" :disabled="submitting"
        @click="submit">
        <span v-if="submitting" class="spinner"></span>
        {{ submitting ? "提交中…" : `${side === "BUY" ? "买入" : "卖出"} ${stock.name}` }}
      </button>
    </div>
  </AppModal>
</template>

<style scoped>
.order-body { display: flex; flex-direction: column; gap: 4px; }
.stock-line { display: flex; align-items: center; gap: 9px; margin-bottom: 12px; flex-wrap: wrap; }
.price { font-size: 20px; font-weight: 800; }
.hint { font-size: 11px; color: var(--text-3); }
.seg-row { display: flex; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
.seg { display: flex; background: var(--inset-bg); border: 1px solid var(--border); border-radius: var(--radius); padding: 3px; gap: 3px; }
.seg button {
  border: none; background: transparent; color: var(--text-2);
  padding: 6px 18px; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 13px;
  transition: all 0.18s;
}
.seg button:hover { color: var(--text-1); }
.seg button.on.buy { background: var(--up); color: #fff; box-shadow: 0 0 14px rgba(255, 77, 94, 0.4); }
.seg button.on.sell { background: var(--down); color: #04261c; box-shadow: 0 0 14px rgba(0, 212, 156, 0.4); }
.seg button.on:not(.buy):not(.sell) { background: rgba(34, 211, 238, 0.16); color: var(--brand-a); }
.quick-price { display: flex; gap: 6px; margin-top: 7px; flex-wrap: wrap; }
.estimate {
  display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap;
  padding: 10px 12px; border-radius: var(--radius);
  background: var(--inset-bg-soft); border: 1px dashed var(--border);
  font-size: 12px; color: var(--text-2); margin: 8px 0 4px;
}
</style>
