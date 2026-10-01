const foundations = [
  "Auditable imports and data quality",
  "Observed profitability with explicit coverage",
  "Explainable accounts warranting review",
  "Action and outcome feedback trail",
];

export default function App() {
  return (
    <main>
      <p className="eyebrow">SPRINT 0 · ENGINEERING FOUNDATION</p>
      <h1>B2B Sales Profitability Intelligence</h1>
      <p className="lede">
        Decision support for sales teams deciding which existing accounts warrant review—and why.
      </p>
      <aside aria-label="Data readiness">
        <strong>Pending real anonymized data</strong>
        <span>D0 contracts and modeling feasibility remain provisional.</span>
      </aside>
      <section aria-labelledby="foundation-title">
        <h2 id="foundation-title">Foundation scope</h2>
        <ul>
          {foundations.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
      <footer>No model metrics or business outcomes are claimed in this build.</footer>
    </main>
  );
}
