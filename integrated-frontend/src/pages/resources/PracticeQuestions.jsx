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
      <button onClick={toggleAll} className="text-sm text-blue-600 hover:underline mb-3">
        {allShown ? "Hide all answers" : "Show all answers"}
      </button>

      <ol className="space-y-3">
        {questions.map((item, index) => (
          <li key={index} className="bg-white rounded-lg shadow-sm p-5">
            <p className="font-medium mb-2">
              {index + 1}. {item.question}
            </p>

            {revealed[index] ? (
              <div className="text-sm text-gray-800 bg-gray-50 border rounded p-3">
                {item.answer}
              </div>
            ) : (
              <button onClick={() => toggle(index)} className="text-sm text-blue-600 hover:underline">
                Show answer
              </button>
            )}

            {revealed[index] && (
              <button
                onClick={() => toggle(index)}
                className="text-sm text-gray-500 hover:underline mt-2 block"
              >
                Hide
              </button>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}

export default PracticeQuestions;
