import { useState } from "react";

function Section({ title, children }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border-b border-gray-300 py-4">
      <button
        onClick={() => setOpen(!open)}
        className="w-full text-left text-lg md:text-xl font-bold text-blue-600 flex justify-between items-center px-4 py-2 focus:outline-none"
      >
        {title}
        <span>{open ? "▲" : "▼"}</span>
      </button>
      <div className={`overflow-hidden transition-max-height duration-500 ${open ? "max-h-96" : "max-h-0"}`}>
        <div className="mt-2 px-6 text-gray-800 text-base md:text-lg">{open && children}</div>
      </div>
    </div>
  );
}

export default Section;
