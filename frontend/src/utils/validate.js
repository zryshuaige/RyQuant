/** 下单校验与费用预估(与后端规则保持一致,纯函数,可单测) */

export function parseQuantity(raw) {
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0 || !Number.isInteger(n)) return null;
  return n;
}

/**
 * 手数校验:买入必须整手;卖出需整手或一次性清仓全部可用持仓。
 * 返回错误信息字符串,合法返回 null。
 */
export function lotError(quantity, lotSize, { side = "BUY", available = 0 } = {}) {
  const qty = Number(quantity);
  if (!Number.isFinite(qty) || qty <= 0 || !Number.isInteger(qty)) return "数量必须为正整数";
  const lot = Number(lotSize) || 100;
  if (side === "BUY") {
    if (qty % lot !== 0) return `买入数量必须为 ${lot} 的整数倍`;
  } else if (qty % lot !== 0 && qty !== Number(available)) {
    return `卖出数量需为 ${lot} 的整数倍,或一次性清仓全部可用持仓(${available} 股)`;
  }
  return null;
}

/** 价格校验:required 时必须 > 0;提供涨跌停范围时校验区间。 */
export function priceError(price, { required = true, low = 0, high = 0 } = {}) {
  if (price === "" || price === null || price === undefined) {
    return required ? "请输入委托价格" : null;
  }
  const p = Number(price);
  if (!Number.isFinite(p) || p <= 0) return "委托价格必须大于 0";
  if (low > 0 && high > 0 && (p < low || p > high)) {
    return `委托价超出涨跌停范围 ${low.toFixed(2)} ~ ${high.toFixed(2)}`;
  }
  return null;
}

/** 费用预估:佣金 max(金额×0.025%, 5 元),卖出另加印花税 0.05%(与后端 FEES 一致)。 */
export function estimateFee(amount, side = "BUY") {
  const amt = Number(amount);
  if (!Number.isFinite(amt) || amt <= 0) return { commission: 0, stamp: 0, fee: 0, total: 0 };
  const commission = Math.max(amt * 0.00025, 5);
  const stamp = side === "SELL" ? amt * 0.0005 : 0;
  const fee = Math.round((commission + stamp) * 100) / 100;
  return {
    commission: Math.round(commission * 100) / 100,
    stamp: Math.round(stamp * 100) / 100,
    fee,
    total: side === "BUY" ? Math.round((amt + fee) * 100) / 100 : Math.round((amt - fee) * 100) / 100,
  };
}
