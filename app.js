const $ = (id) => document.getElementById(id);

const fmtCny = (value, digits = 2) =>
  new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);

const fmtUsd = (value) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);

function formatDate(value) {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

async function getJson(path) {
  const joiner = path.includes("?") ? "&" : "?";
  const response = await fetch(`${path}${joiner}v=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

function setStatus(ok, text) {
  $("status-dot").className = `status-dot ${ok ? "ok" : "error"}`;
  $("status-text").textContent = text;
}

function renderLatest(latest) {
  const products = [...latest.products].sort((a, b) => a.face_value_try - b.face_value_try);
  const best = products.reduce((a, b) =>
    a.cny_per_100_try <= b.cny_per_100_try ? a : b
  );

  $("best-face").textContent = `${best.face_value_try} TRY`;
  $("best-cost").textContent = `${fmtCny(best.cny_per_100_try, 2)} / 100 TRY`;
  $("fx-rate").textContent = Number(latest.exchange_rate.usd_cny).toFixed(4);
  $("fx-source").textContent = latest.exchange_rate.source || "公开汇率源";
  $("product-count").textContent = `${products.length} 个`;
  $("updated-at").textContent = `北京时间 ${formatDate(latest.checked_at)} 更新`;

  const ageMinutes = (Date.now() - new Date(latest.checked_at).getTime()) / 60000;
  if (ageMinutes > 90) {
    setStatus(false, `数据已超过 ${Math.floor(ageMinutes)} 分钟未更新，请检查 Actions`);
  } else {
    setStatus(true, "采集正常 · SEAGM");
  }

  $("price-body").innerHTML = products
    .map((item) => {
      const ratio = item.cny_per_100_try / best.cny_per_100_try;
      const isBest = ratio <= 1.002;
      const label = isBest ? "最低" : ratio <= 1.02 ? "不错" : "正常";
      return `
        <tr class="${isBest ? "best-row" : ""}">
          <td><strong>${item.face_value_try} TRY</strong></td>
          <td>${fmtUsd(item.price_usd)}</td>
          <td>${fmtCny(item.price_cny)}</td>
          <td><strong>${fmtCny(item.cny_per_100_try, 2)}</strong></td>
          <td><span class="badge ${isBest ? "best" : ""}">${label}</span></td>
        </tr>`;
    })
    .join("");

  const select = $("face-select");
  select.innerHTML = products
    .map((item) => `<option value="${item.face_value_try}">${item.face_value_try} TRY</option>`)
    .join("");

  const preferred = products.find((item) => item.face_value_try === 1000) || best;
  select.value = String(preferred.face_value_try);
}

function historyPoints(history, faceValue) {
  return (history.snapshots || [])
    .map((snapshot) => {
      const item = (snapshot.products || []).find(
        (product) => Number(product.face_value_try) === Number(faceValue)
      );
      if (!item) return null;
      return {
        time: new Date(snapshot.checked_at).getTime(),
        value: Number(item.cny_per_100_try),
      };
    })
    .filter((item) => item && Number.isFinite(item.time) && Number.isFinite(item.value))
    .sort((a, b) => a.time - b.time);
}

function averageSince(points, days) {
  const cutoff = Date.now() - days * 86400000;
  const values = points.filter((p) => p.time >= cutoff).map((p) => p.value);
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function downsample(points, maxPoints = 280) {
  if (points.length <= maxPoints) return points;
  const step = Math.ceil(points.length / maxPoints);
  return points.filter((_, index) => index % step === 0 || index === points.length - 1);
}

function renderChart(history, faceValue) {
  const all = historyPoints(history, faceValue);
  const cutoff30 = Date.now() - 30 * 86400000;
  const recent = all.filter((p) => p.time >= cutoff30);

  const avg7 = averageSince(all, 7);
  const avg30 = averageSince(all, 30);
  const low = all.length ? Math.min(...all.map((p) => p.value)) : null;

  $("avg-7").textContent = avg7 == null ? "—" : `${fmtCny(avg7, 2)} / 100`;
  $("avg-30").textContent = avg30 == null ? "—" : `${fmtCny(avg30, 2)} / 100`;
  $("history-low").textContent = low == null ? "—" : `${fmtCny(low, 2)} / 100`;

  if (recent.length < 2) {
    $("chart").innerHTML = '<div class="empty">历史数据积累后将在这里显示趋势</div>';
    return;
  }

  const points = downsample(recent);
  const width = 900;
  const height = 250;
  const padX = 46;
  const padY = 28;
  const minX = points[0].time;
  const maxX = points[points.length - 1].time || minX + 1;
  const values = points.map((p) => p.value);
  let minY = Math.min(...values);
  let maxY = Math.max(...values);
  const spread = Math.max(maxY - minY, Math.abs(minY) * 0.015, 0.05);
  minY -= spread * 0.35;
  maxY += spread * 0.35;

  const x = (time) => padX + ((time - minX) / (maxX - minX || 1)) * (width - padX * 2);
  const y = (value) => height - padY - ((value - minY) / (maxY - minY || 1)) * (height - padY * 2);

  const line = points.map((p) => `${x(p.time).toFixed(1)},${y(p.value).toFixed(1)}`).join(" ");
  const area = `${padX},${height - padY} ${line} ${width - padX},${height - padY}`;
  const midY = (minY + maxY) / 2;

  $("chart").innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-label="${faceValue} TRY 最近 30 天价格趋势">
      <line class="axis" x1="${padX}" y1="${padY}" x2="${padX}" y2="${height - padY}" />
      <line class="axis" x1="${padX}" y1="${height - padY}" x2="${width - padX}" y2="${height - padY}" />
      <text x="6" y="${padY + 4}">${minY.toFixed(2)}</text>
      <text x="6" y="${y(midY) + 4}">${midY.toFixed(2)}</text>
      <text x="6" y="${height - padY + 4}">${maxY.toFixed(2)}</text>
      <polygon class="area" points="${area}" />
      <polyline class="line" points="${line}" />
      <text x="${padX}" y="${height - 7}">${formatDate(points[0].time)}</text>
      <text x="${width - 112}" y="${height - 7}">${formatDate(points[points.length - 1].time)}</text>
    </svg>`;
}

async function main() {
  try {
    const [latest, history] = await Promise.all([
      getJson("data/latest.json"),
      getJson("data/history.json").catch(() => ({ snapshots: [] })),
    ]);

    if (latest.status !== "ok" || !Array.isArray(latest.products) || !latest.products.length) {
      throw new Error("latest.json 数据格式异常");
    }

    renderLatest(latest);
    renderChart(history, $("face-select").value);
    $("face-select").addEventListener("change", (event) => {
      renderChart(history, event.target.value);
    });
  } catch (error) {
    console.error(error);
    setStatus(false, "暂时读取不到价格数据，请稍后再试或检查 GitHub Actions");
    $("price-body").innerHTML = '<tr><td colspan="5" class="empty">暂无可用数据</td></tr>';
  }
}

main();
