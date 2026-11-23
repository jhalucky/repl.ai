export function SiteFooter() {
  return (
    <footer className="border-t border-[var(--line)]">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-10 text-sm text-[var(--muted)] sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <p>Repl.ai · read-only Gmail · no bodies stored</p>
        <nav aria-label="Footer">
          <ul className="flex flex-wrap gap-4">
            <li>
              <a href="#faq" className="hover:text-[var(--fg)]">
                Privacy
              </a>
            </li>
            <li>
              <a href="#pricing" className="hover:text-[var(--fg)]">
                Pricing
              </a>
            </li>
            <li>
              <a href="#how" className="hover:text-[var(--fg)]">
                How it works
              </a>
            </li>
          </ul>
        </nav>
      </div>
    </footer>
  );
}
