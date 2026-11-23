import Link from "next/link";
import { PRODUCT_NAME } from "@/lib/brand";

const nav = [
  { href: "#how", label: "How it works" },
  { href: "#pricing", label: "Pricing" },
  { href: "#faq", label: "FAQ" },
];

export function SiteHeader() {
  return (
    <header className="border-b border-[var(--line)] bg-[var(--bg)]">
      <div className="mx-auto flex min-h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <Link href="/" className="font-display text-lg tracking-tight">
          {PRODUCT_NAME}
        </Link>
        <nav aria-label="Primary" className="hidden items-center gap-6 text-sm text-[var(--muted)] md:flex">
          {nav.map((item) => (
            <a key={item.href} href={item.href} className="hover:text-[var(--fg)]">
              {item.label}
            </a>
          ))}
          <Link href="/register?plan=founder" className="hover:text-[var(--fg)]">
            Manav
          </Link>
        </nav>
      </div>
    </header>
  );
}
