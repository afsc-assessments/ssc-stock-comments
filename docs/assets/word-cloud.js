(function (root) {
  "use strict";

  const stopWords = new Set((
    "a about above across after again against all also am an and any are as at " +
    "be because been before being below between both but by can cannot could did do " +
    "does doing down during each either else even few for from further had has have " +
    "having he her here hers herself him himself his how however i if in into is it " +
    "its itself just may me might more most much must my myself no nor not now of " +
    "off on once only or other our ours ourselves out over own same shall she should " +
    "so some such than that the their theirs them themselves then there these they " +
    "this those through to too under until up upon us use used using very was we " +
    "were what when where whether which while who whom why will with within would " +
    "you your yours yourself yourselves e g eg etc s t " +
    "ssc council committee meeting meetings report reports page pages " +
    "noted notes presented presentation presentations"
  ).split(/\s+/));
  const abbreviations = new Set(["abc", "ofl", "bsai", "goa", "ebs", "ai", "fmp", "nmfs", "npfmc", "noaa", "tac", "cpue", "cv", "esp", "mse", "bmsy", "fmsy"]);

  function wordLabel(word) {
    if (word === "maxabc") return "maxABC";
    return abbreviations.has(word) ? word.toUpperCase() : word;
  }

  function countWords(records, limit = 60) {
    const paragraphs = new Map();
    for (const record of records) {
      // One paragraph can have several stock records. Count its original text once.
      const key = JSON.stringify([record.source_file, record.page, record.paragraph_index]);
      if (!paragraphs.has(key)) paragraphs.set(key, record.full_text || "");
    }
    const counts = new Map();
    for (const text of paragraphs.values()) {
      const words = text.normalize("NFKC").toLowerCase().match(/[\p{L}]+(?:[-\u2010\u2011][\p{L}]+)*/gu) || [];
      for (let word of words) {
        word = word.replace(/[\u2010\u2011]/g, "-");
        if (word.length < 3 || stopWords.has(word)) continue;
        counts.set(word, (counts.get(word) || 0) + 1);
      }
    }
    const words = [...counts].map(([word, count]) => ({ word: wordLabel(word), count }))
      .sort((a, b) => b.count - a.count || a.word.localeCompare(b.word, "en"))
      .slice(0, limit);
    return { words, paragraphCount: paragraphs.size };
  }

  function overlaps(a, b) {
    return a.x < b.x + b.width && a.x + a.width > b.x &&
      a.y < b.y + b.height && a.y + a.height > b.y;
  }

  function layoutWords(words, width, height, measure) {
    if (!words.length || width <= 0 || height <= 0) return [];
    const low = Math.sqrt(words[words.length - 1].count);
    const high = Math.sqrt(words[0].count);
    const maxFont = Math.min(56, width / 7);
    let best = [];
    // Retry at a smaller scale when long words leave too little space.
    for (const scale of [1, 0.88, 0.76, 0.64]) {
      const placed = [];
      for (const word of words) {
        const relative = high === low ? 0.3 : (Math.sqrt(word.count) - low) / (high - low);
        let fontSize = Math.max(12, (14 + relative * (maxFont - 14)) * scale);
        let textWidth = measure(word.word, fontSize);
        if (textWidth > width - 16) {
          fontSize *= (width - 16) / textWidth;
          textWidth = measure(word.word, fontSize);
        }
        const boxWidth = textWidth + 8;
        const boxHeight = fontSize * 1.25 + 6;
        for (let step = 0; step < 1800; step += 1) {
          const angle = step * 0.47;
          const radius = Math.sqrt(step / 1800);
          const x = width / 2 + Math.cos(angle) * radius * width / 2 - boxWidth / 2;
          const y = height / 2 + Math.sin(angle) * radius * height / 2 - boxHeight / 2;
          const box = { x, y, width: boxWidth, height: boxHeight };
          if (x < 4 || y < 4 || x + boxWidth > width - 4 || y + boxHeight > height - 4) continue;
          if (placed.some((item) => overlaps(box, item.box))) continue;
          placed.push({ ...word, fontSize, x: x + boxWidth / 2, y: y + boxHeight / 2, box });
          break;
        }
      }
      if (placed.length > best.length) best = placed;
      if (best.length === words.length) break;
    }
    return best;
  }

  const api = { countWords, layoutWords };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (!root.document) return;

  class WordCloud {
    constructor() {
      this.container = document.querySelector("#word-cloud");
      this.summary = document.querySelector("#word-cloud-summary");
      this.table = document.querySelector("#word-cloud-table");
      this.details = document.querySelector("#word-cloud-counts");
      this.words = [];
      this.canvas = document.createElement("canvas");
      this.context = this.canvas.getContext("2d");
      this.frame = null;
      this.width = 0;
      if (typeof ResizeObserver !== "undefined") {
        this.observer = new ResizeObserver(() => {
          const width = Math.round(this.container.getBoundingClientRect().width);
          if (width !== this.width) this.scheduleDraw();
        });
        this.observer.observe(this.container);
      } else {
        window.addEventListener("resize", () => this.scheduleDraw());
      }
    }

    update(records) {
      const { words, paragraphCount } = countWords(records);
      this.words = words;
      this.summary.textContent = !records.length
        ? "No comments match the selected options."
        : !words.length ? "The selected paragraphs contain no words to display."
          : `${paragraphCount.toLocaleString()} source paragraphs · ${words.length} most frequent words`;
      this.details.hidden = !words.length;
      const fragment = document.createDocumentFragment();
      for (const { word, count } of words) {
        const row = document.createElement("tr");
        const label = document.createElement("th");
        label.scope = "row";
        label.textContent = word;
        const value = document.createElement("td");
        value.textContent = count.toLocaleString();
        row.append(label, value);
        fragment.append(row);
      }
      this.table.replaceChildren(fragment);
      // Remove the preceding selection immediately while the new layout is drawn.
      this.container.replaceChildren();
      this.scheduleDraw();
    }

    scheduleDraw() {
      if (this.frame !== null) cancelAnimationFrame(this.frame);
      this.frame = requestAnimationFrame(() => {
        this.frame = null;
        this.draw();
      });
    }

    draw() {
      this.width = Math.round(this.container.getBoundingClientRect().width);
      if (!this.words.length || !this.width) return;
      let height = this.width < 500 ? 400 : 320;
      const measure = (word, size) => {
        this.context.font = `700 ${size}px Arial, sans-serif`;
        return this.context.measureText(word).width;
      };
      let placed = layoutWords(this.words, this.width, height, measure);
      while (placed.length < this.words.length && height < 800) {
        height += 80;
        placed = layoutWords(this.words, this.width, height, measure);
      }
      const ns = "http://www.w3.org/2000/svg";
      const svg = document.createElementNS(ns, "svg");
      svg.setAttribute("viewBox", `0 0 ${this.width} ${height}`);
      svg.setAttribute("role", "img");
      svg.setAttribute("aria-labelledby", "word-cloud-svg-title word-cloud-svg-description");
      const title = document.createElementNS(ns, "title");
      title.id = "word-cloud-svg-title";
      title.textContent = "Word cloud for the selected SSC comments";
      const description = document.createElementNS(ns, "desc");
      description.id = "word-cloud-svg-description";
      description.textContent = "Words are sized by occurrence count in the matching source paragraphs. Exact frequencies are available in View word counts.";
      svg.append(title, description);
      const colors = ["#15506d", "#1f6f8b", "#416c25", "#745016", "#3f547b"];
      for (const [index, item] of placed.entries()) {
        const text = document.createElementNS(ns, "text");
        text.setAttribute("x", item.x);
        text.setAttribute("y", item.y);
        text.setAttribute("font-size", item.fontSize);
        text.setAttribute("text-anchor", "middle");
        text.setAttribute("dominant-baseline", "central");
        text.setAttribute("fill", colors[index % colors.length]);
        text.textContent = item.word;
        const tip = document.createElementNS(ns, "title");
        tip.textContent = `${item.word}: ${item.count.toLocaleString()} occurrences`;
        text.append(tip);
        svg.append(text);
      }
      this.container.replaceChildren(svg);
    }
  }

  root.wordCloud = new WordCloud();
})(typeof window !== "undefined" ? window : globalThis);
