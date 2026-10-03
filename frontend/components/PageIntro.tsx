import Link from "next/link";
import { ArrowLeft } from "lucide-react";
export default function PageIntro({ step, title, accent, description }: { step: string; title: string; accent: string; description: string }) {
  return <div className="page-intro">
    <Link href="/" className="back-link"><ArrowLeft size={15} /> Torna alla panoramica</Link>
    <div className="eyebrow"><span /> {step}</div>
    <h1>{title} <em>{accent}</em></h1><p>{description}</p>
  </div>;
}
