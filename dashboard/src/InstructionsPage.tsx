import { useEffect, useState } from "react";
import { getText } from "./api";
import { Markdown } from "./Markdown";

export function InstructionsPage() {
  const [text, setText] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    getText("/api/instructions")
      .then(setText)
      .catch(() => {
        setFailed(true);
      });
  }, []);

  if (failed) return <p role="alert">The instructions could not be loaded.</p>;
  return (
    <>
      <h1>Agent instructions</h1>
      <p className="note">
        What the UnderCover Agent follows on every claim. Read only.
      </p>
      <section className="panel prose">
        {text === null ? (
          <p>Loading the instructions</p>
        ) : (
          <Markdown text={text} />
        )}
      </section>
    </>
  );
}
