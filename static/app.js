/* ForgeLedger client — Mourad.Soltani */
const $ = (s) => document.querySelector(s);

async function api(path, opts) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (res.status === 204) return null;
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function money(n, currency = "USD") {
  try {
    return Number(n || 0).toLocaleString(undefined, {
      style: "currency",
      currency: currency || "USD",
    });
  } catch (_) {
    return `${Number(n || 0).toFixed(2)} ${currency || "USD"}`;
  }
}

async function refreshStats() {
  const s = await api("/api/stats");
  $("#stats").innerHTML = [
    ["Clients", s.clients],
    ["Invoices", s.invoices],
    ["Billed", money(s.billed)],
    ["Paid", money(s.paid)],
    ["Outstanding", money(s.outstanding)],
    ["Net", money(s.net)],
  ]
    .map(([k, v]) => `<div class="stat"><b>${v}</b><span>${k}</span></div>`)
    .join("");
}

async function refreshClients() {
  const rows = await api("/api/clients");
  $("#client-list").innerHTML = rows
    .map(
      (c) => `<article class="item"><div class="row"><h3>${c.name}</h3><span>#${c.id}</span></div>
      <p>${c.company || "Independent"} · ${c.email || "no email"}</p>
      <p>${c.notes || ""}</p></article>`
    )
    .join("");
  const sel = $("#invoice-client");
  sel.innerHTML = rows.map((c) => `<option value="${c.id}">${c.name}</option>`).join("");
}

async function refreshInvoices() {
  const rows = await api("/api/invoices");
  $("#invoice-list").innerHTML = rows
    .map(
      (i) => `<article class="item"><div class="row"><h3>${i.number}</h3><span class="status">${i.status}</span></div>
      <p>${money(i.total, i.currency)} · client #${i.client_id}</p>
      <p>${(i.items || []).map((x) => x.description).join(", ")}</p>
      <div class="row actions">
        <button data-pay="${i.id}">Mark paid</button>
        <a class="btn-link" href="/api/invoices/${i.id}/pdf" target="_blank" rel="noopener">PDF</a>
        <button data-checkout="${i.id}">Checkout</button>
        <button data-email="${i.id}">Email</button>
      </div></article>`
    )
    .join("");
}

async function applyBrand() {
  try {
    const b = await api("/api/brand");
    const foot = document.querySelector("footer");
    if (foot) foot.innerHTML = b.footer || foot.innerHTML;
    const badge = document.querySelector(".badge");
    if (badge) badge.textContent = `v1.1 · ${b.studio_name || "signed"}`;
  } catch (_) {}
}

async function refreshExpenses() {
  const rows = await api("/api/expenses");
  $("#expense-list").innerHTML = rows
    .map(
      (e) => `<article class="item"><div class="row"><h3>${money(e.amount)}</h3><span>${e.category}</span></div>
      <p>${e.description} · ${e.billable ? "billable" : "overhead"}</p></article>`
    )
    .join("");
}

async function refreshProposals() {
  const rows = await api("/api/proposals");
  $("#proposal-list").innerHTML = rows
    .map(
      (p) => `<article class="item"><h3>${p.title}</h3><p>${p.client_name} · ${money(p.investment)}</p>
      <p>${p.body}</p></article>`
    )
    .join("");
}

async function boot() {
  await Promise.all([
    applyBrand(),
    refreshStats(),
    refreshClients(),
    refreshInvoices(),
    refreshExpenses(),
    refreshProposals(),
  ]);
}

document.querySelectorAll(".tabs button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tabs button").forEach((b) => b.classList.remove("on"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("on"));
    btn.classList.add("on");
    document.getElementById(btn.dataset.tab).classList.add("on");
  });
});

$("#client-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  await api("/api/clients", {
    method: "POST",
    body: JSON.stringify(Object.fromEntries(f)),
  });
  e.target.reset();
  await boot();
});

document.getElementById("add-line")?.addEventListener("click", () => {
  const box = document.getElementById("line-items");
  const row = document.createElement("div");
  row.className = "line-row";
  row.innerHTML = `
    <input name="item_desc" placeholder="Line item description" required />
    <input name="qty" type="number" step="0.1" value="1" />
    <input name="unit_price" type="number" step="0.01" placeholder="Unit price" required />
    <button type="button" class="ghost remove-line">×</button>`;
  box.appendChild(row);
});

document.getElementById("line-items")?.addEventListener("click", (e) => {
  if (e.target.classList.contains("remove-line")) {
    const rows = document.querySelectorAll("#line-items .line-row");
    if (rows.length > 1) e.target.closest(".line-row").remove();
  }
});

$("#invoice-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  const descs = f.getAll("item_desc");
  const qtys = f.getAll("qty");
  const prices = f.getAll("unit_price");
  const items = descs.map((d, i) => ({
    description: d,
    qty: Number(qtys[i] || 1),
    unit_price: Number(prices[i] || 0),
  })).filter((x) => x.description);
  if (!items.length) return;
  await api("/api/invoices", {
    method: "POST",
    body: JSON.stringify({
      client_id: Number(f.get("client_id")),
      status: f.get("status"),
      currency: f.get("currency") || "USD",
      items,
    }),
  });
  e.target.reset();
  const box = document.getElementById("line-items");
  box.innerHTML = `<div class="line-row">
    <input name="item_desc" placeholder="Line item description" required />
    <input name="qty" type="number" step="0.1" value="1" />
    <input name="unit_price" type="number" step="0.01" placeholder="Unit price" required />
  </div>`;
  await boot();
});

$("#expense-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  await api("/api/expenses", {
    method: "POST",
    body: JSON.stringify({
      category: f.get("category"),
      description: f.get("description"),
      amount: Number(f.get("amount")),
      billable: f.get("billable") === "on",
    }),
  });
  e.target.reset();
  await boot();
});

$("#proposal-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  await api("/api/proposals", {
    method: "POST",
    body: JSON.stringify({
      title: f.get("title"),
      client_name: f.get("client_name"),
      problem: f.get("problem"),
      solution: f.get("solution"),
      scope: f.get("scope"),
      investment: Number(f.get("investment") || 0),
      timeline: f.get("timeline"),
    }),
  });
  e.target.reset();
  await boot();
});

$("#invoice-list").addEventListener("click", async (e) => {
  const payId = e.target.dataset.pay;
  if (payId) {
    await api(`/api/invoices/${payId}/status?status=paid`, { method: "PATCH" });
    await boot();
    return;
  }
  const checkoutId = e.target.dataset.checkout;
  if (checkoutId) {
    const session = await api(`/api/invoices/${checkoutId}/checkout`, { method: "POST" });
    if (session.url) {
      if (session.mode === "demo") {
        alert(`Demo checkout ready (${session.id}). Marking invoice paid.`);
        await api(`/api/invoices/${checkoutId}/status?status=paid`, { method: "PATCH" });
        await boot();
      } else {
        window.location.href = session.url;
      }
    } else {
      alert(session.error || "Checkout unavailable");
    }
    return;
  }
  const emailId = e.target.dataset.email;
  if (emailId) {
    try {
      const res = await api(`/api/invoices/${emailId}/email`, { method: "POST" });
      if (res.mode === "demo") {
        alert(`Demo email preview to ${res.preview?.to || "(no email)"}:\n\n${res.preview?.subject || ""}`);
      } else if (res.sent) {
        alert(`Invoice emailed to ${res.to}`);
      } else {
        alert(res.error || "Email failed");
      }
      await boot();
    } catch (err) {
      alert(String(err.message || err));
    }
  }
});

boot().catch((err) => console.error(err));
