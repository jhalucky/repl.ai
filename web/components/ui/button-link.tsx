import Link from "next/link";

type Variant = "primary" | "ghost" | "quiet";

const variants: Record<Variant, string> = {
  primary:
    "bg-[var(--fg)] text-[var(--bg)] hover:bg-white disabled:bg-[var(--muted)] disabled:text-[var(--bg)]",
  ghost:
    "border border-[var(--line)] bg-white/5 text-[var(--fg)] hover:bg-white/10 disabled:opacity-50",
  quiet:
    "text-[var(--muted)] hover:text-[var(--fg)] underline-offset-4 hover:underline disabled:opacity-50",
};

type Props = {
  href: string;
  children: React.ReactNode;
  variant?: Variant;
  className?: string;
  external?: boolean;
};

export function ButtonLink({
  href,
  children,
  variant = "primary",
  className = "",
  external = false,
}: Props) {
  const classes = [
    "inline-flex min-h-11 items-center justify-center rounded-none px-5 text-sm font-medium transition-colors",
    variants[variant],
    className,
  ].join(" ");

  if (external) {
    return (
      <a href={href} className={classes}>
        {children}
      </a>
    );
  }

  return (
    <Link href={href} className={classes}>
      {children}
    </Link>
  );
}
