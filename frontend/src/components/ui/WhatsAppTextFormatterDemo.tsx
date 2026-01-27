import React from "react";
import WhatsAppTextFormatter from "../ui/WhatsAppTextFormatter";

/**
 * Demo component showing WhatsAppTextFormatter in action.
 * Remove this file after testing.
 */
export const WhatsAppTextFormatterDemo: React.FC = () => {
  const examples = [
    {
      title: "Bold Text",
      text: "*Order confirmed* ✅",
    },
    {
      title: "Italic Text",
      text: "_Thank you for your purchase!_",
    },
    {
      title: "Strikethrough",
      text: "Price: ~$50~ $30",
    },
    {
      title: "Code Block",
      text: "Your verification code is ```1234567```",
    },
    {
      title: "Links",
      text: "Visit https://example.com or www.google.com for more info",
    },
    {
      title: "Line Breaks",
      text: "Line 1\nLine 2\nLine 3",
    },
    {
      title: "Complex Example",
      text:
        "*Order confirmed* ✅\nYour code is ```1234```.\n_Thank you for your purchase!_\nVisit https://example.com for tracking",
    },
    {
      title: "Nested Formatting",
      text: "*This is *bold* with _italic_ inside*",
    },
    {
      title: "Multiple Code Blocks",
      text: "Use ```npm install``` then ```npm start``` to get started",
    },
  ];

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-8">WhatsApp Text Formatter Demo</h1>

      <div className="grid grid-cols-1 gap-8">
        {examples.map((example, index) => (
          <div
            key={index}
            className="border border-gray-200 rounded-lg p-6 bg-white shadow-sm"
          >
            <h2 className="text-lg font-semibold mb-2 text-gray-700">
              {example.title}
            </h2>

            <div className="mb-4">
              <p className="text-xs text-gray-500 mb-2">Input:</p>
              <pre className="bg-gray-100 p-3 rounded text-sm overflow-x-auto">
                {example.text}
              </pre>
            </div>

            <div>
              <p className="text-xs text-gray-500 mb-2">Output:</p>
              <div className="bg-gray-50 border border-gray-200 p-4 rounded text-sm">
                <WhatsAppTextFormatter text={example.text} />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-12 p-6 bg-blue-50 border border-blue-200 rounded-lg">
        <h3 className="font-semibold text-blue-900 mb-2">Formatting Guide:</h3>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>
            <code className="bg-blue-100 px-2 py-1 rounded">*bold*</code> →
            Bold text
          </li>
          <li>
            <code className="bg-blue-100 px-2 py-1 rounded">_italic_</code> →
            Italic text (gray)
          </li>
          <li>
            <code className="bg-blue-100 px-2 py-1 rounded">~strikethrough~</code>{" "}
            → Strikethrough
          </li>
          <li>
            <code className="bg-blue-100 px-2 py-1 rounded">```code```</code> →
            Code block
          </li>
          <li>URLs are automatically converted to clickable links</li>
          <li>Line breaks (\n) are rendered as &lt;br/&gt;</li>
        </ul>
      </div>
    </div>
  );
};

export default WhatsAppTextFormatterDemo;
