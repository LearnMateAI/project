/** Render generated keypoints as a simple numbered list. */

function Flashcards({ points }) {
  if (!points?.length) return null;

  return (
    <ul className="card p-4 sm:p-7 space-y-3.5 list-none m-0">
      {points.map((point, index) => (
        <li key={index} className="flex gap-3 text-[14px] leading-relaxed text-body font-serif">
          <span className="shrink-0 w-6 h-6 rounded-lg bg-primary-light text-primary text-[11px] font-bold flex items-center justify-center mt-0.5 font-sans">
            {index + 1}
          </span>
          {point}
        </li>
      ))}
    </ul>
  );
}

export default Flashcards;
