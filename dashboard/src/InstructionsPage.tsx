import { useEffect, useState } from "react";
import { getText } from "./api";
import { Markdown } from "./Markdown";

interface Texts {
  queue: string;
  claim: string;
}

function Instructions({
  heading,
  text,
}: Readonly<{ heading: string; text: string | undefined }>) {
  return (
    <section className="panel prose">
      <h2>{heading}</h2>
      {text === undefined ? (
        <p>Loading the instructions</p>
      ) : (
        <Markdown text={text} />
      )}
    </section>
  );
}

export function InstructionsPage() {
  const [texts, setTexts] = useState<Texts | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    Promise.all([
      getText("/api/instructions/queue"),
      getText("/api/instructions/claim"),
    ])
      .then(([queue, claim]) => {
        setTexts({ queue, claim });
      })
      .catch(() => {
        setFailed(true);
      });
  }, []);

  if (failed) return <p role="alert">The instructions could not be loaded.</p>;
  return (
    <>
      <h1>Agent instructions</h1>
      <p className="note">What the UnderCover Agent follows. Read only.</p>
      <div className="stack">
        <Instructions heading="Running the queue" text={texts?.queue} />
        <Instructions heading="Working a claim" text={texts?.claim} />
      </div>
    </>
  );
}
