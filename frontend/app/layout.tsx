import type { Metadata } from "next";
import Header from "@/components/Header";
import ConnectionSettings from "@/components/ConnectionSettings";
import "./globals.css";
export const metadata: Metadata = { title: { default: "Energia Workspace | Offerte e bollette", template: "%s | Energia Workspace" }, description: "Carica le condizioni economiche e confronta le offerte luce e gas a partire dalla tua bolletta." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="it"><body><a className="skip-link" href="#main">Vai al contenuto</a><Header /><ConnectionSettings /><main id="main">{children}</main><footer className="footer shell"><span>ENERGIA<span className="brand-dot">.</span> <small>WORKSPACE</small></span><p>Condizioni chiare. Scelte consapevoli.</p><span className="footer-label">LUCE & GAS</span></footer></body></html>;
}
