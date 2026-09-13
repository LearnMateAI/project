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
import { ProgressRing } from "../../components/charts.jsx";

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

  const barStyle = questions.some((question) => question.difficulty === "hard");

  return (
    <div>
      {barStyle && (
        <p className="notice notice-info mb-4">
          Practice set — challenging questions based only on this document.
        </p>
      )}
      {submitted && (
        <div className="card p-5 mb-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            {/* The score as a ring: a mark out of ten is read against the total, and the
                ring shows the total without a second line of text. */}
            <ProgressRing value={(score / questions.length) * 100} size={72} stroke={7} />
            <div>
              <p className="text-[17px] font-bold text-heading m-0">
                {score} / {questions.length} correct
              </p>
              <p className="text-[13px] text-muted m-0">
                {score === questions.length
                  ? "Every one right."
                  : "The correct answers are marked below."}
              </p>
            </div>
          </div>
          <button onClick={retry} className="btn-secondary shrink-0">
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
            <li key={index} className="card p-5">
              <div className="flex items-start justify-between gap-3 mb-3.5">
                <p className="text-[14.5px] font-semibold text-heading m-0 leading-relaxed">
                  <span className="text-primary mr-1.5">{index + 1}.</span>
                  {question.question}
                </p>
                <span className="flex items-center gap-2 shrink-0">
                  {question.difficulty && (
                    <span className="badge badge-gray">{question.difficulty}</span>
                  )}
                  {submitted && (
                  <span className={`badge shrink-0 ${gotItRight ? "badge-green" : "badge-red"}`}>
                    <span className="badge-dot" />
                    {gotItRight ? "Correct" : "Incorrect"}
                  </span>
                  )}
                </span>
              </div>

              <div className="space-y-2">
                {(question.options || []).map((option, optionIndex) => {
                  const isChosen = chosen === option;
                  const isCorrect = option === correct;

                  // Before submitting, only the choice is highlighted. After, the correct
                  // option is always green and a wrong choice is red -- so a blank answer
                  // still teaches you what the answer was.
                  let tone = "border-border";
                  if (submitted && isCorrect) tone = "border-success bg-success-light";
                  else if (submitted && isChosen) tone = "border-danger bg-danger-light";
                  else if (isChosen) tone = "border-primary bg-primary-soft";

                  return (
                    <label
                      key={optionIndex}
                      className={`flex items-start gap-2.5 text-[13.5px] text-body border rounded-xl px-3.5 py-2.5 ${tone} ${
                        submitted ? "cursor-default" : "cursor-pointer hover:border-border-strong"
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
                      {/* After marking, the correct option is named as well as coloured. */}
                      {submitted && isCorrect && (
                        <span className="ml-auto text-[11px] font-bold uppercase tracking-wide text-success shrink-0">
                          Answer
                        </span>
                      )}
                    </label>
                  );
                })}
              </div>
            </li>
          );
        })}
      </ol>

      {!submitted && (
        <div className="mt-5 flex items-center gap-4 sticky bottom-0 bg-background/85 backdrop-blur-sm py-3 rounded-xl">
          <button onClick={() => setSubmitted(true)} className="btn-primary">
            Submit answers
          </button>
          <span className="text-[13px] text-muted">
            {answered} of {questions.length} answered
          </span>
        </div>
      )}
    </div>
  );
}

export default McqQuiz;
