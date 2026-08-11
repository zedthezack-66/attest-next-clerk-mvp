import { ClerkProvider, SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/nextjs";
import Link from "next/link";
import "./globals.css";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body>
          <nav className="border-b border-stone-300 bg-white">
            <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
              <Link href="/" className="font-semibold">Attest</Link>
              <div className="flex items-center gap-4 text-sm">
                <Link href="/dashboard">Dashboard</Link>
                <SignedOut><SignInButton mode="modal"><button className="rounded bg-slate-900 px-3 py-2 text-white">Sign in</button></SignInButton></SignedOut>
                <SignedIn><UserButton afterSignOutUrl="/" /></SignedIn>
              </div>
            </div>
          </nav>
          {children}
        </body>
      </html>
    </ClerkProvider>
  );
}

