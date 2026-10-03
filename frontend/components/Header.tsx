"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowUpRight, Zap } from "lucide-react";

export default function Header() {
  const pathname = usePathname();
  return <header className="header"><div className="shell header-inner">
    <Link href="/" className="brand" aria-label="Energia Workspace, homepage"><span className="brand-icon"><Zap size={25} fill="currentColor" /></span><span><strong>ENERGIA<span className="brand-dot">.</span></strong><small>WORKSPACE</small></span></Link>
    <nav aria-label="Navigazione principale">
      <Link href="/" aria-current={pathname === "/" ? "page" : undefined}>Panoramica</Link>
      <Link href="/cte" aria-current={pathname === "/cte" ? "page" : undefined}>Carica CTE</Link>
      <Link href="/bollette" aria-current={pathname === "/bollette" ? "page" : undefined}>Confronta bollette</Link>
    </nav>
    <Link className="button primary header-cta" href="/bollette">Inizia il confronto <ArrowUpRight size={16} /></Link>
  </div></header>;
}
