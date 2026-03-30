import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'SentinelStream Analytics | Enterprise Governance',
  description: 'Real-time dashboard for autonomous DevOps governance.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} min-h-screen bg-vulcan-950 selection:bg-emerald-500/30`}>
        {/* Background Gradients */}
        <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none">
          <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-emerald-500/10 blur-[120px]" />
          <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-blue-500/10 blur-[120px]" />
        </div>
        
        {/* Main Content */}
        <main className="relative z-10 w-full min-h-screen flex flex-col">
          <nav className="w-full px-8 py-4 glass-panel flexitems-center justify-between sticky top-0 z-50">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center border border-emerald-500/50">
                <span className="text-emerald-400 font-bold tracking-tighter">S</span>
              </div>
              <span className="text-lg font-semibold tracking-tight text-vulcan-50 drop-shadow-sm">
                SentinelStream <span className="text-vulcan-400 font-normal">Analytics</span>
              </span>
            </div>
            <div className="flex gap-4 text-sm text-vulcan-300">
              <a href="#" className="hover:text-emerald-400 transition-colors">Dashboard</a>
              <a href="#" className="hover:text-emerald-400 transition-colors">Policies</a>
              <a href="#" className="hover:text-emerald-400 transition-colors">Audit Log</a>
            </div>
          </nav>
          <div className="flex-1 p-8">
            {children}
          </div>
        </main>
      </body>
    </html>
  );
}
