/**
 * Key points as flip cards.
 *
 * The engine still generates `keypoints` (a list of strings). This is a presentation of
 * that list so a student can drill rather than only read. A point with an em-dash or colon
 * splits into term / definition; otherwise the back is the full sentence.
 */

import { useState } from "react";

function splitPoint(point) {
  const text = String(point || "").trim();
  const match = text.match(/^(.{2,80}?)(?:\s+[—–-]\s+|:\s+)(.{8,})$/);
  if (match) return { front: match[1].replace(/^\*\*|\*\*$/g, "").trim(), back: match[2].trim() };
  const words = text.split(/\s+/);
  if (words.length > 8) {
    return { front: words.slice(0, 6).join(" ") + "…", back: text };
  }
  return { front: text, back: "Flip to review the full point against the source." };
}

function Flashcards({ points }) {
  const [flipped, setFlipped] = useState({});
  const [index, setIndex] = useState(0);
  const [mode, setMode] = useState("cards");

  if (!points?.length) return null;

  if (mode === "list") {
    return (
      <div>
        <div className="flex justify-end mb-3">
          <button type="button" className="btn-ghost" onClick={() => setMode("cards")}>
            Flip cards
          </button>
        </div>
        <ul className="card p-4 sm:p-7 space-y-3.5 list-none m-0">
          {points.map((point, i) => (
            <li key={i} className="flex gap-3 text-[14px] leading-relaxed text-body font-serif">
              <span className="shrink-0 w-6 h-6 rounded-lg bg-primary-light text-primary text-[11px] font-bold flex items-center justify-center mt-0.5 font-sans">
                {i + 1}
              </span>
              {point}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  const current = splitPoint(points[index]);
  const isFlipped = Boolean(flipped[index]);

  return (
    <div>
      <div className="flex items-center justify-between gap-3 mb-3">
        <p className="text-[12.5px] text-muted m-0">
          Card {index + 1} of {points.length} · click to flip
        </p>
        <button type="button" className="btn-ghost" onClick={() => setMode("list")}>
          List view
        </button>
      </div>

      <button
        type="button"
        className={`flashcard w-full text-left ${isFlipped ? "is-flipped" : ""}`}
        onClick={() => setFlipped((currentMap) => ({ ...currentMap, [index]: !currentMap[index] }))}
        aria-pressed={isFlipped}
      >
        <div className="flashcard-inner">
          <div className="flashcard-face paper">
            <p className="text-[11px] font-sans font-semibold uppercase tracking-wider text-muted m-0 mb-2">
              Prompt
            </p>
            <p className="m-0 text-[1.15rem] leading-snug">{current.front}</p>
          </div>
          <div className="flashcard-face flashcard-back">
            <p className="text-[11px] font-sans font-semibold uppercase tracking-wider text-muted m-0 mb-2">
              Answer
            </p>
            <p className="m-0 font-serif text-[1.05rem] leading-relaxed text-body">{current.back}</p>
          </div>
        </div>
      </button>

      <div className="flex justify-between mt-4">
        <button
          type="button"
          className="btn-secondary"
          disabled={index === 0}
          onClick={() => setIndex((value) => Math.max(0, value - 1))}
        >
          Previous
        </button>
        <button
          type="button"
          className="btn-secondary"
          disabled={index === points.length - 1}
          onClick={() => setIndex((value) => Math.min(points.length - 1, value + 1))}
        >
          Next
        </button>
      </div>
    </div>
  );
}

export default Flashcards;
