export function ClaimPage({ id }: Readonly<{ id: string }>) {
  return (
    <>
      <p>
        <a href="#/">Back to the queue</a>
      </p>
      <h1 className="mono">{id}</h1>
    </>
  );
}
