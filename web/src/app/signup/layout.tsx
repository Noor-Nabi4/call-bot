import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata({
  title: "Start a Free Trial",
  description:
    "Create your Call & Flow workspace, choose an AI voice agent plan, and start answering business calls with an AI receptionist.",
  path: "/signup",
  keywords: [
    "Call & Flow free trial",
    "AI receptionist signup",
    "AI voice agent trial",
  ],
});

export default function SignupLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return children;
}
