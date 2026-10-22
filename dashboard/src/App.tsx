import { ClaimPage } from "./ClaimPage";
import { InstructionsPage } from "./InstructionsPage";
import { Queue } from "./Queue";
import { useRoute } from "./router";

export function App() {
  const route = useRoute();
  const onQueue = route.name === "queue" || route.name === "claim";

  return (
    <>
      <header className="panel bar">
        <a className="brand" href="#/">
          UnderCover
        </a>
        <span className="tagline">Claims</span>
        <nav aria-label="Main">
          <a href="#/" aria-current={onQueue ? "page" : undefined}>
            Queue
          </a>
          <a
            href="#/instructions"
            aria-current={route.name === "instructions" ? "page" : undefined}
          >
            Agent instructions
          </a>
        </nav>
      </header>
      <main>
        {route.name === "queue" && <Queue />}
        {route.name === "claim" && <ClaimPage key={route.id} id={route.id} />}
        {route.name === "instructions" && <InstructionsPage />}
        {route.name === "missing" && <p>That page does not exist.</p>}
      </main>
    </>
  );
}
