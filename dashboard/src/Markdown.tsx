import { Fragment, type ReactNode } from "react";

function inline(text: string): ReactNode {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/).map((part, index) => {
    if (part.startsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`")) {
      return <code key={index}>{part.slice(1, -1)}</code>;
    }
    return <Fragment key={index}>{part}</Fragment>;
  });
}

interface Item {
  text: string;
  children: string[];
}

interface Block {
  kind: "h2" | "p" | "ul" | "ol";
  start: number;
  items: Item[];
}

const MARKER = /^(## |[-*] |(\d+)\. )/;

function kindOf(text: string): Block["kind"] {
  if (text.startsWith("## ")) return "h2";
  if (/^[-*] /.test(text)) return "ul";
  if (/^\d+\. /.test(text)) return "ol";
  return "p";
}

function isList(block: Block | undefined): block is Block {
  return block?.kind === "ul" || block?.kind === "ol";
}

function addLine(result: Block[], line: string): void {
  const text = line.trim();
  const kind = kindOf(text);
  const last = result.at(-1);
  const body = kind === "p" ? text : text.replace(MARKER, "");
  if (isList(last) && kind === "ul" && /^\s/.test(line)) {
    last.items.at(-1)?.children.push(body);
  } else if (isList(last) && last.kind === kind) {
    last.items.push({ text: body, children: [] });
  } else {
    const start = Number(MARKER.exec(text)?.[2] ?? 1);
    result.push({ kind, start, items: [{ text: body, children: [] }] });
  }
}

function blocks(markdown: string): Block[] {
  const result: Block[] = [];
  for (const line of markdown.split("\n")) {
    if (line.trim() !== "") addLine(result, line);
  }
  return result;
}

function Items({ items }: Readonly<{ items: Item[] }>) {
  return items.map((item, index) => (
    <li key={index}>
      {inline(item.text)}
      {item.children.length > 0 && (
        <ul>
          {item.children.map((child, i) => (
            <li key={i}>{inline(child)}</li>
          ))}
        </ul>
      )}
    </li>
  ));
}

export function Markdown({ text }: Readonly<{ text: string }>) {
  return (
    <>
      {blocks(text).map((block, index) => {
        if (block.kind === "ul") {
          return (
            <ul key={index}>
              <Items items={block.items} />
            </ul>
          );
        }
        if (block.kind === "ol") {
          return (
            <ol key={index} start={block.start}>
              <Items items={block.items} />
            </ol>
          );
        }
        const content = inline(block.items.map((i) => i.text).join(" "));
        if (block.kind === "h2") return <h3 key={index}>{content}</h3>;
        return <p key={index}>{content}</p>;
      })}
    </>
  );
}
