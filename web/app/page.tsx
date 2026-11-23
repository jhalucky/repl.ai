import { AlertPreview } from "@/components/landing/alert-preview";
import { Faq } from "@/components/landing/faq";
import { Hero } from "@/components/landing/hero";
import { HowItWorks } from "@/components/landing/how-it-works";
import { Pricing } from "@/components/landing/pricing";
import { SiteFooter } from "@/components/landing/site-footer";
import { SiteHeader } from "@/components/landing/site-header";

export default function Home() {
  return (
    <div className="site-shell">
      <SiteHeader />
      <main id="main">
        <Hero />
        <HowItWorks />
        <AlertPreview />
        <Pricing />
        <Faq />
      </main>
      <SiteFooter />
    </div>
  );
}
