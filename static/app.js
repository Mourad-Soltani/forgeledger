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

function money(n) {
  return Number(n || 0).toLocaleString(undefined, { style: "currency", currency: "USD" });
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
      <p>${money(i.total)} ${i.currency} · client #${i.client_id}</p>
      <p>${(i.items || []).map((x) => x.description).join(", ")}</p>
      <button data-pay="${i.id}">Mark paid</button></article>`
    )
    .join("");
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
  await Promise.all([refreshStats(), refreshClients(), refreshInvoices(), refreshExpenses(), refreshProposals()]);
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

$("#invoice-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  await api("/api/invoices", {
    method: "POST",
    body: JSON.stringify({
      client_id: Number(f.get("client_id")),
      status: f.get("status"),
      items: [
        {
          description: f.get("item_desc"),
          qty: Number(f.get("qty")),
          unit_price: Number(f.get("unit_price")),
        },
      ],
    }),
  });
  e.target.reset();
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
  const id = e.target.dataset.pay;
  if (!id) return;
  await api(`/api/invoices/${id}/status?status=paid`, { method: "PATCH" });
  await boot();
});

boot().catch((err) => console.error(err));
