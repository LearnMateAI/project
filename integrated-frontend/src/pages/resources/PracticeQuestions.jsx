/**
 * Short-answer practice questions.
 *
 *     [{question, answer}, ...]
 *
 * Answers are hidden behind a per-question toggle for the same reason the MCQ page hides
 * its options: an answer visible beside the question is a page you read, not one you
 * practise with. "Show all" is there for reviewing the set afterwards.
 */

import { useState } from "react";

function PracticeQuestions({ questions }) {
  const [revealed, setRevealed] = useState({});

  const allShown = questions.length > 0 && questions.every((_, index) => revealed[index]);

  function toggle(index) {
    setRevealed((current) => ({ ...current, [index]: !current[index] }));
  }

  function toggleAll() {
    setRevealed(allShown ? {} : Object.fromEntries(questions.map((_, index) => [index, true])));
  }

  return (
    <div>
      <button onClick={toggleAll} className="btn-secondary mb-4">
        {allShown ? "Hide all answers" : "Show all answers"}
      </button>

      <ol className="space-y-3 list-none p-0 m-0">
        {questions.map((item, index) => (
          <li key={index} className="card p-5">
            <p className="text-[14.5px] font-semibold text-heading m-0 mb-2.5 leading-relaxed">
              <span className="text-primary mr-1.5">{index + 1}.</span>
              {item.question}
            </p>

            {revealed[index] ? (
              <>
                <div className="text-[13.5px] leading-relaxed text-body bg-surface-alt border border-border-light rounded-xl p-3.5">
                  {item.answer}
                </div>
                <button onClick={() => toggle(index)} className="btn-ghost mt-2">
                  Hide answer
                </button>
              </>
            ) : (
              <button onClick={() => toggle(index)} className="btn-secondary py-1.5 px-3 text-[12.5px]">
                Show answer
              </button>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}

export default PracticeQuestions;
