export function formatCurrencyValue(v) {
  if (v === null || v === undefined || v === '') return null;
  const n = Number(String(v).replace(/[^0-9\-.,]/g, ''));
  if (Number.isNaN(n)) return null;
  return n;
}

export function formatCurrencyDisplay(v, opts = { symbol: 'R$' }) {
  const n = formatCurrencyValue(v);
  if (n === null) return '—';
  return `${opts.symbol} ${n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default { formatCurrencyValue, formatCurrencyDisplay };
