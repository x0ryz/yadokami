import React from "react";

interface WhatsAppTextFormatterProps {
  text: string;
  className?: string;
}

/**
 * Renders WhatsApp-style formatted text with support for:
 * - *bold text* → bold
 * - _gray text_ → italic (gray/dimmed)
 * - ~strikethrough text~ → strikethrough
 * - ```code block``` → monospace code block
 * - URLs → clickable links
 * - \n → line breaks
 */
export const WhatsAppTextFormatter: React.FC<WhatsAppTextFormatterProps> = ({
  text,
  className = "",
}) => {
  // Type for parsed nodes
  type ParsedNode =
    | string
    | { type: "br" }
    | { type: "bold"; children: ParsedNode[] }
    | { type: "gray"; children: ParsedNode[] }
    | { type: "strikethrough"; children: ParsedNode[] }
    | { type: "code"; content: string }
    | { type: "link"; url: string; text: string };

  // Step 1: Extract code blocks first (highest priority)
  const extractCodeBlocks = (
    content: string
  ): { text: string; codeBlocks: string[] } => {
    const codeBlocks: string[] = [];
    const placeholder = "\x00CODE_BLOCK_\x00";

    const processed = content.replace(/```([\s\S]*?)```/g, (match, code) => {
      codeBlocks.push(code.trim());
      return `${placeholder}${codeBlocks.length - 1}${placeholder}`;
    });

    return { text: processed, codeBlocks };
  };

  // Step 2: Parse formatting in text
  const parseFormatting = (
    content: string
  ): ParsedNode[] => {
    const nodes: ParsedNode[] = [];
    let remaining = content;

    // Process each character to find formatting patterns
    const boldRegex = /\*([^\*]+)\*/;
    const grayRegex = /_([^_]+)_/;
    const strikeRegex = /~([^~]+)~/;
    const lineBreakRegex = /\n/;
    const urlRegex =
      /(https?:\/\/[^\s\)]+|www\.[^\s\)]+)/;

    while (remaining) {
      // Find next formatting occurrence
      const boldMatch = remaining.match(boldRegex);
      const grayMatch = remaining.match(grayRegex);
      const strikeMatch = remaining.match(strikeRegex);
      const lineBreakMatch = remaining.match(lineBreakRegex);
      const urlMatch = remaining.match(urlRegex);

      // Find which occurs first
      const matches = [
        boldMatch && {
          type: "bold" as const,
          index: boldMatch.index || 0,
          content: boldMatch[1],
          fullLength: boldMatch[0].length,
        },
        grayMatch && {
          type: "gray" as const,
          index: grayMatch.index || 0,
          content: grayMatch[1],
          fullLength: grayMatch[0].length,
        },
        strikeMatch && {
          type: "strikethrough" as const,
          index: strikeMatch.index || 0,
          content: strikeMatch[1],
          fullLength: strikeMatch[0].length,
        },
        lineBreakMatch && {
          type: "br" as const,
          index: lineBreakMatch.index || 0,
          fullLength: 1,
        },
        urlMatch && {
          type: "link" as const,
          index: urlMatch.index || 0,
          url: urlMatch[0],
          fullLength: urlMatch[0].length,
        },
      ].filter(Boolean);

      if (matches.length === 0) {
        // No more formatting, add remaining text
        if (remaining) nodes.push(remaining);
        break;
      }

      // Get the earliest match
      const earliest = matches.reduce((min, curr) =>
        curr && min && curr.index < min.index ? curr : min
      );

      if (!earliest) {
        nodes.push(remaining);
        break;
      }

      // Add text before match
      if (earliest.index > 0) {
        nodes.push(remaining.substring(0, earliest.index));
      }

      // Add the formatted/special node
      if (earliest.type === "bold") {
        nodes.push({
          type: "bold",
          children: parseFormatting(earliest.content),
        });
      } else if (earliest.type === "gray") {
        nodes.push({
          type: "gray",
          children: parseFormatting(earliest.content),
        });
      } else if (earliest.type === "strikethrough") {
        nodes.push({
          type: "strikethrough",
          children: parseFormatting(earliest.content),
        });
      } else if (earliest.type === "br") {
        nodes.push({ type: "br" });
      } else if (earliest.type === "link") {
        nodes.push({
          type: "link",
          url: earliest.url,
          text: earliest.url,
        });
      }

      // Continue with remaining text
      remaining = remaining.substring(
        earliest.index + earliest.fullLength
      );
    }

    return nodes;
  };

  // Step 3: Replace code block placeholders back
  const restoreCodeBlocks = (
    nodes: ParsedNode[],
    codeBlocks: string[]
  ): ParsedNode[] => {
    return nodes
      .map((node) => {
        if (typeof node === "string") {
          const placeholder = "\x00CODE_BLOCK_\x00";
          const parts: ParsedNode[] = [];
          let remaining = node;
          let match;

          const regex =
            /\x00CODE_BLOCK_\x00(\d+)\x00CODE_BLOCK_\x00/g;
          let lastIndex = 0;

          while ((match = regex.exec(remaining)) !== null) {
            if (match.index > lastIndex) {
              parts.push(remaining.substring(lastIndex, match.index));
            }

            const blockIndex = parseInt(match[1]);
            if (blockIndex < codeBlocks.length) {
              parts.push({
                type: "code" as const,
                content: codeBlocks[blockIndex],
              });
            }

            lastIndex = regex.lastIndex;
          }

          if (lastIndex < remaining.length) {
            parts.push(remaining.substring(lastIndex));
          }

          return parts.length > 1 ? (parts as any) : node;
        } else if (
          node &&
          typeof node === "object" &&
          "children" in node
        ) {
          return {
            ...node,
            children: restoreCodeBlocks(node.children, codeBlocks),
          };
        }

        return node;
      })
      .flat() as ParsedNode[];
  };

  // Step 4: Render parsed nodes to JSX
  let nodeCounter = 0;

  const renderNode = (node: ParsedNode | ParsedNode[]): React.ReactNode => {
    if (Array.isArray(node)) {
      return node.map((n) => renderNode(n));
    }

    if (typeof node === "string") {
      return node;
    }

    if (!node || typeof node !== "object") {
      return null;
    }

    const key = `node-${nodeCounter++}`;

    if (node.type === "br") {
      return <br key={key} />;
    }

    if (node.type === "code") {
      return (
        <code
          key={key}
          className="font-mono text-sm bg-gray-100 text-rose-500 px-1 rounded inline-block"
        >
          {node.content}
        </code>
      );
    }

    if (node.type === "bold") {
      return (
        <strong key={key} className="font-bold">
          {renderNode(node.children)}
        </strong>
      );
    }

    if (node.type === "gray") {
      return (
        <span key={key} className="text-gray-600">
          {renderNode(node.children)}
        </span>
      );
    }

    if (node.type === "strikethrough") {
      return (
        <del key={key} className="line-through">
          {renderNode(node.children)}
        </del>
      );
    }

    if (node.type === "link") {
      const href = node.url.startsWith("http")
        ? node.url
        : `https://${node.url}`;
      return (
        <a
          key={key}
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-500 hover:underline break-all"
        >
          {node.text}
        </a>
      );
    }

    return null;
  };

  // Main processing pipeline
  const { text: textWithPlaceholders, codeBlocks } =
    extractCodeBlocks(text);
  let parsed = parseFormatting(textWithPlaceholders);
  parsed = restoreCodeBlocks(parsed, codeBlocks).flat();

  return (
    <div className={`whitespace-pre-wrap break-words ${className}`}>
      {renderNode(parsed)}
    </div>
  );
};

export default WhatsAppTextFormatter;
