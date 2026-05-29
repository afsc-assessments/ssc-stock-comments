const state = {
  records: [],
  filtered: [],
  pageSize: 80,
};

const els = {
  stock: document.querySelector("#stock-filter"),
  year: document.querySelector("#year-filter"),
  fmp: document.querySelector("#fmp-filter"),
  type: document.querySelector("#type-filter"),
  buffer: document.querySelector("#buffer-filter"),
  search: document.querySelector("#search-filter"),
  sort: document.querySelector("#sort-order"),
  cards: document.querySelector("#cards"),
  shown: document.querySelector("#shown-count"),
  total: document.querySelector("#record-count"),
  clear: document.querySelector("#clear-filters"),
  copy: document.querySelector("#copy-link"),
  template: document.querySelector("#card-template"),
};

const bufferTypeLabels = {
  "maximum permissible ABC": "maximum permissible",
  "ABC buffer": "buffer",
  "ABC reduction": "reduction",
  "from maxABC": "from maxABC",
};

function selectedValues(select) {
  return Array.from(select.selectedOptions).map((option) => option.value);
}

function fillSelect(select, values) {
  select.replaceChildren();
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.append(option);
  });
}

function setSelected(select, values) {
  const wanted = new Set(values);
  Array.from(select.options).forEach((option) => {
    option.selected = wanted.has(option.value);
  });
}

function recordText(record) {
  return `${record.stock} ${record.fmp} ${record.comment_type} ${record.section} ${record.abc_buffer_terms || ""} ${record.excerpt} ${record.full_text}`.toLowerCase();
}

function recordTypes(record) {
  const bufferTerms = (record.abc_buffer_terms || "")
    .split(";")
    .map((value) => value.trim())
    .filter(Boolean);
  const bufferLabels = bufferTerms
    .map((term) => bufferTypeLabels[term])
    .filter(Boolean);
  return [record.comment_type, ...bufferTerms, ...bufferLabels];
}

function applyFilters() {
  const stocks = new Set(selectedValues(els.stock));
  const years = new Set(selectedValues(els.year));
  const fmps = new Set(selectedValues(els.fmp));
  const types = new Set(selectedValues(els.type));
  const bufferOnly = els.buffer.checked;
  const query = els.search.value.trim().toLowerCase();

  state.filtered = state.records.filter((record) => {
    if (stocks.size && !stocks.has(record.stock)) return false;
    if (years.size && !years.has(String(record.year))) return false;
    if (fmps.size && !fmps.has(record.fmp)) return false;
    if (types.size && !recordTypes(record).some((type) => types.has(type))) return false;
    if (bufferOnly && !record.abc_buffer_terms) return false;
    if (query && !recordText(record).includes(query)) return false;
    return true;
  });

  sortRecords();
  render();
  writeUrlState();
}

function sortRecords() {
  const order = els.sort.value;
  state.filtered.sort((a, b) => {
    if (order === "oldest") return Number(a.year) - Number(b.year) || a.stock.localeCompare(b.stock);
    if (order === "stock") return a.stock.localeCompare(b.stock) || Number(b.year) - Number(a.year);
    return Number(b.year) - Number(a.year) || a.stock.localeCompare(b.stock);
  });
}

function render() {
  els.cards.replaceChildren();
  els.shown.textContent = state.filtered.length.toLocaleString();

  const fragment = document.createDocumentFragment();
  state.filtered.slice(0, state.pageSize).forEach((record) => {
    const node = els.template.content.cloneNode(true);
    node.querySelector(".stock").textContent = `${record.stock} (${record.year})`;
    node.querySelector(".fmp").textContent = record.fmp;
    node.querySelector(".type").textContent = record.comment_type;
    const bufferTopic = node.querySelector(".buffer-topic");
    if (record.abc_buffer_terms) {
      bufferTopic.hidden = false;
      bufferTopic.textContent = "ABC buffer";
      bufferTopic.title = record.abc_buffer_terms;
    }
    node.querySelector(".excerpt").textContent = record.excerpt;
    node.querySelector(".full-text").textContent = record.full_text;
    node.querySelector(".source").textContent = `${record.source_file}, page ${record.page}`;
    const link = node.querySelector(".pdf-link");
    link.href = record.page_url;
    link.textContent = `Open page ${record.page}`;
    fragment.append(node);
  });

  if (state.filtered.length > state.pageSize) {
    const more = document.createElement("button");
    more.type = "button";
    more.textContent = `Show next ${Math.min(80, state.filtered.length - state.pageSize)} comments`;
    more.addEventListener("click", () => {
      state.pageSize += 80;
      render();
    });
    fragment.append(more);
  }

  els.cards.append(fragment);
}

function writeUrlState() {
  const params = new URLSearchParams();
  const entries = [
    ["stock", selectedValues(els.stock)],
    ["year", selectedValues(els.year)],
    ["fmp", selectedValues(els.fmp)],
    ["type", selectedValues(els.type)],
  ];
  entries.forEach(([key, values]) => {
    if (values.length) params.set(key, values.join("|"));
  });
  if (els.search.value.trim()) params.set("q", els.search.value.trim());
  if (els.buffer.checked) params.set("abc_buffer", "1");
  const next = `${location.pathname}${params.toString() ? `?${params}` : ""}`;
  history.replaceState(null, "", next);
}

function readUrlState() {
  const params = new URLSearchParams(location.search);
  setSelected(els.stock, (params.get("stock") || "").split("|").filter(Boolean));
  setSelected(els.year, (params.get("year") || "").split("|").filter(Boolean));
  setSelected(els.fmp, (params.get("fmp") || "").split("|").filter(Boolean));
  setSelected(els.type, (params.get("type") || "").split("|").filter(Boolean));
  els.buffer.checked = params.get("abc_buffer") === "1";
  els.search.value = params.get("q") || "";
}

function clearFilters() {
  [els.stock, els.year, els.fmp, els.type].forEach((select) => {
    Array.from(select.options).forEach((option) => {
      option.selected = false;
    });
  });
  els.buffer.checked = false;
  els.search.value = "";
  state.pageSize = 80;
  applyFilters();
}

async function copyStateLink() {
  writeUrlState();
  await navigator.clipboard.writeText(location.href);
  els.copy.textContent = "Copied";
  window.setTimeout(() => {
    els.copy.textContent = "Copy state";
  }, 1200);
}

async function init() {
  let payload = window.SSC_COMMENTS_DATA;
  if (!payload) {
    const response = await fetch("assets/comments.json");
    payload = await response.json();
  }
  state.records = payload.records;
  fillSelect(els.stock, payload.filters.stocks);
  fillSelect(els.year, payload.filters.years.reverse());
  fillSelect(els.fmp, payload.filters.fmps);
  fillSelect(els.type, payload.filters.comment_types);
  els.total.textContent = `${state.records.length.toLocaleString()} indexed comments`;
  readUrlState();
  applyFilters();
}

[els.stock, els.year, els.fmp, els.type, els.buffer, els.sort].forEach((el) => {
  el.addEventListener("change", () => {
    state.pageSize = 80;
    applyFilters();
  });
});

els.search.addEventListener("input", () => {
  state.pageSize = 80;
  applyFilters();
});
els.clear.addEventListener("click", clearFilters);
els.copy.addEventListener("click", copyStateLink);

init().catch((error) => {
  els.total.textContent = "Data failed to load";
  console.error(error);
});
