import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host =
    requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host");
  const protocol =
    requestHeaders.get("x-forwarded-proto") ??
    (host?.startsWith("localhost") ? "http" : "https");
  const metadataBase = new URL(
    host ? `${protocol}://${host}` : "http://localhost:3000",
  );
  const imageUrl = new URL("/og.png", metadataBase).toString();

  return {
    title: "DataQuery数据仓库｜自然语言数据分析",
    description: "用自然语言查询业务数据，实时查看分析过程并获得清晰的数据结果。",
    metadataBase,
    openGraph: {
      title: "DataQuery数据仓库｜自然语言数据分析",
      description: "把业务问题变成可信的数据结果，不必手写 SQL。",
      type: "website",
      locale: "zh_CN",
      images: [{ url: imageUrl, width: 1200, height: 630, alt: "DataQuery数据仓库" }],
    },
    twitter: {
      card: "summary_large_image",
      title: "DataQuery数据仓库｜自然语言数据分析",
      description: "把业务问题变成可信的数据结果，不必手写 SQL。",
      images: [imageUrl],
    },
  };
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
