import { useSyncExternalStore } from "react";

export type Route =
  | { name: "queue" }
  | { name: "claim"; id: string }
  | { name: "instructions" }
  | { name: "missing" };

export function parseHash(hash: string): Route {
  const path = hash.replace(/^#/, "");
  if (path === "" || path === "/") return { name: "queue" };
  if (path === "/instructions") return { name: "instructions" };
  const claim = /^\/claims\/([\w-]+)$/.exec(path);
  if (claim?.[1]) return { name: "claim", id: claim[1] };
  return { name: "missing" };
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener("hashchange", onChange);
  return () => {
    window.removeEventListener("hashchange", onChange);
  };
}

function currentHash(): string {
  return window.location.hash;
}

export function useRoute(): Route {
  return parseHash(useSyncExternalStore(subscribe, currentHash));
}
