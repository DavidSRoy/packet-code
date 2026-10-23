import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
	title: "Landing",
};

export default function RootLayout({
	children,
}: Readonly<{
	children: React.ReactNode;
}>) {
	return (
		<html lang="en">
			<head>
				<link rel="icon" href="/favicon.svg" type="image/svg+xml"></link>
			</head>
			<body className="antialiased">{children}</body>
		</html>
	);
}
