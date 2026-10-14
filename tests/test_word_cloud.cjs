const test = require("node:test");
const assert = require("node:assert/strict");
const { countWords, layoutWords } = require("../docs/assets/word-cloud.js");

const paragraph = (index, text, stock = "Walleye pollock") => ({
  source_file: "SSC June 2026.pdf", page: 2, paragraph_index: index,
  full_text: text, stock,
});

test("counts source text once when several stock labels match the same paragraph", () => {
  const records = [
    paragraph(1, "The SSC noted recruitment recruitment and ABC."),
    paragraph(1, "The SSC noted recruitment recruitment and ABC.", "Pacific cod"),
    paragraph(2, "Recruitment and OFL inform age-structured models."),
  ];
  const result = countWords(records);
  assert.equal(result.paragraphCount, 2);
  const counts = Object.fromEntries(result.words.map(({ word, count }) => [word, count]));
  assert.equal(counts.recruitment, 3);
  assert.equal(counts.ABC, 1);
  assert.equal(counts.OFL, 1);
  assert.equal(counts["age-structured"], 1);
  assert.equal(counts.ssc, undefined);
  assert.equal(counts.the, undefined);
});

test("uses only the selected records and handles empty selections", () => {
  const record = paragraph(3, "Biomass biomass maxABC.");
  assert.deepEqual(countWords([record]).words, [
    { word: "biomass", count: 2 }, { word: "maxABC", count: 1 },
  ]);
  assert.deepEqual(countWords([]), { words: [], paragraphCount: 0 });
  assert.deepEqual(countWords([paragraph(4, "The and 2026.")]).words, []);
});

test("keeps words within the cloud and apart at desktop and mobile widths", () => {
  const words = ["assessment", "model", "stock", "survey", "data", "crab", "ABC", "biomass", "catch", "fishery", "OFL", "tier", "GOA", "authors", "BSAI", "recruitment", "pollock", "uncertainty", "age-structured", "recommendations"]
    .map((word, index) => ({ word, count: 80 - index * 3 }));
  for (const width of [280, 840]) {
    const placed = layoutWords(words, width, 480, (word, size) => word.length * size * 0.55);
    assert.equal(placed.length, words.length);
    for (let i = 0; i < placed.length; i += 1) {
      const a = placed[i].box;
      assert(a.x >= 0 && a.y >= 0 && a.x + a.width <= width && a.y + a.height <= 480);
      for (const { box: b } of placed.slice(i + 1)) {
        assert(a.x + a.width <= b.x || b.x + b.width <= a.x || a.y + a.height <= b.y || b.y + b.height <= a.y);
      }
    }
  }
});
