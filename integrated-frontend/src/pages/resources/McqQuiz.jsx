/**
 * Multiple-choice questions, as a quiz you can actually sit.
 *
 *     [{question, options[4], correct_answer}, ...]
 *
 * Answers stay hidden until Submit, then every question is marked and the correct option
 * revealed. Showing the answers straight away would make the set something to read rather
 * than something to test yourself with, which is most of the value of generating them.
 *
 * Scoring is entirely client-side -- `correct_answer` is a verbatim copy of one of that
 * question's own options, so comparison is a string match. Nothing is posted back: the
 * backend stores question sets, not attempts.
 */

import { useState } from "react";

function McqQuiz({ questions }) {
  const [answers, setAnswers] = useState({});
  const [submitted, setSubmitted] = useState(false);

  const answered = Object.keys(answers).length;
  const score = questions.reduce(
    (total, question, index) => total + (answers[index] === question.correct_answer ? 1 : 0),
    0,
  );

  function choose(index, option) {
    if (submitted) return;
    setAnswers((current) => ({ ...current, [index]: option }));
  }

  function retry() {
    setAnswers({});
    setSubmitted(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <div>
      {submitted && (
        <div className="bg-white rounded-lg shadow-sm p-5 mb-4 flex items-center justify-between">
          <div>
            <p className="text-lg font-semibold">
              {score} / {questions.length} correct
            </p>
            <p className="text-sm text-gray-500">
              {score === questions.length
                ? "Every one right."
                : "The correct answers are marked below."}
            </p>
          </div>
          <button onClick={retry} className="text-sm text-blue-600 hover:underline">
            Try again
          </button>
        </div>
      )}

      <ol className="space-y-4">
        {questions.map((question, index) => {
          const chosen = answers[index];
          const correct = question.correct_answer;
          const gotItRight = chosen === correct;

          return (
            <li key={index} className="bg-white rounded-lg shadow-sm p-5">
              <div className="flex items-start justify-between gap-3 mb-3">
                <p className="font-medium">
                  {index + 1}. {question.question}
                </p>
                {submitted && (
                  <span
                    className={`text-xs rounded px-2 py-1 shrink-0 ${
                      gotItRight ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                    }`}
                  >
                    {gotItRight ? "Correct" : "Incorrect"}
                  </span>
                )}
              </div>

              <div className="space-y-2">
                {(question.options || []).map((option, optionIndex) => {
                  const isChosen = chosen === option;
                  const isCorrect = option === correct;

                  // Before submitting, only the choice is highlighted. After, the correct
                  // option is always green and a wrong choice is red -- so a blank answer
                  // still teaches you what the answer was.
                  let tone = "border-gray-200";
                  if (submitted && isCorrect) tone = "border-green-400 bg-green-50";
                  else if (submitted && isChosen) tone = "border-red-400 bg-red-50";
                  else if (isChosen) tone = "border-blue-400 bg-blue-50";

                  return (
                    <label
                      key={optionIndex}
                      className={`flex items-start gap-2 text-sm border rounded px-3 py-2 ${tone} ${
                        submitted ? "cursor-default" : "cursor-pointer hover:bg-gray-50"
                      }`}
                    >
                      <input
                        type="radio"
                        name={`question-${index}`}
                        checked={isChosen || false}
                        onChange={() => choose(index, option)}
                        disabled={submitted}
                        className="mt-0.5"
                      />
                      <span>{option}</span>
                    </label>
                  );
                })}
              </div>
            </li>
          );
        })}
      </ol>

      {!submitted && (
        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={() => setSubmitted(true)}
            className="bg-blue-600 text-white rounded px-4 py-2 text-sm"
          >
            Submit answers
          </button>
          <span className="text-sm text-gray-500">
            {answered} of {questions.length} answered
          </span>
        </div>
      )}
    </div>
  );
}

export default McqQuiz;
